"""
API Keys dialog.

Packaged installs had no way to enter an API key — config only ever read
.env, so a user who wanted Claude/OpenAI/Gemini had to find the install
folder and hand-edit a file next to Clicky.exe. This dialog is that missing
surface: paste a key, hit Save, and it applies immediately and persists.

Reachable from Tray → Setup & Diagnostics → API Keys…, and from the
"Use an API key instead" step of the first-run wizard.
"""

from __future__ import annotations

import os
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QWidget, QFrame, QCheckBox,
)

from config import cfg


# env var → (label, where to get one, what it unlocks)
PROVIDERS = [
    ("ANTHROPIC_API_KEY",  "Anthropic — Claude",
     "https://console.anthropic.com/settings/keys",
     "Best answers and screen understanding."),
    ("OPENAI_API_KEY",     "OpenAI — GPT",
     "https://platform.openai.com/api-keys",
     "Also upgrades speech-to-text and Clicky's voice."),
    ("GOOGLE_API_KEY",     "Google — Gemini",
     "https://aistudio.google.com/app/apikey",
     "Generous free tier."),
    ("ELEVENLABS_API_KEY", "ElevenLabs — voice (optional)",
     "https://elevenlabs.io/app/settings/api-keys",
     "Much more natural speech than the built-in voice."),
    ("DEEPGRAM_API_KEY",   "Deepgram — speech-to-text (optional)",
     "https://console.deepgram.com/",
     "Faster, more accurate transcription than local Whisper."),
    ("TAVILY_API_KEY",     "Tavily — web search (optional)",
     "https://app.tavily.com/home",
     "Better search results than the free DuckDuckGo fallback."),
]

# Adding one of these keys should also make Clicky start using that provider.
LLM_PROVIDER_FOR_KEY = {
    "ANTHROPIC_API_KEY": "claude",
    "OPENAI_API_KEY":    "openai",
    "GOOGLE_API_KEY":    "gemini",
}


STYLE = """
QDialog { background: #0e1014; color: #e8eaed; }
QLabel  { color: #e8eaed; }
QLabel#title    { font-size: 20px; font-weight: 700; }
QLabel#subtitle { color: #a0a3a8; font-size: 13px; }
QLabel#name     { font-size: 13px; font-weight: 600; }
QLabel#hint     { color: #8b8e94; font-size: 11px; }
QLabel#saved    { color: #3fb950; font-size: 12px; }
QLineEdit {
    background: #16181d; border: 1px solid #2a2d33; border-radius: 6px;
    padding: 8px 10px; color: #e8eaed; font-size: 12px;
}
QLineEdit:focus { border-color: #1f6feb; }
QPushButton {
    background: #1f6feb; color: white; border: none;
    padding: 9px 18px; border-radius: 8px; font-weight: 600; font-size: 13px;
}
QPushButton:hover { background: #2f7fff; }
QPushButton#secondary {
    background: transparent; color: #a0a3a8; border: 1px solid #2a2d33;
}
QPushButton#secondary:hover { color: #e8eaed; border-color: #444; }
QPushButton#link {
    background: transparent; color: #58a6ff; border: none;
    padding: 2px 0; font-size: 11px; font-weight: 500; text-align: left;
}
QPushButton#link:hover { color: #79c0ff; }
QCheckBox { color: #a0a3a8; font-size: 12px; }
QScrollArea { border: none; background: transparent; }
QWidget#scrollBody { background: transparent; }
QFrame#sep { background: #1e2127; max-height: 1px; border: none; }
"""


class ApiKeysDialog(QDialog):
    """Paste-a-key settings screen. Emits keys_saved when anything changed."""

    keys_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clicky — API Keys")
        self.setModal(False)
        self.setMinimumSize(560, 560)
        self.setStyleSheet(STYLE)

        self._edits: dict[str, QLineEdit] = {}
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(6)

        title = QLabel("API Keys")
        title.setObjectName("title")
        root.addWidget(title)

        subtitle = QLabel(
            "Clicky works with no keys at all using Ollama. Add a key here "
            "only if you want a cloud model instead — every field is optional."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        root.addSpacing(10)

        # scrollable provider list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("scrollBody")
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 10, 0)
        col.setSpacing(14)

        for i, (env_var, label, url, blurb) in enumerate(PROVIDERS):
            if i:
                sep = QFrame()
                sep.setObjectName("sep")
                sep.setFrameShape(QFrame.Shape.HLine)
                col.addWidget(sep)
            col.addLayout(self._provider_row(env_var, label, url, blurb))

        col.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # show/hide
        self._reveal = QCheckBox("Show keys")
        self._reveal.toggled.connect(self._on_reveal)
        root.addWidget(self._reveal)

        self._status = QLabel("")
        self._status.setObjectName("saved")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        where = QLabel(f"Saved to {cfg.env_path()}")
        where.setObjectName("hint")
        where.setWordWrap(True)
        root.addWidget(where)

        root.addSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(10)
        close = QPushButton("Close")
        close.setObjectName("secondary")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        row.addStretch(1)
        save = QPushButton("Save keys")
        save.clicked.connect(self._on_save)
        row.addWidget(save)
        root.addLayout(row)

    def _provider_row(self, env_var: str, label: str, url: str, blurb: str):
        col = QVBoxLayout()
        col.setSpacing(5)

        name = QLabel(label)
        name.setObjectName("name")
        col.addWidget(name)

        hint = QLabel(blurb)
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        col.addWidget(hint)

        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText("Paste key here — leave blank to skip")
        edit.setText(cfg.get_api_key(env_var))
        self._edits[env_var] = edit
        col.addWidget(edit)

        link = QPushButton(f"Get a key → {url}")
        link.setObjectName("link")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda _=False, u=url: webbrowser.open(u))
        col.addWidget(link)

        return col

    # ── Handlers ─────────────────────────────────────────────────────────

    def _on_reveal(self, shown: bool):
        mode = (QLineEdit.EchoMode.Normal if shown
                else QLineEdit.EchoMode.Password)
        for edit in self._edits.values():
            edit.setEchoMode(mode)

    def _on_save(self):
        changed, newly_added_llm = [], []

        for env_var, edit in self._edits.items():
            new = edit.text().strip()
            if new == cfg.get_api_key(env_var):
                continue
            cfg.set_api_key(env_var, new)
            changed.append(cfg.API_KEY_FIELDS[env_var][1])
            if new and env_var in LLM_PROVIDER_FOR_KEY:
                newly_added_llm.append(LLM_PROVIDER_FOR_KEY[env_var])

        if not changed:
            self._status.setText("No changes.")
            return

        # A provider pinned earlier (tray switch writes CLICKY_ACTIVE_LLM)
        # outranks the key-priority chain. Without these two adjustments,
        # pasting a key while pinned to Ollama silently changes nothing, and
        # deleting the pinned provider's key leaves Clicky pointed at a
        # provider that can no longer answer.
        if newly_added_llm:
            cfg.set_active_llm(newly_added_llm[0])
        elif (pinned := os.environ.get("CLICKY_ACTIVE_LLM", "").strip().lower()):
            if pinned not in cfg.available_llm_providers():
                cfg.clear_active_llm()

        active = cfg.llm_provider()
        self._status.setText(
            f"Saved: {', '.join(changed)}.  Now using: {active}."
        )
        self.keys_saved.emit()
