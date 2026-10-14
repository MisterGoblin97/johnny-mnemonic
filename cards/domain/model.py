"""Слово из словаря и ответы на карточки."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Optional

# Языки, по которым ведётся словарь
SUPPORTED_LANGUAGES = ("en", "fr")


class Grade(str, Enum):
    """Оценка, которую человек ставит себе после показа карточки."""

    AGAIN = "again"  # «Не помню»
    HARD = "hard"    # «Сомневаюсь»
    GOOD = "good"    # «Запомнил»


@dataclass(frozen=True)
class Review:
    """Один ответ на карточку: оценка и день."""

    grade: Grade
    day: date


class InvalidWordError(ValueError):
    """У слова не заполнено само слово или перевод."""


class DuplicateWordError(ValueError):
    """Такое слово уже есть в словаре этого языка."""


class WordNotFoundError(LookupError):
    """Слова с таким id нет — например, его уже удалили."""


@dataclass(eq=False)
class Word:
    """Слово с переводом и его расписание повторений."""

    language: str
    text: str
    translation: str
    example: str
    next_review: date                   # когда показать в следующий раз
    created_at: date
    interval_days: int = 0              # текущий интервал между показами
    last_review: Optional[date] = None
    reviews: int = 0                    # сколько раз слово повторялось
    lapses: int = 0                     # сколько раз нажато «Не помню»
    id: Optional[int] = None

    @classmethod
    def create(cls, language: str, text: str, translation: str, example: str,
               today: date) -> Word:
        """Новое слово сразу попадает в сегодняшнюю очередь."""
        word = cls(language, "", "", "", next_review=today, created_at=today)
        word.edit(language, text, translation, example)
        return word

    def edit(self, language: str, text: str, translation: str, example: str = "") -> None:
        text, translation = text.strip(), translation.strip()
        if not text or not translation:
            raise InvalidWordError("Заполните слово и перевод.")
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Неизвестный язык: {language!r}")
        self.language = language
        self.text = text
        self.translation = translation
        self.example = example.strip()

    def is_due(self, today: date) -> bool:
        return self.next_review <= today

    def schedule_after(self, review: Review, interval_days: int) -> None:
        """Учесть ответ: следующий показ — через interval_days дней."""
        self.interval_days = interval_days
        self.next_review = review.day + timedelta(days=interval_days)
        self.last_review = review.day
        self.reviews += 1
        if review.grade is Grade.AGAIN:
            self.lapses += 1

    def reset(self, today: date) -> None:
        """Начать заново: слово снова попадёт в сегодняшнюю очередь."""
        self.interval_days = 0
        self.next_review = today
