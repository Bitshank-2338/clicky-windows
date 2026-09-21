from audio.tts.base_tts import BaseTTS


class OffTTSProvider(BaseTTS):
    """Silent TTS. Text still shows in the panel."""

    def set_voice(self, voice: str) -> None:
        pass

    async def speak(self, text: str) -> None:
        return
