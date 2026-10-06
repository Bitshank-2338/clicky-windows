import asyncio
import json
import logging
import time
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from ai.ollama_models_registry import (
    DEFAULT_VISION_MODEL, is_dead_model, is_shipped_default, is_vision_capable,
    preferred_models,
)
from config import cfg

_log = logging.getLogger("clicky.ollama")


# Model architectures current Ollama builds can no longer load. Pulling one
# succeeds, so `ollama list` shows it as installed, and it only fails at the
# moment a request tries to load it — as an opaque HTTP 500.
_DEAD_ARCHITECTURES = ("mllama",)


def _explain_ollama_error(status: int, body: str, model: str, had_images: bool) -> str:
    """Turn an Ollama HTTP error into something a user can act on."""
    low = (body or "").lower()
    pull = f"ollama pull {DEFAULT_VISION_MODEL}"

    # llama3.2-vision and friends are built on 'mllama', dropped by newer
    # Ollama. The server logs 'unknown model architecture', llama-server dies,
    # and the client only sees a bare HTTP 500.
    if any(a in low for a in _DEAD_ARCHITECTURES) or "unknown model architecture" in low:
        return (
            "'{m}' cannot be loaded by your version of Ollama. Its model "
            "architecture was dropped in a newer Ollama release, so it fails "
            "even though `ollama list` still shows it installed.\n\n"
            "Switch to a supported vision model:\n"
            "    {pull}\n\n"
            "then choose it under Tray -> Ollama -> Vision model."
        ).format(m=model, pull=pull)

    # A model newer than the installed Ollama understands.
    if "newer version of ollama" in low or "requires a newer" in low:
        return (
            "'{m}' needs a newer version of Ollama than the one installed. "
            "Update Ollama from ollama.com/download, then try again."
        ).format(m=model)

    # Sending images to a text-only model: Ollama answers 400 with this text.
    if "does not support multimodal" in low or "multimodal data provided" in low:
        return (
            "'{m}' is a text-only model, but Clicky sends a screenshot with "
            "every question.\n\n"
            "Choose a vision model under Tray -> Ollama -> Vision model, or "
            "pull one:\n"
            "    {pull}"
        ).format(m=model, pull=pull)

    if "out of memory" in low or "insufficient memory" in low:
        return (
            "Ollama ran out of memory loading '{m}'. Try a smaller model "
            "({d} needs about 3 GB) or close other applications."
        ).format(m=model, d=DEFAULT_VISION_MODEL)

    snippet = (body or "").strip()[:300] or "(no detail returned)"
    hint = (
        "\n\nThis request included a screenshot. If the model is text-only, "
        "choose a vision model under Tray -> Ollama."
        if had_images else ""
    )
    return "Ollama returned HTTP {s} for '{m}': {b}{h}".format(
        s=status, m=model, b=snippet, h=hint
    )


def _installed_match(name: str, installed: List[str]) -> str | None:
    """Find `name` among installed tags, tolerating a missing ':latest'."""
    if name in installed:
        return name
    base = name.split(":", 1)[0]
    if ":" not in name:
        for n in installed:
            if n.split(":", 1)[0] == base:
                return n
    return None


