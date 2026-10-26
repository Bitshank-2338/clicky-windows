from openai import AsyncOpenAI

from audio.tts.base_tts import BaseTTS
from audio.playback import play_mp3_async
from config import cfg
from storage import setting


class OpenAITTSProvider(BaseTTS):
    """OpenAI TTS — high quality, $15/1M chars."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=cfg.openai_api_key)
        self._voice = setting("voice_openai", "alloy") or "alloy"

    def set_voice(self, voice):
        if voice not in {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}:
            raise ValueError("Unknown OpenAI voice")
        self._voice = voice

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        response = await self._client.audio.speech.create(
            model="tts-1",
            voice=self._voice,
            input=text,
            response_format="mp3",
        )

        await play_mp3_async(response.content)
