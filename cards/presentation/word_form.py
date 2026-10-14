"""Поле формы слова: подпись и ввод с автопереключением раскладки."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from cards.application.ports import KeyboardLayouts, Script
from cards.presentation.catalog import FieldSpec
from cards.presentation.theme import label
from cards.presentation.widgets import RoundedEntry


def make_field(parent: tk.Misc, spec: FieldSpec, var: tk.StringVar, keyboard: KeyboardLayouts,
               get_language: Callable[[], str]) -> tuple[tk.Label, RoundedEntry]:
    """При переходе в поле включается раскладка нужного алфавита, а для иностранных
    слов — раскладка этого языка, если она есть в системе."""
    field_label = label(parent, spec.title, size=12, weight="bold", fg="muted")
    entry = RoundedEntry(parent, var)
    entry.entry.bind("<FocusIn>", lambda _e: keyboard.switch_to(
        spec.script, get_language() if spec.script is Script.LATIN else None), add="+")
    return field_label, entry
