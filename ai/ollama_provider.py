import os
import base64
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from ai.ollama_models_registry import is_vision_capable
from config import cfg


# Model architectures current Ollama builds can no longer load. Pulling one
# succeeds, so `ollama list` shows it as installed, and it only fails at the
# moment a request tries to load it — as an opaque HTTP 500.
_DEAD_ARCHITECTURES = ("mllama",)


def _explain_ollama_error(status: int, body: str, model: str, had_images: bool) -> str:
    """Turn an Ollama HTTP error into something a user can act on."""
    low = (body or "").lower()

    # llama3.2-vision and friends are built on 'mllama', dropped by newer
    # Ollama. The server logs 'unknown model architecture', llama-server dies,
    # and the client only sees a bare HTTP 500.
    if any(a in low for a in _DEAD_ARCHITECTURES) or "unknown model architecture" in low:
        return (
            "'{m}' cannot be loaded by your version of Ollama. Its model "
            "architecture was dropped in a newer Ollama release, so it fails "
            "even though `ollama list` still shows it installed.\n\n"
            "Switch to a supported vision model:\n"
            "    ollama pull qwen2.5vl:3b\n\n"
            "then choose it under Tray -> Ollama -> Vision model."
        ).format(m=model)

    # Sending images to a text-only model: Ollama answers 400 with this text.
    if "does not support multimodal" in low or "multimodal data provided" in low:
        return (
            "'{m}' is a text-only model, but Clicky sends a screenshot with "
            "every question.\n\n"
            "Choose a vision model under Tray -> Ollama -> Vision model, or "
            "pull one:\n"
            "    ollama pull qwen2.5vl:3b"
        ).format(m=model)

    if "out of memory" in low or "insufficient memory" in low:
        return (
            "Ollama ran out of memory loading '{m}'. Try a smaller model "
            "(qwen2.5vl:3b needs about 3 GB) or close other applications."
        ).format(m=model)

    snippet = (body or "").strip()[:300] or "(no detail returned)"
    hint = (
        "\n\nThis request included a screenshot. If the model is text-only, "
        "choose a vision model under Tray -> Ollama."
        if had_images else ""
    )
    return "Ollama returned HTTP {s} for '{m}': {b}{h}".format(
        s=status, m=model, b=snippet, h=hint
    )


class OllamaProvider(BaseLLMProvider):
    """
    Streams responses from a local Ollama instance.

    Auto-picks the right model per call:
        • Screenshots present → cfg.get_ollama_model("vision")
        • No screenshots      → cfg.get_ollama_model("text")

    A caller may still pass an explicit `model=` to override that choice
    (e.g. the panel's manual model dropdown).
    """

    def __init__(self):
        self._base = cfg.ollama_host.rstrip("/")
        # Kept for backward compat with old code paths reading self._model
        self._model = cfg.ollama_model
        self._client = httpx.AsyncClient(
            timeout=120,
            limits=httpx.Limits(max_keepalive_connections=4, max_connections=8)
        )

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self._client.aclose()

    def _pick_model(self, has_screenshots: bool) -> str:
        return cfg.get_ollama_model("vision" if has_screenshots else "text")

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        # Resolution order:
        #   1. explicit `model=` arg (panel override)
        #   2. cfg vision/text slot based on attachment kind
        if model:
            chosen = model
        else:
            chosen = self._pick_model(bool(screenshots_b64))

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Ollama passes images as base64 strings inside the message
        user_msg: dict = {"role": "user", "content": user_text}
        if screenshots_b64:
            user_msg["images"] = screenshots_b64
        messages.append(user_msg)

        options: dict = {
            "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "1024") or 1024),
            "num_gpu": cfg.ollama_num_gpu,
            "num_ctx": cfg.ollama_num_ctx,
        }
        if cfg.ollama_num_thread is not None:
            options["num_thread"] = cfg.ollama_num_thread

        payload = {
            "model": chosen,
            "messages": messages,
            "stream": True,
            "keep_alive": cfg.ollama_keep_alive,
            "options": options,
        }

        async with self._client.stream(
            "POST",
            f"{self._base}/api/chat",
            json=payload,
        ) as response:
            if response.status_code == 404:
                # Surface a useful error when the chosen model isn't
                # installed locally — students hit this constantly.
                raise RuntimeError(
                    f"Ollama doesn't have '{chosen}' installed. "
                    f"Run `ollama pull {chosen}` or pick another model "
                    f"from Tray → Ollama."
                )

            if response.status_code >= 400:
                # Anything not handled above used to fall through to
                # raise_for_status(), which surfaces httpx's own text —
                # "Server error '500 Internal Server Error' for url ..."
                # plus a link to MDN. That told users nothing about which
                # model failed or what to do, and Ollama's own explanation
                # in the response body was thrown away.
                body = (await response.aread()).decode("utf-8", "replace")
                raise RuntimeError(_explain_ollama_error(
                    response.status_code, body, chosen, bool(screenshots_b64)
                ))

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
            r = await self._client.get(f"{self._base}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Return all installed model names (flat list)."""
        try:
            r = await self._client.get(f"{self._base}/api/tags", timeout=5)
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []


    async def list_models_classified(self) -> dict[str, list[str]]:
        """Installed models split into {'vision': [...], 'text': [...]}.

        Heuristic-based — see ollama_models_registry.is_vision_capable().
        """
        names = await self.list_models()
        out: dict[str, list[str]] = {"vision": [], "text": []}
        for n in names:
            if is_vision_capable(n):
                out["vision"].append(n)
            else:
                out["text"].append(n)
        out["vision"].sort()
        out["text"].sort()
        return out
