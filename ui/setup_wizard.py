"""
First-run setup wizard.

Shown once on the first launch (or whenever the user clicks
"Tray → Run setup again…"). Walks the user through:

  0. What Clicky is and how to use it
  1. Pick an engine — free local Ollama, or a cloud API key
  2. Detect Ollama       → start it if installed, install only if truly absent
  3. Detect text model   → pull if missing
  4. Detect vision model → pull if missing  (optional, larger)

Everything is optional — the user can Skip at any step. The wizard never
blocks the main app from starting.

Two things this deliberately gets right, because the shipped 1.2.0 build got
them wrong:

  • Ollama detection looks for the *binary*, not just a live server, and
    starts an installed-but-stopped copy instead of re-downloading 700 MB.
  • There is a real API-key screen, so "Skip — I'll use an API key" leads
    somewhere instead of dead-ending at a file the user has to go find.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
)

from ai import ollama_bootstrap as ob
from config import cfg


# Marker file: the wizard skips itself if this exists.
def _flag_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Clicky"
    d.mkdir(parents=True, exist_ok=True)
    return d / "setup_complete.flag"


def setup_already_ran() -> bool:
    return _flag_path().exists()


def mark_setup_complete() -> None:
    try:
        _flag_path().write_text("ok")
    except Exception:
        pass


def _pretty_hotkey() -> str:
    return "+".join(p.strip().capitalize() for p in cfg.hotkey.split("+"))


# ─── Wizard ───────────────────────────────────────────────────────────────────

class SetupWizard(QDialog):
    """One-window wizard: welcome → engine choice → Ollama/keys → done."""

    progress_signal = pyqtSignal(str, float)
    finished_signal = pyqtSignal(bool, str)   # ok, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clicky Setup")
        self.setModal(False)
        self.setMinimumSize(600, 420)
        self.setStyleSheet("""
            QDialog { background: #0e1014; color: #e8eaed; }
            QLabel  { color: #e8eaed; }
            QLabel#title { font-size: 22px; font-weight: 700; }
            QLabel#subtitle { color: #a0a3a8; font-size: 13px; }
            QLabel#status { color: #c8cbd0; font-size: 13px; }
            QPushButton {
                background: #1f6feb; color: white; border: none;
                padding: 10px 18px; border-radius: 8px;
                font-weight: 600; font-size: 13px;
            }
            QPushButton:hover  { background: #2f7fff; }
            QPushButton:disabled { background: #333; color: #888; }
            QPushButton#secondary {
                background: transparent; color: #a0a3a8;
                border: 1px solid #2a2d33;
            }
            QPushButton#secondary:hover { color: #e8eaed; border-color: #444; }
            QProgressBar {
                background: #1a1d22; border: 1px solid #2a2d33;
                border-radius: 6px; height: 12px; text-align: center;
                color: #e8eaed; font-size: 11px;
            }
            QProgressBar::chunk { background: #1f6feb; border-radius: 6px; }
        """)

        self._keys_dialog = None
        self._worker: threading.Thread | None = None
        self._next_step = "done"

        self._build_ui()
        self.progress_signal.connect(self._on_progress)
        self.finished_signal.connect(self._on_finished)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)

        self.title = QLabel("Welcome to Clicky")
        self.title.setObjectName("title")
        layout.addWidget(self.title)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addSpacing(8)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setObjectName("secondary")
        self.skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self.skip_btn)

        btn_row.addStretch(1)

        # Middle button — the "other option" on branching pages.
        self.alt_btn = QPushButton("")
        self.alt_btn.setObjectName("secondary")
        self.alt_btn.clicked.connect(self._on_alt)
        self.alt_btn.hide()
        btn_row.addWidget(self.alt_btn)

        self.action_btn = QPushButton("Get started")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.action_btn)

        layout.addLayout(btn_row)

        self._set_step("welcome")

    # ── State machine ────────────────────────────────────────────────────────

    def _set_step(self, step: str):
        self._step = step
        self.progress.hide()
        self.progress.setValue(0)
        self.status.setText("")
        self.alt_btn.hide()
        self.action_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.skip_btn.show()
        self.skip_btn.setText("Skip")

        if step == "welcome":
            self.title.setText("Meet Clicky")
            self.subtitle.setText(
                "Clicky is an AI tutor that lives next to your cursor and can see "
                "your screen — so it can point at things instead of just describing "
                "them.\n\n"
                f"•  Hold {_pretty_hotkey()} anywhere in Windows, or just say "
                "\"Clicky\", then ask your question out loud.\n"
                "•  Clicky answers by speaking, and draws arrows, circles and "
                "labels directly on your screen.\n"
                "•  Ask it about whatever you're looking at — a PDF, an error "
                "message, a chart, a settings page.\n"
                "•  Everything lives in the tray icon: modes, models, and "
                "settings.\n\n"
                "Next, pick the AI engine that powers it. Takes about a minute."
            )
            self.action_btn.setText("Continue")
            self.skip_btn.setText("Skip setup")

        elif step == "engine":
            self.title.setText("Choose your AI engine")
            self.subtitle.setText(
                "Free and offline — Ollama runs the AI on your own computer. "
                "No account, no API key, nothing leaves your machine. It needs a "
                "one-time model download of a couple of GB.\n\n"
                "Or bring your own key — Claude, OpenAI or Gemini. Faster and "
                "smarter, but the provider charges you and your screen is sent to "
                "their servers.\n\n"
                "You can change this at any time from the tray menu."
            )
            self.action_btn.setText("Use Ollama — free")
            self.alt_btn.setText("I'll use an API key")
            self.alt_btn.show()

        elif step == "detect":
            self.title.setText("Checking for Ollama…")
            self.subtitle.setText(
                "Looking for an existing Ollama installation before downloading "
                "anything."
            )
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Checking…")

        elif step == "install":
            self.title.setText("Install Ollama")
            self.subtitle.setText(
                "Ollama isn't on this computer yet. It's the engine that runs the "
                "AI locally — we'll download and install it for you (≈700 MB)."
            )
            self.action_btn.setText("Install Ollama")

        elif step == "installing":
            self.title.setText("Installing Ollama…")
            self.subtitle.setText(
                "Downloading the official installer from ollama.com, then launching "
                "it. Click through any UAC / installer prompts that appear."
            )
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Starting download…")
            self.progress.show()

        elif step == "text_model":
            name = cfg.ollama_text_model
            self.title.setText("Download the text model")
            self.subtitle.setText(
                f"Pulling {name} (≈2 GB). This is what answers when you ask Clicky "
                f"a question."
            )
            self.action_btn.setText(f"Pull {name}")
            self.skip_btn.setText("Skip this model")

        elif step == "pulling_text":
            self.title.setText(f"Pulling {cfg.ollama_text_model}…")
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Connecting to Ollama…")
            self.progress.show()

        elif step == "vision_model":
            name = cfg.ollama_vision_model
            self.title.setText("Download the vision model (optional)")
            self.subtitle.setText(
                f"Pulling {name} (≈3 GB). Needed only when Clicky reads your screen "
                f"— pointing, screenshots, reading charts. You can skip this and "
                f"add it later from the tray."
            )
            self.action_btn.setText(f"Pull {name}")
            self.skip_btn.setText("Skip — add later")

        elif step == "pulling_vision":
            self.title.setText(f"Pulling {cfg.ollama_vision_model}…")
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Connecting to Ollama…")
            self.progress.show()

        elif step == "keys":
            self.title.setText("Add an API key")
            self.subtitle.setText(
                "Paste a key for Claude, OpenAI or Gemini. Clicky saves it next to "
                "the app and starts using it right away — you can add, change or "
                "remove keys later from Tray → Setup & Diagnostics → API Keys."
            )
            self.action_btn.setText("Open API Keys…")
            self.alt_btn.setText("Use Ollama instead")
            self.alt_btn.show()
            self.skip_btn.setText("Skip for now")
            self._refresh_key_status()

        elif step == "done":
            self.title.setText("All set 🎉")
            providers = cfg.describe()
            self.subtitle.setText(
                f"Clicky is ready, running on {providers['llm']}.\n\n"
                f"•  Hold {_pretty_hotkey()} and speak, or say \"Clicky\".\n"
                "•  Press Esc to cut a long answer short.\n"
                "•  Right-click the tray icon for modes, models and settings.\n"
                "•  Drag a PDF onto the panel to ask questions about it."
            )
            self.action_btn.setText("Start using Clicky")
            self.skip_btn.hide()
            mark_setup_complete()

    def _refresh_key_status(self):
        have = [
            label for env_var, (_, label) in cfg.API_KEY_FIELDS.items()
            if cfg.get_api_key(env_var)
        ]
        self.status.setText(
            f"Configured: {', '.join(have)}" if have else "No keys set yet."
        )

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_action(self):
        s = self._step

        if s == "welcome":
            self._set_step("engine")

        elif s == "engine":
            self._set_step("detect")
            self._start_detect_worker()

        elif s == "install":
            self._set_step("installing")
            self._start_install_worker()

        elif s == "text_model":
            self._set_step("pulling_text")
            self._start_pull_worker(cfg.ollama_text_model)

        elif s == "vision_model":
            self._set_step("pulling_vision")
            self._start_pull_worker(cfg.ollama_vision_model)

        elif s == "keys":
            self._open_keys_dialog()

        elif s == "done":
            self.accept()

    def _on_alt(self):
        if self._step == "engine":
            self._set_step("keys")
        elif self._step == "keys":
            self._set_step("detect")
            self._start_detect_worker()

    def _on_skip(self):
        s = self._step
        if s in ("welcome", "engine", "install", "keys"):
            mark_setup_complete()
            self.reject()
        elif s == "text_model":
            self._set_step("vision_model")
        elif s == "vision_model":
            self._set_step("done")

    def _open_keys_dialog(self):
        from ui.api_keys_dialog import ApiKeysDialog
        dlg = ApiKeysDialog(self)
        dlg.keys_saved.connect(self._refresh_key_status)
        dlg.finished.connect(lambda _: self._on_keys_closed())
        dlg.show()
        self._keys_dialog = dlg   # keep a ref so Qt doesn't GC it

    def _on_keys_closed(self):
        self._refresh_key_status()
        if any(cfg.get_api_key(v) for v in cfg.API_KEY_FIELDS):
            self._set_step("done")

    # ── Workers (run on a background thread) ─────────────────────────────────

    def _start_detect_worker(self):
        """Find/start Ollama without downloading. Never blocks the UI thread."""
        def _worker():
            try:
                if ob.is_ollama_running():
                    self.finished_signal.emit(True, "running")
                    return
                if ob.is_ollama_installed():
                    self.progress_signal.emit(
                        "Ollama is installed — starting it…", 0.0
                    )
                    ok = ob.ensure_ollama_running(timeout=30)
                    self.finished_signal.emit(
                        ok,
                        "running" if ok else
                        "Ollama is installed but wouldn't start. Open it from the "
                        "Start menu, then click Try again."
                    )
                    return
                self.finished_signal.emit(False, "missing")
            except Exception as e:
                self.finished_signal.emit(False, f"Could not check Ollama: {e}")

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _start_install_worker(self):
        def _worker():
            try:
                self.progress_signal.emit("Downloading Ollama installer…", 0.0)
                path = ob.download_ollama_installer(
                    on_progress=lambda pct: self.progress_signal.emit(
                        f"Downloading… {pct:.0f}%", pct
                    )
                )
                self.progress_signal.emit(
                    "Launching installer (approve any UAC prompts)…", 100.0
                )
                ob.run_ollama_installer(path, silent=False)
                self.progress_signal.emit("Waiting for Ollama to start…", 100.0)
                if ob.ensure_ollama_running(timeout=90):
                    self.finished_signal.emit(True, "")
                else:
                    self.finished_signal.emit(
                        False,
                        "Ollama installed but didn't come online. Try rebooting, "
                        "or open Ollama from the Start menu, then re-run setup."
                    )
            except Exception as e:
                self.finished_signal.emit(False, f"Install failed: {e}")

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _start_pull_worker(self, model: str):
        def _worker():
            if ob.is_model_installed(model):
                self.finished_signal.emit(True, "")
                return
            ok = ob.pull_model(
                model,
                on_progress=lambda status, pct: self.progress_signal.emit(
                    f"{status} ({pct:.0f}%)" if pct else status, pct
                ),
            )
            self.finished_signal.emit(ok, "" if ok else f"Could not pull {model}.")

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _on_progress(self, status: str, pct: float):
        self.status.setText(status)
        self.progress.setValue(int(pct))

    def _on_finished(self, ok: bool, msg: str):
        s = self._step

        if s == "detect":
            if ok:
                self._goto_next_model_step()
            elif msg == "missing":
                self._set_step("install")
            else:
                self._set_step("install")
                self.status.setText(f"⚠️ {msg}")
            return

        if not ok:
            self.status.setText(f"⚠️ {msg}")
            self.action_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.action_btn.setText("Try again")
            return

        if s == "installing":
            self._goto_next_model_step()
        elif s == "pulling_text":
            self._set_step("vision_model")
        elif s == "pulling_vision":
            self._set_step("done")

    def _goto_next_model_step(self):
        # Skip straight past anything that's already pulled.
        if not ob.is_model_installed(cfg.ollama_text_model):
            self._set_step("text_model")
        elif not ob.is_model_installed(cfg.ollama_vision_model):
            self._set_step("vision_model")
        else:
            self._set_step("done")


def maybe_show_setup_wizard(parent=None) -> SetupWizard | None:
    """Open the wizard on first run.

    Unlike 1.2.0 this shows even when Ollama is already healthy — a silent
    first launch left new users with no idea what Clicky was or how to talk to
    it. The Ollama steps still skip themselves when there's nothing to do.
    """
    if setup_already_ran():
        return None

    w = SetupWizard(parent)
    w.show()
    return w
