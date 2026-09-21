import asyncio
import os
import tempfile
import wave

import numpy as np

from audio.tts.base_tts import BaseTTS
from audio import playback


def _synth_wav(text: str, rate: int, voice_hint: str) -> tuple[np.ndarray, int]:
    import pyttsx3
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        if voice_hint:
            for v in engine.getProperty("voices"):
                if voice_hint.lower() in (v.name or "").lower():
                    engine.setProperty("voice", v.id)
                    break
        engine.save_to_file(text, path)
        engine.runAndWait()
        engine.stop()
        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            ch = w.getnchannels()
            raw = w.readframes(w.getnframes())
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            pcm = pcm.reshape(-1, ch).mean(axis=1)
        return pcm, sr
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


class LocalTTSProvider(BaseTTS):
    """Offline TTS via Windows SAPI (pyttsx3). No internet, no key."""

    def __init__(self):
        self._rate = int(os.getenv("CLICKY_LOCAL_TTS_RATE", "185"))
        self._voice = os.getenv("CLICKY_LOCAL_TTS_VOICE", "")

    def set_voice(self, voice: str) -> None:
        if voice and isinstance(voice, str):
            self._voice = voice

    async def speak(self, text: str) -> None:
        if not text.strip():
            return
        playback._arm_audio()
        loop = asyncio.get_running_loop()
        pcm, sr = await loop.run_in_executor(None, _synth_wav, text, self._rate, self._voice)
        if pcm.size == 0 or playback._stop_event.is_set():
            return
        await loop.run_in_executor(None, playback._blocking_play_chunked, pcm, sr)
