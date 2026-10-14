"""Вкладка «Учить»: карточка, кнопки оценок и прогресс."""
from __future__ import annotations

import tkinter as tk

from cards.application.study import StudySession
from cards.domain.model import Grade
from cards.presentation.catalog import GRADE_BUTTONS, language_info
from cards.presentation.formatting import describe_date, describe_interval, plural
from cards.presentation.theme import (COLORS, CURSOR, font, frame, label, on_theme_change,
                                      themed)
from cards.presentation.widgets import Card, RoundedButton, Toggle


class LearnTab(tk.Frame):
    def __init__(self, master: tk.Misc, session: StudySession) -> None:
        super().__init__(master)
        themed(self, bg="bg")
        self.session = session
        self.revealed = False  # показан ли перевод текущей карточки
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
        self.grade_buttons: dict[Grade, RoundedButton] = {}
        for column, button_spec in enumerate(GRADE_BUTTONS):
            button = RoundedButton(self.grade_frame, button_spec.title, subtext=" ",
                                   hint=button_spec.key, variant=button_spec.variant,
                                   command=lambda g=button_spec.grade: self.grade(g),
                                   size=15, radius=16, pady=13)
            padx = ((0, 8), (4, 4), (8, 0))[column]  # у всех кнопок одинаковая ширина
            button.grid(row=0, column=column, sticky="ew", padx=padx)
            self.grade_frame.columnconfigure(column, weight=1, uniform="grades")
            self.grade_buttons[button_spec.grade] = button

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

    # --- действия --------------------------------------------------------

    def set_language(self, language: str) -> None:
        self.session.switch_language(language)
        self.revealed = False
        self._render()

    def reload(self) -> None:
        self.session.reload()
        self.revealed = False
        self._render()

    def refresh(self) -> None:
        """Вкладку снова открыли: пересобрать очередь, если словарь менялся."""
        if self.session.refresh():
            self.revealed = False
            self._render()

    def reveal(self) -> None:
        if self.session.current is not None and not self.revealed:
            self.revealed = True
            self._render()

    def grade(self, grade: Grade) -> None:
        if self.session.current is None or not self.revealed:
            return
        self.session.grade(grade)
        self.revealed = False
        self._render()

    def handle_key(self, keysym: str) -> None:
        if keysym in ("space", "Return", "KP_Enter"):
            self.reveal()
            return
        keysym = keysym.replace("KP_", "")
        for button_spec in GRADE_BUTTONS:
            if keysym == button_spec.key:
                self.grade(button_spec.grade)

    # --- отрисовка -------------------------------------------------------

    def _render(self) -> None:
        stats = self.session.stats()
        self.stats_label.config(
            text=f"Всего слов: {stats.total}     ·     Выучено: {stats.learned}"
                 f"     ·     Повторено за сессию: {self.session.reviewed}")
        self.progress_chip.set_text(f"Осталось на сегодня: {self.session.remaining}")

        word = self.session.current
        if word is None:
            self._render_empty(stats.total)
            return

        self.badge.pack_forget()
        front, back = ((word.translation, word.text) if self.reverse.get()
                       else (word.text, word.translation))
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
        self.example_label.config(text=word.example)
        if word.example:
            self.example_label.pack(pady=(14, 0))
        else:
            self.example_label.pack_forget()
        self.back_frame.pack()

        for button_spec in GRADE_BUTTONS:
            days = self.session.preview(button_spec.grade)
            self.grade_buttons[button_spec.grade].set_text(button_spec.title,
                                                           describe_interval(days))
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
            next_day = self.session.next_review_date()
            if next_day is not None:
                when = describe_date(next_day, self.session.today())
                hints.append(f"Следующие слова для повторения: {when}")
        # Подсказать, что в другом языке есть слова на сегодня
        waiting = [f"{language_info(code).name.lower()} — {due} {plural(due, 'слово', 'слова', 'слов')}"
                   for code, due in self.session.due_in_other_languages().items()]
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
