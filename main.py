"""Карточки для изучения иностранных слов.

Запуск:
    python3.14 main.py

Слова хранятся в SQLite-файле cards.db рядом с программой.
Если Python ругается на отсутствие _tkinter (Homebrew):
    brew install python-tk@3.14
"""
from __future__ import annotations

import random
import sqlite3
import tkinter as tk
from collections import deque
from datetime import date
from tkinter import messagebox, ttk
from typing import Callable, NamedTuple, Optional

import db
import keyboard_layout
from db import AGAIN, GOOD, HARD, Database
from keyboard_layout import CYRILLIC, LATIN
from widgets import (COLORS, CURSOR, Card, RoundedButton, RoundedEntry, SegmentedControl,
                     Toggle, blend, font, frame, init_fonts, label, on_theme_change, set_theme,
                     system_is_dark, themed)


class Language(NamedTuple):
    code: str
    name: str
    hints: dict[str, str]  # подсказки в пустых полях «Слово», «Перевод», «Пример»


LANGUAGES = (
    Language("en", "Английский", {
        "word": "например, serendipity",
        "translation": "например, счастливая случайность",
        "example": "It was pure serendipity that we met.",
    }),
    Language("fr", "Французский", {
        "word": "например, la flânerie",
        "translation": "например, неспешная прогулка",
        "example": "J’adore la flânerie dans les rues de Paris.",
    }),
)
LANGUAGE_CODES = [language.code for language in LANGUAGES]

GRADES = (
    # оценка (она же цвет кнопки), надпись, горячая клавиша
    (AGAIN, "Не помню", "1"),
    (HARD, "Сомневаюсь", "2"),
    (GOOD, "Запомнил", "3"),
)

# Поля слова: столбец в БД, подпись, раскладка клавиатуры
WORD_FIELDS = (
    ("word", "Слово", LATIN),
    ("translation", "Перевод", CYRILLIC),
    ("example", "Пример — необязательно", LATIN),
)

# Отступ текста от левого края в таблице: у ttk.Treeview нет своего
CELL_PAD = "  "


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def plural_days(n: int) -> str:
    return plural(n, "день", "дня", "дней")


def describe_duration(days: int) -> str:
    """5 → «5 дней», 30 → «1 месяц», 120 → «4 месяца», 365 → «1 год»."""
    if days >= db.MAX_INTERVAL:
        return "1 год"
    if days >= db.LONG_INTERVAL and days % db.LONG_INTERVAL == 0:
        months = days // db.LONG_INTERVAL
        return f"{months} {plural(months, 'месяц', 'месяца', 'месяцев')}"
    return f"{days} {plural_days(days)}"


def describe_interval(days: int) -> str:
    if days == 0:
        return "ещё раз сегодня"
    if days == 1:
        return "завтра"
    duration = describe_duration(days)
    return "через " + duration.removeprefix("1 ")  # «через месяц», «через год»


def describe_date(day: date, today: date) -> str:
    delta = (day - today).days
    if delta <= 0:
        return "сегодня"
    if delta == 1:
        return "завтра"
    return day.strftime("%d.%m.%Y")


def make_field(parent: tk.Misc, spec: tuple, var: tk.StringVar,
               get_language: Callable[[], str]) -> tuple[tk.Label, RoundedEntry]:
    """Подпись и поле ввода. При переходе в поле включается раскладка нужного алфавита,
    а для иностранных слов — раскладка этого языка, если она есть в системе."""
    _column, title, script = spec
    field_label = label(parent, title, size=12, weight="bold", fg="muted")
    entry = RoundedEntry(parent, var)
    entry.entry.bind("<FocusIn>", lambda _e: keyboard_layout.switch_to(
        script, get_language() if script == LATIN else None), add="+")
    return field_label, entry


def setup_styles(root: tk.Tk) -> None:
    """Стили для таблицы слов — единственного ttk-виджета, который остался."""
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


