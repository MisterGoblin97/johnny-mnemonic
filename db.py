"""Хранение слов в SQLite и расписание повторений."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

DB_PATH = Path(__file__).with_name("cards.db")

# Оценки, которые ставятся после показа карточки
AGAIN = "again"  # «Не помню»   — слово вернётся в конец сегодняшней очереди
HARD = "hard"    # «Сомневаюсь» — покажем завтра
GOOD = "good"    # «Запомнил»   — покажем через 5 дней или отложим на месяц (см. next_interval)

HARD_INTERVAL = 1     # дней
GOOD_INTERVAL = 5     # дней
GOOD_STREAK = 3       # столько раз «Запомнил»...
STREAK_WINDOW = 15    # ...за столько последних дней — и слово откладывается
LONG_INTERVAL = 30    # на месяц,
LONG_MULTIPLIER = 2   # а дальше каждое «Запомнил» удваивает срок: 1 → 2 → 4 месяца...
MAX_INTERVAL = 365    # но не больше года

# Выученными в статистике считаются слова, отложенные на месяц и дольше
LEARNED_INTERVAL = LONG_INTERVAL

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    language      TEXT    NOT NULL,            -- код языка: en, fr
    word          TEXT    NOT NULL,
    translation   TEXT    NOT NULL,
    example       TEXT    NOT NULL DEFAULT '',
    interval_days INTEGER NOT NULL DEFAULT 0,  -- текущий интервал между показами
    next_review   TEXT    NOT NULL,            -- дата следующего показа, YYYY-MM-DD
    last_review   TEXT,
    reviews       INTEGER NOT NULL DEFAULT 0,  -- сколько раз слово повторялось
    lapses        INTEGER NOT NULL DEFAULT 0,  -- сколько раз нажато «Не помню»
    created_at    TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS review_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id     INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    grade       TEXT    NOT NULL,            -- again / hard / good
    reviewed_on TEXT    NOT NULL             -- YYYY-MM-DD
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_words_language_next_review ON words(language, next_review);
CREATE INDEX IF NOT EXISTS idx_review_log_word ON review_log(word_id, grade, reviewed_on);
"""


class DuplicateWordError(ValueError):
    """Такое слово уже есть в словаре."""


def next_interval(current: int, grade: str, good_streak: int = 0) -> int:
    """Через сколько дней снова показать слово после оценки grade.

    current     — текущий интервал слова в днях;
    good_streak — в сколько разных дней за последние STREAK_WINDOW дней слово
                  получило «Запомнил», считая этот ответ и только после
                  последнего «Не помню».
    """
    if grade == AGAIN:
        return 0
    if grade == HARD:
        return HARD_INTERVAL
    if grade == GOOD:
        if current >= LONG_INTERVAL:  # слово уже откладывалось на месяц — срок растёт
            return min(current * LONG_MULTIPLIER, MAX_INTERVAL)
        if good_streak >= GOOD_STREAK:
            return LONG_INTERVAL
        return GOOD_INTERVAL
    raise ValueError(f"Неизвестная оценка: {grade!r}")


