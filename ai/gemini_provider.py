"""
Google Gemini provider — uses the REST SSE streaming API directly (no extra deps).
Default model: gemini-2.5-flash (fast, cheap, vision-capable).
"""

import asyncio
import os
import json
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

DEFAULT_MODEL = "gemini-2.5-flash"
_RETRY_STATUS = {429, 500, 502, 503, 504}
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
            "generationConfig": {"maxOutputTokens": int(os.getenv("CLICKY_MAX_OUTPUT_TOKENS", "1024") or 1024), "temperature": 0.7},
        }

        headers = {"x-goog-api-key": self._api_key or ""}   # keep key out of URLs/logs

        # Retry transient overloads (503/429/5xx), then fall back to the
        # default model once. Retries only happen before any text is yielded.
        models = [model] + ([DEFAULT_MODEL] if model != DEFAULT_MODEL else [])
        last_err: Exception | None = None
        async with httpx.AsyncClient(timeout=120) as client:
            for m in models:
                url = f"{STREAM_URL.format(model=m)}?alt=sse"
                for attempt in range(3):
                    try:
                        async with client.stream("POST", url, json=body, headers=headers) as resp:
                            if resp.status_code in _RETRY_STATUS:
                                await resp.aread()
                                last_err = httpx.HTTPStatusError(
                                    f"HTTP {resp.status_code} from Gemini ({m})",
                                    request=resp.request, response=resp,
                                )
                            else:
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
                                return
                    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                        last_err = e
                    await asyncio.sleep(1.5 * (attempt + 1))
        if last_err:
            raise RuntimeError(
                "Gemini is overloaded or unreachable right now. Try again, "
                "or switch model / use Ollama from the tray."
            ) from last_err

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"x-goog-api-key": self._api_key or ""},
                )
                return r.status_code == 200
        except Exception:
            return False
