"""Правило интервальных повторений: через сколько дней снова показать слово."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from cards.domain.model import Grade, Review, Word


@dataclass(frozen=True)
class SchedulingPolicy:
    hard_interval: int = 1     # «Сомневаюсь» — покажем завтра
    good_interval: int = 5     # «Запомнил» — через 5 дней,
    good_streak: int = 3       # а если «Запомнил» набралось 3 раза
    streak_window: int = 15    # за последние 15 дней,
    long_interval: int = 30    # слово откладывается на месяц;
    long_multiplier: int = 2   # дальше каждое «Запомнил» удваивает срок: 1 → 2 → 4 месяца...
    max_interval: int = 365    # но не больше года

    def next_interval(self, word: Word, grade: Grade, history: Sequence[Review],
                      today: date) -> int:
        """Через сколько дней показать слово, если сегодня поставить оценку grade.

        history — ответы на это слово начиная с history_start(today), от старых к новым.
        """
        if grade is Grade.AGAIN:
            return 0
        if grade is Grade.HARD:
            return self.hard_interval
        if word.interval_days >= self.long_interval:  # уже откладывалось на месяц — срок растёт
            return min(word.interval_days * self.long_multiplier, self.max_interval)
        if self.good_streak_days(history, today) >= self.good_streak:
            return self.long_interval
        return self.good_interval

    def good_streak_days(self, history: Sequence[Review], today: date) -> int:
        """В сколько разных дней набралось бы «Запомнил», если нажать его сегодня.

        Считаются дни за последние streak_window дней и только после последнего
        «Не помню». Несколько «Запомнил» в один день считаются за один.
        """
        start = self.history_start(today)
        days = {today}
        for review in history:
            if review.grade is Grade.AGAIN:
                days = {today}
            elif review.grade is Grade.GOOD and review.day >= start:
                days.add(review.day)
        return len(days)

    def history_start(self, today: date) -> date:
        """С какого дня нужна история ответов, чтобы посчитать серию «Запомнил»."""
        return today - timedelta(days=self.streak_window - 1)

    @property
    def learned_interval(self) -> int:
        """Выученными считаются слова, отложенные на месяц и дольше."""
        return self.long_interval
