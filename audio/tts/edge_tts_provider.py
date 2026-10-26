import io
import asyncio
import logging

import edge_tts
from storage import setting

from audio.tts.base_tts import BaseTTS
from audio.playback import play_mp3_async

# High-quality Microsoft neural voice — no API key required
VOICE = "en-US-AvaNeural"


class EdgeTTSProvider(BaseTTS):
    """
    Free TTS using Microsoft Edge's neural voices via edge-tts.
    No API key. Streams audio over the internet silently.
    ~400 voices available; AvaNeural is natural and fast.
    """

    def __init__(self, voice: str = VOICE, on_fallback=None):
        self._voice = setting("voice_edge_tts", voice) or voice
        self._fallback = None
        self._on_fallback = on_fallback

    def stop(self):
        if self._fallback:
            self._fallback.stop()

    def set_voice(self, voice: str) -> None:
        import re
        if not isinstance(voice,str):
            raise ValueError("Use an Edge voice name")
        if voice.lower() in {'ava','jenny','guy','aria'}:
            voice = 'en-US-'+voice.capitalize()+'Neural'
        if not re.fullmatch(r'[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural',voice):
            raise ValueError("Use a full Edge voice name such as en-US-JennyNeural")
        self._voice = voice

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        if self._fallback:
            await self._fallback.speak(text)
            return

        async def synthesize():
            communicate = edge_tts.Communicate(text, self._voice, rate=f"{int(setting('speech_rate', 0)) * 10:+d}%")
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            if not buf.tell():
                raise RuntimeError('Edge returned no audio')
            return buf.getvalue()

        try:
            audio = await asyncio.wait_for(synthesize(), timeout=25)
        except Exception as exc:
            from audio.tts.sapi_tts_provider import SapiTTSProvider
            self._fallback = SapiTTSProvider()
            status = getattr(exc, 'status', None)
            logging.getLogger('clicky.voice').warning('Edge unavailable: %s, status=%s; using Windows speech', type(exc).__name__, status)
            if self._on_fallback:
                self._on_fallback('Edge voice is unavailable' + (f' (HTTP {status})' if status else '') + '. Using offline Windows voice for this session. Reapply Edge in Voice settings to retry.')
            await self._fallback.speak(text)
            return

        await play_mp3_async(audio)

    @staticmethod
    def list_voices_sync() -> list:
        """Returns available voice names (blocking, for settings UI)."""
        import asyncio as _asyncio
        async def _get():
            return await edge_tts.list_voices()
        return _asyncio.run(_get())