class LearnTab(tk.Frame):
    """Вкладка повторения: по очереди показывает слова, которые пора повторить."""

    def __init__(self, master: tk.Misc, database: Database, language: str) -> None:
        super().__init__(master)
        themed(self, bg="bg")
        self.db = database
        self.language = language
        self.queue: deque[int] = deque()
        self.current: Optional[sqlite3.Row] = None
        self.revealed = False
        self.dirty = True
        self.reviewed = 0
        self.reverse = tk.BooleanVar(value=False)

        header = frame(self)
        header.pack(side="top", fill="x")
        self.progress_chip = RoundedButton(header, variant="chip", size=13, radius=99,
                                           padx=14, pady=7)
        self.progress_chip.pack(side="left")
        Toggle(header, "Сначала показывать перевод", self.reverse,
               command=self._render).pack(side="right")

        self.stats_label = label(self, size=12, fg="muted")
        self.stats_label.pack(side="bottom", pady=(14, 0))

        self.actions = frame(self)
        self.actions.pack(side="bottom", fill="x")
        self.reveal_button = RoundedButton(self.actions, "Показать перевод",
                                           subtext="или нажмите пробел", command=self.reveal,
                                           size=15, radius=16, pady=13)
        self.grade_frame = frame(self.actions)
        self.grade_buttons: dict[str, RoundedButton] = {}
        for column, (grade, title, key) in enumerate(GRADES):
            button = RoundedButton(self.grade_frame, title, subtext=" ", hint=key, variant=grade,
                                   command=lambda g=grade: self.grade(g),
                                   size=15, radius=16, pady=13)
            padx = ((0, 8), (4, 4), (8, 0))[column]  # у всех кнопок одинаковая ширина
            button.grid(row=0, column=column, sticky="ew", padx=padx)
            self.grade_frame.columnconfigure(column, weight=1, uniform="grades")
            self.grade_buttons[grade] = button

        self.card = Card(self, radius=26, padding=28)
        self.card.pack(side="top", fill="both", expand=True, pady=(12, 12))
        self.card.bind("<Configure>", self._on_card_resize, add="+")
        content = frame(self.card.body)
        content.place(relx=0.5, rely=0.5, anchor="center")

        self.badge = themed(tk.Canvas(content, width=76, height=76, highlightthickness=0),
                            bg="surface")
        self.front_label = label(content, size=40, weight="bold", justify="center")
        self.front_label.pack()
        self.back_frame = frame(content)
        frame(self.back_frame, bg="accent_soft", width=56, height=4).pack(pady=20)
        self.back_label = label(self.back_frame, size=28, fg="accent_text", justify="center")
        self.back_label.pack()
        self.example_label = label(self.back_frame, size=15, slant="italic", fg="muted",
                                   justify="center")
        self.hint_label = label(content, size=13, fg="muted", justify="center")

        for widget in (self.card, self.card.body, content, self.front_label, self.hint_label):
            widget.bind("<Button-1>", lambda _e: self.reveal(), add="+")
        on_theme_change(self._render)  # значок на пустой карточке рисуется цветами темы

    def _on_card_resize(self, event: tk.Event) -> None:
        wrap = max(200, event.width - 120)
        for widget in (self.front_label, self.back_label, self.example_label, self.hint_label):
            widget.configure(wraplength=wrap)

    # --- очередь ---------------------------------------------------------

    def set_language(self, language: str) -> None:
        self.language = language
        self.reload()

    def mark_dirty(self) -> None:
        self.dirty = True

    def refresh(self) -> None:
        # Пустую очередь тоже перечитываем: вдруг наступил новый день
        if self.dirty or self.current is None:
            self.reload()

    def reload(self) -> None:
        """Заново собрать очередь слов, которые пора повторить."""
        self.dirty = False
        ids = [row["id"] for row in self.db.due_words(self.language)]
        random.shuffle(ids)
        # Слово, которое сейчас на экране, остаётся первым
        if self.current is not None and self.current["id"] in ids:
            ids.remove(self.current["id"])
            ids.insert(0, self.current["id"])
        self.queue = deque(ids)
        self._next_card()

    def _next_card(self) -> None:
        self.current = None
        while self.queue:
            row = self.db.get_word(self.queue.popleft())
            if row is not None:
                self.current = row
                break
        self.revealed = False
        self._render()

    def reveal(self) -> None:
        if self.current is not None and not self.revealed:
            self.revealed = True
            self._render()

    def grade(self, grade: str) -> None:
        if self.current is None or not self.revealed:
            return
        self.db.review(self.current["id"], grade)
        if grade == AGAIN:
            self.queue.append(self.current["id"])
        self.reviewed += 1
        self._next_card()

    def handle_key(self, keysym: str) -> None:
        if keysym in ("space", "Return", "KP_Enter"):
            self.reveal()
            return
        keysym = keysym.replace("KP_", "")
        for grade, _title, key in GRADES:
            if keysym == key:
                self.grade(grade)

    # --- отрисовка -------------------------------------------------------

    def _render(self) -> None:
        stats = self.db.stats(self.language)
        self.stats_label.config(
            text=f"Всего слов: {stats['total']}     ·     Выучено: {stats['learned']}"
                 f"     ·     Повторено за сессию: {self.reviewed}")
        remaining = len(self.queue) + (1 if self.current is not None else 0)
        self.progress_chip.set_text(f"Осталось на сегодня: {remaining}")

        if self.current is None:
            self._render_empty(stats["total"])
            return

        self.badge.pack_forget()
        word, translation = self.current["word"], self.current["translation"]
        front, back = (translation, word) if self.reverse.get() else (word, translation)
        self.front_label.config(text=front)
        self.card.config(cursor="" if self.revealed else CURSOR)

        if not self.revealed:
            self.back_frame.pack_forget()
            self.hint_label.config(text="Вспомните перевод и нажмите на карточку")
            self.hint_label.pack(pady=(16, 0))
            self.grade_frame.pack_forget()
            self.reveal_button.pack(fill="x")
            return

        self.hint_label.pack_forget()
        self.back_label.config(text=back)
        example = self.current["example"]
        self.example_label.config(text=example)
        if example:
            self.example_label.pack(pady=(14, 0))
        else:
            self.example_label.pack_forget()
        self.back_frame.pack()

        for grade, title, _key in GRADES:
            days = self.db.preview_interval(self.current["id"], grade)
            self.grade_buttons[grade].set_text(title, describe_interval(days))
        self.reveal_button.pack_forget()
        self.grade_frame.pack(fill="x")

    def _render_empty(self, total: int) -> None:
        self.back_frame.pack_forget()
        self.reveal_button.pack_forget()
        self.grade_frame.pack_forget()
        self.card.config(cursor="")
        hints = []
        if total == 0:
            self._show_badge("+", COLORS["accent_text"], COLORS["accent_soft"])
            title = "Слов пока нет"
            hints.append("Добавьте их во вкладке «Мои слова»")
        else:
            self._show_badge("✓", COLORS["good"], COLORS["good_soft"])
            title = "На сегодня всё!"
            next_day = self.db.next_review_date(self.language)
            if next_day is not None:
                hints.append(f"Следующие слова для повторения: {describe_date(next_day, date.today())}")
        # Подсказать, что в другом языке есть слова на сегодня
        waiting = []
        for language in LANGUAGES:
            due = self.db.stats(language.code)["due"] if language.code != self.language else 0
            if due:
                waiting.append(f"{language.name.lower()} — {due} {plural(due, 'слово', 'слова', 'слов')}")
        if waiting:
            hints.append("Сегодня ещё ждут повторения: " + ", ".join(waiting))
        self.front_label.config(text=title)
        self.hint_label.config(text="\n".join(hints))
        self.hint_label.pack(pady=(12, 0))

    def _show_badge(self, symbol: str, color: str, soft: str) -> None:
        self.badge.delete("all")
        self.badge.create_oval(2, 2, 74, 74, fill=soft, outline="")
        self.badge.create_text(38, 38, text=symbol, fill=color, font=font(32, "bold"))
        self.badge.pack(before=self.front_label, pady=(0, 18))


