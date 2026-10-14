"""Настройки пользователя: какой язык открыт."""
from __future__ import annotations

from cards.domain.model import SUPPORTED_LANGUAGES
from cards.domain.repositories import SettingsRepository, WordRepository

LANGUAGE_KEY = "language"


class Preferences:
    def __init__(self, settings: SettingsRepository, words: WordRepository) -> None:
        self.settings = settings
        self.words = words

    def language(self) -> str:
        saved = self.settings.get(LANGUAGE_KEY)
        if saved in SUPPORTED_LANGUAGES:
            return saved
        # Первый запуск: открываем язык, в котором уже есть слова
        for language in SUPPORTED_LANGUAGES:
            if self.words.count(language):
                return language
        return SUPPORTED_LANGUAGES[0]

    def set_language(self, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Неизвестный язык: {language!r}")
        self.settings.set(LANGUAGE_KEY, language)
