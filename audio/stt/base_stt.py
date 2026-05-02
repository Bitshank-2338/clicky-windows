from abc import ABC, abstractmethod


class BaseSTT(ABC):

    @abstractmethod
    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM16 audio bytes to text."""
        ...
