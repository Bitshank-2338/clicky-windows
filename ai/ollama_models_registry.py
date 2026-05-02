"""
Curated registry of Ollama models recommended for Clicky, plus heuristics
for classifying installed models as vision-capable or text-only.

Why curated:
    Ollama's library is huge. Most students don't know which models work
    well for screen-aware AI tutoring. This file is a quality-tested
    shortlist that gets surfaced in the tray menu under "Pull recommended".
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaRec:
    name: str           # exact pull tag, e.g. "qwen2-vl:7b"
    label: str          # human-friendly display name
    size: str           # rough download size, for the tooltip
    use_for: str        # "vision" | "text"
    blurb: str          # one-line description shown in the menu


# ─── Vision models (best for screen-aware queries + grid-pointing) ────────────

RECOMMENDED_VISION: list[OllamaRec] = [
    OllamaRec(
        name="qwen2-vl:7b",
        label="Qwen2-VL 7B",
        size="4.5 GB",
        use_for="vision",
        blurb="Best UI/OCR accuracy — recommended for pointing",
    ),
    OllamaRec(
        name="llama3.2-vision:11b",
        label="Llama 3.2 Vision 11B",
        size="7.9 GB",
        use_for="vision",
        blurb="Meta's flagship vision model — solid all-rounder",
    ),
    OllamaRec(
        name="llava:7b",
        label="LLaVA 7B",
        size="4.7 GB",
        use_for="vision",
        blurb="Lightweight vision fallback — runs on weaker GPUs",
    ),
    OllamaRec(
        name="minicpm-v",
        label="MiniCPM-V 8B",
        size="5.5 GB",
        use_for="vision",
        blurb="Tiny + sharp — best for low-RAM laptops",
    ),
    OllamaRec(
        name="bakllava",
        label="BakLLaVA 7B",
        size="4.4 GB",
        use_for="vision",
        blurb="LLaVA fine-tune on Mistral — fast inference",
    ),
]


# ─── Text models (Code Mode, journal Q&A, no-screenshot replies) ──────────────

RECOMMENDED_TEXT: list[OllamaRec] = [
    OllamaRec(
        name="qwen2.5-coder:7b",
        label="Qwen 2.5 Coder 7B",
        size="4.7 GB",
        use_for="text",
        blurb="Best for Code Mode — strong code reasoning",
    ),
    OllamaRec(
        name="llama3.2:3b",
        label="Llama 3.2 3B",
        size="2.0 GB",
        use_for="text",
        blurb="Fastest text model — great default",
    ),
    OllamaRec(
        name="mistral:7b",
        label="Mistral 7B",
        size="4.1 GB",
        use_for="text",
        blurb="Reliable general-purpose chat",
    ),
    OllamaRec(
        name="phi3.5",
        label="Phi 3.5 Mini",
        size="2.2 GB",
        use_for="text",
        blurb="Microsoft's compact reasoner",
    ),
]


# ─── Vision capability heuristic ──────────────────────────────────────────────

_VISION_KEYWORDS = (
    "vision", "vl", "llava", "bakllava", "minicpm-v", "moondream",
    "cogvlm", "internvl", "qwen-vl", "qwen2-vl",
    "gemma3",   # Gemma 3 is multimodal
    "pixtral",
)


def is_vision_capable(model_name: str) -> bool:
    """Best-effort detection of whether an Ollama model supports images.

    Ollama's /api/tags doesn't reliably expose multimodal support, so we
    fall back to substring matching against well-known vision model names.
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
