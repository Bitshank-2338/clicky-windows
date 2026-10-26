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
import wave
import subprocess
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
        self._audio_lock = threading.Lock()
        self._audio = None
        self._audio_frames = 0
        self._video_frames = 0
        self._overlay = None

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

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        from storage import data_dir
        self._out_dir = data_dir() / "recordings" / ts
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
        self._audio = wave.open(str(self._out_dir / "narration.wav"), "wb")
        self._audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        self._audio_frames = 0
        self._video_frames = 0
        from audio.playback import observe_pcm
        observe_pcm(self._record_audio)
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
        from audio.playback import observe_pcm
        observe_pcm(None)
        if self._thread:
            self._thread.join(timeout=10.0)
            if self._thread.is_alive():
                raise OSError("Recording is still flushing; try stopping it again")
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
        with self._audio_lock:
            if self._audio:
                if self._audio_frames == 0:
                    self._audio.writeframes(b"\0\0" * 240)
                self._audio.close()
                self._audio = None
        if self._out_dir:
            (self._out_dir / "transcript.md").write_text(
                "\n".join(self._md_lines), encoding="utf-8"
            )
        self.is_recording = False
        if self._out_dir:
            import imageio_ffmpeg
            result = subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(self._out_dir / "lesson.mp4"),
                "-i", str(self._out_dir / "narration.wav"), "-c:v", "copy", "-c:a", "aac",
                "-af", "apad", "-t", str(max(1, self._video_frames) / FPS), str(self._out_dir / "lesson-narrated.mp4"),
            ], capture_output=True, timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise OSError("Narration mux failed; the original video and narration.wav have been preserved")
        return self._out_dir

    def _record_audio(self, pcm, sample_rate):
        import numpy as np
        count = max(1, round(len(pcm) * 24000 / sample_rate))
        samples = np.interp(np.arange(count) * sample_rate / 24000, np.arange(len(pcm)), pcm)
        encoded = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
        with self._audio_lock:
            if not self._audio or not self.is_recording:
                return
            target = round((time.monotonic() - self._t0) * 24000)
            gap = max(0, target - self._audio_frames)
            while gap:
                chunk = min(gap, 24000)
                self._audio.writeframesraw(b"\0\0" * chunk)
                gap -= chunk
                self._audio_frames += chunk
            self._audio.writeframesraw(encoded)
            self._audio_frames += count

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
                    from screen.privacy import redact
                    from storage import setting
                    if setting("privacy_guard", True):
                        redact(img, mon["left"], mon["top"])
                    overlay = self._overlay
                    if overlay:
                        ink, left, top, scale = overlay
                        offset_x = round((mon['left'] - left) * scale)
                        offset_y = round((mon['top'] - top) * scale)
                        crop = ink.crop((offset_x, offset_y, offset_x + mon['width'], offset_y + mon['height']))
                        img.paste(crop, (0,0), crop)
                    if self._writer is not None:
                        self._writer.append_data(_to_array(img))
                        self._video_frames += 1
                except Exception:
                    # Never reuse the previous frame if privacy inspection failed.
                    if self._writer is not None:
                        self._writer.append_data(_to_array(Image.new("RGB", (mon["width"], mon["height"]), "black")))
                        self._video_frames += 1
                next_t += interval
                sleep_left = next_t - time.monotonic()
                if sleep_left > 0:
                    time.sleep(sleep_left)
                else:
                    next_t = time.monotonic()


def _to_array(img: Image.Image):
    import numpy as np
    return np.array(img)
