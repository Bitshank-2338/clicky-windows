from openai import AsyncOpenAI

from audio.tts.base_tts import BaseTTS
from audio.playback import play_mp3_async
from config import cfg


class OpenAITTSProvider(BaseTTS):
    """OpenAI TTS — high quality, $15/1M chars."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=cfg.openai_api_key)

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        response = await self._client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="mp3",
        )

        await play_mp3_async(response.content)
