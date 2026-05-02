import base64
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from config import cfg


class OllamaProvider(BaseLLMProvider):
    """
    Streams responses from a local Ollama instance.
    Requires a vision-capable model (llama3.2-vision, llava, etc.).
    """

    def __init__(self):
        self._base = cfg.ollama_host.rstrip("/")
        self._model = cfg.ollama_model

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or self._model

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Ollama passes images as base64 strings inside the message
        user_msg: dict = {"role": "user", "content": user_text}
        if screenshots_b64:
            user_msg["images"] = screenshots_b64
        messages.append(user_msg)

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"num_predict": 1024},
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self._base}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                import json
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self._base}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self._base}/api/tags")
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
