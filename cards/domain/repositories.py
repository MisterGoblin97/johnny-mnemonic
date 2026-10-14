"""Интерфейсы хранилищ. Реализации — в слое infrastructure."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional, Protocol

from cards.domain.model import Review, Word


@dataclass(frozen=True)
class WordStats:
    total: int    # всего слов
    due: int      # пора повторить сегодня
    learned: int  # выучено


class WordRepository(Protocol):
    def get(self, word_id: int) -> Optional[Word]: ...

    def add(self, word: Word) -> Word:
        """Сохранить новое слово и вернуть его с присвоенным id."""

    def update(self, word: Word) -> None: ...

    def delete(self, word_ids: Iterable[int]) -> None:
        """Удалить слова вместе с историей ответов."""

    def find_by_text(self, language: str, text: str) -> Optional[Word]:
        """Слово этого языка без учёта регистра букв."""

    def search(self, language: str, query: str = "") -> list[Word]:
        """Слова языка по алфавиту; query ищется в слове и переводе без учёта регистра."""

    def count(self, language: str) -> int: ...

    def due(self, language: str, today: date) -> list[Word]:
        """Слова, которые пора повторить сегодня (включая просроченные)."""

    def history(self, word_id: int, since: date) -> list[Review]:
        """Ответы на слово начиная с дня since, от старых к новым."""

    def save_review(self, word: Word, review: Review) -> None:
        """Сохранить новое расписание слова и ответ — атомарно."""

    def stats(self, language: str, today: date, learned_interval: int) -> WordStats: ...

    def next_review_date(self, language: str, after: date) -> Optional[date]:
        """Ближайшая дата после after, когда появятся слова для повторения."""


class SettingsRepository(Protocol):
    def get(self, key: str) -> Optional[str]: ...

    def set(self, key: str, value: str) -> None: ...
