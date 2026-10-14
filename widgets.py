"""Оформление: светлая и тёмная палитры, шрифты и закруглённые виджеты на tk.Canvas.

В стандартном tkinter нет скруглённых углов, поэтому кнопки, поля ввода,
карточки и переключатели рисуются вручную. На macOS Canvas сглаживает края,
так что скругления выглядят ровно и на Retina-экранах.

Цвета виджетов берутся из словаря COLORS. При смене темы set_theme() подменяет
его содержимое и перекрашивает всё, что создано через themed() и виджеты ниже.
"""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Optional, Sequence

PALETTES = {
    "light": {
        "bg": "#EEF1F8",            # фон окна
        "surface": "#FFFFFF",       # карточки и панели
        "raised": "#FFFFFF",        # выбранный сегмент переключателя
        "field": "#F4F6FB",         # поля ввода на панелях
        "border": "#E0E4EE",
        "track": "#E2E6F1",         # подложка переключателей
        "track_strong": "#CBD0DF",
        "shadow": "#28304F",
        "text": "#1E2235",
        "muted": "#737A90",
        "placeholder": "#A4AABB",
        "accent": "#6366F1",        # заливка главных кнопок
        "accent_hover": "#575AE6",
        "accent_pressed": "#4B4ED6",
        "accent_soft": "#E8E9FE",
        "accent_text": "#5558E3",   # акцентный текст на панелях
        "on_accent": "#FFFFFF",
        "again": "#DC3E4B",
        "again_soft": "#FDECEE",
        "hard": "#B86E00",
        "hard_soft": "#FDF2DC",
        "good": "#14945A",
        "good_soft": "#E1F5EA",
    },
    "dark": {
        "bg": "#14161D",
        "surface": "#1E212B",
        "raised": "#363B4C",
        "field": "#262A36",
        "border": "#2D3140",
        "track": "#262A36",
        "track_strong": "#444A5C",
        "shadow": "#000000",
        "text": "#E7E9F1",
        "muted": "#9298AC",
        "placeholder": "#5F6578",
        "accent": "#6366F1",
        "accent_hover": "#7376F4",
        "accent_pressed": "#5558E0",
        "accent_soft": "#2B2D55",
        "accent_text": "#A5A7FF",
        "on_accent": "#FFFFFF",
        "again": "#FF7A84",
        "again_soft": "#3B1F26",
        "hard": "#F2B544",
        "hard_soft": "#382D16",
        "good": "#4ADE97",
        "good_soft": "#173428",
    },
}
SHADOW_ALPHA = {"light": 0.09, "dark": 0.35}

COLORS: dict[str, str] = dict(PALETTES["light"])
CURSOR = "hand2"

_theme = "light"
_themed: list[tuple[tk.Misc, dict[str, str]]] = []  # обычные виджеты: опция → ключ палитры
_canvases: list["ThemedCanvas"] = []                # нарисованные виджеты
_listeners: list[Callable[[], None]] = []           # всё остальное (стили ttk и т.п.)
_family = "Helvetica"


def system_is_dark(root: tk.Misc) -> bool:
    """Включена ли в системе тёмная тема. Определяется на macOS, на остальных — светлая."""
    if sys.platform != "darwin":
        return False
    try:
        r, g, b = root.winfo_rgb("systemTextColor")  # в тёмной теме текст светлый
    except tk.TclError:
        return False
    return (r + g + b) / 3 > 0x8000


def set_theme(name: str) -> None:
    """Включить тему "light" или "dark" и перекрасить все виджеты."""
    global _theme
    if name == _theme:
        return
    _theme = name
    COLORS.update(PALETTES[name])
    _themed[:] = [(w, options) for w, options in _themed if w.winfo_exists()]
    for widget, options in _themed:
        widget.configure(**{option: COLORS[key] for option, key in options.items()})
    _canvases[:] = [c for c in _canvases if c.winfo_exists()]
    for canvas in _canvases:
        canvas.apply_theme()
    for listener in _listeners:
        listener()


def on_theme_change(listener: Callable[[], None]) -> None:
    _listeners.append(listener)


