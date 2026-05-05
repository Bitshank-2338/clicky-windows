"""
Ollama bootstrap utilities.

Most users who hit "Clicky listens but won't answer" don't have Ollama
installed (or installed it without pulling a model). This module:

  • Detects whether Ollama is running     → is_ollama_running()
  • Lists installed models                → list_installed_models()
  • Detects whether a model is pulled     → is_model_installed(name)
  • Streams a pull with a progress cb    → pull_model(name, on_progress)
  • Downloads the official Ollama setup   → download_ollama_installer(dest)
  • Launches the official Ollama setup    → run_ollama_installer(path)

Everything is sync httpx so it's safe to call from any thread.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

import httpx

from config import cfg


OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/OllamaSetup.exe"

# Default models we recommend for the free tier. Kept small so the
# download finishes in a reasonable time on a typical home connection.
DEFAULT_TEXT_MODEL = "llama3.2:3b"          # ~2 GB
DEFAULT_VISION_MODEL = "qwen2.5vl:3b"        # ~3 GB


# ─── Detection ────────────────────────────────────────────────────────────────

def is_ollama_running(timeout: float = 1.5) -> bool:
    """Return True if the Ollama HTTP server is reachable."""
    base = cfg.ollama_host.rstrip("/")
    try:
        r = httpx.get(f"{base}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def is_ollama_installed() -> bool:
    """Return True if the `ollama` binary is on PATH (server may still be off)."""
    return shutil.which("ollama") is not None


def list_installed_models() -> List[str]:
    """Return the list of model tags installed locally. Empty list if Ollama is off."""
    base = cfg.ollama_host.rstrip("/")
    try:
        r = httpx.get(f"{base}/api/tags", timeout=3.0)
        r.raise_for_status()
        data = r.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def is_model_installed(name: str) -> bool:
    """Check whether a specific Ollama model tag (e.g. 'llama3.2:3b') is pulled."""
    if not name:
        return False
    installed = list_installed_models()
    # Ollama returns tags like 'llama3.2:3b'. Match by exact tag *or* base name
    # so callers can pass either 'llama3.2' or 'llama3.2:3b'.
    if name in installed:
        return True
    base = name.split(":", 1)[0]
    return any(m.split(":", 1)[0] == base for m in installed)


# ─── Pull a model with progress ───────────────────────────────────────────────

def pull_model(
    name: str,
    on_progress: Optional[Callable[[str, float], None]] = None,
    timeout: float = 1800.0,
) -> bool:
    """
    Pull an Ollama model, streaming progress.

    on_progress(status, percent) is called as the pull progresses.
        status:  human-readable string (e.g. "downloading manifest")
        percent: 0.0–100.0 (or 0.0 if unknown)

    Returns True when the pull finishes successfully.
    """
    base = cfg.ollama_host.rstrip("/")
    payload = {"name": name, "stream": True}

    try:
        with httpx.stream(
            "POST", f"{base}/api/pull", json=payload, timeout=timeout
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue

                status = msg.get("status", "")
                total = msg.get("total")
                done = msg.get("completed")
                pct = 0.0
                if total and done:
                    try:
                        pct = (float(done) / float(total)) * 100.0
                    except Exception:
                        pct = 0.0

                if on_progress:
                    try:
                        on_progress(status, pct)
                    except Exception:
                        pass

                if status == "success":
                    return True
        return True
    except Exception as e:
        if on_progress:
            on_progress(f"error: {e}", 0.0)
        return False


# ─── Installer download / run ─────────────────────────────────────────────────

def _default_installer_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Clicky" / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d / "OllamaSetup.exe"


def download_ollama_installer(
    dest: Optional[Path] = None,
    on_progress: Optional[Callable[[float], None]] = None,
) -> Path:
    """Download the official Ollama installer. Returns the local path on success."""
    target = Path(dest) if dest else _default_installer_path()
    tmp = target.with_suffix(target.suffix + ".part")

    with httpx.stream("GET", OLLAMA_DOWNLOAD_URL, timeout=120.0, follow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", "0"))
        downloaded = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=64 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress and total:
                    try:
                        on_progress((downloaded / total) * 100.0)
                    except Exception:
                        pass

    tmp.replace(target)
    return target


def run_ollama_installer(path: Path, silent: bool = False) -> int:
    """
    Launch the Ollama installer. Returns the process exit code.

    If silent=True we use Ollama's silent install flag (/SILENT). The official
    Ollama installer is an Inno Setup wizard so it accepts the standard flags.
    """
    args: List[str] = [str(path)]
    if silent:
        args.append("/SILENT")
    proc = subprocess.run(args, shell=False)
    return proc.returncode


def wait_for_ollama_server(timeout: float = 60.0, poll_interval: float = 1.0) -> bool:
    """Block until the Ollama server is reachable, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_ollama_running():
            return True
        time.sleep(poll_interval)
    return False


# ─── CLI usage: `python -m ai.ollama_bootstrap status|install|pull <model>` ───

def _cli():
    args = sys.argv[1:]
    if not args:
        print("Usage: python -m ai.ollama_bootstrap [status|install|pull <model>|diag]")
        return

    cmd = args[0].lower()

    if cmd == "status":
        print(f"Ollama binary on PATH:  {is_ollama_installed()}")
        print(f"Ollama server running:  {is_ollama_running()}")
        if is_ollama_running():
            models = list_installed_models()
            print(f"Installed models ({len(models)}):")
            for m in models:
                print(f"  • {m}")
        return

    if cmd == "install":
        print("Downloading Ollama installer…")
        p = download_ollama_installer(on_progress=lambda pct: print(f"  {pct:.0f}%", end="\r"))
        print(f"\nDownloaded to {p}")
        print("Launching installer (you'll see a UAC prompt)…")
        rc = run_ollama_installer(p)
        print(f"Installer exited with code {rc}")
        print("Waiting for Ollama to come online…")
        if wait_for_ollama_server(timeout=60):
            print("Ollama is running.")
        else:
            print("Timed out waiting for Ollama. Reboot or start it from the Start menu.")
        return

    if cmd == "pull":
        if len(args) < 2:
            print("pull needs a model name, e.g.:  python -m ai.ollama_bootstrap pull llama3.2:3b")
            return
        name = args[1]
        print(f"Pulling {name}…")
        ok = pull_model(name, on_progress=lambda s, p: print(f"  {s} {p:.0f}%", end="\r"))
        print()
        print("Done." if ok else "Pull failed.")
        return

    if cmd == "diag":
        print("─── Clicky Ollama diagnostics ───")
        print(f"Configured host:          {cfg.ollama_host}")
        print(f"Configured text model:    {cfg.ollama_text_model}")
        print(f"Configured vision model:  {cfg.ollama_vision_model}")
        print(f"Binary on PATH:           {is_ollama_installed()}")
        print(f"Server reachable:         {is_ollama_running()}")
        if is_ollama_running():
            models = list_installed_models()
            print(f"Installed models:         {models or '(none)'}")
            print(f"Text model present:       {is_model_installed(cfg.ollama_text_model)}")
            print(f"Vision model present:     {is_model_installed(cfg.ollama_vision_model)}")
        return

    print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    _cli()
