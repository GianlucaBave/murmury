"""Global hotkeys on macOS: shortcuts that work while another app (Zoom, Meet, Teams) has focus.

Uses Carbon's RegisterEventHotKey, called through ctypes. Unlike NSEvent global monitors or event taps, it needs
no Accessibility or Input Monitoring permission, and the key press goes to Murmury only.

The module has no Qt in it. The caller passes a callback; in the app that callback emits a Qt signal, so the
action itself runs on the main thread. On other platforms every call is a no-op, so tests and CI keep working.
"""

from __future__ import annotations

import sys
from typing import Callable

# Carbon constants
K_EVENT_CLASS_KEYBOARD = 0x6B657962  # 'keyb'
K_EVENT_HOT_KEY_PRESSED = 5
K_EVENT_PARAM_DIRECT_OBJECT = 0x2D2D2D2D  # '----'
TYPE_EVENT_HOT_KEY_ID = 0x686B6964  # 'hkid'
SIGNATURE = 0x4D555259  # 'MURY'
EVENT_HOT_KEY_EXISTS_ERR = -9878  # another app already owns this combination
EVENT_INTERNAL_ERR = -9868  # macOS 15.0 and 15.1 refused Option-only combinations with this
NATIVE_FAILED = -1  # a native call raised (the message carries this code)
NO_ERR = 0

MODIFIERS = {"cmd": 0x0100, "command": 0x0100, "shift": 0x0200, "alt": 0x0800, "option": 0x0800,
             "opt": 0x0800, "ctrl": 0x1000, "control": 0x1000}

# macOS virtual key codes (ANSI layout)
KEYS = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13,
    "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26,
    "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "space": 49, "return": 36, "tab": 48, "escape": 53,
}


class HotKeyError(Exception):
    """A combination could not be registered. The message is fit to show to the user."""