def themed(widget: tk.Misc, **options: str):
    """Покрасить виджет цветами палитры и перекрашивать при смене темы.

    options: опция виджета → ключ палитры, например bg="surface", fg="muted".
    """
    if "bg" in options:
        widget.theme_bg = options["bg"]
    widget.configure(**{option: COLORS[key] for option, key in options.items()})
    _themed.append((widget, options))
    return widget


def bg_key(widget: tk.Misc) -> str:
    """Ключ палитры, которым залит виджет (чтобы дети могли слиться с фоном)."""
    return getattr(widget, "theme_bg", "bg")


def frame(parent: tk.Misc, bg: Optional[str] = None, **options) -> tk.Frame:
    return themed(tk.Frame(parent, **options), bg=bg or bg_key(parent))


def label(parent: tk.Misc, text: str = "", size: int = 13, weight: str = "normal",
          slant: str = "roman", fg: str = "text", **options) -> tk.Label:
    widget = tk.Label(parent, text=text, font=font(size, weight, slant), **options)
    return themed(widget, fg=fg, bg=bg_key(parent))


def init_fonts() -> None:
    """Взять системный шрифт (на macOS — San Francisco). Вызывать после создания окна."""
    global _family
    _family = tkfont.nametofont("TkDefaultFont").actual("family")


def font(size: int, weight: str = "normal", slant: str = "roman") -> tuple:
    return (_family, size, weight, slant)


