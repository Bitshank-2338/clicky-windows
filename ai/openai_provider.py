from typing import AsyncIterator, List

from openai import AsyncOpenAI

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

DEFAULT_MODEL = "gpt-4o"
MAX_TOKENS = 1024


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):
        self._client = AsyncOpenAI(api_key=cfg.openai_api_key)

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or DEFAULT_MODEL

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        content: list = []
        for img_b64 in screenshots_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"},
            })
        content.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": content})

        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
