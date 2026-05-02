"""
Live model discovery + caching for Claude, OpenAI, and Gemini.

Each provider exposes a "list models" endpoint we hit on demand:
  • Anthropic:  GET /v1/models                    (key in x-api-key)
  • OpenAI:     GET /v1/models                    (key in Authorization)
  • Gemini:     GET /v1beta/models?key=...        (key in query)

Cached per-provider to %LOCALAPPDATA%\\Clicky\\models_<provider>.json with a
30-day TTL — long enough that you don't refetch constantly, short enough
that new model releases land within a month without manual refresh.

GitHub Copilot has its own (separate) implementation in github_copilot_provider.py
because Copilot's flow is more complex (token exchange + per-seat filtering).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx

from config import cfg


CACHE_TTL_SECONDS = 30 * 24 * 60 * 60   # 30 days


# Curated fallback lists — used when the live endpoint is unreachable AND
# the on-disk cache is empty. Reasonable defaults so Clicky still works
# offline / on first run before refresh completes.
_FALLBACKS: dict[str, list[dict]] = {
    "claude": [
        {"id": "claude-sonnet-4-6",          "label": "Claude Sonnet 4.6", "vision": True},
        {"id": "claude-opus-4-7",            "label": "Claude Opus 4.7",   "vision": True},
        {"id": "claude-haiku-4-5-20251001",  "label": "Claude Haiku 4.5",  "vision": True},
    ],
    "openai": [
        {"id": "gpt-4o",        "label": "GPT-4o",       "vision": True},
        {"id": "gpt-4o-mini",   "label": "GPT-4o mini",  "vision": True},
        {"id": "gpt-4-turbo",   "label": "GPT-4 Turbo",  "vision": True},
    ],
    "gemini": [
        {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "vision": True},
        {"id": "gemini-2.5-pro",   "label": "Gemini 2.5 Pro",   "vision": True},
        {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash", "vision": True},
    ],
}


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Clicky"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(provider: str) -> Path:
    return _data_dir() / f"models_{provider}.json"


# ─── Per-provider live fetchers ───────────────────────────────────────────────

async def _fetch_claude() -> list[dict]:
    if not cfg.anthropic_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": cfg.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
        )
    r.raise_for_status()
    data = r.json().get("data", [])
    out = []
    for m in data:
        mid = m.get("id") or m.get("name")
        if not mid:
            continue
        # All current Claude models are vision-capable; future ones likely too.
        out.append({
            "id": mid,
            "label": m.get("display_name") or mid,
            "vision": True,
        })
    # Newest first (Anthropic returns newest first already, but be defensive)
    out.sort(key=lambda m: m["id"], reverse=True)
    return out


async def _fetch_openai() -> list[dict]:
    if not cfg.openai_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
        )
    r.raise_for_status()
    data = r.json().get("data", [])
    out = []
    # Filter to chat-completion-capable models. OpenAI's /v1/models returns
    # everything (embeddings, TTS, image-gen, audio, etc.) so we whitelist by
    # known prefixes. Vision flag is true for the gpt-4o family + o3-vision.
    chat_prefixes = ("gpt-4", "gpt-5", "o1", "o3", "o4", "chatgpt-")
    vision_prefixes = ("gpt-4o", "gpt-4-turbo", "gpt-4-vision", "gpt-5",
                       "o1-", "o3-", "o4-")
    seen = set()
    for m in data:
        mid = m.get("id")
        if not mid or mid in seen:
            continue
        if not mid.startswith(chat_prefixes):
            continue
        # Skip dated snapshots — they're noise. Keep only the alias forms.
        if any(c.isdigit() and "-" in mid[mid.index(c):] for c in mid if False):
            pass
        # Drop fine-tune / preview-snapshot variants like ".../2024-08-06"
        if mid.count("-") >= 4 and any(seg.isdigit() for seg in mid.split("-")):
            continue
        seen.add(mid)
        out.append({
            "id": mid,
            "label": mid,
            "vision": mid.startswith(vision_prefixes),
        })
    out.sort(key=lambda m: m["id"])
    return out


async def _fetch_gemini() -> list[dict]:
    if not cfg.google_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": cfg.google_api_key},
        )
    r.raise_for_status()
    data = r.json().get("models", [])
    out = []
    for m in data:
        # Names look like "models/gemini-2.5-flash" — strip the prefix
        full = m.get("name", "")
        mid = full.replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue   # skip embedding-only / TTS-only models
        if not mid:
            continue
        out.append({
            "id": mid,
            "label": m.get("displayName") or mid,
            # All Gemini 1.5+ models accept images as input
            "vision": "vision" in mid or "gemini-1.5" in mid or "gemini-2" in mid
                      or "gemini-3" in mid,
        })
    # Sort: newer first (rough heuristic — versions in name)
    out.sort(key=lambda m: m["id"], reverse=True)
    return out


_FETCHERS = {
    "claude":  _fetch_claude,
    "openai":  _fetch_openai,
    "gemini":  _fetch_gemini,
}


# ─── Public API ───────────────────────────────────────────────────────────────

def cached_models(provider: str) -> list[dict]:
    """Read on-disk cache, falling back to a curated list if missing."""
    p = _cache_path(provider)
    if p.exists():
        try:
            blob = json.loads(p.read_text())
            ms = blob.get("models", [])
            if ms:
                return ms
        except Exception:
            pass
    return list(_FALLBACKS.get(provider, []))


def cache_is_stale(provider: str, ttl: int = CACHE_TTL_SECONDS) -> bool:
    p = _cache_path(provider)
    if not p.exists():
        return True
    try:
        blob = json.loads(p.read_text())
        return (time.time() - float(blob.get("fetched_at", 0))) > ttl
    except Exception:
        return True


async def refresh(provider: str) -> list[dict]:
    """Fetch live + write to cache. Returns the new model list (raises on error)."""
    fetcher = _FETCHERS.get(provider)
    if not fetcher:
        raise ValueError(f"No live model fetcher for provider '{provider}'")
    models = await fetcher()
    if not models:
        # No key → no models. Don't overwrite cache with empty list.
        return cached_models(provider)
    blob = {"fetched_at": time.time(), "models": models}
    _cache_path(provider).write_text(json.dumps(blob, indent=2))
    return models


async def refresh_all_stale() -> dict[str, int]:
    """Refresh every provider whose cache is stale. Returns counts per provider."""
    results = {}
    for provider in _FETCHERS:
        if cache_is_stale(provider):
            try:
                ms = await refresh(provider)
                results[provider] = len(ms)
            except Exception as e:
                results[provider] = -1   # signals failure
    return results


def model_ids(provider: str) -> list[str]:
    return [m["id"] for m in cached_models(provider)]


def best_default(provider: str) -> Optional[str]:
    """Pick a sensible default model from the cache — vision-capable first."""
    models = cached_models(provider)
    for m in models:
        if m.get("vision"):
            return m["id"]
    return models[0]["id"] if models else None


# ─── CLI: `python -m ai.model_registry [show|refresh] [provider]` ─────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) >= 2 else "show"
    target = sys.argv[2] if len(sys.argv) >= 3 else None

    if cmd == "show":
        for prov in (target,) if target else _FETCHERS:
            stale = "stale" if cache_is_stale(prov) else "fresh"
            print(f"\n[{prov}] {stale}")
            for m in cached_models(prov):
                v = "👁" if m.get("vision") else "  "
                print(f"  {v} {m['id']}")
    elif cmd == "refresh":
        async def _run():
            for prov in (target,) if target else _FETCHERS:
                try:
                    ms = await refresh(prov)
                    print(f"[{prov}] refreshed {len(ms)} models")
                except Exception as e:
                    print(f"[{prov}] FAILED: {e}")
        asyncio.run(_run())
    else:
        print("Usage: python -m ai.model_registry [show|refresh] [claude|openai|gemini]")
