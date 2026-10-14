"""Тема оформления: светлая и тёмная палитры, шрифты, перекраска при смене темы.

Цвета виджетов берутся из словаря COLORS. При смене темы set_theme() подменяет
его содержимое и перекрашивает всё, что создано через themed(), и нарисованные
виджеты из widgets.py.
"""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Optional, Protocol

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
_canvases: list["Redrawable"] = []                  # нарисованные виджеты
_listeners: list[Callable[[], None]] = []           # всё остальное (стили ttk и т.п.)
_family = "Helvetica"


class Redrawable(Protocol):
    def winfo_exists(self) -> int: ...

    def apply_theme(self) -> None: ...


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


def current_theme() -> str:
    return _theme


def on_theme_change(listener: Callable[[], None]) -> None:
    _listeners.append(listener)


def register_canvas(canvas: Redrawable) -> None:
    """Перерисовывать нарисованный виджет при смене темы."""
    _canvases.append(canvas)


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
