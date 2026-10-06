import re
from typing import AsyncIterator, List

import anthropic

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

# "The best combination of speed and intelligence" in Anthropic's lineup, and
# the newest Sonnet. (Clicky previously defaulted to claude-sonnet-4-6, which
# is now a legacy model.)
DEFAULT_MODEL = "claude-sonnet-5-5"

MAX_TOKENS = 1024
# Thinking counts toward max_tokens even when thinking output is not returned.
# A limit sized for a plain answer can be spent entirely on thinking, leaving
# an empty reply, so models that think get more room.
THINKING_MAX_TOKENS = 2048

# Models that accept the top-level `output_config.effort` parameter, per
# Anthropic's effort documentation. Haiku 4.5 and the 4.5-and-earlier Sonnets
# do not — sending it to them is a 400.
_EFFORT_MODELS = re.compile(
    r"^claude-("
    r"(fable|mythos)-"
    r"|opus-(5|4-[5-8])"
    r"|sonnet-(5|4-6)"
    r")"
)


def _supports_effort(model: str) -> bool:
    return _EFFORT_MODELS.match(model) is not None


def _friendly_error(e: Exception, model: str) -> str | None:
    if isinstance(e, anthropic.NotFoundError):
        return (
            f"Anthropic doesn't offer '{model}' — it may have been retired. "
            f"Pick another model in the panel."
        )
    if isinstance(e, anthropic.AuthenticationError):
        return "Anthropic rejected your API key. Check it under Tray → Setup & Diagnostics → API Keys."
    if isinstance(e, anthropic.PermissionDeniedError):
        return f"Your Anthropic account can't use '{model}'. Pick another model in the panel."
    return None


class ClaudeProvider(BaseLLMProvider):

    def __init__(self, client=None):
        self._client = client or anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or DEFAULT_MODEL

        messages = []

        # Inject conversation history
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Build current user message with optional screenshots
        content: list = []
        for i, img_b64 in enumerate(screenshots_b64):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_b64,
                },
            })

        content.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": content})

        kwargs: dict = dict(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        if _supports_effort(model):
            # Newer models default to `high` effort with adaptive thinking, built
            # for hard multi-step work; Anthropic's guidance for chat and
            # latency-sensitive use is medium or low. Measured live: on simple
            # screen questions it made no difference (the models did not think at
            # all, ~1.1-1.6s either way), so this is insurance for harder
            # questions rather than a speed-up — and it is accepted by every model
            # in _EFFORT_MODELS (Haiku 4.5 returns 400, hence the allow-list).
            kwargs["output_config"] = {"effort": "low"}
            kwargs["max_tokens"] = THINKING_MAX_TOKENS

        got_text = False
        stop_reason = None
        for attempt in range(2):
            try:
                async with self._client.messages.stream(**kwargs) as stream:
                    async for text in stream.text_stream:
                        got_text = True
                        yield text
                    final = await stream.get_final_message()
                    stop_reason = final.stop_reason
                break
            except anthropic.BadRequestError as e:
                # If a model rejects effort, take its word for it and retry
                # without rather than failing the user's question.
                low = str(e).lower()
                if (attempt == 0 and not got_text and "output_config" in kwargs
                        and ("effort" in low or "output_config" in low)):
                    del kwargs["output_config"]
                    kwargs["max_tokens"] = MAX_TOKENS
                    continue
                raise
            except Exception as e:
                friendly = _friendly_error(e, model)
                if friendly:
                    raise RuntimeError(friendly) from e
                raise

        if not got_text:
            # Thinking can consume the whole token budget and leave no answer.
            if stop_reason == "max_tokens":
                raise RuntimeError(
                    f"'{model}' used its whole budget thinking and produced no answer. "
                    f"Try again, or pick a faster model such as Claude Haiku."
                )
            raise RuntimeError(f"'{model}' returned an empty reply (stop reason: {stop_reason}).")

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
