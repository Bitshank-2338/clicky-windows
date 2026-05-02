import asyncio
from enum import Enum, auto
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QCursor

from ui.design import (
    PANEL_QSS, PANEL_WIDTH, PANEL_HEIGHT, PANEL_RADIUS,
    STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_SPEAKING,
    FONT_TITLE, FONT_STATUS, FONT_RESPONSE, FONT_LABEL,
    SURFACE, TEXT_SECONDARY, BORDER, ANIM_FAST_MS
)
from config import cfg


class AppState(Enum):
    IDLE      = auto()
    LISTENING = auto()
    THINKING  = auto()
    SPEAKING  = auto()


STATE_LABELS = {
    AppState.IDLE:      "Say 'Clicky' or Ctrl+Alt+Space",
    AppState.LISTENING: "Listening...",
    AppState.THINKING:  "Thinking...",
    AppState.SPEAKING:  "Speaking...",
}

STATE_COLORS = {
    AppState.IDLE:      STATE_IDLE,
    AppState.LISTENING: STATE_LISTENING,
    AppState.THINKING:  STATE_THINKING,
    AppState.SPEAKING:  STATE_SPEAKING,
}


class WaveformWidget(QWidget):
    """Animated waveform bars shown while listening."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._levels = [0.0] * 12
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._decay)

    def set_level(self, rms: float):
        import random
        peak = min(1.0, rms * 3)
        self._levels = [min(1.0, peak * (0.4 + random.random() * 0.6)) for _ in self._levels]
        self.update()

    def _decay(self):
        self._levels = [max(0.0, v * 0.85) for v in self._levels]
        self.update()

    def start(self):
        self._timer.start(50)

    def stop(self):
        self._timer.stop()
        self._levels = [0.0] * 12
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bar_w = max(3, (w - 4 * len(self._levels)) // len(self._levels))
        spacing = (w - bar_w * len(self._levels)) // (len(self._levels) + 1)
        for i, level in enumerate(self._levels):
            x = spacing + i * (bar_w + spacing)
            bar_h = max(4, int(level * (h - 8)))
            y = (h - bar_h) // 2
            alpha = max(80, int(level * 255))
            color = QColor(0, 120, 255, alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_w, bar_h, bar_w // 2, bar_w // 2)
        painter.end()


PROVIDER_LABELS = {
    "claude":  "Claude",
    "openai":  "GPT-4o",
    "gemini":  "Gemini",
    "copilot": "Copilot",
    "ollama":  f"Ollama ({cfg.ollama_model})",
}

# Provider model lists are fetched live from each vendor's /models endpoint
# (see ai/model_registry.py for Claude/OpenAI/Gemini and
# ai/github_copilot_provider.py for Copilot). The hardcoded lists below are
# only used as offline fallbacks when no cache exists yet.


def _copilot_model_choices() -> list[tuple[str, str]]:
    """Returns [(model_id, display_label), ...] for the dropdown.
    Free models first, then ascending multiplier. Display shows '(free)' /
    '(1×)' so the user always knows what burns premium quota."""
    try:
        from ai.github_copilot_provider import (
            cached_models, sorted_model_ids, model_label,
        )
    except Exception:
        return [("gpt-4o-mini", "gpt-4o-mini  (free)")]
    out = []
    for mid in sorted_model_ids():
        out.append((mid, model_label(mid)))
    if not out:
        out.append(("gpt-4o-mini", "gpt-4o-mini  (free)"))
    return out


class ProviderBadge(QLabel):
    """Small pill showing active provider."""

    def __init__(self, provider: str, parent=None):
        super().__init__(parent)
        self.set_provider(provider)
        self.setStyleSheet(
            "background: rgba(0,120,255,25); border: 1px solid rgba(0,120,255,100);"
            "border-radius: 8px; color: rgb(140,180,255); font-size: 11px; padding: 2px 8px;"
        )

    def set_provider(self, provider: str):
        self.setText(PROVIDER_LABELS.get(provider, provider))


class CompanionPanel(QWidget):
    """Floating companion control panel — equivalent to CompanionPanelView.swift."""

    on_push_to_talk_pressed  = pyqtSignal()
    on_push_to_talk_released = pyqtSignal()
    on_model_changed         = pyqtSignal(str)
    on_document_dropped      = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._state = AppState.IDLE
        self._response_text = ""
        self._setup_window()
        self._build_ui()
        self._position_bottom_right()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)
        self.setObjectName("panel")
        self.setStyleSheet(PANEL_QSS)
        self.setAcceptDrops(True)   # drag-drop PDFs / DOCX / TXT

    # ── Drag-drop handlers ───────────────────────────────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.on_document_dropped.emit(path)
        event.acceptProposedAction()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Clicky")
        title.setObjectName("title")
        title.setFont(FONT_TITLE)
        header.addWidget(title)
        header.addStretch()
        provider = cfg.llm_provider()
        self._badge = ProviderBadge(provider)
        header.addWidget(self._badge)

        # Minimize button — hides the panel back to tray
        self._min_btn = QPushButton("—")
        self._min_btn.setFixedSize(24, 24)
        self._min_btn.setStyleSheet(
            "QPushButton { background: rgba(60,60,75,180); color: rgb(220,220,230);"
            "border: none; border-radius: 12px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(80,80,95,220); }"
        )
        self._min_btn.setToolTip("Hide panel (use tray to reopen)")
        self._min_btn.clicked.connect(self.hide)
        header.addWidget(self._min_btn)
        root.addLayout(header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(60,60,75,180);")
        root.addWidget(div)

        # Status row
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: rgb({STATE_IDLE.red()},{STATE_IDLE.green()},{STATE_IDLE.blue()}); font-size: 10px;")
        self._status_label = QLabel(STATE_LABELS[AppState.IDLE])
        self._status_label.setObjectName("status")
        self._status_label.setFont(FONT_STATUS)
        status_row = QHBoxLayout()
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        root.addLayout(status_row)

        # Waveform
        self._waveform = WaveformWidget()
        self._waveform.setVisible(False)
        root.addWidget(self._waveform)

        # Response area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._response_label = QLabel()
        self._response_label.setObjectName("response")
        self._response_label.setFont(FONT_RESPONSE)
        self._response_label.setWordWrap(True)
        self._response_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._response_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._response_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setWidget(self._response_label)
        root.addWidget(scroll, stretch=1)

        # Push-to-talk button
        self._ptt_btn = QPushButton("Say 'Clicky' or hold Ctrl+Alt+Space")
        self._ptt_btn.setObjectName("hotkey_btn")
        self._ptt_btn.setFont(FONT_LABEL)
        self._ptt_btn.setFixedHeight(44)
        root.addWidget(self._ptt_btn)

        # Footer: model selector + provider info
        footer = QHBoxLayout()
        lbl = QLabel("Model:")
        lbl.setFont(FONT_LABEL)
        lbl.setStyleSheet("color: rgb(100,100,120); font-size: 11px;")
        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet(
            "background: rgba(40,40,50,200); border: 1px solid rgba(60,60,75,180);"
            "border-radius: 6px; color: rgb(200,200,215); padding: 2px 6px; font-size: 11px;"
        )
        self._populate_models()
        # Emit the model id (stored in userData), not the display label
        self._model_combo.currentIndexChanged.connect(
            lambda _idx: self.on_model_changed.emit(
                self._model_combo.currentData() or self._model_combo.currentText()
            )
        )
        footer.addWidget(lbl)
        footer.addWidget(self._model_combo, stretch=1)
        root.addLayout(footer)

    def _populate_models(self):
        self._set_models_for(cfg.llm_provider())

    def _set_models_for(self, provider: str):
        # Avoid firing on_model_changed while we rebuild
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        if provider == "copilot":
            for mid, label in _copilot_model_choices():
                self._model_combo.addItem(label, userData=mid)
        elif provider in ("claude", "openai", "gemini"):
            try:
                from ai.model_registry import cached_models
                for m in cached_models(provider):
                    label = m["id"]
                    if not m.get("vision"):
                        label += "  (no vision)"
                    self._model_combo.addItem(label, userData=m["id"])
            except Exception:
                self._model_combo.addItem("default", userData="default")
        else:   # ollama
            self._model_combo.addItem(cfg.ollama_model, userData=cfg.ollama_model)
        self._model_combo.blockSignals(False)
        # Fire once with the new default model id (NOT the display label) so
        # the manager picks it up — important when label != id.
        if self._model_combo.count():
            self.on_model_changed.emit(self._model_combo.currentData() or self._model_combo.currentText())

    def refresh_for_provider(self, provider: str):
        """Called from outside when the active provider is switched at runtime."""
        self._badge.set_provider(provider)
        self._set_models_for(provider)

    def _position_bottom_right(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = screen.right() - PANEL_WIDTH - 24
        y = screen.bottom() - PANEL_HEIGHT - 60
        self.move(x, y)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_state(self, state: AppState):
        self._state = state
        color = STATE_COLORS[state]
        self._status_dot.setStyleSheet(
            f"color: rgb({color.red()},{color.green()},{color.blue()}); font-size: 10px;"
        )
        self._status_label.setText(STATE_LABELS[state])
        self._waveform.setVisible(state == AppState.LISTENING)
        if state == AppState.LISTENING:
            self._waveform.start()
        else:
            self._waveform.stop()

    def update_response(self, text: str):
        """Append streaming text chunk."""
        self._response_text = text
        self._response_label.setText(text)

    def append_response_chunk(self, chunk: str):
        self._response_text += chunk
        self._response_label.setText(self._response_text)

    def set_audio_level(self, rms: float):
        self._waveform.set_level(rms)

    def clear_response(self):
        self._response_text = ""
        self._response_label.setText("")

    def show_copilot_code(self, user_code: str, verification_uri: str):
        """Display the GitHub device code prominently in the panel (thread-safe via signal)."""
        # Must run on the Qt main thread — use a single-shot timer to hop threads
        from PyQt6.QtCore import QTimer
        def _do():
            self.show()   # make sure panel is visible
            self._response_text = (
                "── GitHub Copilot Sign-In ──\n\n"
                f"1.  Open:  {verification_uri}\n\n"
                f"2.  Enter code:\n\n"
                f"        {user_code}\n\n"
                "3.  Click Authorize in GitHub.\n\n"
                "Clicky will sign in automatically once you authorize."
            )
            self._response_label.setText(self._response_text)
            self._status_label.setText("Waiting for Copilot authorization…")
        QTimer.singleShot(0, _do)

    def show_copilot_error(self, error: str):
        from PyQt6.QtCore import QTimer
        def _do():
            self._response_text = f"Copilot login failed:\n\n{error}"
            self._response_label.setText(self._response_text)
        QTimer.singleShot(0, _do)

    # ── Mouse drag to reposition ──────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    # ── Painting: rounded glass background ───────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(18, 18, 22, 235)))
        painter.setPen(QPen(QColor(60, 60, 75, 180), 1))
        painter.drawRoundedRect(self.rect(), PANEL_RADIUS, PANEL_RADIUS)
        painter.end()
