"""Карточки для изучения иностранных слов — точка входа.

Здесь собираются все слои (см. cards/__init__.py): база, хранилища, сценарии и окно.

Запуск из консоли:
    python3.14 main.py
Собрать приложение для macOS (Карточки.app в «Программах»):
    ./build_app.sh
Тесты:
    python3.14 -m unittest

Слова хранятся в SQLite-файле ~/Library/Application Support/cards-learning/cards.db.
Если Python ругается на отсутствие _tkinter (Homebrew):
    brew install python-tk@3.14
"""
from __future__ import annotations

from cards.application.dictionary import Dictionary
from cards.application.preferences import Preferences
from cards.application.study import StudySession
from cards.domain.scheduling import SchedulingPolicy
from cards.infrastructure.keyboard_layout import SystemKeyboardLayouts
from cards.infrastructure.sqlite_database import default_db_path, open_database
from cards.infrastructure.sqlite_repositories import SqliteSettingsRepository, SqliteWordRepository
from cards.presentation.app import App


def main() -> None:
    connection = open_database(default_db_path())
    try:
        words = SqliteWordRepository(connection)
        preferences = Preferences(SqliteSettingsRepository(connection), words)
        app = App(
            dictionary=Dictionary(words),
            session=StudySession(words, SchedulingPolicy(), preferences.language()),
            preferences=preferences,
            keyboard=SystemKeyboardLayouts(),
        )
        app.bring_to_front()
        app.mainloop()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
