"""Тексты интерфейса: названия языков, кнопки оценок, поля формы слова."""
from __future__ import annotations

from typing import NamedTuple

from cards.application.ports import Script
from cards.domain.model import Grade


class LanguageInfo(NamedTuple):
    code: str
    name: str
    hints: dict[str, str]  # подсказки в пустых полях «Слово», «Перевод», «Пример»


LANGUAGES = (
    LanguageInfo("en", "Английский", {
        "text": "например, serendipity",
        "translation": "например, счастливая случайность",
        "example": "It was pure serendipity that we met.",
    }),
    LanguageInfo("fr", "Французский", {
        "text": "например, la flânerie",
        "translation": "например, неспешная прогулка",
        "example": "J’adore la flânerie dans les rues de Paris.",
    }),
)


def language_info(code: str) -> LanguageInfo:
    return next(info for info in LANGUAGES if info.code == code)


class GradeButton(NamedTuple):
    grade: Grade
    title: str
    key: str      # горячая клавиша
    variant: str  # цвет кнопки (см. widgets.RoundedButton)


GRADE_BUTTONS = (
    GradeButton(Grade.AGAIN, "Не помню", "1", "again"),
    GradeButton(Grade.HARD, "Сомневаюсь", "2", "hard"),
    GradeButton(Grade.GOOD, "Запомнил", "3", "good"),
)


class FieldSpec(NamedTuple):
    attribute: str  # поле Word
    title: str
    script: Script  # какую раскладку включать в этом поле


WORD_FIELDS = (
    FieldSpec("text", "Слово", Script.LATIN),
    FieldSpec("translation", "Перевод", Script.CYRILLIC),
    FieldSpec("example", "Пример — необязательно", Script.LATIN),
)