class WordsTab(tk.Frame):
    """Вкладка со словарём: добавление, поиск, редактирование и удаление слов."""

    def __init__(self, master: tk.Misc, database: Database, language: str,
                 on_change: Callable[[], None]) -> None:
        super().__init__(master)
        themed(self, bg="bg")
        self.db = database
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

        self.word_var = tk.StringVar()
        self.translation_var = tk.StringVar()
        self.example_var = tk.StringVar()
        word_spec, translation_spec, example_spec = WORD_FIELDS
        get_language = lambda: self.language
        entries = []
        for column, (spec, var) in enumerate(((word_spec, self.word_var),
                                              (translation_spec, self.translation_var))):
            padx = (0, 8) if column == 0 else (8, 0)
            field_label, entry = make_field(body, spec, var, get_language)
            field_label.grid(row=1, column=column, sticky="w", padx=(padx[0] + 4, 0), pady=(0, 2))
            entry.grid(row=2, column=column, sticky="ew", padx=padx, pady=(0, 10))
            entries.append(entry)
        self.word_entry, self.translation_entry = entries

        example_row = frame(body)
        example_row.grid(row=3, column=0, columnspan=2, sticky="ew")
        example_row.columnconfigure(0, weight=1)
        field_label, self.example_entry = make_field(example_row, example_spec,
                                                     self.example_var, get_language)
        field_label.grid(row=0, column=0, sticky="w", padx=(4, 0), pady=(0, 2))
        self.example_entry.grid(row=1, column=0, sticky="ew")
        RoundedButton(example_row, "Добавить", command=self.add_word, size=14,
                      padx=24, pady=10).grid(row=1, column=1, padx=(12, 0))
        self.form_entries = {"word": self.word_entry, "translation": self.translation_entry,
                             "example": self.example_entry}
        for entry in self.form_entries.values():
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
        columns = (("word", "Слово", 180, "w", True),
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
        info = LANGUAGES[LANGUAGE_CODES.index(language)]
        self.language_chip.set_text(info.name)
        for column, entry in self.form_entries.items():
            entry.set_placeholder(info.hints[column])
        self.refresh()

    def refresh(self) -> None:
        today = date.today()
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        search = self.search_var.get()
        rows = self.db.list_words(self.language, search)
        for row in rows:
            next_day = date.fromisoformat(row["next_review"])
            interval = row["interval_days"]
            self.tree.insert("", "end", iid=str(row["id"]), values=(
                CELL_PAD + row["word"],
                CELL_PAD + row["translation"],
                describe_date(next_day, today),
                describe_duration(interval) if interval else "—",
            ), tags=("due",) if next_day <= today else ())
        self.tree.selection_set([iid for iid in selected if self.tree.exists(iid)])

        text = f"Слов в словаре: {self.db.stats(self.language)['total']}"
        if search.strip():
            text += f"     ·     найдено: {len(rows)}"
        self.count_label.config(text=text)

    def _changed(self) -> None:
        self.refresh()
        self.on_change()

    def _selected_ids(self) -> list[int]:
        return [int(iid) for iid in self.tree.selection()]

    def _on_form_enter(self, _event: tk.Event) -> None:
        # Enter переводит к следующему пустому полю, а когда всё заполнено — добавляет слово
        if not self.word_var.get().strip():
            self.word_entry.focus_set()
        elif not self.translation_var.get().strip():
            self.translation_entry.focus_set()
        else:
            self.add_word()

    def add_word(self) -> None:
        word = self.word_var.get().strip()
        translation = self.translation_var.get().strip()
        if not word or not translation:
            messagebox.showwarning("Не хватает данных", "Заполните слово и перевод.", parent=self)
            return
        try:
            self.db.add_word(self.language, word, translation, self.example_var.get())
        except db.DuplicateWordError:
            messagebox.showwarning("Уже есть", f"Слово «{word}» уже есть в словаре.", parent=self)
            return
        for var in (self.word_var, self.translation_var, self.example_var):
            var.set("")
        self.word_entry.focus_set()
        self._changed()

    def edit_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Изменить", "Выберите слово в списке.", parent=self)
            return
        row = self.db.get_word(ids[0])
        if row is not None:
            EditDialog(self, self.db, row, on_saved=self._changed)

    def reset_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Повторить сегодня", "Выберите слова в списке.", parent=self)
            return
        self.db.reset_words(ids)
        self._changed()

    def delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Удаление", "Выберите слова в списке.", parent=self)
            return
        if len(ids) == 1:
            row = self.db.get_word(ids[0])
            question = f"Удалить слово «{row['word'] if row else ''}»?"
        else:
            question = f"Удалить выбранные слова ({len(ids)} шт.)?"
        if messagebox.askyesno("Удаление", question, parent=self):
            self.db.delete_words(ids)
            self._changed()


class EditDialog(tk.Toplevel):
    """Окно редактирования слова. Здесь же слово можно перенести в другой язык."""

    def __init__(self, master: tk.Misc, database: Database, row: sqlite3.Row,
                 on_saved: Callable[[], None]) -> None:
        super().__init__(master)
        themed(self, bg="surface")
        self.db = database
        self.word_id = row["id"]
        self.language = row["language"]
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
        SegmentedControl(body, [language.name for language in LANGUAGES],
                         command=self._on_language,
                         selected=LANGUAGE_CODES.index(self.language)).pack(anchor="w",
                                                                            pady=(0, 12))
        self.vars = []
        entries = []
        for spec in WORD_FIELDS:
            var = tk.StringVar(value=row[spec[0]])
            field_label, entry = make_field(body, spec, var, lambda: self.language)
            entry.configure(width=400)
            field_label.pack(anchor="w", padx=4, pady=(0, 2))
            entry.pack(fill="x", pady=(0, 10))
            self.vars.append(var)
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
        self.language = LANGUAGES[index].code

    def save(self) -> None:
        word, translation, example = (var.get().strip() for var in self.vars)
        if not word or not translation:
            messagebox.showwarning("Не хватает данных", "Заполните слово и перевод.", parent=self)
            return
        try:
            self.db.update_word(self.word_id, self.language, word, translation, example)
        except db.DuplicateWordError:
            messagebox.showwarning("Уже есть", f"Слово «{word}» уже есть в словаре.", parent=self)
            return
        self.destroy()
        self.on_saved()


class App(tk.Tk):
    def __init__(self, database: Database) -> None:
        super().__init__()
        self.db = database
        init_fonts()
        set_theme("dark" if system_is_dark(self) else "light")
        themed(self, bg="bg")
        setup_styles(self)
        on_theme_change(lambda: setup_styles(self))
        self.title("Карточки — изучение слов")
        self.geometry("900x780")
        self.minsize(820, 680)

        language = self._initial_language()
        shell = frame(self)
        shell.pack(fill="both", expand=True, padx=22, pady=18)
        header = frame(shell)
        header.pack(fill="x", pady=(0, 14))
        label(header, "Карточки", size=24, weight="bold").pack(side="left")
        self.language_switch = SegmentedControl(
            header, [info.name for info in LANGUAGES], command=self._on_language,
            selected=LANGUAGE_CODES.index(language))
        self.language_switch.pack(side="left", padx=(20, 0))
        self.tabs = SegmentedControl(header, ("Учить", "Мои слова"), command=self.show_tab)
        self.tabs.pack(side="right")

        pages = frame(shell)
        pages.pack(fill="both", expand=True)
        self.learn_tab = LearnTab(pages, database, language)
        self.words_tab = WordsTab(pages, database, language, on_change=self.learn_tab.mark_dirty)
        self.pages = (self.learn_tab, self.words_tab)
        self.current_page: Optional[int] = None
        self.bind("<KeyPress>", self._on_key)
        # Тема следует за системной: macOS присылает это событие, когда тема меняется
        self.bind("<<AppearanceChanged>>", lambda _e: self.after_idle(self._sync_theme))

        self.learn_tab.reload()
        self.show_tab(1 if database.stats(language)["total"] == 0 else 0)

    def _initial_language(self) -> str:
        saved = self.db.get_setting("language")
        if saved in LANGUAGE_CODES:
            return saved
        # Первый запуск: открываем язык, в котором уже есть слова
        for code in LANGUAGE_CODES:
            if self.db.stats(code)["total"]:
                return code
        return LANGUAGE_CODES[0]

    def _sync_theme(self) -> None:
        set_theme("dark" if system_is_dark(self) else "light")

    def _on_language(self, index: int) -> None:
        language = LANGUAGE_CODES[index]
        self.db.set_setting("language", language)
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


def main() -> None:
    database = Database()
    try:
        app = App(database)
        # Окно, запущенное из терминала на macOS, иногда открывается позади остальных
        app.lift()
        app.attributes("-topmost", True)
        app.after_idle(app.attributes, "-topmost", False)
        app.mainloop()
    finally:
        database.close()


if __name__ == "__main__":
    main()
