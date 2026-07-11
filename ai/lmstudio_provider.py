"""
LM Studio provider.

LM Studio exposes an OpenAI-compatible REST server (default:
http://localhost:1234/v1) once you press "Start Server" in its Developer
tab. This provider talks to that endpoint directly over HTTP so we don't
need the `openai` SDK's base_url plumbing — same approach as
ollama_provider.py, kept dependency-free and consistent with the rest of
this file's style.

No API key is required for local use; LM Studio ignores the field.
"""

import json
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from config import cfg


class LMStudioProvider(BaseLLMProvider):
    """
    Streams responses from a local LM Studio server (OpenAI-compatible
    /v1/chat/completions endpoint).

    Model selection: LM Studio serves whichever model is currently loaded
    in the app. cfg.lmstudio_model, if set, is sent explicitly (useful if
    you keep several models loaded); otherwise we ask LM Studio to use
    whatever's active via a placeholder id, which it accepts.
    """

    def __init__(self):
        self._base = cfg.lmstudio_host.rstrip("/")
        self._model = cfg.lmstudio_model
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Reused pooled connection instead of a fresh handshake per
        request — same latency win as the Ollama provider."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120,
                limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
            )
        return self._client

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        chosen = model or self._model or "local-model"

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # OpenAI-style multimodal content blocks (LM Studio's vision models
        # accept the same image_url/base64 shape as OpenAI's API).
        content: list = []
        for img_b64 in screenshots_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
            })
        content.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": content if screenshots_b64 else user_text})

        payload = {
            "model": chosen,
            "messages": messages,
            "max_tokens": 1024,
            "stream": True,
        }

        client = self._get_client()
        try:
            async with client.stream(
                "POST",
                f"{self._base}/chat/completions",
                json=payload,
            ) as response:
                if response.status_code == 404:
                    raise RuntimeError(
                        "LM Studio server not reachable at "
                        f"{self._base}. Open LM Studio → Developer tab → "
                        "Start Server, and make sure a model is loaded."
                    )
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except httpx.ConnectError as e:
            raise RuntimeError(
                "Can't reach LM Studio. Is the local server running? "
                "(LM Studio → Developer tab → Start Server)"
            ) from e

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            r = await client.get(f"{self._base}/models", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Return model ids LM Studio currently reports via /v1/models."""
        try:
            client = self._get_client()
            r = await client.get(f"{self._base}/models", timeout=5)
            data = r.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []
