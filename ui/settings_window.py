"""Clicky's native settings, history and first-run feature guide."""
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QTabWidget, QLabel, QCheckBox, QComboBox, QLineEdit, QSpinBox, QPushButton, QPlainTextEdit, QMessageBox, QProgressBar
from config import cfg
from storage import setting, set_setting, data_dir


class SettingsWindow(QWidget):
    update_ready = pyqtSignal(object)
    installer_ready = pyqtSignal(str)
    shortcuts_changed = pyqtSignal()
    open_keys = pyqtSignal()
    preview_voice = pyqtSignal()
    show_sketch = pyqtSignal()
    show_work = pyqtSignal()
    open_connections = pyqtSignal()
    microphone_level = pyqtSignal(float)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.setWindowTitle("Clicky Settings")
        self.resize(620, 600)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        behavior = QWidget()
        form = QFormLayout(behavior)
        for label,key,default,callback in (
            ("Protect sensitive screens",'privacy_guard',True,manager.set_privacy_guard),
            ("Allow web searches for current facts",'web_search',False,manager.set_web_search),
            ("Keep local history and study journal",'journal',True,manager.set_journal),
            ("Reply in my language",'multilang',True,manager.set_multilang),
            ("Enable OCR",'ocr',True,manager.set_ocr_enabled),
            ("Use code context in editors",'code_mode',True,manager.set_code_mode_auto),
        ):
            box = QCheckBox(label)
            box.setChecked(setting(key,default))
            box.toggled.connect(lambda value, call=callback:self.apply(lambda:call(value)))
            form.addRow(box)
        privacy_note = QLabel("Privacy Guard masks windows with sensitive titles on every monitor. It cannot recognize every secret in an ordinary document. Workflow capture never records typed characters.")
        privacy_note.setWordWrap(True)
        form.addRow(privacy_note)
        keys = QPushButton("Manage protected API keys…")
        keys.clicked.connect(self.open_keys.emit)
        form.addRow(keys)
        connections = QPushButton("Browser and app connections…")
        connections.clicked.connect(self.open_connections.emit)
        form.addRow(connections)
        tabs.addTab(behavior,"General")

        voice_page = QWidget()
        voice = QFormLayout(voice_page)
        self.provider = QComboBox()
        for label,value in (("Automatic",'auto'),("Windows voice — offline",'sapi'),("Edge — internet",'edge_tts'),("OpenAI — API key",'openai'),("ElevenLabs — API key",'elevenlabs')):
            self.provider.addItem(label,value)
        self.provider.setCurrentIndex(max(0,self.provider.findData(setting('tts_provider','auto'))))
        voice.addRow("Speech provider",self.provider)
        self.transcription = QComboBox()
        for label,value in (("Automatic",''),("Local Whisper",'faster_whisper'),("Local whisper.cpp",'whisper_cpp'),("Deepgram — internet",'deepgram'),("OpenAI Whisper — internet",'openai')):
            self.transcription.addItem(label,value)
        import os
        self.transcription.setCurrentIndex(max(0,self.transcription.findData(os.getenv('CLICKY_STT',''))))
        voice.addRow("Speech recognition",self.transcription)
        self.voice_name = QLineEdit(setting('voice' if cfg.tts_provider()=='sapi' else 'voice_'+cfg.tts_provider(),''))
        self.voice_name.setPlaceholderText("Installed Windows voice, Edge name, or provider voice ID")
        voice.addRow("Voice (blank uses default)",self.voice_name)
        self.rate = QSpinBox()
        self.rate.setRange(-10,10)
        self.rate.setValue(setting('speech_rate',0))
        voice.addRow("Speech speed",self.rate)
        self.captions = QCheckBox("Show narration captions")
        self.captions.setChecked(setting('captions',True))
        voice.addRow(self.captions)
        save_voice = QPushButton("Apply voice settings")
        save_voice.clicked.connect(self.save_voice)
        voice.addRow(save_voice)
        preview = QPushButton("Hear a sample")
        preview.clicked.connect(self.preview_voice.emit)
        voice.addRow(preview)
        tabs.addTab(voice_page,"Voice")

        microphone_page = QWidget()
        mic = QFormLayout(microphone_page)
        self.microphone = QComboBox()
        mic.addRow('Input device', self.microphone)
        refresh_mics = QPushButton('Refresh device list')
        refresh_mics.clicked.connect(self.refresh_microphones)
        mic.addRow(refresh_mics)
        apply_mic = QPushButton('Use this microphone')
        apply_mic.clicked.connect(lambda: manager.set_mic_device(self.microphone.currentData()))
        mic.addRow(apply_mic)
        self.mic_level = QProgressBar()
        self.mic_level.setRange(0, 100)
        self.mic_level.setTextVisible(False)
        mic.addRow('Input level', self.mic_level)
        self.mic_status = QLabel('')
        self.mic_status.setWordWrap(True)
        mic.addRow(self.mic_status)
        self.mic_test = QPushButton('Test microphone (3 seconds)')
        self.mic_test.clicked.connect(self.test_microphone)
        mic.addRow(self.mic_test)
        note = QLabel('The test stays on this PC and is not saved or sent for transcription. Speak while the meter is moving. Check Windows microphone permissions and mute if no sound arrives. Other driver options are included for troubleshooting.')
        note.setWordWrap(True)
        mic.addRow(note)
        self._mic_listener = None
        self._mic_timer = QTimer(self)
        self._mic_timer.setSingleShot(True)
        self._mic_timer.timeout.connect(self.finish_microphone_test)
        self.microphone_level.connect(lambda level: self.mic_level.setValue(min(100, int(level * 1000))))
        self.refresh_microphones()
        tabs.addTab(microphone_page, 'Microphone')

        shortcuts_page = QWidget()
        shortcuts = QFormLayout(shortcuts_page)
        self.talk_key = QLineEdit(cfg.hotkey)
        self.text_key = QLineEdit(setting('text_hotkey','ctrl+alt+t'))
        self.dictation_key = QLineEdit(setting('dictation_hotkey','ctrl+alt+d'))
        shortcuts.addRow("Hold to talk",self.talk_key)
        shortcuts.addRow("Open typed chat",self.text_key)
        shortcuts.addRow("Hold to dictate",self.dictation_key)
        shortcuts.addRow(QLabel("Examples: ctrl+win, ctrl+alt+space. Esc always stops Clicky."))
        save_shortcuts = QPushButton("Apply shortcuts")
        save_shortcuts.clicked.connect(self.save_shortcuts)
        shortcuts.addRow(save_shortcuts)
        tabs.addTab(shortcuts_page,"Shortcuts")

        history = QWidget()
        history_layout = QVBoxLayout(history)
        history_layout.addWidget(QLabel("History is local to this Windows account. Clearing it does not erase the separate study journal."))
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        history_layout.addWidget(self.history)
        refresh = QPushButton("Refresh history")
        refresh.clicked.connect(self.refresh_history)
        history_layout.addWidget(refresh)
        clear = QPushButton("Clear conversation history")
        clear.clicked.connect(self.clear_history)
        history_layout.addWidget(clear)
        tabs.addTab(history,"History")

        guide = QWidget()
        guide_layout = QVBoxLayout(guide)
        help_text = QLabel("1. Hold your talk shortcut, or type in the panel.\n\n2. Ask 'where is the Save button?' for pointing. Say 'next' to continue using a fresh screen.\n\n3. Ask for a graph, chart or 3D shape to open Clicky Sketch. Drag a 3D shape to turn it; use lesson buttons to ask more.\n\n4. Say 'click the Save button for me' to propose Clicky Drive actions. Review the plan before allowing it. Esc stops; moving your mouse away stops its next action.\n\n5. Use Work & routines for background answers and recurring prompts. Results are saved in your local workspaces.\n\nOffline use: choose Ollama/LM Studio, local Whisper, Windows voice, and leave web search off. Cloud providers and connected browser/app tools use the network.")
        help_text.setWordWrap(True)
        guide_layout.addWidget(help_text)
        for text,signal in (("Try Clicky Sketch",self.show_sketch),("Open Work & routines",self.show_work)):
            button = QPushButton(text)
            button.clicked.connect(signal.emit)
            guide_layout.addWidget(button)
        tabs.addTab(guide,"Getting started")
        updates = QWidget()
        update_layout = QVBoxLayout(updates)
        from updates import VERSION
        self.update_status = QLabel('Installed source version: '+VERSION+'\nUpdates come from your own Clicky GitHub repository.')
        self.update_status.setWordWrap(True)
        update_layout.addWidget(self.update_status)
        check = QPushButton('Check for updates')
        check.clicked.connect(self.check_updates)
        update_layout.addWidget(check)
        self.install = QPushButton('Download verified installer')
        self.install.setEnabled(False)
        self.install.clicked.connect(self.download_update)
        update_layout.addWidget(self.install)
        update_layout.addStretch()
        tabs.addTab(updates,'Updates')
        self._update=None
        self.update_ready.connect(self.show_update)
        self.installer_ready.connect(self.install_update)
        self.refresh_history()

    def check_updates(self):
        async def check():
            try:
                from updates import latest
                self.update_ready.emit(await latest())
            except Exception as exc:self.update_ready.emit({'error':str(exc)})
        self.manager._submit(check())

    def refresh_microphones(self):
        from audio.devices import input_devices, recommended_inputs, resolve_input
        self.microphone.clear()
        self.microphone.addItem('Windows default (recommended)', -1)
        try:
            devices = input_devices()
            preferred = recommended_inputs(devices)
            for item in preferred + [item for item in devices if item not in preferred]:
                prefix = '' if item in preferred else 'Other driver: '
                self.microphone.addItem(prefix + item['name'] + ' (' + item['host_name'] + ')', item['index'])
            saved = setting('mic_identity', {'default': True})
            selected, warning = resolve_input(cfg.mic_device_index, saved)
            if saved != {'default': True} and (saved or cfg.mic_device_index is not None):
                self.microphone.setCurrentIndex(max(0, self.microphone.findData(selected['index'])))
            self.mic_status.setText(warning or 'Ready. Test the selected microphone before using it.')
        except Exception as exc:
            self.mic_status.setText('Microphone unavailable: ' + str(exc))

    def test_microphone(self):
        if self._mic_listener:
            self.finish_microphone_test()
            return
        from audio.ambient_listener import AmbientListener
        from audio.devices import input_devices, identity
        try:
            selected = self.microphone.currentData()
            item = next((item for item in input_devices() if item['index'] == selected), None)
            if selected is not None and selected >= 0 and not item:
                raise ValueError('That microphone is no longer available. Refresh the device list.')
            saved = identity(item) if item else {'default': True}
            self._mic_listener = AmbientListener(self.microphone_level.emit, lambda: None,
                                                 device=selected, ambient=False, identity=saved)
            self._mic_listener.start_recording()
            self.mic_status.setText('Speak now — testing ' + self._mic_listener.device_name)
            self.mic_test.setText('Stop test')
            self._mic_timer.start(3000)
        except Exception as exc:
            if self._mic_listener:
                self._mic_listener.stop()
                self._mic_listener = None
            self.mic_status.setText(str(exc))

    def finish_microphone_test(self):
        self._mic_timer.stop()
        listener, self._mic_listener = self._mic_listener, None
        if listener:
            from audio.capture import capture_problem
            try:
                pcm = listener.stop_recording()
                problem = capture_problem(pcm)
                self.mic_status.setText(problem or 'Audio received from ' + listener.device_name + '. Choose “Use this microphone” to apply it. This test checks capture, not recognition accuracy.')
            finally:
                listener.stop()
        self.mic_test.setText('Test microphone (3 seconds)')
        self.mic_level.setValue(0)

    def closeEvent(self, event):
        self.finish_microphone_test()
        super().closeEvent(event)

    def show_update(self,value):
        self._update=value
        self.install.setEnabled(bool(value and value.get('asset')))
        self.update_status.setText(value.get('error') if value and value.get('error') else ('Available: '+value['version']+'\n'+value['url'] if value else 'No newer release is available.'))

    def download_update(self):
        self.install.setEnabled(False)
        async def fetch():
            try:
                from updates import download
                self.installer_ready.emit(await download(self._update['asset']))
            except Exception as exc:self.update_ready.emit({'error':str(exc)})
        self.manager._submit(fetch())

    def install_update(self,path):
        if QMessageBox.question(self,'Installer verified','Quit Clicky and open the verified installer?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            import subprocess
            subprocess.Popen([path])
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

    def apply(self,callback):
        try:
            callback()
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,"Could not save settings",str(exc))

    def save_voice(self):
        def save():
            self.manager.stop()
            provider = self.provider.currentData()
            if provider == 'openai' and not cfg.openai_api_key or provider == 'elevenlabs' and not cfg.elevenlabs_api_key:
                raise ValueError("Add an API key for that voice provider first")
            import os
            stt = self.transcription.currentData()
            if stt=='deepgram' and not cfg.deepgram_api_key or stt=='openai' and not cfg.openai_api_key:
                raise ValueError('Add the API key for that recognition provider first')
            set_setting('tts_provider',provider)
            cfg._write_env('CLICKY_STT',stt)
            os.environ['CLICKY_STT'] = stt
            self.manager._stt = None
            set_setting('speech_rate',self.rate.value())
            set_setting('captions',self.captions.isChecked())
            selected = cfg.tts_provider()
            set_setting('voice' if selected == 'sapi' else 'voice_'+selected,self.voice_name.text().strip())
            self.manager._tts = None
        self.apply(save)

    def save_shortcuts(self):
        def save():
            import keyboard
            values = [field.text().strip().lower() for field in (self.talk_key,self.text_key,self.dictation_key)]
            if len(set(values)) != 3 or any(not value or value == 'esc' for value in values):
                raise ValueError("Choose three different nonempty shortcuts; Esc is reserved")
            for value in values:
                keyboard.parse_hotkey(value)
            cfg._write_env('CLICKY_HOTKEY',values[0])
            cfg.hotkey = values[0]
            set_setting('text_hotkey',values[1])
            set_setting('dictation_hotkey',values[2])
            self.shortcuts_changed.emit()
        self.apply(save)

    def refresh_history(self):
        import session_store
        self.history.setPlainText('\n\n'.join('['+app+']\n'+'\n\n'.join(row['role']+': '+row['content'] for row in rows) for app,rows in session_store.recent()))

    def clear_history(self):
        if QMessageBox.question(self,"Clear history?","Remove saved conversation history from this PC?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.manager.clear_history()
            self.refresh_history()
