"""
First-run setup wizard.

Shown once on the first launch (or whenever the user clicks
"Tray → Run setup again…"). Walks the user through:

  1. Detect Ollama       → install if missing
  2. Detect text model   → pull if missing
  3. Detect vision model → pull if missing  (optional, larger)

Everything is optional — the user can Skip at any step and use API keys
instead. The wizard never blocks the main app from starting; the user can
close it and Clicky's panel banner will keep nagging until Ollama is set up.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QWidget, QStackedWidget, QSizePolicy
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


# ─── Wizard ───────────────────────────────────────────────────────────────────

class SetupWizard(QDialog):
    """One-window wizard with three pages: Ollama install → text model → vision model."""

    progress_signal = pyqtSignal(str, float)
    finished_signal = pyqtSignal(bool, str)   # ok, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clicky Setup")
        self.setModal(False)
        self.setMinimumSize(560, 380)
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

        self._build_ui()
        self.progress_signal.connect(self._on_progress)
        self.finished_signal.connect(self._on_finished)
        self._worker: threading.Thread | None = None

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)

        self.title = QLabel("Welcome to Clicky")
        self.title.setObjectName("title")
        layout.addWidget(self.title)

        self.subtitle = QLabel(
            "Clicky uses Ollama to run AI locally on your computer — for free, "
            "with no API keys required. Let's set it up in 2 minutes."
        )
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        # status block
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

        # buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.skip_btn = QPushButton("Skip — I'll use an API key")
        self.skip_btn.setObjectName("secondary")
        self.skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self.skip_btn)

        btn_row.addStretch(1)

        self.action_btn = QPushButton("Get started")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.action_btn)

        layout.addLayout(btn_row)

        self._set_step("intro")

    # ── State machine ────────────────────────────────────────────────────────

    def _set_step(self, step: str):
        self._step = step
        self.progress.hide()
        self.progress.setValue(0)

        if step == "intro":
            running = ob.is_ollama_running()
            if running:
                self.title.setText("Ollama detected ✓")
                self.subtitle.setText(
                    "Ollama is already running on your machine. We'll just check that "
                    "the AI models you need are downloaded."
                )
                self.action_btn.setText("Check models")
            else:
                self.title.setText("Step 1 of 3 — Install Ollama")
                self.subtitle.setText(
                    "Ollama is the engine that runs the AI on your computer. "
                    "We'll download and install it for you (≈700 MB)."
                )
                self.action_btn.setText("Install Ollama")
            self.status.setText("")

        elif step == "installing":
            self.title.setText("Installing Ollama…")
            self.subtitle.setText(
                "Downloading the official installer from ollama.com, then launching it. "
                "Click through any UAC / installer prompts that appear."
            )
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Starting download…")
            self.progress.show()

        elif step == "text_model":
            name = cfg.ollama_text_model
            self.title.setText("Step 2 of 3 — Download text model")
            self.subtitle.setText(
                f"Pulling {name} (≈2 GB). This is what answers when you ask Clicky a question."
            )
            self.action_btn.setText(f"Pull {name}")
            self.action_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.skip_btn.setText("Skip this model")
            self.status.setText("")

        elif step == "pulling_text":
            self.title.setText(f"Pulling {cfg.ollama_text_model}…")
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Connecting to Ollama…")
            self.progress.show()

        elif step == "vision_model":
            name = cfg.ollama_vision_model
            self.title.setText("Step 3 of 3 — Download vision model (optional)")
            self.subtitle.setText(
                f"Pulling {name} (≈3 GB). Needed only when Clicky reads your screen "
                f"(Pixel-Perfect Pointing, screenshots). You can skip this and add it later."
            )
            self.action_btn.setText(f"Pull {name}")
            self.action_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.skip_btn.setText("Skip — add later")
            self.status.setText("")

        elif step == "pulling_vision":
            self.title.setText(f"Pulling {cfg.ollama_vision_model}…")
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Connecting to Ollama…")
            self.progress.show()

        elif step == "done":
            self.title.setText("All set 🎉")
            self.subtitle.setText(
                "Clicky is ready. Press Ctrl+Alt+Space anywhere on Windows, "
                "or just say \"Clicky\" to start a conversation."
            )
            self.action_btn.setText("Start using Clicky")
            self.action_btn.setEnabled(True)
            self.skip_btn.hide()
            self.status.setText("")
            mark_setup_complete()

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_action(self):
        s = self._step
        if s == "intro":
            if ob.is_ollama_running():
                self._goto_next_model_step()
            else:
                self._set_step("installing")
                self._start_install_worker()

        elif s == "text_model":
            self._set_step("pulling_text")
            self._start_pull_worker(cfg.ollama_text_model, next_step="vision_model")

        elif s == "vision_model":
            self._set_step("pulling_vision")
            self._start_pull_worker(cfg.ollama_vision_model, next_step="done")

        elif s == "done":
            self.accept()

    def _on_skip(self):
        s = self._step
        if s == "intro":
            mark_setup_complete()
            self.reject()
        elif s == "text_model":
            self._set_step("vision_model")
        elif s == "vision_model":
            self._set_step("done")

    # ── Workers (run on a background thread) ─────────────────────────────────

    def _start_install_worker(self):
        def _worker():
            try:
                self.progress_signal.emit("Downloading Ollama installer…", 0.0)
                path = ob.download_ollama_installer(
                    on_progress=lambda pct: self.progress_signal.emit(
                        f"Downloading… {pct:.0f}%", pct
                    )
                )
                self.progress_signal.emit("Launching installer (approve any UAC prompts)…", 100.0)
                ob.run_ollama_installer(path, silent=False)
                self.progress_signal.emit("Waiting for Ollama to start…", 100.0)
                ok = ob.wait_for_ollama_server(timeout=90)
                if ok:
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

    def _start_pull_worker(self, model: str, next_step: str):
        self._next_step = next_step

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
        if not ok:
            self.status.setText(f"⚠️ {msg}")
            self.action_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.action_btn.setText("Try again")
            return

        s = self._step
        if s == "installing":
            self._goto_next_model_step()
        elif s == "pulling_text":
            self._set_step("vision_model")
        elif s == "pulling_vision":
            self._set_step("done")

    def _goto_next_model_step(self):
        # If text model already there, jump straight to vision step.
        if not ob.is_model_installed(cfg.ollama_text_model):
            self._set_step("text_model")
        elif not ob.is_model_installed(cfg.ollama_vision_model):
            self._set_step("vision_model")
        else:
            self._set_step("done")


def maybe_show_setup_wizard(parent=None) -> SetupWizard | None:
    """Open the wizard only if it hasn't run before AND something is missing."""
    if setup_already_ran():
        return None
    if (
        ob.is_ollama_running()
        and ob.is_model_installed(cfg.ollama_text_model)
    ):
        # Everything is already wired up — don't pester the user.
        mark_setup_complete()
        return None

    w = SetupWizard(parent)
    w.show()
    return w
