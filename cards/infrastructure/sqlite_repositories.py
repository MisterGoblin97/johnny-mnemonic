"""Хранилища слов и настроек в SQLite."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Iterable, Optional

from cards.domain.model import Grade, Review, Word
from cards.domain.repositories import WordStats


class SqliteWordRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.conn = connection

    def get(self, word_id: int) -> Optional[Word]:
        row = self.conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
        return _to_word(row) if row is not None else None

    def add(self, word: Word) -> Word:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO words (language, word, translation, example, interval_days,"
                " next_review, last_review, reviews, lapses, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (word.language, word.text, word.translation, word.example, word.interval_days,
                 word.next_review.isoformat(), _iso(word.last_review), word.reviews,
                 word.lapses, word.created_at.isoformat()),
            )
        word.id = cursor.lastrowid
        return word

    def update(self, word: Word) -> None:
        with self.conn:
            self._update(word)

    def delete(self, word_ids: Iterable[int]) -> None:
        # История ответов удалится сама: ON DELETE CASCADE
        with self.conn:
            self.conn.executemany("DELETE FROM words WHERE id = ?", [(i,) for i in word_ids])

    def find_by_text(self, language: str, text: str) -> Optional[Word]:
        row = self.conn.execute(
            "SELECT * FROM words WHERE language = ? AND casefold(word) = ?",
            (language, text.casefold()),
        ).fetchone()
        return _to_word(row) if row is not None else None

    def search(self, language: str, query: str = "") -> list[Word]:
        sql = "SELECT * FROM words WHERE language = ?"
        params: tuple = (language,)
        query = query.strip()
        if query:
            pattern = f"%{_escape_like(query.casefold())}%"
            sql += (" AND (casefold(word) LIKE ? ESCAPE '\\'"
                    " OR casefold(translation) LIKE ? ESCAPE '\\')")
            params += (pattern, pattern)
        sql += " ORDER BY casefold(word)"
        return [_to_word(row) for row in self.conn.execute(sql, params)]

    def count(self, language: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM words WHERE language = ?", (language,)).fetchone()[0]

    def due(self, language: str, today: date) -> list[Word]:
        rows = self.conn.execute(
            "SELECT * FROM words WHERE language = ? AND next_review <= ?"
            " ORDER BY next_review, id",
            (language, today.isoformat()),
        )
        return [_to_word(row) for row in rows]

    def history(self, word_id: int, since: date) -> list[Review]:
        rows = self.conn.execute(
            "SELECT grade, reviewed_on FROM review_log"
            " WHERE word_id = ? AND reviewed_on >= ? ORDER BY id",
            (word_id, since.isoformat()),
        )
        return [Review(Grade(row["grade"]), date.fromisoformat(row["reviewed_on"]))
                for row in rows]

    def save_review(self, word: Word, review: Review) -> None:
        with self.conn:
            self._update(word)
            self.conn.execute(
                "INSERT INTO review_log (word_id, grade, reviewed_on) VALUES (?, ?, ?)",
                (word.id, review.grade.value, review.day.isoformat()),
            )

    def stats(self, language: str, today: date, learned_interval: int) -> WordStats:
        total, due, learned = self.conn.execute(
            "SELECT COUNT(*),"
            " COALESCE(SUM(next_review <= ?), 0),"
            " COALESCE(SUM(interval_days >= ?), 0)"
            " FROM words WHERE language = ?",
            (today.isoformat(), learned_interval, language),
        ).fetchone()
        return WordStats(total=total, due=due, learned=learned)

    def next_review_date(self, language: str, after: date) -> Optional[date]:
        value = self.conn.execute(
            "SELECT MIN(next_review) FROM words WHERE language = ? AND next_review > ?",
            (language, after.isoformat()),
        ).fetchone()[0]
        return date.fromisoformat(value) if value else None

    def _update(self, word: Word) -> None:
        self.conn.execute(
            "UPDATE words SET language = ?, word = ?, translation = ?, example = ?,"
            " interval_days = ?, next_review = ?, last_review = ?, reviews = ?, lapses = ?"
            " WHERE id = ?",
            (word.language, word.text, word.translation, word.example, word.interval_days,
             word.next_review.isoformat(), _iso(word.last_review), word.reviews, word.lapses,
             word.id),
        )


class SqliteSettingsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.conn = connection

    def get(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None else None

    def set(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _to_word(row: sqlite3.Row) -> Word:
    return Word(
        id=row["id"],
        language=row["language"],
        text=row["word"],
        translation=row["translation"],
        example=row["example"],
        interval_days=row["interval_days"],
        next_review=date.fromisoformat(row["next_review"]),
        last_review=date.fromisoformat(row["last_review"]) if row["last_review"] else None,
        reviews=row["reviews"],
        lapses=row["lapses"],
        created_at=date.fromisoformat(row["created_at"]),
    )


def _iso(day: Optional[date]) -> Optional[str]:
    return day.isoformat() if day is not None else None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
