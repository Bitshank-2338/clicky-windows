"""
Live model discovery + caching for Claude, OpenAI, and Gemini.

Each provider exposes a "list models" endpoint we hit on demand:
  • Anthropic:  GET /v1/models                    (key in x-api-key)
  • OpenAI:     GET /v1/models                    (key in Authorization)
  • Gemini:     GET /v1beta/models                (key in x-goog-api-key)

Cached per-provider to %LOCALAPPDATA%\\Clicky\\models_<provider>.json.

Three things this module is careful about, each learned the hard way:

  1. ORDER IS THE DEFAULT. The panel selects the first entry of each list as
     the active model, so list order decides what users actually talk to.
     Lists are therefore sorted newest-first with the recommended default
     pinned on top, rather than alphabetically.

  2. A vendor's model list is not a list of models that work. OpenAI returns
     deprecated models that 404, Responses-only "pro" models that reject chat
     requests, and image/audio/search models; Gemini returns TTS, image and
     live-audio models under the same generateContent method as chat models.
     Picking any of those made Clicky fail or go silent, so lists are filtered
     and, for OpenAI, each survivor is probed once with a tiny request.

  3. The cache can outlive the logic that produced it. Entries carry a schema
     version, so shipping a better filter invalidates older caches immediately
     instead of leaving users on a stale list for weeks.

GitHub Copilot has its own (separate) implementation in github_copilot_provider.py
because Copilot's flow is more complex (token exchange + per-seat filtering).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import httpx

from config import cfg


# New releases should show up within a day, not a month.
CACHE_TTL_SECONDS = 24 * 60 * 60

# Bump whenever filtering / ordering / flags change, so older caches written by
# previous logic are ignored rather than trusted for their full TTL.
SCHEMA_VERSION = 2


# Curated fallback lists — used when the live endpoint is unreachable AND the
# on-disk cache is empty (offline, first run before refresh, no key yet).
# Listed in the order they should appear: the first entry is the default.
_FALLBACKS: dict[str, list[dict]] = {
    "claude": [
        {"id": "claude-sonnet-5-5",         "label": "Claude Sonnet 5.5", "vision": True},
        {"id": "claude-opus-5-5",           "label": "Claude Opus 5.5",   "vision": True},
        {"id": "claude-fable-5-1",          "label": "Claude Fable 5.1",  "vision": True},
        {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5",  "vision": True},
    ],
    "openai": [
        {"id": "gpt-6-sol",    "label": "GPT-6 Sol",    "vision": True},
        {"id": "gpt-6-luna",   "label": "GPT-6 Luna",   "vision": True},
        {"id": "gpt-6.1-sol",  "label": "GPT-6.1 Sol",  "vision": True},
        {"id": "gpt-6-astra",  "label": "GPT-6 Astra",  "vision": True},
        {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini", "vision": True},
        {"id": "gpt-4.1",      "label": "GPT-4.1",      "vision": True},
        {"id": "gpt-4o",       "label": "GPT-4o",       "vision": True},
    ],
    "gemini": [
        {"id": "gemini-3.6-flash",       "label": "Gemini 3.6 Flash",        "vision": True},
        {"id": "gemini-3.8-flash",       "label": "Gemini 3.8 Flash",        "vision": True},
        {"id": "gemini-3.5-flash-lite",  "label": "Gemini 3.5 Flash-Lite",   "vision": True},
        {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro (preview)", "vision": True},
    ],
}


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Clicky"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(provider: str) -> Path:
    return _data_dir() / f"models_{provider}.json"


# ─── Ordering + defaults ──────────────────────────────────────────────────────
#
# For a voice assistant the right default is the fast, vision-capable,
# affordable tier of the newest generation — not the most capable one. Each
# provider has a preference list; the first one actually present wins, and if
# none match we fall back to "newest vision model".

_PREFERRED_DEFAULT: dict[str, list[str]] = {
    # Anthropic: Sonnet is "the best combination of speed and intelligence".
    "claude": [r"^claude-sonnet-\d+-\d+$", r"^claude-sonnet-\d+$",
               r"^claude-haiku-", r"^claude-opus-"],
    # gpt-6-sol: balanced tier, priced like the GPT-4o Clicky used before, and
    # measured at 1.3s time-to-first-word versus 3.1s for the newer gpt-6.1-sol
    # (see openai_provider.py). Luna is the cheap/fast tier.
    "openai": [r"^gpt-6-sol$", r"^gpt-6-luna$", r"^gpt-6\.\d+-sol$",
               r"^gpt-5\.\d+-mini$", r"^gpt-4\.1$", r"^gpt-4o$"],
    # gemini-3.6-flash, deliberately, not the newest Flash. Measured over four
    # rounds through Clicky's own provider: 3.6 answered in 3.3s median with no
    # errors; 3.8 took 6.4s and returned HTTP 503 "high demand" on 2 of 4
    # requests (launch-week overload). 3.8 stays one click away in the picker.
    "gemini": [r"^gemini-3\.6-flash$", r"^gemini-\d+\.\d+-flash$",
               r"^gemini-\d+-flash$", r"^gemini-\d+\.\d+-flash-lite$",
               r"^gemini-\d+\.\d+-pro"],
}


def _version_key(mid: str) -> tuple:
    """Sortable (major, minor) pulled from an id, newest = largest.

    Handles claude-sonnet-5-5, claude-3-5-sonnet-..., gpt-6.1-sol, gpt-5-mini,
    o3, gemini-3.8-flash. Ids with no version sort last.
    """
    m = re.match(r"claude-(?:[a-z]+)-(\d+)(?:-(\d{1,2})(?!\d))?", mid)       # claude-sonnet-5-5
    if m:
        return (int(m.group(1)), int(m.group(2) or 0))
    m = re.match(r"claude-(\d+)(?:-(\d{1,2})(?!\d))?-", mid)                  # claude-3-5-sonnet
    if m:
        return (int(m.group(1)), int(m.group(2) or 0))
    m = re.match(r"gpt-(\d+)(?:\.(\d+))?", mid)                                # gpt-6.1-sol
    if m:
        return (int(m.group(1)), int(m.group(2) or 0))
    m = re.match(r"o(\d+)", mid)                                               # o3 / o4-mini
    if m:
        return (4, 9)       # reasoning o-series: above gpt-4.x, below gpt-5
    m = re.match(r"gemini-(\d+)(?:\.(\d+))?", mid)                             # gemini-3.8-flash
    if m:
        return (int(m.group(1)), int(m.group(2) or 0))
    return (-1, 0)


_CLAUDE_FAMILY_RANK = {"fable": 5, "mythos": 5, "opus": 4, "sonnet": 3, "haiku": 2}


def _family_rank(mid: str) -> int:
    for fam, rank in _CLAUDE_FAMILY_RANK.items():
        if f"-{fam}" in mid or mid.startswith(f"claude-{fam}"):
            return rank
    return 0


def _order_for_picker(provider: str, models: list[dict]) -> list[dict]:
    """Newest generation first, recommended default pinned to the top."""
    ordered = sorted(
        models,
        key=lambda m: (_version_key(m["id"]), _family_rank(m["id"]), m["id"]),
        reverse=True,
    )
    for pattern in _PREFERRED_DEFAULT.get(provider, []):
        # within a preference, the newest match wins
        hits = [m for m in ordered if re.search(pattern, m["id"])]
        if hits:
            pick = hits[0]
            return [pick] + [m for m in ordered if m is not pick]
    return ordered


# ─── Per-provider filters ─────────────────────────────────────────────────────

# OpenAI model ids that match a chat-looking prefix but cannot be used for a
# conversation through /v1/chat/completions.
_OPENAI_NON_CHAT = (
    "image", "audio", "realtime", "tts", "transcribe", "embed", "moderation",
    "dall", "instruct", "codex", "search", "live", "whisper", "sora",
    "diarize", "translate", "computer-use", "davinci", "babbage",
)


def _is_openai_chat_model(mid: str) -> bool:
    """True for ids that can plausibly hold a chat-completions conversation.

    Deliberately generation-agnostic: the previous whitelist ("gpt-4", "gpt-5",
    "o1"...) silently dropped every gpt-6 model, and would have dropped gpt-7
    the day it shipped.
    """
    if not (mid.startswith("gpt-") or mid == "chat-latest"
            or re.match(r"^o\d", mid) or mid.startswith("chatgpt-")):
        return False
    if any(marker in mid for marker in _OPENAI_NON_CHAT):
        return False
    # "-pro" models exist only on the Responses API; chat completions rejects
    # them, so offering one makes Clicky fail on every question.
    if re.search(r"(^|-)pro($|-)", mid):
        return False
    # Dated snapshots (gpt-5-2025-08-07, gpt-4o-2024-08-06) duplicate the alias.
    if re.search(r"-\d{4}-\d{2}-\d{2}$", mid) or re.search(r"-\d{4}$", mid):
        return False
    # Legacy: no vision, 8k context, superseded long ago.
    if mid.startswith("gpt-3.5") or mid in ("gpt-4", "gpt-4-0613") or mid.startswith("gpt-4-turbo-preview"):
        return False
    return True


def _openai_vision(mid: str) -> bool:
    if mid in ("o3-mini", "o1-mini", "o1-preview") or mid.startswith(("o1-mini", "o1-preview", "o3-mini")):
        return False
    return True


_GEMINI_NON_CHAT = (
    "image", "tts", "live", "audio", "embed", "aqa", "imagen", "veo",
    "computer-use", "robotics", "diffusion", "learnlm", "lyria",
    # Found by testing a real key against the live list: gemini-3.5-transcribe is
    # a speech model (HTTP 400, image input unsupported), -customtools is a
    # specialised agent variant, and the omni models are undocumented any-to-any
    # previews that never answered a plain chat request.
    "transcribe", "customtools", "omni",
)


def _is_gemini_chat_model(mid: str, methods: list[str]) -> bool:
    """generateContent is shared by chat, TTS, image-generation and live-audio
    models, so the method alone is not enough to tell a chat model apart."""
    if "generateContent" not in methods:
        return False
    if not mid.startswith("gemini-"):      # gemma-* rejects systemInstruction
        return False
    if any(marker in mid for marker in _GEMINI_NON_CHAT):
        return False
    # dated / numbered snapshots duplicate the alias (gemini-2.0-flash-001)
    if re.search(r"-\d{3}$", mid) or re.search(r"-\d{2}-\d{2}$", mid):
        return False
    # Gemini 1.x and 2.x are still *listed* but answer 404 — confirmed live for
    # 2.5 Pro, Flash and Flash-Lite — and Google's current model page no longer
    # mentions them. Offering them just makes a picker full of dead entries.
    if re.match(r"gemini-[12][.-]", mid):
        return False
    return True


# ─── Per-provider live fetchers ───────────────────────────────────────────────

async def _fetch_claude() -> list[dict]:
    if not cfg.anthropic_api_key:
        return []
    out: list[dict] = []
    after: Optional[str] = None
    async with httpx.AsyncClient(timeout=15) as client:
        # Anthropic pages at 20 by default — with the legacy models still
        # listed, the newest releases would fall off the first page.
        for _ in range(10):
            params: dict = {"limit": 1000}
            if after:
                params["after_id"] = after
            r = await client.get(
                "https://api.anthropic.com/v1/models",
                params=params,
                headers={
                    "x-api-key": cfg.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            r.raise_for_status()
            body = r.json()
            for m in body.get("data", []):
                mid = m.get("id") or m.get("name")
                if not mid:
                    continue
                # Models API reports capabilities; fall back to "yes" since all
                # current Claude models accept images.
                caps = (m.get("capabilities") or {})
                img = (caps.get("image_input") or {}).get("supported", True)
                out.append({
                    "id": mid,
                    "label": m.get("display_name") or mid,
                    "vision": bool(img),
                })
            if body.get("has_more") and body.get("last_id"):
                after = body["last_id"]
            else:
                break
    return _order_for_picker("claude", out)


async def _fetch_openai() -> list[dict]:
    if not cfg.openai_api_key:
        return []
    if cfg.openai_base_url:
        # A custom OpenAI-compatible server (DeepSeek, OpenRouter, ...) has its
        # own catalogue; api.openai.com's list would be wrong for it.
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
        )
        r.raise_for_status()
        ids = sorted({m.get("id") for m in r.json().get("data", []) if m.get("id")})
        candidates = [i for i in ids if _is_openai_chat_model(i)]
        candidates = await _verify_openai(client, candidates)

    out = [{"id": i, "label": i, "vision": _openai_vision(i)} for i in candidates]
    return _order_for_picker("openai", out)


async def _verify_openai(client: httpx.AsyncClient, ids: list[str]) -> list[str]:
    """Drop ids that the chat-completions endpoint will not actually serve.

    /v1/models advertises deprecated models (which 404) and models limited to
    other endpoints (which 400). One 16-token request each costs a fraction of
    a cent in total and means the picker only ever offers models that answer.

    Anything inconclusive (timeouts, 5xx, rate limiting) is kept: the goal is to
    remove models that are known-bad, not to hide good ones on a bad network day.
    """
    sem = asyncio.Semaphore(6)
    headers = {"Authorization": f"Bearer {cfg.openai_api_key}"}

    async def usable(mid: str) -> bool:
        async with sem:
            try:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": mid,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_completion_tokens": 16,
                    },
                    timeout=30,
                )
            except Exception:
                return True                      # inconclusive → keep
            if r.status_code == 200 or r.status_code == 429 or r.status_code >= 500:
                return True
            # A reasoning model that spends the whole 16-token probe budget on
            # thinking answers HTTP 400 "Could not finish the message because
            # max_tokens or model output limit was reached". That is proof the
            # model exists and accepted the request, so it must count as usable
            # — o3 was being dropped from the picker intermittently without it.
            if r.status_code == 400 and "output limit was reached" in r.text:
                return True
            return False                          # other 400 / 401 / 403 / 404 → not servable

    results = await asyncio.gather(*(usable(i) for i in ids))
    kept = [i for i, ok in zip(ids, results) if ok]
    # If literally nothing survived the network is probably down; trust the list.
    return kept or ids


async def _fetch_gemini() -> list[dict]:
    if not cfg.google_api_key:
        return []
    out: list[dict] = []
    token: Optional[str] = None
    # The key goes in a header, never the URL: httpx puts the URL in its error
    # text, and that text ends up in the tray toast and the log file.
    headers = {"x-goog-api-key": cfg.google_api_key}
    async with httpx.AsyncClient(timeout=15) as client:
        for _ in range(10):
            params: dict = {"pageSize": 1000}
            if token:
                params["pageToken"] = token
            r = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params=params, headers=headers,
            )
            r.raise_for_status()
            body = r.json()
            for m in body.get("models", []):
                mid = (m.get("name") or "").replace("models/", "")
                if not mid:
                    continue
                if not _is_gemini_chat_model(mid, m.get("supportedGenerationMethods", [])):
                    continue
                out.append({
                    "id": mid,
                    "label": m.get("displayName") or mid,
                    "vision": True,    # every Gemini chat model since 1.5 takes images
                })
            token = body.get("nextPageToken")
            if not token:
                break
    return _order_for_picker("gemini", out)


_FETCHERS = {
    "claude":  _fetch_claude,
    "openai":  _fetch_openai,
    "gemini":  _fetch_gemini,
}


# ─── Public API ───────────────────────────────────────────────────────────────

def _read_cache(provider: str) -> Optional[dict]:
    p = _cache_path(provider)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    # A cache written by older filtering logic is worse than no cache: it can
    # hide new models for weeks, or offer ones that never worked.
    if blob.get("schema") != SCHEMA_VERSION:
        return None
    return blob


def cached_models(provider: str) -> list[dict]:
    """Read on-disk cache, falling back to a curated list if missing."""
    blob = _read_cache(provider)
    if blob and blob.get("models"):
        return blob["models"]
    return list(_FALLBACKS.get(provider, []))


def cache_is_stale(provider: str, ttl: int = CACHE_TTL_SECONDS) -> bool:
    blob = _read_cache(provider)
    if blob is None:
        return True
    try:
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
    blob = {"schema": SCHEMA_VERSION, "fetched_at": time.time(), "models": models}
    _cache_path(provider).write_text(json.dumps(blob, indent=2), encoding="utf-8")
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
    """The model Clicky should start on for this provider (top of the list)."""
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
            for i, m in enumerate(cached_models(prov)):
                v = "V" if m.get("vision") else " "
                star = "*" if i == 0 else " "
                print(f"  {star}{v} {m['id']}")
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
