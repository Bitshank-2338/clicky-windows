import threading
from typing import Callable

import keyboard

from config import cfg


class GlobalHotkeyMonitor:
    """
    Registers a system-wide hotkey (default: ctrl+alt+space).
    Fires on_press when held, on_release when released.
    Runs in a daemon thread so it doesn't block the Qt event loop.
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        hotkey: str | None = None,
    ):
        self._hotkey = hotkey or cfg.hotkey
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._thread: threading.Thread | None = None

    def start(self):
        keyboard.on_press_key(self._hotkey.split("+")[-1], self._handle_press)
        keyboard.on_release_key(self._hotkey.split("+")[-1], self._handle_release)

    def _modifiers_held(self) -> bool:
        parts = [p.strip() for p in self._hotkey.lower().split("+")]
        mods = parts[:-1]
        mod_map = {
            "ctrl": keyboard.is_pressed("ctrl"),
            "alt": keyboard.is_pressed("alt"),
            "shift": keyboard.is_pressed("shift"),
            "win": keyboard.is_pressed("windows"),
        }
        return all(mod_map.get(m, False) for m in mods)

    def _handle_press(self, event):
        if not self._held and self._modifiers_held():
            self._held = True
            self._on_press()

    def _handle_release(self, event):
        if self._held:
            self._held = False
            self._on_release()

    def stop(self):
        keyboard.unhook_all()


class StopHotkey:
    """A global key that cancels the current generation (default: Esc).

    Only fires while Clicky is actively talking/thinking — the callback itself
    should no-op when Clicky is idle, so this can be left always-on without
    stealing Esc from other apps' UX.
    """

    def __init__(self, on_stop: Callable[[], None], key: str = "esc"):
        self._on_stop = on_stop
        self._key = key

    def start(self):
        keyboard.add_hotkey(self._key, self._on_stop, suppress=False)
