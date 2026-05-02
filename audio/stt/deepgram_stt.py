import httpx

from audio.stt.base_stt import BaseSTT
from audio.capture import pcm16_to_wav
from config import cfg

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


class DeepgramSTT(BaseSTT):
    """
    Deepgram Nova-2 — upload-based, real-time quality, free tier 12k min/month.
    Faster and more accurate than Whisper for English.
    """

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        wav_bytes = pcm16_to_wav(pcm_bytes, sample_rate)
        headers = {
            "Authorization": f"Token {cfg.deepgram_api_key}",
            "Content-Type": "audio/wav",
        }
        params = {
            "model": "nova-2",
            "language": "en",
            "smart_format": "true",
            "punctuate": "true",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                DEEPGRAM_URL,
                headers=headers,
                params=params,
                content=wav_bytes,
            )
            r.raise_for_status()
            data = r.json()
            transcript = (
                data.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                    .strip()
            )
            return transcript