def parse_combo(text: str) -> tuple[int, int]:
    """'option+space' -> (key code, modifier mask). At least one modifier is required."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        raise ValueError(f"{text!r}: use a modifier and a key, like option+space")
    *mods, key = parts
    mask = 0
    for mod in mods:
        if mod not in MODIFIERS:
            raise ValueError(f"{text!r}: unknown modifier {mod!r}")
        mask |= MODIFIERS[mod]
    if key not in KEYS:
        raise ValueError(f"{text!r}: unknown key {key!r}")
    return KEYS[key], mask


class CarbonBackend:
    """The native calls. Kept apart from HotKeys so tests can replace it with a fake."""

    def __init__(self) -> None:
        import ctypes
        import ctypes.util

        self.ct = ctypes
        path = ctypes.util.find_library("Carbon") or "/System/Library/Frameworks/Carbon.framework/Carbon"
        self.lib = ctypes.CDLL(path)
        ct = ctypes

        class EventTypeSpec(ct.Structure):
            _fields_ = [("eventClass", ct.c_uint32), ("eventKind", ct.c_uint32)]

        class EventHotKeyID(ct.Structure):
            _fields_ = [("signature", ct.c_uint32), ("id", ct.c_uint32)]

        self.EventTypeSpec, self.EventHotKeyID = EventTypeSpec, EventHotKeyID
        lib = self.lib
        lib.GetApplicationEventTarget.restype = ct.c_void_p
        lib.GetApplicationEventTarget.argtypes = []
        self.handler_type = ct.CFUNCTYPE(ct.c_int32, ct.c_void_p, ct.c_void_p, ct.c_void_p)
        lib.InstallEventHandler.restype = ct.c_int32
        lib.InstallEventHandler.argtypes = [ct.c_void_p, self.handler_type, ct.c_uint32,
                                            ct.POINTER(EventTypeSpec), ct.c_void_p, ct.POINTER(ct.c_void_p)]
        lib.RemoveEventHandler.restype = ct.c_int32
        lib.RemoveEventHandler.argtypes = [ct.c_void_p]
        lib.RegisterEventHotKey.restype = ct.c_int32
        lib.RegisterEventHotKey.argtypes = [ct.c_uint32, ct.c_uint32, EventHotKeyID, ct.c_void_p, ct.c_uint32,
                                            ct.POINTER(ct.c_void_p)]
        lib.UnregisterEventHotKey.restype = ct.c_int32
        lib.UnregisterEventHotKey.argtypes = [ct.c_void_p]
        lib.GetEventParameter.restype = ct.c_int32
        lib.GetEventParameter.argtypes = [ct.c_void_p, ct.c_uint32, ct.c_uint32, ct.c_void_p, ct.c_uint32,
                                          ct.c_void_p, ct.c_void_p]
        if ct.sizeof(EventHotKeyID) != 8 or ct.sizeof(EventTypeSpec) != 8:  # the layout Carbon expects
            raise OSError("unexpected Carbon struct size")
        self.on_pressed: Callable[[int], None] | None = None
        self.handler_ref = ct.c_void_p()
        self.installed = False
        self.refs: dict[int, ct.c_void_p] = {}
        self.c_handler = self.handler_type(self._handle)  # keep a reference: ctypes frees the callback otherwise

    def _handle(self, _call, event, _data) -> int:
        hot_key = self.EventHotKeyID()
        status = self.lib.GetEventParameter(event, K_EVENT_PARAM_DIRECT_OBJECT, TYPE_EVENT_HOT_KEY_ID, None,
                                            self.ct.sizeof(hot_key), None, self.ct.byref(hot_key))
        if status == NO_ERR and hot_key.signature == SIGNATURE and self.on_pressed:
            try:
                self.on_pressed(hot_key.id)
            except Exception:  # never let an exception cross back into Carbon
                pass
        return NO_ERR

    def install(self, on_pressed: Callable[[int], None]) -> int:
        self.on_pressed = on_pressed
        if self.installed:
            return NO_ERR
        try:
            spec = self.EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOT_KEY_PRESSED)
            status = self.lib.InstallEventHandler(self.lib.GetApplicationEventTarget(), self.c_handler, 1,
                                                  self.ct.byref(spec), None, self.ct.byref(self.handler_ref))
        except Exception:
            return NATIVE_FAILED
        self.installed = status == NO_ERR
        return status

    def register(self, hotkey_id: int, key_code: int, modifiers: int) -> int:
        ref = self.ct.c_void_p()
        try:
            status = self.lib.RegisterEventHotKey(key_code, modifiers, self.EventHotKeyID(SIGNATURE, hotkey_id),
                                                  self.lib.GetApplicationEventTarget(), 0, self.ct.byref(ref))
        except Exception:
            return NATIVE_FAILED
        if status == NO_ERR:
            self.refs[hotkey_id] = ref
        return status

    def unregister(self, hotkey_id: int) -> None:
        ref = self.refs.pop(hotkey_id, None)
        if ref is not None:
            self.lib.UnregisterEventHotKey(ref)

    def remove(self) -> None:
        if self.installed:
            self.lib.RemoveEventHandler(self.handler_ref)
            self.installed = False


class HotKeys:
    """Registers global hotkeys and calls back with the name of the one pressed."""

    def __init__(self, callback: Callable[[str], None], backend=None, platform: str | None = None) -> None:
        self.callback = callback
        self.names: dict[int, str] = {}
        self.next_id = 1
        self.backend = backend
        if self.backend is None and (platform or sys.platform) == "darwin":
            try:
                self.backend = CarbonBackend()
            except Exception:  # Carbon could not be loaded: stay on the in-window shortcuts
                self.backend = None

    @property
    def available(self) -> bool:
        return self.backend is not None

    def register(self, name: str, combo: str) -> None:
        """Register `combo` (like 'option+space') under `name`. Raises HotKeyError with a readable message."""
        if self.backend is None:
            raise HotKeyError("global shortcuts need macOS")
        try:
            key_code, modifiers = parse_combo(combo)
        except ValueError as error:
            raise HotKeyError(str(error)) from None
        try:
            status = self.backend.install(self._pressed)
        except Exception as error:
            raise HotKeyError(f"could not start listening for {combo} ({error})") from None
        if status != NO_ERR:
            raise HotKeyError(f"could not start listening for {combo} (error {status})")
        hotkey_id = self.next_id
        try:
            status = self.backend.register(hotkey_id, key_code, modifiers)
        except Exception as error:
            raise HotKeyError(f"could not register {combo} ({error})") from None
        if status == EVENT_HOT_KEY_EXISTS_ERR:
            raise HotKeyError(f"{combo} is already used by another app")
        if status == EVENT_INTERNAL_ERR:
            raise HotKeyError(f"macOS refused {combo}; some macOS versions block shortcuts that use only Option")
        if status != NO_ERR:
            raise HotKeyError(f"could not register {combo} (error {status})")
        self.next_id += 1
        self.names[hotkey_id] = name

    def _pressed(self, hotkey_id: int) -> None:
        if name := self.names.get(hotkey_id):
            self.callback(name)

    def unregister_all(self) -> None:
        if self.backend is None:
            return
        for hotkey_id in list(self.names):
            self.backend.unregister(hotkey_id)
        self.names.clear()
        self.backend.remove()
