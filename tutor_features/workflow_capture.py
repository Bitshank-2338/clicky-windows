"""
Workflow capture — record a sequence of clicks + keystrokes the user
performs, then let Clicky explain or replay them.

Status: foundation laid. Hotkey + recording loop work. Replay layer is
intentionally a stub — playback of synthetic input is a security concern
and needs a careful UX (preview, confirm, undo) before it's safe to ship.

Use:
    capt = WorkflowCapture()
    capt.start()      # Ctrl+Alt+R → starts capture
    # ... user clicks around, types
    capt.stop()       # Ctrl+Alt+R again → stops, returns events list

Each event:  {"t": float, "kind": "click"|"key", "data": {...}}
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional


class WorkflowCapture:
    def __init__(self):
        self._events: list[dict] = []
        self._t0: float = 0.0
        self._is_running = False
        self._listener_kb = None
        self._listener_mouse = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> bool:
        try:
            from pynput import mouse, keyboard   # type: ignore
        except ImportError:
            return False
        self._events = []
        self._t0 = time.monotonic()
        self._is_running = True

        def on_click(x, y, button, pressed):
            if pressed and self._is_running:
                self._events.append({
                    "t": time.monotonic() - self._t0,
                    "kind": "click",
                    "data": {"x": x, "y": y, "button": str(button)},
                })

        def on_press(key):
            if self._is_running:
                self._events.append({
                    "t": time.monotonic() - self._t0,
                    "kind": "key",
                    "data": {"key": str(key)},
                })

        from pynput import mouse, keyboard
        self._listener_mouse = mouse.Listener(on_click=on_click)
        self._listener_kb    = keyboard.Listener(on_press=on_press)
        self._listener_mouse.start()
        self._listener_kb.start()
        return True

    def stop(self) -> list[dict]:
        if not self._is_running:
            return []
        self._is_running = False
        for li in (self._listener_mouse, self._listener_kb):
            try:
                if li:
                    li.stop()
            except Exception:
                pass
        return list(self._events)

    def summarise(self) -> str:
        """Plain-English summary the LLM can ingest."""
        if not self._events:
            return "(no actions recorded)"
        lines = []
        for e in self._events[:40]:
            t = e["t"]
            if e["kind"] == "click":
                d = e["data"]
                lines.append(f"  [{t:5.1f}s] click {d['button']} at ({d['x']}, {d['y']})")
            else:
                lines.append(f"  [{t:5.1f}s] key {e['data']['key']}")
        if len(self._events) > 40:
            lines.append(f"  …and {len(self._events) - 40} more events.")
        return "Recorded workflow:\n" + "\n".join(lines)
