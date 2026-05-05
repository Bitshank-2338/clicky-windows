"""
GitHub Copilot provider — uses the device-flow OAuth handshake (same flow
VS Code / nvim-copilot use) so students don't need to paste an API key.

Default model is `gpt-4o-mini` — it's on Copilot's *no premium request* tier
at the time of writing, so Free/Pro/Student seats don't burn premium quota.

Auth flow (one-time, ~30 seconds):
    python -m ai.github_copilot_provider login
    → prints a 9-char user code + opens https://github.com/login/device
    → you paste the code, click "Authorize"
    → token cached to %LOCALAPPDATA%\\Clicky\\github_token.json

Chat flow (every call):
    GitHub token  → exchange for short-lived Copilot token (cached to ~25 min)
                  → stream from https://api.githubcopilot.com/chat/completions

Note: this uses the same public client_id VS Code ships with. It's unofficial
— GitHub has not published a public Copilot Chat API — but it's the de-facto
standard path dozens of community clients (copilot.vim, copilot.lua, aider,
etc.) use. Your Copilot subscription is consumed normally.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import AsyncIterator, List, Optional

import httpx

from ai.base_provider import BaseLLMProvider, Message


VSCODE_CLIENT_ID = "Iv1.b507a08c87ecfe98"   # Public VS Code Copilot client id
DEVICE_CODE_URL  = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_CHAT_URL   = "https://api.githubcopilot.com/chat/completions"
COPILOT_MODELS_URL = "https://api.githubcopilot.com/models"

# Fallback used only if the live /models endpoint is unreachable AND the local
# cache is empty. Real list is fetched from GitHub on first run + every login.
FALLBACK_MODEL = "gpt-4o-mini"
MAX_TOKENS = 1024

# Cache TTL — refetch /models if cache is older than this.
MODEL_CACHE_TTL_SECONDS = 6 * 60 * 60   # 6 hours

# Editor identity. Bumping these every release year matches what VS Code's
# Copilot Chat extension actually sends — older values get 400'd.
EDITOR_VERSION = "vscode/1.96.0"
EDITOR_PLUGIN  = "copilot-chat/0.23.1"
USER_AGENT     = "GitHubCopilotChat/0.23.1"


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Clicky"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _token_path() -> Path:
    return _data_dir() / "github_token.json"


def _models_cache_path() -> Path:
    return _data_dir() / "copilot_models.json"


# ─── Device-flow login ────────────────────────────────────────────────────────

def _login_log_path() -> Path:
    return _data_dir() / "copilot_login.log"


def _log_login(line: str) -> None:
    """Append a timestamped line to the login log so we can debug failures
    after the fact (the user can grab this from %LOCALAPPDATA%\\Clicky\\)."""
    try:
        from datetime import datetime
        with open(_login_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")
    except Exception:
        pass


async def device_login(open_browser: bool = True,
                       on_code: "Optional[callable]" = None) -> str:
    """Run the GitHub device-code OAuth flow. Returns the github access token.

    on_code(user_code, verification_uri) — optional callback fired once the
    device code is known, before we start polling. The UI uses this to display
    the code in the panel instead of (or in addition to) the terminal.
    """
    _log_login("=== device_login() started ===")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            DEVICE_CODE_URL,
            data={"client_id": VSCODE_CLIENT_ID, "scope": "read:user"},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        d = r.json()

    user_code = d["user_code"]
    verification_uri = d["verification_uri"]
    device_code = d["device_code"]
    interval = max(5, int(d.get("interval", 5)))
    expires_in = int(d.get("expires_in", 900))
    _log_login(f"Got device code. user_code={user_code} interval={interval}s expires_in={expires_in}s")

    print("\n" + "─" * 56)
    print("  GITHUB COPILOT LOGIN")
    print("─" * 56)
    print(f"  1. Open: {verification_uri}")
    print(f"  2. Enter code: {user_code}")
    print(f"  3. Click 'Authorize' in GitHub.")
    print("─" * 56 + "\n")

    # Notify the UI so the code is visible even when there's no terminal
    if on_code is not None:
        try:
            on_code(user_code, verification_uri)
        except Exception:
            pass

    if open_browser:
        try:
            webbrowser.open(verification_uri)
        except Exception:
            pass

    deadline = time.time() + expires_in
    poll_count = 0
    async with httpx.AsyncClient(timeout=15) as client:
        while time.time() < deadline:
            await asyncio.sleep(interval)
            poll_count += 1
            try:
                r = await client.post(
                    ACCESS_TOKEN_URL,
                    data={
                        "client_id": VSCODE_CLIENT_ID,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Accept": "application/json"},
                )
            except Exception as e:
                _log_login(f"poll #{poll_count} network error: {e}")
                continue
            if r.status_code != 200:
                _log_login(f"poll #{poll_count} HTTP {r.status_code}")
                continue
            body = r.json()
            if "access_token" in body:
                token = body["access_token"]
                _token_path().write_text(json.dumps({"access_token": token}))
                _log_login(f"✅ Signed in after {poll_count} polls. Token saved.")
                print("✅  Signed in. Token saved to", _token_path())
                # Eagerly fetch the model list so the panel reflects what
                # the user actually has access to *right now*.
                try:
                    models = await refresh_models_to_cache()
                    print(f"   Found {len(models)} chat models on your seat. "
                          f"Free: {len([m for m in models if m['multiplier']==0])}.")
                except Exception as e:
                    print(f"   (Could not refresh model list: {e})")
                return token
            if body.get("error") == "authorization_pending":
                if poll_count % 6 == 0:   # log roughly every 30s
                    _log_login(f"poll #{poll_count}: still pending…")
                continue
            if body.get("error") == "slow_down":
                interval += 5
                _log_login(f"poll #{poll_count}: slow_down — interval now {interval}s")
                continue
            if body.get("error") in ("expired_token", "access_denied"):
                _log_login(f"poll #{poll_count}: terminal error {body.get('error')}")
                raise RuntimeError(f"Copilot login failed: {body.get('error')}")
            _log_login(f"poll #{poll_count}: unexpected body keys={list(body.keys())}")

    _log_login(f"❌ Timed out after {poll_count} polls.")
    raise TimeoutError("Copilot device-flow login timed out.")


def load_github_token() -> Optional[str]:
    p = _token_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text()).get("access_token")
    except Exception:
        return None


def is_authenticated() -> bool:
    return load_github_token() is not None


# ─── Live model discovery ─────────────────────────────────────────────────────
#
# GitHub Copilot exposes `GET /models` which returns every model the user's
# Copilot seat can currently access, along with its billing multiplier
# (0 = free / does not burn a premium request, ≥1 = consumes premium quota).
#
# We auto-refresh this list whenever:
#   • cache is older than MODEL_CACHE_TTL_SECONDS
#   • user signs in via device flow
#   • user clicks "Refresh Copilot models" in the tray menu
#   • user switches to Copilot from another provider

async def fetch_copilot_token_only() -> str:
    """Exchange the GitHub OAuth token for a Copilot session token (one-shot)."""
    gh = load_github_token()
    if not gh:
        raise RuntimeError("Not signed in to GitHub Copilot.")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            COPILOT_TOKEN_URL,
            headers={
                "Authorization": f"token {gh}",
                "Editor-Version": EDITOR_VERSION,
                "Editor-Plugin-Version": EDITOR_PLUGIN,
                "User-Agent": USER_AGENT,
            },
        )
    if r.status_code == 401:
        raise RuntimeError(
            "GitHub rejected your token (401). Re-run the login from "
            "Tray → Model → Sign in to GitHub Copilot…"
        )
    if r.status_code == 403:
        raise RuntimeError(
            "Your GitHub account doesn't have an active Copilot subscription "
            "(403). Verify at https://github.com/settings/copilot — Free, Pro, "
            "and Education seats all work; the seat just needs to be active."
        )
    r.raise_for_status()
    return r.json()["token"]


async def fetch_models_live() -> list[dict]:
    """Hit /models on api.githubcopilot.com and return the raw model list."""
    tok = await fetch_copilot_token_only()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            COPILOT_MODELS_URL,
            headers={
                "Authorization": f"Bearer {tok}",
                "Editor-Version": EDITOR_VERSION,
                "Editor-Plugin-Version": EDITOR_PLUGIN,
                "Copilot-Integration-Id": "vscode-chat",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
    r.raise_for_status()
    payload = r.json()
    # API returns either {"data": [...]} (OpenAI-style) or a bare list.
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected /models payload: {payload!r}")
    return items


def _normalise_model(m: dict) -> dict:
    """Pull out the bits we care about into a flat shape."""
    cap = m.get("capabilities", {}) or {}
    supports = cap.get("supports", {}) or {}
    billing = m.get("billing", {}) or {}
    multiplier = billing.get("multiplier")
    if multiplier is None:
        # Some non-premium models omit the field entirely
        multiplier = 0 if not billing.get("is_premium", False) else 1
    return {
        "id":          m.get("id") or m.get("name"),
        "label":       m.get("name") or m.get("id"),
        "vendor":      m.get("vendor", ""),
        "type":        cap.get("type", "chat"),
        "vision":      bool(supports.get("vision", False)),
        "streaming":   bool(supports.get("streaming", True)),
        "multiplier":  float(multiplier),
        "is_premium":  bool(billing.get("is_premium", multiplier and multiplier > 0)),
        "picker":      bool(m.get("model_picker_enabled", True)),
    }


async def refresh_models_to_cache() -> list[dict]:
    """Fetch live + write to %LOCALAPPDATA%\\Clicky\\copilot_models.json."""
    raw = await fetch_models_live()
    flat = [_normalise_model(m) for m in raw if m.get("id")]
    flat = [m for m in flat if m["type"] == "chat" and m["picker"]]
    blob = {"fetched_at": time.time(), "models": flat}
    _models_cache_path().write_text(json.dumps(blob, indent=2))
    return flat


def cached_models() -> list[dict]:
    """Read the cached model list, or return the built-in fallback if missing."""
    p = _models_cache_path()
    if p.exists():
        try:
            blob = json.loads(p.read_text())
            return blob.get("models", [])
        except Exception:
            pass
    # Conservative fallback — gpt-4o-mini is free across all Copilot tiers
    # historically. The real list will replace this on first successful call.
    return [
        {"id": "gpt-4o-mini",       "label": "GPT-4o mini",       "vendor": "OpenAI",
         "type": "chat", "vision": True,  "streaming": True, "multiplier": 0.0, "is_premium": False, "picker": True},
        {"id": "gpt-4o",            "label": "GPT-4o",            "vendor": "OpenAI",
         "type": "chat", "vision": True,  "streaming": True, "multiplier": 1.0, "is_premium": True,  "picker": True},
        {"id": "claude-3.5-sonnet", "label": "Claude 3.5 Sonnet", "vendor": "Anthropic",
         "type": "chat", "vision": True,  "streaming": True, "multiplier": 1.0, "is_premium": True,  "picker": True},
    ]


def cache_is_stale() -> bool:
    """True if the cache is missing or older than MODEL_CACHE_TTL_SECONDS."""
    p = _models_cache_path()
    if not p.exists():
        return True
    try:
        blob = json.loads(p.read_text())
        return (time.time() - float(blob.get("fetched_at", 0))) > MODEL_CACHE_TTL_SECONDS
    except Exception:
        return True


def free_model_ids() -> list[str]:
    """Multiplier-0 models from the cache (or fallback). Vision-capable first."""
    models = cached_models()
    free = [m for m in models if m["multiplier"] == 0]
    free.sort(key=lambda m: (not m["vision"], m["id"]))   # vision first, then alpha
    return [m["id"] for m in free]


def pick_default_free_model() -> str:
    """Best free model for Clicky — vision-capable, multiplier 0."""
    models = cached_models()
    # Vision-capable AND free → ideal (Clicky sends screenshots)
    for m in models:
        if m["vision"] and m["multiplier"] == 0:
            return m["id"]
    # Free-but-no-vision → still usable (ignores the screenshot)
    for m in models:
        if m["multiplier"] == 0:
            return m["id"]
    # Should never happen, but don't crash
    return FALLBACK_MODEL


def model_label(model_id: str) -> str:
    """Pretty UI label: 'gpt-4o-mini  (free)' or 'claude-3.5-sonnet  (1×)'."""
    for m in cached_models():
        if m["id"] == model_id:
            mult = m["multiplier"]
            tag = "free" if mult == 0 else (
                f"{mult:g}×" if mult != 1 else "1× premium"
            )
            return f"{model_id}  ({tag})"
    return model_id


def sorted_model_ids() -> list[str]:
    """All Copilot model IDs, free ones first, then by ascending multiplier."""
    models = cached_models()
    models = sorted(models, key=lambda m: (m["multiplier"], not m["vision"], m["id"]))
    return [m["id"] for m in models]


# ─── Provider ─────────────────────────────────────────────────────────────────

class GitHubCopilotProvider(BaseLLMProvider):

    def __init__(self):
        self._gh_token = load_github_token()
        if not self._gh_token:
            raise RuntimeError(
                "GitHub Copilot not signed in. Run:  python -m ai.github_copilot_provider login"
            )
        self._copilot_token: Optional[str] = None
        self._copilot_token_expires: float = 0.0

    async def _get_copilot_token(self, client: httpx.AsyncClient) -> str:
        # Short-lived token, refresh with ~2 min buffer
        if self._copilot_token and time.time() < self._copilot_token_expires - 120:
            return self._copilot_token
        r = await client.get(
            COPILOT_TOKEN_URL,
            headers={
                "Authorization": f"token {self._gh_token}",
                "Editor-Version": EDITOR_VERSION,
                "Editor-Plugin-Version": EDITOR_PLUGIN,
                "User-Agent": USER_AGENT,
            },
        )
        if r.status_code == 401:
            raise RuntimeError(
                "GitHub rejected your token. Sign in again: Tray → Model → "
                "Sign in to GitHub Copilot…"
            )
        if r.status_code == 403:
            body = (r.text or "")[:300]
            raise RuntimeError(
                "Your GitHub account has no active Copilot Chat seat. Verify "
                "at https://github.com/settings/copilot. Server said: " + body
            )
        r.raise_for_status()
        data = r.json()
        self._copilot_token = data["token"]
        self._copilot_token_expires = float(data.get("expires_at", time.time() + 1500))
        # Useful flags for diagnostics — log if Chat is disabled on this seat
        if data.get("chat_enabled") is False:
            raise RuntimeError(
                "Copilot Chat is disabled on this seat. Enable it at "
                "https://github.com/settings/copilot (toggle 'Copilot Chat')."
            )
        return self._copilot_token

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        # Dynamic default — picks the best free + vision-capable model from
        # whatever GitHub currently exposes for this seat.
        model = model or pick_default_free_model()

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Vision: Copilot's OpenAI-compatible endpoint supports image_url parts
        # on vision-capable models (gpt-4o, gpt-4o-mini). Encode as data URIs.
        content_parts: list = []
        for img_b64 in screenshots_b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
            })
        content_parts.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": content_parts if screenshots_b64 else user_text})

        async with httpx.AsyncClient(timeout=120) as client:
            tok = await self._get_copilot_token(client)
            headers = {
                "Authorization": f"Bearer {tok}",
                "Editor-Version": EDITOR_VERSION,
                "Editor-Plugin-Version": EDITOR_PLUGIN,
                "Copilot-Integration-Id": "vscode-chat",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }
            body = {
                "model": model,
                "messages": messages,
                "max_tokens": MAX_TOKENS,
                "temperature": 0.7,
                "stream": True,
            }
            async with client.stream("POST", COPILOT_CHAT_URL, json=body, headers=headers) as r:
                if r.status_code >= 400:
                    err = await r.aread()
                    snippet = (err.decode("utf-8", "replace") or "")[:400]
                    if r.status_code == 400 and "model" in snippet.lower():
                        raise RuntimeError(
                            f"Copilot rejected model '{model}'. It may have been "
                            f"removed by GitHub. Use Tray → Model → Refresh "
                            f"Copilot models. Server: {snippet}"
                        )
                    if r.status_code == 402:
                        raise RuntimeError(
                            f"Copilot says you've hit your premium-request quota. "
                            f"Switch to a free model (Tray → Model). Server: {snippet}"
                        )
                    if r.status_code == 403:
                        raise RuntimeError(
                            f"Copilot Chat seat issue. Check "
                            f"https://github.com/settings/copilot. Server: {snippet}"
                        )
                    raise RuntimeError(
                        f"Copilot HTTP {r.status_code}: {snippet}"
                    )
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in obj.get("choices", []):
                        delta = choice.get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                await self._get_copilot_token(client)
            return True
        except Exception:
            return False


# ─── CLI entry: `python -m ai.github_copilot_provider login` ──────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) >= 2 else ""
    if cmd == "login":
        asyncio.run(device_login())
    elif cmd == "status":
        print("signed in" if is_authenticated() else "not signed in")
        print("token file:", _token_path())
        print("models cache:", _models_cache_path(),
              "(stale)" if cache_is_stale() else "(fresh)")
    elif cmd == "models":
        # Show what's currently cached
        for m in cached_models():
            tag = "FREE" if m["multiplier"] == 0 else f"{m['multiplier']:g}× premium"
            vision = "👁 " if m["vision"] else "   "
            print(f"  {vision}{m['id']:30s}  {tag:14s}  {m['vendor']}")
    elif cmd == "refresh":
        models = asyncio.run(refresh_models_to_cache())
        print(f"Refreshed {len(models)} models → {_models_cache_path()}")
        for m in models:
            tag = "FREE" if m["multiplier"] == 0 else f"{m['multiplier']:g}×"
            print(f"  {m['id']:30s}  {tag}")
    elif cmd == "logout":
        for p in (_token_path(), _models_cache_path()):
            if p.exists():
                p.unlink()
                print(f"removed {p}")
    else:
        print("Usage: python -m ai.github_copilot_provider [login|status|models|refresh|logout]")
