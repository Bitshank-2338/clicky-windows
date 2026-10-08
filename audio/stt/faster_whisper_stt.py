import io
import asyncio
from typing import Optional

from audio.stt.base_stt import BaseSTT
from audio.capture import pcm16_to_wav, trim_silence
from config import cfg

_model_cache = None


def wav_to_whisper_input(wav_bytes: bytes):
    """Decode Clicky's own 16 kHz mono PCM16 WAV into the float32 array
    faster-whisper accepts directly.

    Handing faster-whisper a file path makes it decode through PyAV, and
    faster-whisper 1.2.x calls av.open(metadata_errors=...), an argument PyAV
    19 removed — so on a fresh install every voice question failed with
    "open() got an unexpected keyword argument 'metadata_errors'". We already
    hold the raw samples, so skip the round trip through a temp file and PyAV.
    """
    import wave
    import numpy as np

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1 or w.getframerate() != 16000:
            raise ValueError("expected 16 kHz mono 16-bit audio for transcription")
        pcm = w.readframes(w.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def _get_model():
    global _model_cache
    if _model_cache is None:
        from faster_whisper import WhisperModel
        # compute_type="int8" runs on CPU without CUDA; use "float16" if GPU available
        _model_cache = WhisperModel(cfg.whisper_model, device="cpu", compute_type="int8")
    return _model_cache


class FasterWhisperSTT(BaseSTT):
    """
    Local, offline speech-to-text using faster-whisper.
    No API key required. Runs entirely on CPU.
    Model is loaded once and cached.
    """

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        pcm_bytes = trim_silence(pcm_bytes)
        wav_bytes = pcm16_to_wav(pcm_bytes, sample_rate)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run, wav_bytes)

    def _run(self, wav_bytes: bytes) -> str:
        model = _get_model()
        lang = cfg.whisper_language or None  # None = auto-detect
        segments, _ = model.transcribe(
            wav_to_whisper_input(wav_bytes), beam_size=5, language=lang,
        )
        return " ".join(s.text.strip() for s in segments).strip()
