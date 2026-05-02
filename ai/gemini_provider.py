"""
Google Gemini provider — uses the REST SSE streaming API directly (no extra deps).
Default model: gemini-2.5-flash (fast, cheap, vision-capable).
"""

import json
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

DEFAULT_MODEL = "gemini-2.5-flash"
STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
)


class GeminiProvider(BaseLLMProvider):

    def __init__(self):
        self._api_key = cfg.google_api_key

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or DEFAULT_MODEL

        contents = []
        for msg in history:
            role = "user" if msg.role == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        parts: list = []
        for img_b64 in screenshots_b64:
            parts.append({
                "inline_data": {"mime_type": "image/jpeg", "data": img_b64},
            })
        parts.append({"text": user_text})
        contents.append({"role": "user", "parts": parts})

        body = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7},
        }

        url = f"{STREAM_URL.format(model=model)}?alt=sse&key={self._api_key}"

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for cand in obj.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            text = part.get("text", "")
                            if text:
                                yield text

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self._api_key}"
                )
                return r.status_code == 200
        except Exception:
            return False
