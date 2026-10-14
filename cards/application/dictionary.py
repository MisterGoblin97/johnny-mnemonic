"""Ведение словаря: добавить, исправить, удалить, найти слова."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from cards.application.ports import Clock
from cards.domain.model import DuplicateWordError, Word, WordNotFoundError
from cards.domain.repositories import WordRepository


class Dictionary:
    def __init__(self, words: WordRepository, clock: Clock = date.today) -> None:
        self.words = words
        self.clock = clock

    def today(self) -> date:
        return self.clock()

    def add(self, language: str, text: str, translation: str, example: str = "") -> Word:
        word = Word.create(language, text, translation, example, self.today())
        self._ensure_unique(word)
        return self.words.add(word)

    def edit(self, word_id: int, language: str, text: str, translation: str,
             example: str = "") -> Word:
        """Исправить слово; здесь же его можно перенести в другой язык."""
        word = self._get(word_id)
        word.edit(language, text, translation, example)
        self._ensure_unique(word)
        self.words.update(word)
        return word

    def delete(self, word_ids: Iterable[int]) -> None:
        self.words.delete(word_ids)

    def repeat_today(self, word_ids: Iterable[int]) -> None:
        """Сбросить прогресс: слова снова попадут в сегодняшнюю очередь."""
        today = self.today()
        for word_id in word_ids:
            word = self.words.get(word_id)
            if word is not None:
                word.reset(today)
                self.words.update(word)

    def get(self, word_id: int) -> Optional[Word]:
        return self.words.get(word_id)

    def search(self, language: str, query: str = "") -> list[Word]:
        return self.words.search(language, query)

    def count(self, language: str) -> int:
        return self.words.count(language)

    def _get(self, word_id: int) -> Word:
        word = self.words.get(word_id)
        if word is None:
            raise WordNotFoundError(word_id)
        return word

    def _ensure_unique(self, word: Word) -> None:
        same = self.words.find_by_text(word.language, word.text)
        if same is not None and same.id != word.id:
            raise DuplicateWordError(f"Слово «{word.text}» уже есть в словаре.")
