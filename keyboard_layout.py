"""Автоматическое переключение раскладки клавиатуры на латиницу или кириллицу.

Работает на macOS через системный API Text Input Sources (Carbon) без сторонних
библиотек. На других системах switch_to() ничего не делает.
"""
from __future__ import annotations

import ctypes
import sys
import unicodedata
from typing import Optional

LATIN = "LATIN"
CYRILLIC = "CYRILLIC"

# Клавиши A, S, D, Q, W: по символам, которые они печатают, определяем алфавит раскладки
_PROBE_KEYCODES = (0, 1, 2, 12, 13)
_UC_KEY_ACTION_DISPLAY = 3
_UC_NO_DEAD_KEYS = 1
_UTF8 = 0x08000100


class _MacInputSources:
    def __init__(self) -> None:
        vp = ctypes.c_void_p
        carbon = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
        cf = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

        def func(lib, name, restype, *argtypes):
            f = getattr(lib, name)
            f.restype, f.argtypes = restype, list(argtypes)
            return f

        self._current = func(carbon, "TISCopyCurrentKeyboardInputSource", vp)
        self._list = func(carbon, "TISCreateInputSourceList", vp, vp, ctypes.c_bool)
        self._property = func(carbon, "TISGetInputSourceProperty", vp, vp, vp)
        self._select = func(carbon, "TISSelectInputSource", ctypes.c_int32, vp)
        self._kbd_type = func(carbon, "LMGetKbdType", ctypes.c_uint8)
        self._translate = func(
            carbon, "UCKeyTranslate", ctypes.c_int32,
            vp, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_uint16))
        self._count = func(cf, "CFArrayGetCount", ctypes.c_long, vp)
        self._item = func(cf, "CFArrayGetValueAtIndex", vp, vp, ctypes.c_long)
        self._bytes = func(cf, "CFDataGetBytePtr", vp, vp)
        self._cstring = func(cf, "CFStringGetCString", ctypes.c_bool,
                             vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32)
        self._bool = func(cf, "CFBooleanGetValue", ctypes.c_bool, vp)
        self._equal = func(cf, "CFEqual", ctypes.c_bool, vp, vp)
        self._release = func(cf, "CFRelease", None, vp)

        def const(name):
            return vp.in_dll(carbon, name).value

        self._k_id = const("kTISPropertyInputSourceID")
        self._k_category = const("kTISPropertyInputSourceCategory")
        self._k_keyboard = const("kTISCategoryKeyboardInputSource")
        self._k_selectable = const("kTISPropertyInputSourceIsSelectCapable")
        self._k_layout_data = const("kTISPropertyUnicodeKeyLayoutData")
        self._k_languages = const("kTISPropertyInputSourceLanguages")

        # Раскладка, которой человек пользовался в поле каждого вида
        # (алфавит + язык): если для французских слов он сам выбрал
        # французскую раскладку, а не ABC, возвращаемся именно на неё.
        self._remembered: dict[tuple[str, Optional[str]], str] = {}
        self._slot: Optional[tuple[str, Optional[str]]] = None

    def _string(self, cf_string: int) -> str:
        buffer = ctypes.create_string_buffer(256)
        self._cstring(cf_string, buffer, len(buffer), _UTF8)
        return buffer.value.decode()

    def _source_id(self, source: int) -> str:
        return self._string(self._property(source, self._k_id))

    def _language(self, source: int) -> Optional[str]:
        """Основной язык раскладки: en, fr, ru..."""
        languages = self._property(source, self._k_languages)
        if not languages or self._count(languages) == 0:
            return None
        return self._string(self._item(languages, 0))

    def _script(self, source: int) -> Optional[str]:
        data = self._property(source, self._k_layout_data)
        if not data:  # не обычная раскладка, а метод ввода (японский и т.п.)
            return None
        layout = self._bytes(data)
        for keycode in _PROBE_KEYCODES:
            dead_key_state = ctypes.c_uint32(0)
            length = ctypes.c_ulong(0)
            chars = (ctypes.c_uint16 * 4)()
            status = self._translate(layout, keycode, _UC_KEY_ACTION_DISPLAY, 0,
                                     self._kbd_type(), _UC_NO_DEAD_KEYS,
                                     ctypes.byref(dead_key_state), len(chars),
                                     ctypes.byref(length), chars)
            if status != 0 or length.value == 0:
                continue
            name = unicodedata.name(chr(chars[0]), "")
            for script in (LATIN, CYRILLIC):
                if name.startswith(script):
                    return script
        return None

    def current(self) -> tuple[str, Optional[str]]:
        source = self._current()
        try:
            return self._source_id(source), self._script(source)
        finally:
            self._release(source)

    def switch_to(self, script: str, language: Optional[str] = None) -> None:
        current_id, current_script = self.current()
        # Запоминаем, на какой раскладке человек печатал в предыдущем поле
        if self._slot is not None and current_script == self._slot[0]:
            self._remembered[self._slot] = current_id
        slot = (script, language)
        self._slot = slot

        sources = self._list(None, False)  # только включённые в настройках источники
        try:
            candidates: dict[str, tuple[int, Optional[str]]] = {}
            for i in range(self._count(sources)):
                source = self._item(sources, i)
                if not self._equal(self._property(source, self._k_category), self._k_keyboard):
                    continue
                selectable = self._property(source, self._k_selectable)
                if not selectable or not self._bool(selectable):
                    continue
                if self._script(source) == script:
                    candidates.setdefault(self._source_id(source),
                                          (source, self._language(source)))
            if not candidates:
                return
            # Порядок выбора: то, что человек выбирал сам в таком поле → раскладка
            # нужного языка → текущая, если алфавит уже подходит → первая подходящая
            target = self._remembered.get(slot)
            if target not in candidates:
                same_language = [i for i, (_, lang) in candidates.items()
                                 if language is not None and lang == language]
                if same_language:
                    target = same_language[0]
                elif current_id in candidates:
                    target = current_id
                else:
                    target = next(iter(candidates))
            if target != current_id:
                self._select(candidates[target][0])
        finally:
            self._release(sources)


_backend: Optional[_MacInputSources] = None
_backend_failed = False


def switch_to(script: str, language: Optional[str] = None) -> None:
    """Переключить раскладку на LATIN или CYRILLIC, если такая раскладка включена в системе.

    language (en, fr...) — если для этого языка есть своя раскладка, выбрать её.
    """
    global _backend, _backend_failed
    if sys.platform != "darwin" or _backend_failed:
        return
    try:
        if _backend is None:
            _backend = _MacInputSources()
        _backend.switch_to(script, language)
    except (OSError, AttributeError, ValueError):
        # Нет нужного системного API — просто работаем без автопереключения
        _backend_failed = True
