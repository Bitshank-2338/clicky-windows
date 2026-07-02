import threading
import time
from typing import Callable

import keyboard

from config import cfg


# Canonical names the `keyboard` lib uses for each modifier, in the order we
# should probe them. is_pressed("ctrl") only matches LEFT ctrl on some layouts,
# so we check the sided variants too.
_MOD_ALIASES = {
    "ctrl":    ("ctrl", "left ctrl", "right ctrl"),
    "control": ("ctrl", "left ctrl", "right ctrl"),
    "alt":     ("alt", "left alt", "right alt"),
    "shift":   ("shift", "left shift", "right shift"),
    "win":     ("windows", "left windows", "right windows"),
    "windows": ("windows", "left windows", "right windows"),
    "cmd":     ("windows", "left windows", "right windows"),
}


def _is_down(token: str) -> bool:
    for alias in _MOD_ALIASES.get(token, (token,)):
        try:
            if keyboard.is_pressed(alias):
                return True
        except Exception:
            continue
    return False


class GlobalHotkeyMonitor:
    """
    Registers a system-wide push-to-talk hotkey (default: ctrl+win).
    Fires on_press when held, on_release when released.

    Two modes, picked automatically from the hotkey string:

      • MODIFIER-ONLY combos ("ctrl+win", "ctrl+shift"): every part is a
        modifier, so there's no terminal key to hook. We hook ALL key events
        and track state — combo engages when every part is down, releases
        when any part lifts.

      • CLASSIC combos ("ctrl+alt+space", "alt+q"): last part is a normal
        key; hook press/release of that key and require the modifiers.

    Start-menu suppression: when a combo containing Win engages, we inject a
    dummy F24 press. Windows only opens the Start menu if the Win key is
    pressed and released *alone* — the dummy key marks the hold as "used",
    so releasing Win afterwards does nothing.
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        hotkey: str | None = None,
    ):
        self._hotkey = (hotkey or cfg.hotkey).lower()
        self._parts = [p.strip() for p in self._hotkey.split("+") if p.strip()]
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._has_win = any(p in ("win", "windows", "cmd") for p in self._parts)
        self._modifier_only = all(p in _MOD_ALIASES for p in self._parts)
        self._hook_handle = None

    def start(self):
        if self._modifier_only:
            # No terminal key — watch the global key stream and poll state.
            self._hook_handle = keyboard.hook(self._on_any_event)
        else:
            terminal = self._parts[-1]
            keyboard.on_press_key(terminal, self._handle_press)
            keyboard.on_release_key(terminal, self._handle_release)

    # ── Modifier-only mode ────────────────────────────────────────────────────

    def _combo_down(self) -> bool:
        return all(_is_down(p) for p in self._parts)

    def _on_any_event(self, event):
        try:
            if not self._held:
                if event.event_type == "down" and self._combo_down():
                    self._held = True
                    if self._has_win:
                        self._suppress_start_menu()
                    self._on_press()
            else:
                if not self._combo_down():
                    self._held = False
                    self._on_release()
        except Exception:
            pass  # never let a callback error kill the keyboard hook

    @staticmethod
    def _suppress_start_menu():
        """Inject a dummy key while Win is held so its release is a no-op."""
        try:
            keyboard.press_and_release("f24")
        except Exception:
            pass

    # ── Classic terminal-key mode ─────────────────────────────────────────────

    def _modifiers_held(self) -> bool:
        return all(_is_down(m) for m in self._parts[:-1])

    def _handle_press(self, event):
        if not self._held and self._modifiers_held():
            self._held = True
            if self._has_win:
                self._suppress_start_menu()
            self._on_press()

    def _handle_release(self, event):
        if self._held:
            self._held = False
            self._on_release()

    def stop(self):
        if self._hook_handle is not None:
            try:
                keyboard.unhook(self._hook_handle)
            except Exception:
                pass
            self._hook_handle = None
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
