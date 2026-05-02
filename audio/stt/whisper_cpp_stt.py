"""
Whisper.cpp STT — same engine [Handy](https://github.com/cjpais/Handy) uses.

3-5× faster than faster-whisper on the same hardware because it ships with
GPU acceleration (CUDA on NVIDIA, Vulkan on AMD/Intel) and uses quantised
GGML weights instead of CTranslate2.

Setup:
    pip install pywhispercpp

The first call auto-downloads the model GGML file (~150 MB for `base.en`)
into ~/.cache/whisper.cpp/. After that it's fully offline.

If pywhispercpp isn't installed, this provider raises ImportError so the
manager can fall back to faster-whisper without crashing.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import wave
from pathlib import Path
from typing import Optional

from audio.stt.base_stt import BaseSTT
from config import cfg


# Model size:  tiny / base / small / medium / large
# Append `.en` for English-only (smaller, faster, more accurate for English).
DEFAULT_MODEL = os.getenv("WHISPERCPP_MODEL", "base.en")


class WhisperCppSTT(BaseSTT):
    """Local STT via whisper.cpp + pywhispercpp."""

    def __init__(self, model: Optional[str] = None):
        try:
            from pywhispercpp.model import Model    # type: ignore
        except ImportError as e:
            raise ImportError(
                "whisper.cpp not installed. Run:  pip install pywhispercpp"
            ) from e

        self._Model = Model
        self._model_name = model or DEFAULT_MODEL
        self._model = None  # lazy — first transcribe loads it

    def _load(self):
        if self._model is None:
            # n_threads = physical cores - 1 (leave one for the UI)
            try:
                cores = max(1, (os.cpu_count() or 4) - 1)
            except Exception:
                cores = 4
            self._model = self._Model(
                self._model_name,
                n_threads=cores,
                print_realtime=False,
                print_progress=False,
            )
        return self._model

    async def transcribe(self, pcm_bytes: bytes) -> str:
        """Convert raw 16-bit mono PCM @ 16 kHz → text."""
        if not pcm_bytes:
            return ""

        # whisper.cpp expects a WAV file path. Stage to a temp file —
        # cleanup is automatic.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_transcribe, pcm_bytes)

    def _sync_transcribe(self, pcm_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with wave.open(tmp_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)        # 16-bit
                w.setframerate(16000)    # AmbientListener captures at 16 kHz
                w.writeframes(pcm_bytes)
            model = self._load()
            segments = model.transcribe(tmp_path)
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
