from typing import AsyncIterator, List

import anthropic

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


class ClaudeProvider(BaseLLMProvider):

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or DEFAULT_MODEL

        messages = []

        # Inject conversation history
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Build current user message with optional screenshots
        content: list = []
        for i, img_b64 in enumerate(screenshots_b64):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_b64,
                },
            })

        content.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": content})

        async with self._client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
