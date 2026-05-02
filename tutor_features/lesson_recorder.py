"""
Lesson recording.

Captures Clicky lessons as:
  • MP4 video — primary monitor, 8 fps, Clicky's pointer overlaid
  • Markdown transcript — Q&A + timestamps next to the video

Output:  ~/Documents/Clicky Lessons/<timestamp>/

Backend: imageio-ffmpeg (auto-bundles ffmpeg, no system install needed).
"""

from __future__ import annotations

import io
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import mss
from PIL import Image


FPS = 8


class LessonRecorder:
    """Headless screen recorder. Markdown transcript built up alongside."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._writer = None
        self._md_lines: list[str] = []
        self._t0: float = 0.0
        self._out_dir: Optional[Path] = None
        self.is_recording = False

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> Optional[Path]:
        """Begin recording. Returns the output directory or None on failure."""
        if self.is_recording:
            return self._out_dir

        try:
            import imageio_ffmpeg   # noqa: F401  (required by imageio[ffmpeg])
            import imageio
        except ImportError:
            return None

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._out_dir = Path.home() / "Documents" / "Clicky Lessons" / ts
        self._out_dir.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            mon = sct.monitors[1]      # primary
            w, h = mon["width"], mon["height"]

        self._writer = imageio.get_writer(
            str(self._out_dir / "lesson.mp4"),
            fps=FPS,
            codec="libx264",
            quality=7,
            macro_block_size=None,
        )
        self._md_lines = [f"# Clicky Lesson — {ts}", ""]
        self._t0 = time.monotonic()
        self._stop_evt.clear()
        self.is_recording = True

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._out_dir

    def stop(self) -> Optional[Path]:
        """Stop and flush. Returns the output directory."""
        if not self.is_recording:
            return None
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
        if self._out_dir:
            (self._out_dir / "transcript.md").write_text(
                "\n".join(self._md_lines), encoding="utf-8"
            )
        self.is_recording = False
        return self._out_dir

    # ── Transcript hooks (manager calls these) ──────────────────────────────

    def log_question(self, q: str):
        if self.is_recording:
            t = time.monotonic() - self._t0
            self._md_lines.append(f"\n## [{t:6.1f}s] Q: {q}\n")

    def log_answer(self, a: str):
        if self.is_recording:
            self._md_lines.append(f"**A:** {a.strip()}\n")

    # ── Internal ────────────────────────────────────────────────────────────

    def _loop(self):
        with mss.mss() as sct:
            mon = sct.monitors[1]
            interval = 1.0 / FPS
            next_t = time.monotonic()
            while not self._stop_evt.is_set():
                try:
                    raw = sct.grab(mon)
                    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                    if self._writer is not None:
                        self._writer.append_data(_to_array(img))
                except Exception:
                    pass
                next_t += interval
                sleep_left = next_t - time.monotonic()
                if sleep_left > 0:
                    time.sleep(sleep_left)
                else:
                    next_t = time.monotonic()


def _to_array(img: Image.Image):
    import numpy as np
    return np.array(img)
