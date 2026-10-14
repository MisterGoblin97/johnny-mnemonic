"""Сессия повторения: сегодняшняя очередь карточек одного языка."""
from __future__ import annotations

import random
from collections import deque
from datetime import date
from typing import Callable, Optional

from cards.application.ports import Clock
from cards.domain.model import SUPPORTED_LANGUAGES, Grade, Review, Word
from cards.domain.repositories import WordRepository, WordStats
from cards.domain.scheduling import SchedulingPolicy


class StudySession:
    def __init__(self, words: WordRepository, policy: SchedulingPolicy, language: str,
                 clock: Clock = date.today,
                 shuffle: Callable[[list], None] = random.shuffle) -> None:
        self.words = words
        self.policy = policy
        self.language = language
        self.clock = clock
        self.shuffle = shuffle
        self.queue: deque[int] = deque()
        self.current: Optional[Word] = None
        self.reviewed = 0     # сколько ответов за сессию (по всем языкам)
        self._stale = True    # словарь менялся — очередь пора пересобрать

    def today(self) -> date:
        return self.clock()

    @property
    def remaining(self) -> int:
        """Сколько карточек осталось на сегодня, считая текущую."""
        return len(self.queue) + (1 if self.current is not None else 0)

    # --- очередь ---------------------------------------------------------

    def switch_language(self, language: str) -> None:
        self.language = language
        self.reload()

    def invalidate(self) -> None:
        """Словарь изменился: при следующем refresh() очередь соберётся заново."""
        self._stale = True

    def refresh(self) -> bool:
        """Пересобрать очередь, если словарь менялся или карточки кончились
        (вдруг наступил новый день). Возвращает True, если очередь пересобрана."""
        if self._stale or self.current is None:
            self.reload()
            return True
        return False

    def reload(self) -> None:
        """Заново собрать очередь слов, которые пора повторить."""
        self._stale = False
        ids = [word.id for word in self.words.due(self.language, self.today())]
        self.shuffle(ids)
        # Слово, которое сейчас на экране, остаётся первым
        if self.current is not None and self.current.id in ids:
            ids.remove(self.current.id)
            ids.insert(0, self.current.id)
        self.queue = deque(ids)
        self._advance()

    def _advance(self) -> None:
        self.current = None
        while self.queue:
            word = self.words.get(self.queue.popleft())
            if word is not None:  # слово могли удалить, пока оно ждало в очереди
                self.current = word
                break

    # --- ответы ----------------------------------------------------------

    def preview(self, grade: Grade) -> int:
        """Через сколько дней покажем текущее слово, если поставить оценку grade."""
        return self._interval(self._current(), grade)

    def grade(self, grade: Grade) -> int:
        """Ответить на текущую карточку и перейти к следующей. Возвращает интервал в днях."""
        word = self._current()
        interval = self._interval(word, grade)
        review = Review(grade, self.today())
        word.schedule_after(review, interval)
        self.words.save_review(word, review)
        if grade is Grade.AGAIN:
            self.queue.append(word.id)  # «Не помню» — покажем ещё раз в этой сессии
        self.reviewed += 1
        self._advance()
        return interval

    def _current(self) -> Word:
        if self.current is None:
            raise LookupError("На сегодня карточек нет")
        return self.current

    def _interval(self, word: Word, grade: Grade) -> int:
        today = self.today()
        history = self.words.history(word.id, self.policy.history_start(today))
        return self.policy.next_interval(word, grade, history, today)

    # --- прогресс --------------------------------------------------------

    def stats(self) -> WordStats:
        return self.words.stats(self.language, self.today(), self.policy.learned_interval)

    def next_review_date(self) -> Optional[date]:
        return self.words.next_review_date(self.language, self.today())

    def due_in_other_languages(self) -> dict[str, int]:
        """Сколько слов ждёт повторения сегодня в других языках."""
        result = {}
        for language in SUPPORTED_LANGUAGES:
            if language != self.language:
                due = self.words.stats(language, self.today(), self.policy.learned_interval).due
                if due:
                    result[language] = due
        return result
