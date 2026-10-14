"""SQLite: где лежит файл базы, схема таблиц и обновление старых версий схемы."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "cards-learning"

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


def default_db_path() -> Path:
    """Где хранить базу: в папке данных пользователя, а не рядом с программой.

    Так собранное приложение и запуск из консоли работают с одной и той же базой.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME / "cards.db"


def open_database(path: Path | str) -> sqlite3.Connection:
    """Открыть базу (":memory:" — в памяти), создать таблицы и обновить старую схему."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    # Встроенный NOCASE в SQLite понимает только латиницу,
    # поэтому регистр без учёта языка сравниваем через Python.
    connection.create_function("casefold", 1, _casefold, deterministic=True)
    connection.execute("PRAGMA foreign_keys = ON")
    had_review_log = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'review_log'"
    ).fetchone() is not None
    connection.executescript(SCHEMA)
    _migrate(connection, had_review_log)
    connection.executescript(INDEXES)
    return connection


def _migrate(connection: sqlite3.Connection, had_review_log: bool) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(words)")}
    if "language" not in columns:
        # Языки появились позже: все слова, добавленные до этого, — французские
        with connection:
            connection.execute("ALTER TABLE words ADD COLUMN language TEXT NOT NULL DEFAULT 'fr'")
            connection.execute("DROP INDEX IF EXISTS idx_words_next_review")
    if not had_review_log:
        # Истории ответов раньше не было, но последний ответ восстанавливается
        # по текущему интервалу слова — переносим его, чтобы он учитывался в серии
        with connection:
            connection.execute(
                "INSERT INTO review_log (word_id, grade, reviewed_on)"
                " SELECT id, CASE WHEN interval_days = 0 THEN 'again'"
                "                 WHEN interval_days = 1 THEN 'hard' ELSE 'good' END,"
                "        last_review"
                " FROM words WHERE last_review IS NOT NULL ORDER BY last_review, id")


def _casefold(value: Optional[str]) -> Optional[str]:
    return value.casefold() if value is not None else None
