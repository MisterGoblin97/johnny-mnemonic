"""Окно редактирования слова. Здесь же слово можно перенести в другой язык."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from cards.application.dictionary import Dictionary
from cards.application.ports import KeyboardLayouts
from cards.domain.model import (SUPPORTED_LANGUAGES, DuplicateWordError, InvalidWordError,
                                Word, WordNotFoundError)
from cards.presentation.catalog import LANGUAGES, WORD_FIELDS
from cards.presentation.theme import frame, label, themed
from cards.presentation.widgets import RoundedButton, SegmentedControl
from cards.presentation.word_form import make_field


class EditDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, dictionary: Dictionary, keyboard: KeyboardLayouts,
                 word: Word, on_saved: Callable[[], None]) -> None:
        super().__init__(master)
        themed(self, bg="surface")
        self.dictionary = dictionary
        self.word_id = word.id
        self.language = word.language
        self.on_saved = on_saved
        self.title("Изменить слово")
        self.resizable(False, False)
        parent = master.winfo_toplevel()
        self.transient(parent)

        body = frame(self, padx=24, pady=20)
        body.pack(fill="both", expand=True)
        label(body, "Изменить слово", size=17, weight="bold").pack(anchor="w", pady=(0, 14))
        label(body, "Язык", size=12, weight="bold", fg="muted").pack(anchor="w", padx=4,
                                                                     pady=(0, 4))
        SegmentedControl(body, [info.name for info in LANGUAGES], command=self._on_language,
                         selected=SUPPORTED_LANGUAGES.index(self.language)).pack(anchor="w",
                                                                                pady=(0, 12))
        self.vars: dict[str, tk.StringVar] = {}
        entries = []
        for spec in WORD_FIELDS:
            var = tk.StringVar(value=getattr(word, spec.attribute))
            field_label, entry = make_field(body, spec, var, keyboard, lambda: self.language)
            entry.configure(width=400)
            field_label.pack(anchor="w", padx=4, pady=(0, 2))
            entry.pack(fill="x", pady=(0, 10))
            self.vars[spec.attribute] = var
            entries.append(entry)

        buttons = frame(body)
        buttons.pack(fill="x", pady=(8, 0))
        RoundedButton(buttons, "Сохранить", command=self.save, size=14,
                      padx=22, pady=10).pack(side="right")
        RoundedButton(buttons, "Отмена", command=self.destroy, variant="subtle", size=14,
                      padx=22, pady=10).pack(side="right", padx=(0, 10))
        self.bind("<Return>", lambda _e: self.save())
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{x}+{y}")
        entries[0].focus_set()
        entries[0].entry.select_range(0, "end")
        self.wait_visibility()
        self.grab_set()

    def _on_language(self, index: int) -> None:
        self.language = SUPPORTED_LANGUAGES[index]

    def save(self) -> None:
        try:
            self.dictionary.edit(self.word_id, self.language, self.vars["text"].get(),
                                 self.vars["translation"].get(), self.vars["example"].get())
        except InvalidWordError as error:
            messagebox.showwarning("Не хватает данных", str(error), parent=self)
            return
        except DuplicateWordError as error:
            messagebox.showwarning("Уже есть", str(error), parent=self)
            return
        except WordNotFoundError:
            # Сохранять нечего — просто закрываем окно и обновляем список
            messagebox.showwarning("Слово удалено", "Этого слова уже нет в словаре.", parent=self)
        self.destroy()
        self.on_saved()
