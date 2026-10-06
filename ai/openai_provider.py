import re
from typing import AsyncIterator, List

import openai
from openai import AsyncOpenAI

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

# The "Sol" tier is OpenAI's balanced one, priced like the GPT-4o Clicky used
# before. Deliberately gpt-6-sol rather than the newer gpt-6.1-sol: measured
# time-to-first-word over six runs was 1.3s vs 3.1s median, and for a voice
# assistant that wait is the product. 6.1-sol stays one click away in the picker;
# gpt-6-luna (1.1s, ~20x cheaper) is the budget tier.
DEFAULT_MODEL = "gpt-6-sol"

MAX_TOKENS = 1024
# Reasoning models count their hidden thinking against the same limit as the
# visible answer. With the limit too tight they can finish thinking and have
# nothing left to say, which reaches the user as a blank reply (or, on
# non-streaming calls, as "Could not finish the message because max_tokens or
# model output limit was reached").
REASONING_MAX_TOKENS = 2048


def _is_reasoning_model(model: str) -> bool:
    """GPT-5 and newer, plus the o-series, all think before answering."""
    if model == "chat-latest" or model.startswith("chatgpt-"):
        return False
    m = re.match(r"gpt-(\d+)", model)
    if m:
        return int(m.group(1)) >= 5
    return re.match(r"o\d", model) is not None


def _friendly_error(e: Exception, model: str) -> str | None:
    """Plain-language version of the API errors people actually hit."""
    if isinstance(e, openai.NotFoundError):
        return (
            f"OpenAI no longer serves '{model}' — it has probably been retired. "
            f"Pick another model in the panel."
        )
    if isinstance(e, openai.PermissionDeniedError):
        return (
            f"Your OpenAI account isn't allowed to use '{model}'. Some newer models "
            f"need organization verification at platform.openai.com. Pick another "
            f"model in the panel."
        )
    if isinstance(e, openai.AuthenticationError):
        return "OpenAI rejected your API key. Check it under Tray → Setup & Diagnostics → API Keys."
    if isinstance(e, openai.RateLimitError):
        low = str(e).lower()
        if "quota" in low or "billing" in low or "credit" in low:
            return "Your OpenAI account is out of credit. Add billing at platform.openai.com."
    return None


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):
        # OPENAI_BASE_URL turns this into a generic OpenAI-compatible client:
        # DeepSeek (https://api.deepseek.com), Alibaba DashScope/Qwen,
        # SiliconFlow, OpenRouter, etc. Set OPENAI_DEFAULT_MODEL to match.
        kwargs = {"api_key": cfg.openai_api_key}
        if cfg.openai_base_url:
            kwargs["base_url"] = cfg.openai_base_url
        self._client = AsyncOpenAI(**kwargs)
        self._custom_server = bool(cfg.openai_base_url)

    def _request_kwargs(self, model: str, messages: list) -> dict:
        kwargs: dict = dict(model=model, messages=messages, stream=True)
        if self._custom_server:
            # Third-party servers mostly still speak the original parameter.
            kwargs["max_tokens"] = MAX_TOKENS
            return kwargs

        # api.openai.com: every GPT-5/6 and o-series model rejects `max_tokens`
        # with HTTP 400 ("Unsupported parameter: 'max_tokens' ... Use
        # 'max_completion_tokens' instead"), and older models accept the new
        # name too, so it is the right parameter across the board.
        reasoning = _is_reasoning_model(model)
        kwargs["max_completion_tokens"] = REASONING_MAX_TOKENS if reasoning else MAX_TOKENS
        if reasoning:
            # "low" is the one value every reasoning model accepts ("minimal"
            # is gpt-5 only, "none" is 5.1+ only). It also cuts time to the
            # first word substantially: gpt-5 went from 6.8s to 2.7s.
            kwargs["reasoning_effort"] = "low"
        return kwargs

    @staticmethod
    def _adapt(kwargs: dict, error_text: str) -> bool:
        """Adjust a rejected request in place. True if something changed.

        Parameter support differs per model and server and keeps changing, so
        rather than trusting a hard-coded table, take the server's word for it
        and retry once with the offending parameter swapped or removed.
        """
        low = error_text.lower()
        if "reasoning_effort" in low and "reasoning_effort" in kwargs:
            del kwargs["reasoning_effort"]
            return True
        if "max_completion_tokens" in low and "max_completion_tokens" in kwargs:
            kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
            return True
        if "max_tokens" in low and "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            return True
        return False

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or cfg.openai_default_model or DEFAULT_MODEL

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

        kwargs = self._request_kwargs(model, messages)

        stream = None
        for attempt in range(3):
            try:
                stream = await self._client.chat.completions.create(**kwargs)
                break
            except openai.BadRequestError as e:
                if attempt < 2 and self._adapt(kwargs, str(e)):
                    continue
                raise
            except Exception as e:
                friendly = _friendly_error(e, model)
                if friendly:
                    raise RuntimeError(friendly) from e
                raise

        got_text = False
        finish = None
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.delta.content:
                got_text = True
                yield choice.delta.content
            if choice.finish_reason:
                finish = choice.finish_reason

        if not got_text:
            # A reasoning model that spent its whole budget thinking used to
            # produce silence. Say so instead.
            if finish == "length":
                raise RuntimeError(
                    f"'{model}' ran out of room while thinking and produced no answer. "
                    f"Try again, or pick a faster model such as gpt-6-luna."
                )
            raise RuntimeError(f"'{model}' returned an empty reply (finish reason: {finish}).")

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
