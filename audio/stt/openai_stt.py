import io
from openai import AsyncOpenAI

from audio.stt.base_stt import BaseSTT
from audio.capture import pcm16_to_wav
from config import cfg


class OpenAISTT(BaseSTT):
    """OpenAI Whisper API — upload-based, high accuracy."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=cfg.openai_api_key)

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        wav_bytes = pcm16_to_wav(pcm_bytes, sample_rate)
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"
        result = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )
        return result.strip() if isinstance(result, str) else result.text.strip()
