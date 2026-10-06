"""
Curated registry of Ollama models recommended for Clicky, plus heuristics
for classifying installed models as vision-capable or text-only.

Why curated:
    Ollama's library is huge. Most students don't know which models work
    well for screen-aware AI tutoring. This file is a quality-tested
    shortlist that gets surfaced in the tray menu under "Pull recommended".

Every entry here was checked against ollama.com's registry (the tag exists and
carries an image projector), and the recommended defaults were benchmarked on a
4 GB laptop GPU against a realistic screen — see DEFAULT_VISION_MODEL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaRec:
    name: str           # exact pull tag, e.g. "qwen3.5:4b"
    label: str          # human-friendly display name
    size: str           # rough download size, for the tooltip
    use_for: str        # "vision" | "text"
    blurb: str          # one-line description shown in the menu


# ─── The default ──────────────────────────────────────────────────────────────

# qwen2.5vl:3b — chosen by measurement, and it beat the newer families.
#
# Benchmarked on a 4 GB laptop GPU and on CPU only, using Clicky's real prompt:
#
#                   screen reading   web-search     CPU-only      notes
#                   (easy + hard)    grounding      first word
#   qwen2.5vl:3b        15/16          5/6             2.2 s     concise, admits when
#                                                                results lack the answer
#   qwen2.5vl:7b        10/10 (hard)   6/6          4-12 s (4GB   best accuracy measured;
#                                                    GPU, mostly   slower on weak hardware,
#                                                    CPU offload)  so an upgrade, not default
#   qwen3.5:4b          16/16          4/6            ~82   s     thinks by default; gets
#                                                                distracted by the screenshot
#   qwen3.5:2b          15/16          5/6            ~70   s     rambles, invented a
#                                                                number (hallucination)
#   qwen3-vl:2b         16/16          2/6             5.9  s     CANNOT disable thinking:
#                                                                blank replies at 300 tok
#   gemma3:4b             ?            2/6            ~67   s     fires [POINT] tags at
#                                                                non-screen questions
#   minicpm-v4.6:1b      8/10            -             37   s     weak and slow
#   llava:7b              3/6          4/6               -       hallucinates screen text
#
# The newer families read screens a little better but are 30x slower on the
# CPU-only laptops many students use, or ignore the instruction to skip
# thinking, or fail to answer from supplied search results. A model that
# answers well and quickly everywhere beats one that is best on a good GPU.
# Re-run those benchmarks before changing this.
#
# One model serves both slots: the panel sends its selected model for every
# question, so the old separate text model (llama3.2:3b) was a 2 GB download
# that almost never ran.
DEFAULT_VISION_MODEL = "qwen2.5vl:3b"
DEFAULT_TEXT_MODEL = "qwen2.5vl:3b"


# ─── Vision models (best for screen-aware queries + grid-pointing) ────────────

RECOMMENDED_VISION: list[OllamaRec] = [
    OllamaRec(
        name="qwen2.5vl:3b",
        label="Qwen2.5-VL 3B",
        size="3.2 GB",
        use_for="vision",
        blurb="The default — accurate, concise, fast even without a GPU",
    ),
    OllamaRec(
        name="qwen2.5vl:7b",
        label="Qwen2.5-VL 7B",
        size="6 GB",
        use_for="vision",
        blurb="Most accurate we tested (6/6 on web-search answers) — best with 8 GB+ graphics",
    ),
    OllamaRec(
        name="qwen3.5:4b",
        label="Qwen3.5 4B",
        size="3.3 GB",
        use_for="vision",
        blurb="Newest — reads screens very well, but needs a GPU (very slow on CPU)",
    ),
    OllamaRec(
        name="llava:7b",
        label="LLaVA 7B",
        size="4.7 GB",
        use_for="vision",
        blurb="Older fallback — misreads small text more often",
    ),
]


# ─── Text models (Code Mode, journal Q&A, no-screenshot replies) ──────────────

RECOMMENDED_TEXT: list[OllamaRec] = [
    OllamaRec(
        name="qwen2.5vl:3b",
        label="Qwen2.5-VL 3B",
        size="3.2 GB",
        use_for="text",
        blurb="The default — same download as the vision model",
    ),
    OllamaRec(
        name="llama3.2:3b",
        label="Llama 3.2 3B",
        size="2.0 GB",
        use_for="text",
        blurb="Fastest text-only model",
    ),
    OllamaRec(
        name="qwen2.5-coder:7b",
        label="Qwen 2.5 Coder 7B",
        size="4.7 GB",
        use_for="text",
        blurb="Best for Code Mode — strong code reasoning",
    ),
    OllamaRec(
        name="mistral:7b",
        label="Mistral 7B",
        size="4.1 GB",
        use_for="text",
        blurb="Reliable general-purpose chat",
    ),
]


# ─── Which installed model to use when the configured one isn't usable ────────

# Models Clicky has itself defaulted to or recommended, in any release. A user
# who still has one of these configured did not choose it deliberately, so it is
# safe to swap for something that works; a model they picked themselves is not.
_SHIPPED_DEFAULTS = {
    "llama3.2-vision", "llama3.2-vision:latest", "llama3.2-vision:11b",
    "qwen2-vl:7b", "qwen2.5vl:3b", "qwen2.5vl:7b",
    "llama3.2:3b", "llama3.2", "llama3.2:latest",
}

# Order of preference among what is installed: the best working screen model
# first, ending with older fallbacks. Follows the benchmark in DEFAULT_VISION_MODEL;
# the qwen3.5 / qwen3-vl / gemma families are deliberately NOT here — they lost
# on CPU speed or reliability, so they are never picked automatically.
_PREFERRED_VISION = [
    "qwen2.5vl:3b", "qwen2.5vl:7b",
    "qwen3.5:4b",
    "llava:7b", "llava", "moondream",
]
_PREFERRED_TEXT = [
    "qwen2.5vl:3b", "llama3.2:3b", "llama3.2",
    "qwen2.5-coder:7b", "mistral:7b", "phi3.5",
]

# Pulling these succeeds and `ollama list` shows them, but current Ollama cannot
# load them (their 'mllama' architecture was dropped), so every request 500s.
_DEAD_PREFIXES = ("llama3.2-vision",)


def is_dead_model(name: str) -> bool:
    n = (name or "").lower()
    return any(n.startswith(p) for p in _DEAD_PREFIXES)


def is_shipped_default(name: str) -> bool:
    return (name or "").lower() in _SHIPPED_DEFAULTS


def preferred_models(has_images: bool) -> list[str]:
    """Fallback candidates, best first. Text questions can use any model, so
    the vision list follows the text list rather than being excluded."""
    if has_images:
        return list(_PREFERRED_VISION)
    return list(_PREFERRED_TEXT) + list(_PREFERRED_VISION)


# ─── Vision capability heuristic ──────────────────────────────────────────────
#
# Only a FALLBACK. Ollama reports each model's real capabilities through
# /api/show, and OllamaProvider.list_models_classified() uses that. This name
# matching exists for servers too old to report them — and it has to be kept
# current by hand, which is exactly why it is no longer the primary mechanism:
# it classed qwen3.5 and gemma4, both multimodal, as text-only.

_VISION_KEYWORDS = (
    "vision", "llava", "bakllava", "minicpm-v", "moondream", "cogvlm",
    "internvl", "smolvlm", "pixtral", "medgemma",
    "vl:", "-vl", "qwen2.5vl",
    "qwen3.5", "qwen3.6", "qwen3.8", "gemma3", "gemma4", "mistral-small3",
)


def is_vision_capable(model_name: str) -> bool:
    """Best-effort name-based guess at whether an Ollama model supports images.

    Prefer the capabilities Ollama reports; see OllamaProvider.
    """
    n = (model_name or "").lower()
    return any(kw in n for kw in _VISION_KEYWORDS)


# ─── Pull helper ──────────────────────────────────────────────────────────────

async def pull_model(name: str, host: str, on_progress=None) -> bool:
    """Stream `ollama pull <name>` over the HTTP API.

    Returns True on success. on_progress (optional) is called with status
    strings as the download advances ("pulling manifest", "verifying", etc.).
    """
    import httpx

    url = host.rstrip("/") + "/api/pull"
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", url, json={"name": name, "stream": True},
            ) as r:
                if r.status_code >= 400:
                    return False
                import json as _json
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        msg = _json.loads(line)
                    except Exception:
                        continue
                    if on_progress:
                        try:
                            on_progress(msg.get("status", ""))
                        except Exception:
                            pass
                    if msg.get("error"):
                        return False
                return True
    except Exception:
        return False
