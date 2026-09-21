"""Wraps a cloud LLM provider. If it fails before producing any text
(503 overload, 429 quota, 404, network down), the same request is retried
on local Ollama. Disable with CLICKY_FALLBACK_OLLAMA=0."""

import logging
import os
from typing import AsyncIterator, Callable, List

from ai.base_provider import BaseLLMProvider, Message

_log = logging.getLogger("clicky.fallback")


class FallbackLLM(BaseLLMProvider):

    def __init__(self, primary: BaseLLMProvider, make_fallback: Callable[[], BaseLLMProvider],
                 name: str = "cloud", notify: Callable[[str], None] | None = None):
        self._primary = primary
        self._make_fallback = make_fallback
        self._name = name
        self._notify = notify

    def __getattr__(self, item):
        return getattr(self._primary, item)

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        yielded = False
        try:
            async for chunk in self._primary.stream_response(
                user_text=user_text, screenshots_b64=screenshots_b64,
                history=history, system_prompt=system_prompt, model=model,
            ):
                yielded = True
                yield chunk
            return
        except Exception as e:
            if yielded:
                raise   # partial answer already shown; don't mix models
            _log.warning("%s failed (%s); falling back to Ollama", self._name, type(e).__name__)
        if self._notify:
            try:
                self._notify(f"({self._name} unavailable, using local model)\n")
            except Exception:
                pass
        fb = self._make_fallback()
        async for chunk in fb.stream_response(
            user_text=user_text, screenshots_b64=screenshots_b64,
            history=history, system_prompt=system_prompt, model=None,
        ):
            yield chunk

    async def health_check(self) -> bool:
        return await self._primary.health_check()
