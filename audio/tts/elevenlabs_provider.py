import httpx

from audio.tts.base_tts import BaseTTS
from audio.playback import play_mp3_async
from config import cfg

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah — natural, clear


class ElevenLabsProvider(BaseTTS):
    """ElevenLabs TTS — premium quality. Free tier: 10k chars/month."""

    def __init__(self):
        self._voice_id = cfg.elevenlabs_voice_id or DEFAULT_VOICE_ID

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        url = ELEVENLABS_TTS_URL.format(voice_id=self._voice_id)
        headers = {
            "xi-api-key": cfg.elevenlabs_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            audio_bytes = r.content

        await play_mp3_async(audio_bytes)
