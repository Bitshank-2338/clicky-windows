from abc import ABC, abstractmethod


class BaseTTS(ABC):

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesize and play audio for the given text."""
        ...
