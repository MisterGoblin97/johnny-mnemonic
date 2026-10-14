import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from cards.application.preferences import Preferences
from cards.domain.model import Grade
from cards.infrastructure.sqlite_database import open_database
from cards.infrastructure.sqlite_repositories import SqliteSettingsRepository, SqliteWordRepository
from tests.helpers import DAY0

# Схема самой первой версии: ни языков, ни истории ответов
OLD_SCHEMA = """
CREATE TABLE words (
    id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT NOT NULL, translation TEXT NOT NULL,
    example TEXT NOT NULL DEFAULT '', interval_days INTEGER NOT NULL DEFAULT 0,
    next_review TEXT NOT NULL, last_review TEXT, reviews INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE INDEX idx_words_next_review ON words(next_review);
INSERT INTO words (word, translation, interval_days, next_review, last_review, reviews, created_at)
VALUES ('bonjour', 'привет', 0, '2026-10-14', NULL,         0, '2026-10-14'),
       ('merci',   'спасибо', 1, '2026-10-15', '2026-10-14', 1, '2026-10-14'),
       ('pomme',   'яблоко', 5, '2026-10-19', '2026-10-14', 1, '2026-10-14');
"""


class MigrationTest(unittest.TestCase):
    def test_old_database_gets_languages_and_review_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cards.db"
            with closing(sqlite3.connect(path)) as old:
                old.executescript(OLD_SCHEMA)

            for _ in range(2):  # повторное открытие ничего не должно задублировать
                connection = open_database(path)
                words = SqliteWordRepository(connection)
                self.assertEqual(words.count("fr"), 3)
                history = {word.text: [r.grade for r in words.history(word.id, DAY0.replace(month=1))]
                           for word in words.search("fr")}
                self.assertEqual(history, {"bonjour": [], "merci": [Grade.HARD],
                                           "pomme": [Grade.GOOD]})
                connection.close()


class PreferencesTest(unittest.TestCase):
    def test_language_is_remembered_and_defaults_to_one_with_words(self):
        connection = open_database(":memory:")
        self.addCleanup(connection.close)
        words = SqliteWordRepository(connection)
        preferences = Preferences(SqliteSettingsRepository(connection), words)
        self.assertEqual(preferences.language(), "en")  # слов нет — первый язык
        connection.execute("INSERT INTO words (language, word, translation, next_review, created_at)"
                           " VALUES ('fr', 'pomme', 'яблоко', '2026-11-01', '2026-11-01')")
        self.assertEqual(preferences.language(), "fr")  # язык, где уже есть слова
        preferences.set_language("en")
        preferences.set_language("en")
        self.assertEqual(preferences.language(), "en")
        with self.assertRaises(ValueError):
            preferences.set_language("de")


if __name__ == "__main__":
    unittest.main()
