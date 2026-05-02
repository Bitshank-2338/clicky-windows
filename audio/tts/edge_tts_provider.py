import io

import edge_tts

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

    def __init__(self, voice: str = VOICE):
        self._voice = voice

    def set_voice(self, voice: str) -> None:
        if voice and isinstance(voice, str):
            self._voice = voice

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        communicate = edge_tts.Communicate(text, self._voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])

        await play_mp3_async(buf.getvalue())

    @staticmethod
    def list_voices_sync() -> list:
        """Returns available voice names (blocking, for settings UI)."""
        import asyncio as _asyncio
        async def _get():
            return await edge_tts.list_voices()
        return _asyncio.run(_get())
