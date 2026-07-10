from abc import ABC, abstractmethod
from typing import Optional


class BaseTTS(ABC):

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesize and play audio for the given text."""
        ...

    async def synthesize(self, text: str) -> Optional[bytes]:
        """Optional: synthesize audio WITHOUT playing it, so the next
        sentence's audio can be generated while the current one still
        plays (removes the network round-trip from perceived latency).
        Providers that don't implement this return None — speak() still
        works, just without the prefetch win."""
        return None
