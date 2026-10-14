"""Вкладка «Мои слова»: добавление, поиск, редактирование и удаление слов."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from cards.application.dictionary import Dictionary
from cards.application.ports import KeyboardLayouts
from cards.domain.model import DuplicateWordError, InvalidWordError
from cards.presentation.catalog import WORD_FIELDS, language_info
from cards.presentation.edit_dialog import EditDialog
from cards.presentation.formatting import describe_date, describe_duration
from cards.presentation.theme import COLORS, blend, font, frame, label, on_theme_change, themed
from cards.presentation.widgets import Card, RoundedButton, RoundedEntry
from cards.presentation.word_form import make_field

# Отступ текста от левого края в таблице: у ttk.Treeview нет своего
CELL_PAD = "  "


def setup_table_styles(root: tk.Tk) -> None:
    """Стили таблицы слов — единственного ttk-виджета в приложении."""
    c = COLORS
    style = ttk.Style(root)
    if style.theme_use() != "clam":
        style.theme_use("clam")

    style.layout("Words.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure("Words.Treeview", background=c["surface"], fieldbackground=c["surface"],
                    foreground=c["text"], rowheight=36, font=font(14), borderwidth=0)
    style.map("Words.Treeview", background=[("selected", c["accent_soft"])],
              foreground=[("selected", c["text"])])
    style.configure("Words.Treeview.Heading", background=c["surface"], foreground=c["muted"],
                    font=font(12, "bold"), relief="flat", borderwidth=0, padding=(0, 6, 0, 10),
                    bordercolor=c["surface"], lightcolor=c["surface"], darkcolor=c["surface"])
    style.map("Words.Treeview.Heading", background=[("active", c["surface"])])

    style.layout("Thin.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("Thin.Vertical.TScrollbar", troughcolor=c["surface"],
                    background=c["track_strong"], bordercolor=c["surface"],
                    lightcolor=c["track_strong"], darkcolor=c["track_strong"],
                    arrowsize=8, width=8, gripcount=0)
    hover = blend(c["track_strong"], c["text"], 0.15)
    style.map("Thin.Vertical.TScrollbar", background=[("active", hover)],
              lightcolor=[("active", hover)], darkcolor=[("active", hover)])


class WordsTab(tk.Frame):
    def __init__(self, master: tk.Misc, dictionary: Dictionary, keyboard: KeyboardLayouts,
                 language: str, on_change: Callable[[], None]) -> None:
        super().__init__(master)
        themed(self, bg="bg")
        self.dictionary = dictionary
        self.keyboard = keyboard
        self.language = language
        self.on_change = on_change

        form = Card(self, radius=22, padding=18)
        form.pack(fill="x")
        body = form.body
        body.columnconfigure((0, 1), weight=1, uniform="fields")
        title_row = frame(body)
        title_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        label(title_row, "Новое слово", size=17, weight="bold").pack(side="left")
        self.language_chip = RoundedButton(title_row, variant="chip", size=12, radius=99,
                                           padx=12, pady=4)
        self.language_chip.pack(side="left", padx=(10, 0))

        self.vars = {spec.attribute: tk.StringVar() for spec in WORD_FIELDS}
        text_spec, translation_spec, example_spec = WORD_FIELDS
        get_language = lambda: self.language
        self.entries: dict[str, RoundedEntry] = {}
        for column, spec in enumerate((text_spec, translation_spec)):
            padx = (0, 8) if column == 0 else (8, 0)
            field_label, entry = make_field(body, spec, self.vars[spec.attribute],
                                            keyboard, get_language)
            field_label.grid(row=1, column=column, sticky="w", padx=(padx[0] + 4, 0), pady=(0, 2))
            entry.grid(row=2, column=column, sticky="ew", padx=padx, pady=(0, 10))
            self.entries[spec.attribute] = entry

        example_row = frame(body)
        example_row.grid(row=3, column=0, columnspan=2, sticky="ew")
        example_row.columnconfigure(0, weight=1)
        field_label, entry = make_field(example_row, example_spec,
                                        self.vars[example_spec.attribute], keyboard, get_language)
        field_label.grid(row=0, column=0, sticky="w", padx=(4, 0), pady=(0, 2))
        entry.grid(row=1, column=0, sticky="ew")
        self.entries[example_spec.attribute] = entry
        RoundedButton(example_row, "Добавить", command=self.add_word, size=14,
                      padx=24, pady=10).grid(row=1, column=1, padx=(12, 0))
        for entry in self.entries.values():
            entry.entry.bind("<Return>", self._on_form_enter)

        toolbar = frame(self)
        toolbar.pack(fill="x", pady=(16, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        search = RoundedEntry(toolbar, self.search_var, width=300)
        search.set_placeholder("Поиск по словам и переводам")
        search.pack(side="left")
        for text, command, variant in (("Удалить", self.delete_selected, "danger"),
                                       ("Повторить сегодня", self.reset_selected, "secondary"),
                                       ("Изменить", self.edit_selected, "secondary")):
            RoundedButton(toolbar, text, command=command, variant=variant, size=13, radius=10,
                          padx=14, pady=8).pack(side="right", padx=(8, 0))

        self.count_label = label(self, size=12, fg="muted")
        self.count_label.pack(side="bottom", anchor="w", padx=6, pady=(8, 0))

        table = Card(self, radius=22, padding=12)
        table.pack(fill="both", expand=True)
        columns = (("text", "Слово", 180, "w", True),
                   ("translation", "Перевод", 220, "w", True),
                   ("next", "Следующий показ", 140, "center", False),
                   ("interval", "Интервал", 100, "center", False))
        self.tree = ttk.Treeview(table.body, columns=[c[0] for c in columns], show="headings",
                                 style="Words.Treeview")
        for name, title, width, anchor, stretch in columns:
            self.tree.heading(name, text=CELL_PAD + title if anchor == "w" else title,
                              anchor=anchor)
            self.tree.column(name, width=width, minwidth=60, anchor=anchor, stretch=stretch)
        scrollbar = ttk.Scrollbar(table.body, orient="vertical", command=self.tree.yview,
                                  style="Thin.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        for key in ("<Delete>", "<BackSpace>"):
            self.tree.bind(key, lambda _e: self.delete_selected())
        self._color_tags()
        on_theme_change(self._color_tags)

        self.set_language(language)

    def _color_tags(self) -> None:
        self.tree.tag_configure("due", foreground=COLORS["accent_text"])

    def set_language(self, language: str) -> None:
        self.language = language
        info = language_info(language)
        self.language_chip.set_text(info.name)
        for attribute, entry in self.entries.items():
            entry.set_placeholder(info.hints[attribute])
        self.refresh()

    def refresh(self) -> None:
        today = self.dictionary.today()
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        search = self.search_var.get()
        words = self.dictionary.search(self.language, search)
        for word in words:
            self.tree.insert("", "end", iid=str(word.id), values=(
                CELL_PAD + word.text,
                CELL_PAD + word.translation,
                describe_date(word.next_review, today),
                describe_duration(word.interval_days) if word.interval_days else "—",
            ), tags=("due",) if word.is_due(today) else ())
        self.tree.selection_set([iid for iid in selected if self.tree.exists(iid)])

        text = f"Слов в словаре: {self.dictionary.count(self.language)}"
        if search.strip():
            text += f"     ·     найдено: {len(words)}"
        self.count_label.config(text=text)

    def _changed(self) -> None:
        self.refresh()
        self.on_change()

    def _selected_ids(self) -> list[int]:
        return [int(iid) for iid in self.tree.selection()]

    def _on_form_enter(self, _event: tk.Event) -> None:
        # Enter переводит к следующему пустому полю, а когда всё заполнено — добавляет слово
        for attribute in ("text", "translation"):
            if not self.vars[attribute].get().strip():
                self.entries[attribute].focus_set()
                return
        self.add_word()

    def add_word(self) -> None:
        try:
            self.dictionary.add(self.language, self.vars["text"].get(),
                                self.vars["translation"].get(), self.vars["example"].get())
        except InvalidWordError as error:
            messagebox.showwarning("Не хватает данных", str(error), parent=self)
            return
        except DuplicateWordError as error:
            messagebox.showwarning("Уже есть", str(error), parent=self)
            return
        for var in self.vars.values():
            var.set("")
        self.entries["text"].focus_set()
        self._changed()

    def edit_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Изменить", "Выберите слово в списке.", parent=self)
            return
        word = self.dictionary.get(ids[0])
        if word is not None:
            EditDialog(self, self.dictionary, self.keyboard, word, on_saved=self._changed)

    def reset_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Повторить сегодня", "Выберите слова в списке.", parent=self)
            return
        self.dictionary.repeat_today(ids)
        self._changed()

    def delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Удаление", "Выберите слова в списке.", parent=self)
            return
        if len(ids) == 1:
            word = self.dictionary.get(ids[0])
            question = f"Удалить слово «{word.text if word else ''}»?"
        else:
            question = f"Удалить выбранные слова ({len(ids)} шт.)?"
        if messagebox.askyesno("Удаление", question, parent=self):
            self.dictionary.delete(ids)
            self._changed()
