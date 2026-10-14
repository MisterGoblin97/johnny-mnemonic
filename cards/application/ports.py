"""Порты — то, что приложению нужно от внешнего мира. Реализации — в infrastructure."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Callable, Optional, Protocol

# Источник сегодняшней даты: в тестах подменяется на фиксированную
Clock = Callable[[], date]


class Script(str, Enum):
    """Алфавит раскладки клавиатуры."""

    LATIN = "LATIN"
    CYRILLIC = "CYRILLIC"


class KeyboardLayouts(Protocol):
    def switch_to(self, script: Script, language: Optional[str] = None) -> None:
        """Включить раскладку нужного алфавита; для language — раскладку этого языка,
        если она есть в системе. Если переключить нельзя — ничего не делать."""
