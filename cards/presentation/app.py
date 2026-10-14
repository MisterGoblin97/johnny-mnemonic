"""Главное окно: шапка с переключателями языка и вкладок, тема как в системе."""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from cards.application.dictionary import Dictionary
from cards.application.ports import KeyboardLayouts
from cards.application.preferences import Preferences
from cards.application.study import StudySession
from cards.domain.model import SUPPORTED_LANGUAGES
from cards.presentation.catalog import language_info
from cards.presentation.learn_tab import LearnTab
from cards.presentation.theme import (frame, init_fonts, label, on_theme_change, set_theme,
                                      system_is_dark, themed)
from cards.presentation.widgets import SegmentedControl
from cards.presentation.words_tab import WordsTab, setup_table_styles


class App(tk.Tk):
    def __init__(self, dictionary: Dictionary, session: StudySession, preferences: Preferences,
                 keyboard: KeyboardLayouts) -> None:
        super().__init__()
        self.preferences = preferences
        init_fonts()
        set_theme("dark" if system_is_dark(self) else "light")
        themed(self, bg="bg")
        setup_table_styles(self)
        on_theme_change(lambda: setup_table_styles(self))
        self.title("Карточки — изучение слов")
        self.geometry("900x780")
        self.minsize(820, 680)

        language = session.language
        shell = frame(self)
        shell.pack(fill="both", expand=True, padx=22, pady=18)
        header = frame(shell)
        header.pack(fill="x", pady=(0, 14))
        label(header, "Карточки", size=24, weight="bold").pack(side="left")
        self.language_switch = SegmentedControl(
            header, [language_info(code).name for code in SUPPORTED_LANGUAGES],
            command=self._on_language, selected=SUPPORTED_LANGUAGES.index(language))
        self.language_switch.pack(side="left", padx=(20, 0))
        self.tabs = SegmentedControl(header, ("Учить", "Мои слова"), command=self.show_tab)
        self.tabs.pack(side="right")

        pages = frame(shell)
        pages.pack(fill="both", expand=True)
        self.learn_tab = LearnTab(pages, session)
        self.words_tab = WordsTab(pages, dictionary, keyboard, language,
                                  on_change=session.invalidate)
        self.pages = (self.learn_tab, self.words_tab)
        self.current_page: Optional[int] = None
        self.bind("<KeyPress>", self._on_key)
        # Тема следует за системной: macOS присылает это событие, когда тема меняется
        self.bind("<<AppearanceChanged>>", lambda _e: self.after_idle(self._sync_theme))

        self.learn_tab.reload()
        self.show_tab(1 if dictionary.count(language) == 0 else 0)

    def bring_to_front(self) -> None:
        """Окно, запущенное из терминала на macOS, иногда открывается позади остальных."""
        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(self.attributes, "-topmost", False)

    def _sync_theme(self) -> None:
        set_theme("dark" if system_is_dark(self) else "light")

    def _on_language(self, index: int) -> None:
        language = SUPPORTED_LANGUAGES[index]
        self.preferences.set_language(language)
        self.learn_tab.set_language(language)
        self.words_tab.set_language(language)

    def show_tab(self, index: int) -> None:
        if index == self.current_page:
            return
        self.current_page = index
        self.tabs.select(index)
        for i, page in enumerate(self.pages):
            if i == index:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        if self._learning():
            self.learn_tab.refresh()
            self.learn_tab.focus_set()  # чтобы нажатия не уходили в поля ввода на другой вкладке
        else:
            self.words_tab.refresh()

    def _learning(self) -> bool:
        return self.current_page == 0

    def _on_key(self, event: tk.Event) -> None:
        if self._learning() and not isinstance(event.widget, tk.Entry):
            self.learn_tab.handle_key(event.keysym)