def _casefold(value: Optional[str]) -> Optional[str]:
    return value.casefold() if value is not None else None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Database:
    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        # Встроенный NOCASE в SQLite понимает только латиницу,
        # поэтому регистр без учёта языка сравниваем через Python.
        self.conn.create_function("casefold", 1, _casefold, deterministic=True)
        self.conn.execute("PRAGMA foreign_keys = ON")
        had_review_log = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'review_log'"
        ).fetchone() is not None
        self.conn.executescript(SCHEMA)
        self._migrate(had_review_log)
        self.conn.executescript(INDEXES)

    def _migrate(self, had_review_log: bool) -> None:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(words)")}
        if "language" not in columns:
            # Языки появились позже: все слова, добавленные до этого, — французские
            with self.conn:
                self.conn.execute(
                    "ALTER TABLE words ADD COLUMN language TEXT NOT NULL DEFAULT 'fr'")
                self.conn.execute("DROP INDEX IF EXISTS idx_words_next_review")
        if not had_review_log:
            # Истории ответов раньше не было, но последний ответ восстанавливается
            # по текущему интервалу слова — переносим его, чтобы он учитывался в серии
            with self.conn:
                self.conn.execute(
                    "INSERT INTO review_log (word_id, grade, reviewed_on)"
                    " SELECT id, CASE WHEN interval_days = 0 THEN 'again'"
                    "                 WHEN interval_days = 1 THEN 'hard' ELSE 'good' END,"
                    "        last_review"
                    " FROM words WHERE last_review IS NOT NULL ORDER BY last_review, id")

    def close(self) -> None:
        self.conn.close()

    # --- настройки -------------------------------------------------------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # --- словарь ---------------------------------------------------------

    def add_word(self, language: str, word: str, translation: str, example: str = "",
                 today: Optional[date] = None) -> int:
        word, translation, example = word.strip(), translation.strip(), example.strip()
        self._ensure_unique(word, language)
        today_iso = (today or date.today()).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO words (language, word, translation, example, next_review, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (language, word, translation, example, today_iso, today_iso),
            )
        return cursor.lastrowid

    def update_word(self, word_id: int, language: str, word: str, translation: str,
                    example: str = "") -> None:
        word, translation, example = word.strip(), translation.strip(), example.strip()
        self._ensure_unique(word, language, exclude_id=word_id)
        with self.conn:
            self.conn.execute(
                "UPDATE words SET language = ?, word = ?, translation = ?, example = ?"
                " WHERE id = ?",
                (language, word, translation, example, word_id),
            )

    def delete_words(self, word_ids: Iterable[int]) -> None:
        with self.conn:
            self.conn.executemany("DELETE FROM words WHERE id = ?", [(i,) for i in word_ids])

    def get_word(self, word_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()

    def list_words(self, language: str, search: str = "") -> list[sqlite3.Row]:
        query = "SELECT * FROM words WHERE language = ?"
        params: tuple = (language,)
        search = search.strip()
        if search:
            pattern = f"%{_escape_like(search.casefold())}%"
            query += (" AND (casefold(word) LIKE ? ESCAPE '\\'"
                      " OR casefold(translation) LIKE ? ESCAPE '\\')")
            params += (pattern, pattern)
        query += " ORDER BY casefold(word)"
        return self.conn.execute(query, params).fetchall()

    def _ensure_unique(self, word: str, language: str, exclude_id: Optional[int] = None) -> None:
        row = self.conn.execute(
            "SELECT id FROM words WHERE language = ? AND casefold(word) = ? AND id != ?",
            (language, word.casefold(), exclude_id if exclude_id is not None else -1),
        ).fetchone()
        if row is not None:
            raise DuplicateWordError(word)

    # --- повторения ------------------------------------------------------

    def due_words(self, language: str, today: Optional[date] = None) -> list[sqlite3.Row]:
        """Слова, которые пора повторить сегодня (включая просроченные)."""
        today_iso = (today or date.today()).isoformat()
        return self.conn.execute(
            "SELECT * FROM words WHERE language = ? AND next_review <= ?"
            " ORDER BY next_review, id",
            (language, today_iso),
        ).fetchall()

    def preview_interval(self, word_id: int, grade: str, today: Optional[date] = None) -> int:
        """Через сколько дней покажем слово, если сейчас поставить оценку grade."""
        row = self.get_word(word_id)
        if row is None:
            raise KeyError(word_id)
        today = today or date.today()
        streak = self._good_streak(word_id, today) if grade == GOOD else 0
        return next_interval(row["interval_days"], grade, streak)

    def _good_streak(self, word_id: int, today: date) -> int:
        """Сколько разных дней набралось бы с «Запомнил», если нажать его сегодня."""
        since = (today - timedelta(days=STREAK_WINDOW - 1)).isoformat()
        earlier_days = self.conn.execute(
            "SELECT COUNT(DISTINCT reviewed_on) FROM review_log"
            " WHERE word_id = ? AND grade = ? AND reviewed_on >= ? AND reviewed_on != ?"
            "   AND id > COALESCE((SELECT MAX(id) FROM review_log"
            "                      WHERE word_id = ? AND grade = ?), 0)",
            (word_id, GOOD, since, today.isoformat(), word_id, AGAIN),
        ).fetchone()[0]
        return earlier_days + 1

    def review(self, word_id: int, grade: str, today: Optional[date] = None) -> int:
        """Записать оценку и перенести следующий показ. Возвращает новый интервал в днях."""
        today = today or date.today()
        interval = self.preview_interval(word_id, grade, today)
        with self.conn:
            self.conn.execute(
                "UPDATE words SET interval_days = ?, next_review = ?, last_review = ?,"
                " reviews = reviews + 1, lapses = lapses + ? WHERE id = ?",
                (
                    interval,
                    (today + timedelta(days=interval)).isoformat(),
                    today.isoformat(),
                    1 if grade == AGAIN else 0,
                    word_id,
                ),
            )
            self.conn.execute(
                "INSERT INTO review_log (word_id, grade, reviewed_on) VALUES (?, ?, ?)",
                (word_id, grade, today.isoformat()),
            )
        return interval

    def reset_words(self, word_ids: Iterable[int], today: Optional[date] = None) -> None:
        """Сбросить прогресс: слова снова попадут в сегодняшнюю очередь."""
        today_iso = (today or date.today()).isoformat()
        with self.conn:
            self.conn.executemany(
                "UPDATE words SET interval_days = 0, next_review = ? WHERE id = ?",
                [(today_iso, i) for i in word_ids],
            )

    def next_review_date(self, language: str, today: Optional[date] = None) -> Optional[date]:
        """Ближайшая дата после сегодняшней, когда появятся слова для повторения."""
        today_iso = (today or date.today()).isoformat()
        value = self.conn.execute(
            "SELECT MIN(next_review) FROM words WHERE language = ? AND next_review > ?",
            (language, today_iso),
        ).fetchone()[0]
        return date.fromisoformat(value) if value else None

    def stats(self, language: str, today: Optional[date] = None) -> dict[str, int]:
        today_iso = (today or date.today()).isoformat()
        total, due, learned = self.conn.execute(
            "SELECT COUNT(*),"
            " COALESCE(SUM(next_review <= ?), 0),"
            " COALESCE(SUM(interval_days >= ?), 0)"
            " FROM words WHERE language = ?",
            (today_iso, LEARNED_INTERVAL, language),
        ).fetchone()
        return {"total": total, "due": due, "learned": learned}
