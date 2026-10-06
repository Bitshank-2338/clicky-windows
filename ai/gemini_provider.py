"""
Google Gemini provider — uses the REST SSE streaming API directly (no extra deps).
Default model: gemini-3.6-flash — see model_registry.py for why it is not the
newest Flash.
"""

import asyncio
import json
import logging
import re
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

_log = logging.getLogger("clicky.gemini")

DEFAULT_MODEL = "gemini-3.6-flash"
STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
)

# New Gemini releases get overloaded: gemini-3.8-flash answered HTTP 503 "This
# model is currently experiencing high demand" on half of a live test's
# requests. When the chosen model stays overloaded after one retry, answer with
# a sibling instead of showing the user an error — a voice assistant that goes
# silent is worse than one that quietly uses a slightly different model.
_OVERLOAD_FALLBACKS = ("gemini-3.6-flash", "gemini-3.5-flash-lite")
_OVERLOAD_RETRY_DELAY_S = 1.5

MAX_OUTPUT_TOKENS = 1024
# On Gemini 3 the output limit includes the model's thinking tokens, and
# thinking cannot be turned off. A limit sized for a plain answer can be spent
# entirely on thinking and return nothing, so these models get more room.
GEMINI3_MAX_OUTPUT_TOKENS = 2048


class _Overloaded(Exception):
    """The model answered 503/UNAVAILABLE before producing any text."""


def _is_gemini3(model: str) -> bool:
    return re.match(r"^gemini-3", model) is not None


def _error_message(body_text: str) -> str:
    try:
        err = json.loads(body_text).get("error", {})
        return str(err.get("message") or body_text)
    except Exception:
        return body_text


def _friendly_error(status: int, message: str, model: str) -> str:
    low = message.lower()
    if "api key not valid" in low or "api_key_invalid" in low:
        return "Google rejected your API key. Check it under Tray → Setup & Diagnostics → API Keys."
    if status == 404:
        return (
            f"Google doesn't offer '{model}' (or your key can't see it). "
            f"Pick another model in the panel."
        )
    if status == 503 or "high demand" in low or "unavailable" in low:
        return (
            f"Gemini is overloaded right now ('{model}' and its fallbacks are all "
            f"busy). Try again in a moment, or pick another model in the panel."
        )
    if status == 429 or "quota" in low or "resource_exhausted" in low:
        return (
            "Gemini quota reached for this key. Free-tier limits are per-minute and "
            "per-day — wait a bit, switch to a lighter model, or enable billing."
        )
    if status == 403:
        return f"Google refused the request for '{model}': {message[:160]}"
    return f"Gemini returned HTTP {status} for '{model}': {message[:200]}"


class GeminiProvider(BaseLLMProvider):

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._api_key = cfg.google_api_key
        self._transport = transport     # injectable for tests

    def _headers(self) -> dict:
        # The key travels in a header, never in the URL. httpx quotes the full
        # URL in its error text, which reaches the tray toast and clicky.log —
        # with the key in the query string, every failed request leaked it.
        return {"x-goog-api-key": self._api_key or "", "Content-Type": "application/json"}

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

        candidates = [model] + [m for m in _OVERLOAD_FALLBACKS if m != model]
        for i, candidate in enumerate(candidates):
            try:
                async for text in self._stream_model(candidate, contents, system_prompt):
                    yield text
                return
            except _Overloaded:
                nxt = candidates[i + 1] if i + 1 < len(candidates) else None
                if nxt:
                    _log.warning("%s is overloaded — answering with %s instead", candidate, nxt)
                    continue
                raise RuntimeError(_friendly_error(503, "high demand", model))

    async def _stream_model(self, model: str, contents: list, system_prompt: str) -> AsyncIterator[str]:
        if _is_gemini3(model):
            gen_config: dict = {
                "maxOutputTokens": GEMINI3_MAX_OUTPUT_TOKENS,
                # "low" is valid on every 3.x model (some also offer "minimal",
                # others start at "low"); verified live against 3.1-3.8. Default
                # thinking is "medium". Temperature is left at Google's default:
                # it recommends against lowering it on Gemini 3.
                "thinkingConfig": {"thinkingLevel": "low"},
            }
        else:
            gen_config = {"maxOutputTokens": MAX_OUTPUT_TOKENS, "temperature": 0.7}

        body = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": gen_config,
        }
        url = f"{STREAM_URL.format(model=model)}?alt=sse"

        got_text = False
        finish = None
        block_reason = None
        overload_retried = False
        thinking_retried = False

        while True:
            async with httpx.AsyncClient(timeout=120, transport=self._transport) as client:
                async with client.stream("POST", url, json=body, headers=self._headers()) as resp:
                    if resp.status_code >= 400:
                        raw = (await resp.aread()).decode("utf-8", "replace")
                        message = _error_message(raw)
                        low = message.lower()

                        # Overloaded: one short retry, then let the caller fall back.
                        if resp.status_code == 503 or "high demand" in low:
                            if not overload_retried:
                                overload_retried = True
                                await asyncio.sleep(_OVERLOAD_RETRY_DELAY_S)
                                continue
                            raise _Overloaded()

                        # Thinking parameters differ between model generations
                        # and I can't enumerate them all — if the server objects
                        # to ours, retry once without rather than fail the question.
                        if (not thinking_retried and "thinkingConfig" in gen_config
                                and "thinking" in low):
                            thinking_retried = True
                            del gen_config["thinkingConfig"]
                            continue
                        raise RuntimeError(_friendly_error(resp.status_code, message, model))

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
                        pf = obj.get("promptFeedback") or {}
                        if pf.get("blockReason"):
                            block_reason = pf["blockReason"]
                        for cand in obj.get("candidates", []):
                            if cand.get("finishReason"):
                                finish = cand["finishReason"]
                            for part in cand.get("content", {}).get("parts", []):
                                if part.get("thought"):
                                    continue        # never speak thought summaries
                                text = part.get("text", "")
                                if text:
                                    got_text = True
                                    yield text
            break

        if not got_text:
            if block_reason:
                raise RuntimeError(f"Gemini declined to answer (blocked: {block_reason}).")
            if finish == "MAX_TOKENS":
                raise RuntimeError(
                    f"'{model}' used its whole budget thinking and produced no answer. "
                    f"Try again, or pick a lighter model such as a Flash-Lite."
                )
            raise RuntimeError(f"'{model}' returned an empty reply (finish reason: {finish}).")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5, transport=self._transport) as client:
                r = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers=self._headers(),
                )
                return r.status_code == 200
        except Exception:
            return False