class OllamaProvider(BaseLLMProvider):
    """
    Streams responses from a local Ollama instance.

    Auto-picks the right model per call:
        • Screenshots present → cfg.get_ollama_model("vision")
        • No screenshots      → cfg.get_ollama_model("text")

    A caller may still pass an explicit `model=` to override that choice
    (e.g. the panel's manual model dropdown).
    """

    _TAGS_TTL_S = 30.0

    def __init__(self):
        self._base = cfg.ollama_host.rstrip("/")
        # Kept for backward compat with old code paths reading self._model
        self._model = cfg.ollama_model
        self._client = httpx.AsyncClient(
            timeout=120,
            limits=httpx.Limits(max_keepalive_connections=4, max_connections=8)
        )
        self._tags_cache: tuple[float, List[str]] = (0.0, [])
        self._caps_cache: dict[str, list[str]] = {}

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self._client.aclose()

    def _pick_model(self, has_screenshots: bool) -> str:
        return cfg.get_ollama_model("vision" if has_screenshots else "text")

    # ── What is actually installed ───────────────────────────────────────────

    async def _installed(self) -> List[str]:
        ts, names = self._tags_cache
        if names and time.monotonic() - ts < self._TAGS_TTL_S:
            return names
        names = await self.list_models()
        if names:
            self._tags_cache = (time.monotonic(), names)
        return names

    async def _capabilities(self, model: str) -> list[str]:
        """Ollama's own report of what a model can do (vision, thinking, ...).

        Cached per model. Empty if the server is old or the call fails — callers
        treat "unknown" as "don't assume".
        """
        if model in self._caps_cache:
            return self._caps_cache[model]
        caps: list[str] = []
        try:
            r = await self._client.post(
                f"{self._base}/api/show", json={"model": model}, timeout=15,
            )
            if r.status_code == 200:
                caps = list(r.json().get("capabilities") or [])
        except Exception:
            pass
        self._caps_cache[model] = caps
        return caps

    async def _resolve_model(self, chosen: str, has_images: bool) -> str:
        """Make sure the model we send actually exists and can load.

        Clicky's default has changed over time, and `ollama pull` happily
        installs models that can no longer load (llama3.2-vision). Anyone who
        upgrades with an old default configured — or whose default was never
        pulled — used to hit a hard error on their first question. If the
        configured model is one Clicky itself recommended (or is known dead),
        use the best working model they already have instead.

        A model the user chose deliberately is never swapped out from under them.
        """
        installed = await self._installed()
        if not installed:
            return chosen            # server unreachable: let the request report it

        present = _installed_match(chosen, installed)
        if present and not is_dead_model(present):
            return present
        if not (is_dead_model(chosen) or is_shipped_default(chosen)):
            return chosen            # user's own choice — leave it alone

        for cand in preferred_models(has_images):
            hit = _installed_match(cand, installed)
            if hit and not is_dead_model(hit):
                _log.info("model %r unavailable — using installed %r instead", chosen, hit)
                return hit
        return chosen

    # ── Chat ─────────────────────────────────────────────────────────────────

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
        chosen = await self._resolve_model(chosen, bool(screenshots_b64))

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Ollama passes images as base64 strings inside the message
        user_msg: dict = {"role": "user", "content": user_text}
        if screenshots_b64:
            user_msg["images"] = screenshots_b64
        messages.append(user_msg)

        options: dict = {
            "num_predict": 1024,
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

        # Newer model families (Qwen3.5, Gemma 4, ...) think before answering by
        # default. Clicky only reads the answer, so the user would sit through
        # all of that reasoning in silence: qwen3.5:4b took over a minute to
        # produce its first word, versus 2.0s with thinking off. Thinking also
        # spends the num_predict budget. Only sent to models that report the
        # capability, so older models and servers never see the field.
        if "thinking" in await self._capabilities(chosen):
            payload["think"] = False

        for attempt in range(2):
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
                    # An Ollama that rejects `think` — retry once without it.
                    if attempt == 0 and "think" in payload and "think" in body.lower():
                        del payload["think"]
                        continue
                    raise RuntimeError(_explain_ollama_error(
                        response.status_code, body, chosen, bool(screenshots_b64)
                    ))

                got_text = False
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise RuntimeError(_explain_ollama_error(
                            500, str(data["error"]), chosen, bool(screenshots_b64)
                        ))
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        got_text = True
                        yield chunk
                    if data.get("done"):
                        break
                if not got_text:
                    raise RuntimeError(
                        f"'{chosen}' returned an empty reply. If it is a reasoning "
                        f"model it may have spent its whole budget thinking — try "
                        f"a different model under Tray -> Ollama."
                    )
                return

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

        Asks Ollama what each model can actually do (its `capabilities` report)
        rather than guessing from the name — a name heuristic classes
        qwen3.5 and gemma4, both multimodal, as text-only. Models that can't be
        loaded by this Ollama (dead architectures) and embedding-only models are
        left out, since picking one only produces errors. Falls back to the name
        heuristic for a server too old to report capabilities.
        """
        names = await self.list_models()
        caps_list = await asyncio.gather(*(self._capabilities(n) for n in names))
        out: dict[str, list[str]] = {"vision": [], "text": []}
        for n, caps in zip(names, caps_list):
            if is_dead_model(n):
                continue
            if caps:
                if "completion" not in caps:
                    continue             # embedding-only
                (out["vision"] if "vision" in caps else out["text"]).append(n)
            else:
                (out["vision"] if is_vision_capable(n) else out["text"]).append(n)
        out["vision"].sort()
        out["text"].sort()
        return out
