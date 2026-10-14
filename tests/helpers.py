from __future__ import annotations

import unittest
from datetime import date, timedelta

from cards.infrastructure.sqlite_database import open_database
from cards.infrastructure.sqlite_repositories import SqliteWordRepository

DAY0 = date(2026, 11, 1)


class FakeClock:
    """Подставная «сегодняшняя дата», которую тест двигает сам."""

    def __init__(self, today: date = DAY0) -> None:
        self.today = today

    def __call__(self) -> date:
        return self.today

    def advance(self, days: int) -> None:
        self.today += timedelta(days=days)


def memory_repository(test: unittest.TestCase) -> SqliteWordRepository:
    """Хранилище в памяти; база закрывается после теста."""
    connection = open_database(":memory:")
    test.addCleanup(connection.close)
    return SqliteWordRepository(connection)


def keep_order(items: list) -> None:
    """Вместо случайного перемешивания очереди — оставить порядок как есть."""
