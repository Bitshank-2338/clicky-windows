from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject

from config import cfg


def _make_tray_icon(color: QColor) -> QIcon:
    """Generate a simple coloured circle as the tray icon.
    Must be called AFTER QApplication exists (Qt requirement)."""
    px = QPixmap(QSize(22, 22))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(3, 3, 16, 16)
    painter.end()
    return QIcon(px)


class TrayManager(QObject):
    """Windows system tray icon and context menu."""

    on_show_panel         = pyqtSignal()
    on_hide_panel         = pyqtSignal()
    on_quit               = pyqtSignal()
    on_toggle_search      = pyqtSignal(bool)
    on_toggle_wake_word   = pyqtSignal(bool)
    on_toggle_slow_mode   = pyqtSignal(bool)
    on_toggle_quiz_mode   = pyqtSignal(bool)
    on_toggle_privacy     = pyqtSignal(bool)
    on_switch_provider    = pyqtSignal(str)     # "claude" | "openai" | "copilot" | ...
    on_copilot_login      = pyqtSignal()
    on_copilot_refresh    = pyqtSignal()
    on_ollama_set_model   = pyqtSignal(str, str)   # (kind, name): kind = "vision" | "text"
    on_ollama_pull        = pyqtSignal(str)        # model name
    on_ollama_refresh     = pyqtSignal()
    on_stop               = pyqtSignal()
    on_toggle_code_mode   = pyqtSignal(bool)
    on_toggle_multilang   = pyqtSignal(bool)
    on_toggle_journal     = pyqtSignal(bool)
    on_toggle_ocr         = pyqtSignal(bool)
    on_record_start       = pyqtSignal()
    on_record_stop        = pyqtSignal()
    on_collab_start       = pyqtSignal()
    on_collab_join        = pyqtSignal()
    on_workflow_start     = pyqtSignal()
    on_workflow_stop      = pyqtSignal()
    on_journal_open       = pyqtSignal()
    on_attach_doc         = pyqtSignal()
    on_run_setup          = pyqtSignal()
    on_diagnostics        = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Icons MUST be created after QApplication exists
        self._icons = {
            "idle":      _make_tray_icon(QColor(80, 80, 120)),
            "listening": _make_tray_icon(QColor(50, 200, 100)),
            "thinking":  _make_tray_icon(QColor(0, 120, 255)),
            "speaking":  _make_tray_icon(QColor(255, 140, 0)),
        }

        self._tray = QSystemTrayIcon()
        self._tray.setIcon(self._icons["idle"])
        self._tray.setToolTip(
            f"Clicky - AI Companion\nHold {cfg.hotkey} to speak"
        )
        self._search_enabled = True
        self._wake_enabled = True
        self._slow_enabled = False
        self._quiz_enabled = False
        self._privacy_enabled = True
        self._code_enabled = True
        self._multilang_enabled = True
        self._journal_enabled = True
        self._ocr_enabled = True
        self._is_recording = False

        # Ollama model state — populated by manager via set_ollama_models()
        self._ollama_installed: dict[str, list[str]] = {"vision": [], "text": []}

        self._build_menu()
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: rgb(22,22,28); border: 1px solid rgb(55,55,70);"
            "border-radius: 8px; color: rgb(220,220,230); font-size: 13px; }"
            "QMenu::item:selected { background: rgb(0,90,200); border-radius: 4px; }"
            "QMenu::separator { height: 1px; background: rgb(55,55,70); margin: 4px 8px; }"
        )

        providers = cfg.describe()
        info = menu.addAction(
            f"LLM: {providers['llm']}  |  STT: {providers['stt']}  |  TTS: {providers['tts']}"
        )
        info.setEnabled(False)
        menu.addSeparator()

        show_action = menu.addAction("Show Panel")
        show_action.triggered.connect(self.on_show_panel)

        hide_action = menu.addAction("Hide Panel")
        hide_action.triggered.connect(self.on_hide_panel)

        stop_action = menu.addAction("Stop (Esc)")
        stop_action.triggered.connect(self.on_stop)

        menu.addSeparator()

        # Model switcher submenu
        switch_menu = menu.addMenu(f"Model: {providers['llm']}")
        active = providers['llm']
        for name in cfg.available_llm_providers():
            label = f"● {name}" if name == active else f"  {name}"
            act = switch_menu.addAction(label)
            act.triggered.connect(lambda _=False, n=name: self.on_switch_provider.emit(n))
        switch_menu.addSeparator()
        login_act = switch_menu.addAction("Sign in to GitHub Copilot…")
        login_act.triggered.connect(self.on_copilot_login)
        refresh_act = switch_menu.addAction("Refresh Copilot models")
        refresh_act.triggered.connect(self.on_copilot_refresh)

        # ── Ollama-specific submenu (always visible — Ollama is the offline fallback) ──
        self._build_ollama_submenu(menu, providers)

        menu.addSeparator()

        search_action = menu.addAction(
            "Web Search: ON" if self._search_enabled else "Web Search: OFF"
        )
        search_action.setCheckable(True)
        search_action.setChecked(self._search_enabled)
        search_action.triggered.connect(self._toggle_search)
        self._search_action = search_action

        wake_action = menu.addAction(
            "Wake word 'Clicky': ON" if self._wake_enabled else "Wake word 'Clicky': OFF"
        )
        wake_action.setCheckable(True)
        wake_action.setChecked(self._wake_enabled)
        wake_action.triggered.connect(self._toggle_wake)
        self._wake_action = wake_action

        # ── Tutor toggles ──
        menu.addSeparator()
        tutor_menu = menu.addMenu("Tutor Mode")

        slow_action = tutor_menu.addAction(
            "Slow Mode (teacher pace): ON" if self._slow_enabled
            else "Slow Mode (teacher pace): OFF"
        )
        slow_action.setCheckable(True)
        slow_action.setChecked(self._slow_enabled)
        slow_action.triggered.connect(self._toggle_slow)
        self._slow_action = slow_action

        quiz_action = tutor_menu.addAction(
            "Quiz Mode: ON" if self._quiz_enabled else "Quiz Mode: OFF"
        )
        quiz_action.setCheckable(True)
        quiz_action.setChecked(self._quiz_enabled)
        quiz_action.triggered.connect(self._toggle_quiz)
        self._quiz_action = quiz_action

        privacy_action = tutor_menu.addAction(
            "Privacy Guard: ON" if self._privacy_enabled
            else "Privacy Guard: OFF"
        )
        privacy_action.setCheckable(True)
        privacy_action.setChecked(self._privacy_enabled)
        privacy_action.triggered.connect(self._toggle_privacy)
        self._privacy_action = privacy_action

        code_action = tutor_menu.addAction(
            "Code Mode (auto): ON" if self._code_enabled else "Code Mode (auto): OFF"
        )
        code_action.setCheckable(True)
        code_action.setChecked(self._code_enabled)
        code_action.triggered.connect(self._toggle_code)
        self._code_action = code_action

        ml_action = tutor_menu.addAction(
            "Multilingual: ON" if self._multilang_enabled else "Multilingual: OFF"
        )
        ml_action.setCheckable(True)
        ml_action.setChecked(self._multilang_enabled)
        ml_action.triggered.connect(self._toggle_multilang)
        self._ml_action = ml_action

        ocr_action = tutor_menu.addAction(
            "OCR Fallback: ON" if self._ocr_enabled else "OCR Fallback: OFF"
        )
        ocr_action.setCheckable(True)
        ocr_action.setChecked(self._ocr_enabled)
        ocr_action.triggered.connect(self._toggle_ocr)
        self._ocr_action = ocr_action

        # ── Journal ──
        menu.addSeparator()
        journal_menu = menu.addMenu("Journal")

        journal_action = journal_menu.addAction(
            "Logging: ON" if self._journal_enabled else "Logging: OFF"
        )
        journal_action.setCheckable(True)
        journal_action.setChecked(self._journal_enabled)
        journal_action.triggered.connect(self._toggle_journal)
        self._journal_action = journal_action

        open_journal = journal_menu.addAction("Open journal folder")
        open_journal.triggered.connect(self.on_journal_open)

        attach = journal_menu.addAction("Attach document (PDF / TXT / DOCX)…")
        attach.triggered.connect(self.on_attach_doc)

        # ── Recording ──
        rec_menu = menu.addMenu("Lesson Recording")
        if self._is_recording:
            stop_rec = rec_menu.addAction("● Stop recording")
            stop_rec.triggered.connect(self.on_record_stop)
        else:
            start_rec = rec_menu.addAction("Start recording")
            start_rec.triggered.connect(self.on_record_start)

        # ── Workflow capture ──
        wf_menu = menu.addMenu("Workflow Capture")
        wf_start = wf_menu.addAction("Start capturing my clicks")
        wf_start.triggered.connect(self.on_workflow_start)
        wf_stop  = wf_menu.addAction("Stop + send to Clicky")
        wf_stop.triggered.connect(self.on_workflow_stop)

        # ── Live collaboration ──
        # NOTE: WebRTC signalling server isn't shipped yet, so this whole
        # menu is hidden until tutor_features/collab.py gets a real backend.
        # The signals are still defined on this object so any existing
        # bindings in main.py don't crash on connect().
        # collab_menu = menu.addMenu("Live Session")  # disabled in this build
        # host = collab_menu.addAction("Start hosting")
        # host.triggered.connect(self.on_collab_start)
        # join = collab_menu.addAction("Join with code…")
        # join.triggered.connect(self.on_collab_join)

        menu.addSeparator()

        # ── Setup / Diagnostics ──
        setup_menu = menu.addMenu("Setup && Diagnostics")
        run_setup = setup_menu.addAction("Run setup wizard again…")
        run_setup.triggered.connect(self.on_run_setup)
        diag = setup_menu.addAction("Save diagnostics report…")
        diag.triggered.connect(self.on_diagnostics)

        menu.addSeparator()

        quit_action = menu.addAction("Quit Clicky")
        quit_action.triggered.connect(self.on_quit)

        self._tray.setContextMenu(menu)
        # Keep refs to prevent GC
        self._menu = menu

    def _build_ollama_submenu(self, parent_menu: QMenu, providers: dict):
        """Vision/Text model pickers + 'Pull recommended' for Ollama."""
        from ai.ollama_models_registry import (
            RECOMMENDED_VISION, RECOMMENDED_TEXT,
        )

        ol_menu = parent_menu.addMenu("Ollama")
        active_vision = providers.get("ollama_vision_model", "")
        active_text   = providers.get("ollama_text_model", "")

        # ─ Vision model picker ─
        v_menu = ol_menu.addMenu(f"Vision model: {active_vision or '(none)'}")
        installed_vision = self._ollama_installed.get("vision", [])
        if installed_vision:
            for name in installed_vision:
                label = f"● {name}" if name == active_vision else f"  {name}"
                act = v_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, n=name: self.on_ollama_set_model.emit("vision", n)
                )
        else:
            empty = v_menu.addAction("(no vision models installed)")
            empty.setEnabled(False)

        # ─ Text model picker ─
        t_menu = ol_menu.addMenu(f"Text model: {active_text or '(none)'}")
        installed_text = self._ollama_installed.get("text", [])
        if installed_text:
            for name in installed_text:
                label = f"● {name}" if name == active_text else f"  {name}"
                act = t_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, n=name: self.on_ollama_set_model.emit("text", n)
                )
        else:
            empty = t_menu.addAction("(no text models installed)")
            empty.setEnabled(False)

        ol_menu.addSeparator()

        # ─ Pull recommended ─
        pull_menu = ol_menu.addMenu("Pull recommended…")
        already = set(installed_vision) | set(installed_text)

        def _add_recs(rec_list, header):
            hdr = pull_menu.addAction(header)
            hdr.setEnabled(False)
            for rec in rec_list:
                # Mark already-installed entries (matching by tag prefix)
                installed = any(n == rec.name or n.startswith(rec.name.split(":")[0] + ":") for n in already)
                tag = "✓ " if installed else "  "
                label = f"{tag}{rec.label}  ·  {rec.size}  —  {rec.blurb}"
                act = pull_menu.addAction(label)
                if installed:
                    act.setEnabled(False)
                else:
                    act.triggered.connect(
                        lambda _=False, n=rec.name: self.on_ollama_pull.emit(n)
                    )

        _add_recs(RECOMMENDED_VISION, "── Vision ──")
        pull_menu.addSeparator()
        _add_recs(RECOMMENDED_TEXT, "── Text ──")

        ol_menu.addSeparator()
        refresh_act = ol_menu.addAction("Refresh installed models")
        refresh_act.triggered.connect(self.on_ollama_refresh)

    def set_ollama_models(self, classified: dict):
        """Called by the manager after polling /api/tags. Triggers menu rebuild."""
        self._ollama_installed = {
            "vision": list(classified.get("vision", [])),
            "text":   list(classified.get("text", [])),
        }
        self.rebuild_menu()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.on_show_panel.emit()

    def _toggle_search(self, checked: bool):
        self._search_enabled = checked
        self._search_action.setText(
            "Web Search: ON" if checked else "Web Search: OFF"
        )
        self.on_toggle_search.emit(checked)

    def _toggle_wake(self, checked: bool):
        self._wake_enabled = checked
        self._wake_action.setText(
            "Wake word 'Clicky': ON" if checked else "Wake word 'Clicky': OFF"
        )
        self.on_toggle_wake_word.emit(checked)

    def _toggle_slow(self, checked: bool):
        self._slow_enabled = checked
        self._slow_action.setText(
            "Slow Mode (teacher pace): ON" if checked
            else "Slow Mode (teacher pace): OFF"
        )
        self.on_toggle_slow_mode.emit(checked)

    def _toggle_quiz(self, checked: bool):
        self._quiz_enabled = checked
        self._quiz_action.setText(
            "Quiz Mode: ON" if checked else "Quiz Mode: OFF"
        )
        self.on_toggle_quiz_mode.emit(checked)

    def _toggle_privacy(self, checked: bool):
        self._privacy_enabled = checked
        self._privacy_action.setText(
            "Privacy Guard: ON" if checked else "Privacy Guard: OFF"
        )
        self.on_toggle_privacy.emit(checked)

    def _toggle_code(self, checked: bool):
        self._code_enabled = checked
        self._code_action.setText(
            "Code Mode (auto): ON" if checked else "Code Mode (auto): OFF"
        )
        self.on_toggle_code_mode.emit(checked)

    def _toggle_multilang(self, checked: bool):
        self._multilang_enabled = checked
        self._ml_action.setText(
            "Multilingual: ON" if checked else "Multilingual: OFF"
        )
        self.on_toggle_multilang.emit(checked)

    def _toggle_ocr(self, checked: bool):
        self._ocr_enabled = checked
        self._ocr_action.setText(
            "OCR Fallback: ON" if checked else "OCR Fallback: OFF"
        )
        self.on_toggle_ocr.emit(checked)

    def _toggle_journal(self, checked: bool):
        self._journal_enabled = checked
        self._journal_action.setText(
            "Logging: ON" if checked else "Logging: OFF"
        )
        self.on_toggle_journal.emit(checked)

    def set_recording_state(self, on: bool):
        self._is_recording = on
        self.rebuild_menu()

    def set_state_icon(self, state: str):
        self._tray.setIcon(self._icons.get(state, self._icons["idle"]))

    def rebuild_menu(self):
        """Rebuild so the Model submenu reflects the newly-active provider."""
        self._build_menu()

    def show_notification(self, title: str, message: str):
        self._tray.showMessage(
            title, message, QSystemTrayIcon.MessageIcon.Information, 3000
        )

    @property
    def search_enabled(self) -> bool:
        return self._search_enabled