def blend(color: str, other: str, amount: float) -> str:
    """Смешать два цвета #RRGGBB: amount=0 — color, amount=1 — other."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
                 radius: float, **options) -> int:
    """Нарисовать прямоугольник со скруглёнными углами."""
    r = max(0.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = (
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r,
        x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r,
        x1, y1,
    )
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **options)


class ThemedCanvas(tk.Canvas):
    """Холст, который сливается с фоном родителя и перерисовывается при смене темы."""

    def __init__(self, master: tk.Misc, **options) -> None:
        self.theme_bg = bg_key(master)
        super().__init__(master, bg=COLORS[self.theme_bg], highlightthickness=0, bd=0,
                         takefocus=0, **options)
        _canvases.append(self)

    def apply_theme(self) -> None:
        self.configure(bg=COLORS[self.theme_bg])
        self._draw()

    def _draw(self) -> None:
        raise NotImplementedError


class Card(ThemedCanvas):
    """Панель со скруглёнными углами и мягкой тенью. Содержимое кладите в .body."""

    SHADOW = 8        # ширина тени
    SHADOW_SHIFT = 2  # насколько тень смещена вниз

    def __init__(self, master: tk.Misc, radius: int = 20, padding: int = 20) -> None:
        super().__init__(master)
        self.radius = radius
        s, dy = self.SHADOW, self.SHADOW_SHIFT
        self.body = frame(self, bg="surface")
        self.body.pack(fill="both", expand=True, padx=s + padding,
                       pady=(s - dy + padding, s + dy + padding))
        self.bind("<Configure>", lambda _e: self._draw())

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        s, dy = self.SHADOW, self.SHADOW_SHIFT
        x1, y1, x2, y2 = s, s - dy, w - s, h - s - dy
        for i in range(s, 0, -1):
            alpha = SHADOW_ALPHA[_theme] * (1 - (i - 1) / s) ** 2
            rounded_rect(self, x1 - i, y1 - i + dy, x2 + i, y2 + i + dy, self.radius + i,
                         fill=blend(COLORS[self.theme_bg], COLORS["shadow"], alpha), outline="")
        rounded_rect(self, x1, y1, x2, y2, self.radius,
                     fill=COLORS["surface"], outline=COLORS["border"])


def _button_palette(variant: str) -> dict[str, Optional[str]]:
    c = COLORS
    if variant == "primary":
        return dict(fill=c["accent"], hover=c["accent_hover"], pressed=c["accent_pressed"],
                    fg=c["on_accent"], sub=blend(c["on_accent"], c["accent"], 0.3), outline=None)
    if variant == "secondary":
        return dict(fill=c["surface"], hover=blend(c["surface"], c["text"], 0.04),
                    pressed=blend(c["surface"], c["text"], 0.08), fg=c["text"], sub=c["muted"],
                    outline=c["border"])
    if variant == "subtle":
        return dict(fill=c["track"], hover=blend(c["track"], c["text"], 0.06),
                    pressed=blend(c["track"], c["text"], 0.12), fg=c["text"], sub=c["muted"],
                    outline=None)
    if variant == "chip":
        return dict(fill=c["accent_soft"], hover=c["accent_soft"], pressed=c["accent_soft"],
                    fg=c["accent_text"], sub=c["accent_text"], outline=None)
    # again / hard / good / danger: мягкая цветная подложка и цветной текст
    name = "again" if variant == "danger" else variant
    color, soft = c[name], c[f"{name}_soft"]
    return dict(fill=soft, hover=blend(soft, color, 0.12), pressed=blend(soft, color, 0.22),
                fg=color, sub=blend(color, soft, 0.3), outline=None)


class RoundedButton(ThemedCanvas):
    """Кнопка со скруглёнными углами.

    subtext — вторая строка мелким шрифтом, hint — значок горячей клавиши в углу.
    Без command кнопка работает как неактивная «плашка» (например, счётчик).
    """

    def __init__(self, master: tk.Misc, text: str = "",
                 command: Optional[Callable[[], None]] = None, variant: str = "primary",
                 subtext: str = "", hint: str = "", size: int = 14, radius: int = 12,
                 padx: int = 18, pady: int = 10) -> None:
        super().__init__(master)
        self.command = command
        self.variant = variant
        self.text, self.subtext, self.hint = text, subtext, hint
        self.radius, self.padx, self.pady = radius, padx, pady
        self.main_font = tkfont.Font(font=font(size, "bold"))
        self.sub_font = tkfont.Font(font=font(size - 2))
        self.hint_font = tkfont.Font(font=font(11, "bold"))
        self.state = "normal"
        self.pressed = False

        self.bind("<Configure>", lambda _e: self._draw())
        if command is not None:
            self.configure(cursor=CURSOR)
            self.bind("<Enter>", lambda _e: self._set_state("pressed" if self.pressed else "hover"))
            self.bind("<Leave>", lambda _e: self._set_state("normal"))
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)
        self._update_size()

    def set_text(self, text: str, subtext: Optional[str] = None) -> None:
        self.text = text
        if subtext is not None:
            self.subtext = subtext
        self._update_size()
        self._draw()

    def _update_size(self) -> None:
        width = self.main_font.measure(self.text)
        height = self.main_font.metrics("linespace")
        if self.subtext:
            width = max(width, self.sub_font.measure(self.subtext))
            height += 2 + self.sub_font.metrics("linespace")
        self.configure(width=width + 2 * self.padx, height=height + 2 * self.pady)

    def _set_state(self, state: str) -> None:
        self.state = state
        self._draw()

    def _on_press(self, _event: tk.Event) -> None:
        self.pressed = True
        self._set_state("pressed")

    def _on_release(self, event: tk.Event) -> None:
        was_pressed, self.pressed = self.pressed, False
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self._set_state("hover" if inside else "normal")
        if was_pressed and inside and self.command is not None:
            self.command()

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width() if self.winfo_width() > 1 else int(self["width"])
        h = self.winfo_height() if self.winfo_height() > 1 else int(self["height"])
        p = _button_palette(self.variant)
        fill = p["fill"] if self.state == "normal" else p[self.state]
        rounded_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=fill, outline=p["outline"] or fill)

        main_h = self.main_font.metrics("linespace")
        if self.subtext:
            top = (h - main_h - 2 - self.sub_font.metrics("linespace")) / 2
            self.create_text(w / 2, top, text=self.text, font=self.main_font, fill=p["fg"], anchor="n")
            self.create_text(w / 2, top + main_h + 2, text=self.subtext, font=self.sub_font,
                             fill=p["sub"], anchor="n")
        else:
            self.create_text(w / 2, h / 2, text=self.text, font=self.main_font, fill=p["fg"])

        if self.hint:
            hint_w = max(20, self.hint_font.measure(self.hint) + 10)
            x2, y1 = w - 9, 9
            rounded_rect(self, x2 - hint_w, y1, x2, y1 + 20, 6,
                         fill=blend(fill, p["fg"], 0.14), outline="")
            self.create_text(x2 - hint_w / 2, y1 + 10, text=self.hint, font=self.hint_font,
                             fill=p["fg"])


class RoundedEntry(ThemedCanvas):
    """Поле ввода со скруглёнными углами, подсветкой при фокусе и серой подсказкой.

    Сам tk.Entry доступен как .entry — к нему привязываются обработчики клавиш.
    """

    RING = 3  # толщина подсветки вокруг поля в фокусе

    def __init__(self, master: tk.Misc, textvariable: Optional[tk.StringVar] = None,
                 placeholder: str = "", width: int = 200, size: int = 14, radius: int = 12) -> None:
        super().__init__(master, width=width, cursor="xterm")
        self.radius = radius
        self.focused = False
        self.textvariable = textvariable

        self.entry = tk.Entry(self, textvariable=textvariable, font=font(size), relief="flat",
                              bd=0, highlightthickness=0, insertwidth=2)
        linespace = tkfont.Font(font=font(size)).metrics("linespace")
        self.configure(height=linespace + 20 + 2 * self.RING)
        self._entry_item = self.create_window(0, 0, window=self.entry, anchor="w")

        self.placeholder = tk.Label(self, text=placeholder, font=font(size), bd=0, padx=0,
                                    pady=0, cursor="xterm", anchor="w")
        self._placeholder_item = self.create_window(0, 0, window=self.placeholder, anchor="w")
        self.placeholder.bind("<Button-1>", lambda _e: self.focus_set())
        self._apply_colors()

        self.bind("<Button-1>", lambda _e: self.focus_set())
        self.bind("<Configure>", lambda _e: self._draw())
        self.entry.bind("<FocusIn>", lambda _e: self._set_focused(True), add="+")
        self.entry.bind("<FocusOut>", lambda _e: self._set_focused(False), add="+")
        if textvariable is not None:
            textvariable.trace_add("write", lambda *_: self._update_placeholder())

    @property
    def fill(self) -> str:
        # На панели поле чуть темнее/светлее панели, на фоне окна — цвета панели
        return COLORS["field"] if self.theme_bg == "surface" else COLORS["surface"]

    def focus_set(self) -> None:
        self.entry.focus_set()

    def set_placeholder(self, text: str) -> None:
        self.placeholder.configure(text=text)

    def apply_theme(self) -> None:
        self._apply_colors()
        super().apply_theme()

    def _apply_colors(self) -> None:
        self.entry.configure(bg=self.fill, fg=COLORS["text"], insertbackground=COLORS["text"],
                             selectbackground=COLORS["accent_soft"],
                             selectforeground=COLORS["text"])
        self.placeholder.configure(bg=self.fill, fg=COLORS["placeholder"])

    def _set_focused(self, focused: bool) -> None:
        self.focused = focused
        self._draw()

    def _update_placeholder(self) -> None:
        # Значение берём из переменной: её трейс срабатывает раньше, чем обновится Entry
        text = self.textvariable.get() if self.textvariable is not None else self.entry.get()
        visible = not self.focused and not text and self.placeholder["text"]
        self.itemconfigure(self._placeholder_item, state="normal" if visible else "hidden")

    def _draw(self) -> None:
        self.delete("bg")
        w, h, r = self.winfo_width(), self.winfo_height(), self.RING
        if self.focused:
            rounded_rect(self, 0, 0, w, h, self.radius + r,
                         fill=COLORS["accent_soft"], outline="", tags="bg")
        rounded_rect(self, r, r, w - r, h - r, self.radius, fill=self.fill,
                     outline=COLORS["accent"] if self.focused else COLORS["border"],
                     width=1.5 if self.focused else 1, tags="bg")
        x = r + 12
        self.coords(self._entry_item, x, h / 2)
        self.itemconfigure(self._entry_item, width=max(10, w - 2 * x))
        self.coords(self._placeholder_item, x + 1, h / 2)
        self.itemconfigure(self._placeholder_item, width=max(10, w - 2 * x))
        self._update_placeholder()


class Toggle(ThemedCanvas):
    """Переключатель-«тумблер» с подписью слева."""

    WIDTH, HEIGHT = 42, 24

    def __init__(self, master: tk.Misc, text: str, variable: tk.BooleanVar,
                 command: Optional[Callable[[], None]] = None, size: int = 13) -> None:
        self.label_font = tkfont.Font(font=font(size))
        self.text = text
        self.text_width = self.label_font.measure(text)
        height = max(self.HEIGHT, self.label_font.metrics("linespace")) + 2
        super().__init__(master, width=self.text_width + 10 + self.WIDTH, height=height,
                         cursor=CURSOR)
        self.variable = variable
        self.command = command
        self.bind("<Button-1>", self._toggle)
        self.variable.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _toggle(self, _event: tk.Event) -> None:
        self.variable.set(not self.variable.get())
        if self.command is not None:
            self.command()

    def _draw(self) -> None:
        self.delete("all")
        h = int(self["height"])
        on = self.variable.get()
        self.create_text(0, h / 2, text=self.text, font=self.label_font,
                         fill=COLORS["text"] if on else COLORS["muted"], anchor="w")
        x1 = self.text_width + 10
        y1 = (h - self.HEIGHT) / 2
        rounded_rect(self, x1, y1, x1 + self.WIDTH, y1 + self.HEIGHT, self.HEIGHT / 2,
                     fill=COLORS["accent"] if on else COLORS["track_strong"], outline="")
        knob = self.HEIGHT / 2 - 3
        cx = x1 + self.WIDTH - self.HEIGHT / 2 if on else x1 + self.HEIGHT / 2
        cy = y1 + self.HEIGHT / 2
        self.create_oval(cx - knob, cy - knob, cx + knob, cy + knob, fill="#FFFFFF", outline="")


class SegmentedControl(ThemedCanvas):
    """Переключатель в виде «таблетки» с несколькими сегментами."""

    PAD = 4

    def __init__(self, master: tk.Misc, options: Sequence[str],
                 command: Callable[[int], None], selected: int = 0, size: int = 13) -> None:
        self.options = list(options)
        self.command = command
        self.selected = selected
        self.label_font = tkfont.Font(font=font(size, "bold"))
        self.segment_width = max(self.label_font.measure(o) for o in self.options) + 40
        self.segment_height = self.label_font.metrics("linespace") + 16
        super().__init__(master, cursor=CURSOR,
                         width=self.segment_width * len(self.options) + 2 * self.PAD,
                         height=self.segment_height + 2 * self.PAD)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def select(self, index: int) -> None:
        self.selected = index
        self._draw()

    def _on_click(self, event: tk.Event) -> None:
        index = int((event.x - self.PAD) // self.segment_width)
        index = max(0, min(index, len(self.options) - 1))
        if index != self.selected:
            self.select(index)
            self.command(index)

    def _draw(self) -> None:
        self.delete("all")
        w, h, p = int(self["width"]), int(self["height"]), self.PAD
        rounded_rect(self, 0, 0, w, h, h / 2, fill=COLORS["track"], outline="")
        for i, option in enumerate(self.options):
            x1 = p + i * self.segment_width
            x2 = x1 + self.segment_width
            if i == self.selected:
                rounded_rect(self, x1, p + 1, x2, h - p + 1, (h - 2 * p) / 2,
                             fill=blend(COLORS["track"], COLORS["shadow"], 0.12), outline="")
                rounded_rect(self, x1, p, x2, h - p, (h - 2 * p) / 2,
                             fill=COLORS["raised"], outline="")
            self.create_text((x1 + x2) / 2, h / 2, text=option, font=self.label_font,
                             fill=COLORS["text"] if i == self.selected else COLORS["muted"])
