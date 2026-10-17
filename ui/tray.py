from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QDialog, QVBoxLayout, QTextEdit,
    QPushButton, QLabel, QHBoxLayout,
)
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
    on_api_keys           = pyqtSignal()
    on_diagnostics        = pyqtSignal()
    on_set_mic_device     = pyqtSignal(int)     # sounddevice input device index
    on_set_response_language = pyqtSignal(str)  # "" = auto-detect, else ISO code
    on_set_stt_language      = pyqtSignal(str)  # "" = auto-detect, else ISO code
    on_set_custom_instructions = pyqtSignal(str)

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
            f"კლიკი — AI თანაშემწე\nდააჭირეთ {cfg.hotkey} და ილაპარაკეთ"
        )
        self._search_enabled = True
        # Mirrors the persisted mic mode — off by default, so Clicky only
        # listens while you're actually asking it something.
        self._wake_enabled = cfg.ambient_mic()
        self._response_language = ""
        try:
            from config import cfg as _cfg
            self._custom_instructions = _cfg.custom_instructions
        except Exception:
            self._custom_instructions = ""
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
            f"AI: {providers['llm']}  |  ამოცნობა: {providers['stt']}  |  ხმა: {providers['tts']}"
        )
        info.setEnabled(False)
        menu.addSeparator()

        show_action = menu.addAction("პანელის ჩვენება")
        show_action.triggered.connect(self.on_show_panel)

        hide_action = menu.addAction("პანელის დამალვა")
        hide_action.triggered.connect(self.on_hide_panel)

        stop_action = menu.addAction("გაჩერება (Esc)")
        stop_action.triggered.connect(self.on_stop)

        menu.addSeparator()

        # Model switcher submenu
        switch_menu = menu.addMenu(f"მოდელი: {providers['llm']}")
        active = providers['llm']
        for name in cfg.available_llm_providers():
            label = f"● {name}" if name == active else f"  {name}"
            act = switch_menu.addAction(label)
            act.triggered.connect(lambda _=False, n=name: self.on_switch_provider.emit(n))
        switch_menu.addSeparator()
        login_act = switch_menu.addAction("GitHub Copilot-ში შესვლა…")
        login_act.triggered.connect(self.on_copilot_login)
        refresh_act = switch_menu.addAction("Copilot-ის მოდელების განახლება")
        refresh_act.triggered.connect(self.on_copilot_refresh)

        # ── Ollama-specific submenu (always visible — Ollama is the offline fallback) ──
        self._build_ollama_submenu(menu, providers)

        menu.addSeparator()

        search_action = menu.addAction(
            "ინტერნეტში ძიება: ჩართულია" if self._search_enabled else "ინტერნეტში ძიება: გამორთულია"
        )
        search_action.setCheckable(True)
        search_action.setChecked(self._search_enabled)
        search_action.triggered.connect(self._toggle_search)
        self._search_action = search_action

        wake_action = menu.addAction(
            "მუდმივი მოსმენა („კლიკი“): ჩართულია" if self._wake_enabled
            else "მუდმივი მოსმენა („კლიკი“): გამორთულია — სალაპარაკოდ დააჭირეთ კლავიშებს"
        )
        wake_action.setCheckable(True)
        wake_action.setChecked(self._wake_enabled)
        wake_action.triggered.connect(self._toggle_wake)
        self._wake_action = wake_action

        self._build_language_submenu(menu)

        scope_label = "ინსტრუქციები კლიკისთვის…"
        scope_action = menu.addAction(scope_label)
        scope_action.triggered.connect(self._prompt_custom_instructions)

        # ── Tutor toggles ──
        menu.addSeparator()
        tutor_menu = menu.addMenu("სწავლების რეჟიმი")

        slow_action = tutor_menu.addAction(
            "ნელი რეჟიმი (მასწავლებლის ტემპი): ჩართულია" if self._slow_enabled
            else "ნელი რეჟიმი (მასწავლებლის ტემპი): გამორთულია"
        )
        slow_action.setCheckable(True)
        slow_action.setChecked(self._slow_enabled)
        slow_action.triggered.connect(self._toggle_slow)
        self._slow_action = slow_action

        quiz_action = tutor_menu.addAction(
            "ქვიზის რეჟიმი: ჩართულია" if self._quiz_enabled else "ქვიზის რეჟიმი: გამორთულია"
        )
        quiz_action.setCheckable(True)
        quiz_action.setChecked(self._quiz_enabled)
        quiz_action.triggered.connect(self._toggle_quiz)
        self._quiz_action = quiz_action

        privacy_action = tutor_menu.addAction(
            "კონფიდენციალურობის დაცვა: ჩართულია" if self._privacy_enabled
            else "კონფიდენციალურობის დაცვა: გამორთულია"
        )
        privacy_action.setCheckable(True)
        privacy_action.setChecked(self._privacy_enabled)
        privacy_action.triggered.connect(self._toggle_privacy)
        self._privacy_action = privacy_action

        code_action = tutor_menu.addAction(
            "კოდის რეჟიმი (ავტომატური): ჩართულია" if self._code_enabled else "კოდის რეჟიმი (ავტომატური): გამორთულია"
        )
        code_action.setCheckable(True)
        code_action.setChecked(self._code_enabled)
        code_action.triggered.connect(self._toggle_code)
        self._code_action = code_action

        ml_action = tutor_menu.addAction(
            "მრავალენოვანი: ჩართულია" if self._multilang_enabled else "მრავალენოვანი: გამორთულია"
        )
        ml_action.setCheckable(True)
        ml_action.setChecked(self._multilang_enabled)
        ml_action.triggered.connect(self._toggle_multilang)
        self._ml_action = ml_action

        ocr_action = tutor_menu.addAction(
            "ტექსტის ამოცნობა (OCR): ჩართულია" if self._ocr_enabled else "ტექსტის ამოცნობა (OCR): გამორთულია"
        )
        ocr_action.setCheckable(True)
        ocr_action.setChecked(self._ocr_enabled)
        ocr_action.triggered.connect(self._toggle_ocr)
        self._ocr_action = ocr_action

        # ── Journal ──
        menu.addSeparator()
        journal_menu = menu.addMenu("ჟურნალი")

        journal_action = journal_menu.addAction(
            "ჩაწერა: ჩართულია" if self._journal_enabled else "ჩაწერა: გამორთულია"
        )
        journal_action.setCheckable(True)
        journal_action.setChecked(self._journal_enabled)
        journal_action.triggered.connect(self._toggle_journal)
        self._journal_action = journal_action

        open_journal = journal_menu.addAction("ჟურნალის საქაღალდის გახსნა")
        open_journal.triggered.connect(self.on_journal_open)

        attach = journal_menu.addAction("დოკუმენტის მიმაგრება (PDF / TXT / DOCX)…")
        attach.triggered.connect(self.on_attach_doc)

        # ── Recording ──
        rec_menu = menu.addMenu("გაკვეთილის ჩაწერა")
        if self._is_recording:
            stop_rec = rec_menu.addAction("● ჩაწერის შეწყვეტა")
            stop_rec.triggered.connect(self.on_record_stop)
        else:
            start_rec = rec_menu.addAction("ჩაწერის დაწყება")
            start_rec.triggered.connect(self.on_record_start)

        # ── Workflow capture ──
        wf_menu = menu.addMenu("მოქმედებების ჩაწერა")
        wf_start = wf_menu.addAction("ჩემი დაწკაპუნებების ჩაწერის დაწყება")
        wf_start.triggered.connect(self.on_workflow_start)
        wf_stop  = wf_menu.addAction("შეწყვეტა და კლიკისთვის გაგზავნა")
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
        setup_menu = menu.addMenu("პარამეტრები && დიაგნოსტიკა")
        self._build_mic_submenu(setup_menu)
        self._build_stt_language_submenu(setup_menu)
        keys_act = setup_menu.addAction("API გასაღებები…")
        keys_act.triggered.connect(self.on_api_keys)
        run_setup = setup_menu.addAction("დაყენების ოსტატის ხელახლა გაშვება…")
        run_setup.triggered.connect(self.on_run_setup)
        diag = setup_menu.addAction("დიაგნოსტიკის ანგარიშის შენახვა…")
        diag.triggered.connect(self.on_diagnostics)

        menu.addSeparator()

        quit_action = menu.addAction("კლიკის დახურვა")
        quit_action.triggered.connect(self.on_quit)

        self._tray.setContextMenu(menu)
        # Keep refs to prevent GC
        self._menu = menu

    def hide_icon(self):
        """Remove the tray icon from the notification area. MUST run before
        app.quit(): killing the process without Shell_NotifyIcon(NIM_DELETE)
        leaves a ghost icon in the tray until hovered (GitHub issue #2)."""
        try:
            self._tray.hide()
        except Exception:
            pass

    def _prompt_custom_instructions(self):
        dlg = QDialog(None)
        dlg.setWindowTitle("ინსტრუქციები კლიკისთვის")
        dlg.setMinimumSize(480, 380)
        dlg.setStyleSheet("""
            QDialog { background-color: #1e1e24; }
            QLabel { color: #e8e8ec; font-size: 13px; }
            QTextEdit {
                background-color: #26262e; color: #f0f0f4;
                border: 1px solid #3a3a44; border-radius: 8px;
                padding: 10px; font-size: 13px;
            }
            QTextEdit:focus { border: 1px solid #7c5cff; }
            QPushButton {
                background-color: #3a3a44; color: #f0f0f4;
                border: none; border-radius: 6px; padding: 8px 18px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #47475400; }
            QPushButton#primary { background-color: #7c5cff; }
            QPushButton#primary:hover { background-color: #8f72ff; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        title = QLabel("ინსტრუქციები კლიკისთვის")
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #ffffff;")
        layout.addWidget(title)

        subtitle = QLabel(
            "ცვლის კლიკის ძირითად ქცევას (სახელი, წესები, ტონი).\n"
            "{{CONTEXT}} და {{TODAY}} ჩანაცვლების ადგილებია — სჯობს დატოვოთ."
        )
        subtitle.setStyleSheet("color: #9a9aa4; font-size: 12px;")
        layout.addWidget(subtitle)

        editor = QTextEdit()
        editor.setPlainText(self._custom_instructions)
        editor.setPlaceholderText("მაგ.: \"შენი სახელია მაქსი, მშვიდი თანაშემწე…\"")
        layout.addWidget(editor, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("გაუქმება")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn = QPushButton("შენახვა")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._custom_instructions = editor.toPlainText().strip()
            self.on_set_custom_instructions.emit(self._custom_instructions)

    def _build_stt_language_submenu(self, parent_menu: QMenu):
        """Pin the speech-recognition language.

        Separate from the reply language: this one controls what Whisper
        assumes it is hearing. Auto-detect re-decides every utterance, which is
        what makes code-mixed speech (Hinglish) transcribe inconsistently.
        """
        from tutor_features.multilang import _LANG_VOICE, display_name

        current = getattr(self, "_stt_language", "")
        label = display_name(current) if current else "ავტომატური"
        menu = parent_menu.addMenu(f"მეტყველების ამოცნობა: {label}")

        auto_act = menu.addAction("ავტომატური")
        auto_act.setCheckable(True)
        auto_act.setChecked(current == "")
        auto_act.triggered.connect(lambda: self.on_set_stt_language.emit(""))

        menu.addSeparator()
        for code in _LANG_VOICE:
            act = menu.addAction(display_name(code))
            act.setCheckable(True)
            act.setChecked(current == code)
            act.triggered.connect(
                lambda _=False, c=code: self.on_set_stt_language.emit(c)
            )

    def _build_language_submenu(self, parent_menu: QMenu):
        """Lets the user pin Clicky's reply language instead of relying on
        (sometimes unreliable) auto-detect from the transcript."""
        from tutor_features.multilang import _LANG_VOICE, display_name

        current = getattr(self, "_response_language", "")
        lang_menu = parent_menu.addMenu(
            f"პასუხის ენა: {display_name(current) if current else 'ავტომატური'}"
        )

        auto_act = lang_menu.addAction("ავტომატური")
        auto_act.setCheckable(True)
        auto_act.setChecked(current == "")
        auto_act.triggered.connect(lambda: self.on_set_response_language.emit(""))

        lang_menu.addSeparator()
        for code in _LANG_VOICE:
            act = lang_menu.addAction(display_name(code))
            act.setCheckable(True)
            act.setChecked(current == code)
            act.triggered.connect(lambda checked, c=code: self.on_set_response_language.emit(c))

    def _build_mic_submenu(self, parent_menu: QMenu):
        """Lists available input devices so the user can pick a mic without
        digging through Windows sound settings."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_idx = sd.default.device[0]
        except Exception:
            return  # sounddevice not ready yet — skip silently, not fatal

        mic_menu = parent_menu.addMenu("მიკროფონი")
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) <= 0:
                continue
            label = dev["name"]
            if idx == default_idx:
                label += "  (სისტემის ნაგულისხმევი)"
            act = mic_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(idx == getattr(self, "_active_mic_index", default_idx))
            act.triggered.connect(lambda checked, i=idx: self.on_set_mic_device.emit(i))

    def _build_ollama_submenu(self, parent_menu: QMenu, providers: dict):
        """Vision/Text model pickers + 'Pull recommended' for Ollama."""
        from ai.ollama_models_registry import (
            RECOMMENDED_VISION, RECOMMENDED_TEXT,
        )

        ol_menu = parent_menu.addMenu("Ollama")
        active_vision = providers.get("ollama_vision_model", "")
        active_text   = providers.get("ollama_text_model", "")

        # ─ Vision model picker ─
        v_menu = ol_menu.addMenu(f"ხედვის მოდელი: {active_vision or '(არცერთი)'}")
        installed_vision = self._ollama_installed.get("vision", [])
        if installed_vision:
            for name in installed_vision:
                label = f"● {name}" if name == active_vision else f"  {name}"
                act = v_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, n=name: self.on_ollama_set_model.emit("vision", n)
                )
        else:
            empty = v_menu.addAction("(ხედვის მოდელები არ არის დაყენებული)")
            empty.setEnabled(False)

        # ─ Text model picker ─
        t_menu = ol_menu.addMenu(f"ტექსტური მოდელი: {active_text or '(არცერთი)'}")
        installed_text = self._ollama_installed.get("text", [])
        if installed_text:
            for name in installed_text:
                label = f"● {name}" if name == active_text else f"  {name}"
                act = t_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, n=name: self.on_ollama_set_model.emit("text", n)
                )
        else:
            empty = t_menu.addAction("(ტექსტური მოდელები არ არის დაყენებული)")
            empty.setEnabled(False)

        ol_menu.addSeparator()

        # ─ Pull recommended ─
        pull_menu = ol_menu.addMenu("რეკომენდებულის ჩამოტვირთვა…")
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

        _add_recs(RECOMMENDED_VISION, "── ხედვა ──")
        pull_menu.addSeparator()
        _add_recs(RECOMMENDED_TEXT, "── ტექსტი ──")

        ol_menu.addSeparator()
        refresh_act = ol_menu.addAction("დაყენებული მოდელების განახლება")
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
            "ინტერნეტში ძიება: ჩართულია" if checked else "ინტერნეტში ძიება: გამორთულია"
        )
        self.on_toggle_search.emit(checked)

    def _toggle_wake(self, checked: bool):
        self._wake_enabled = checked
        self._wake_action.setText(
            "მუდმივი მოსმენა („კლიკი“): ჩართულია" if checked else "მუდმივი მოსმენა („კლიკი“): გამორთულია"
        )
        self.on_toggle_wake_word.emit(checked)

    def _toggle_slow(self, checked: bool):
        self._slow_enabled = checked
        self._slow_action.setText(
            "ნელი რეჟიმი (მასწავლებლის ტემპი): ჩართულია" if checked
            else "ნელი რეჟიმი (მასწავლებლის ტემპი): გამორთულია"
        )
        self.on_toggle_slow_mode.emit(checked)

    def _toggle_quiz(self, checked: bool):
        self._quiz_enabled = checked
        self._quiz_action.setText(
            "ქვიზის რეჟიმი: ჩართულია" if checked else "ქვიზის რეჟიმი: გამორთულია"
        )
        self.on_toggle_quiz_mode.emit(checked)

    def _toggle_privacy(self, checked: bool):
        self._privacy_enabled = checked
        self._privacy_action.setText(
            "კონფიდენციალურობის დაცვა: ჩართულია" if checked else "კონფიდენციალურობის დაცვა: გამორთულია"
        )
        self.on_toggle_privacy.emit(checked)

    def _toggle_code(self, checked: bool):
        self._code_enabled = checked
        self._code_action.setText(
            "კოდის რეჟიმი (ავტომატური): ჩართულია" if checked else "კოდის რეჟიმი (ავტომატური): გამორთულია"
        )
        self.on_toggle_code_mode.emit(checked)

    def _toggle_multilang(self, checked: bool):
        self._multilang_enabled = checked
        self._ml_action.setText(
            "მრავალენოვანი: ჩართულია" if checked else "მრავალენოვანი: გამორთულია"
        )
        self.on_toggle_multilang.emit(checked)

    def _toggle_ocr(self, checked: bool):
        self._ocr_enabled = checked
        self._ocr_action.setText(
            "ტექსტის ამოცნობა (OCR): ჩართულია" if checked else "ტექსტის ამოცნობა (OCR): გამორთულია"
        )
        self.on_toggle_ocr.emit(checked)

    def _toggle_journal(self, checked: bool):
        self._journal_enabled = checked
        self._journal_action.setText(
            "ჩაწერა: ჩართულია" if checked else "ჩაწერა: გამორთულია"
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
