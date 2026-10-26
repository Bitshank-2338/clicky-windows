"""
Clicky for Windows — Entry Point.
Boots Qt, spawns overlay+panel+tray, starts ambient mic listener, binds hotkey.
"""

import os
import sys
from pathlib import Path


def _ensure_std_streams() -> None:
    """Give the process real stdout/stderr before anything tries to write.

    PyInstaller windowed builds (console=False) set both to None. Most code
    survives that — bare print() tolerates it — but anything calling
    .write() directly does not. tqdm is the one that matters: huggingface_hub
    uses it for the download bar when faster-whisper fetches its model on the
    first transcription, so the very first activation died with
    "'NoneType' object has no attribute 'write'". The model then never
    cached, so it failed again on every subsequent attempt, and the toast
    showed only the bare message with no traceback (GitHub issue #15).

    Runs at import time, ahead of the heavy imports below, so library code
    that writes while loading is covered too.
    """
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is not None:
            continue
        try:
            stream = open(os.devnull, "w", encoding="utf-8")
        except Exception:
            continue
        setattr(sys, name, stream)
        # Some libraries reach for the __-prefixed originals instead.
        if getattr(sys, f"__{name}__", None) is None:
            setattr(sys, f"__{name}__", stream)


_ensure_std_streams()

# Run before normal startup imports, credentials, microphone and global hooks.
if __name__ == "__main__" and "--smoke-test" in sys.argv:
    from packaging_smoke import run
    sys.exit(run())

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from config import cfg
from ui.tray import TrayManager
from ui.panel import CompanionPanel, AppState
from ui.overlay import (
    CursorOverlay, MODE_IDLE, MODE_LISTENING, MODE_THINKING, MODE_SPEAKING
)
from hotkey import GlobalHotkeyMonitor, StopHotkey
from companion_manager import CompanionManager


STATE_TO_CURSOR_MODE = {
    AppState.IDLE:      MODE_IDLE,
    AppState.LISTENING: MODE_LISTENING,
    AppState.THINKING:  MODE_THINKING,
    AppState.SPEAKING:  MODE_SPEAKING,
}


def _copilot_login_flow(tray, panel, manager):
    """Run the GitHub device-flow login in a worker thread so the UI stays live."""
    import asyncio, threading
    from ai.github_copilot_provider import device_login

    def _on_code(user_code: str, verification_uri: str):
        """Called as soon as the device code arrives — display it in the panel."""
        msg = (
            f"GitHub Copilot Sign-In\n\n"
            f"1. Visit: {verification_uri}\n"
            f"2. Enter code:  {user_code}\n"
            f"3. Click Authorize — Clicky will sign in automatically."
        )
        # Show in panel (cross-thread safe via Qt signal)
        panel.show_copilot_code(user_code, verification_uri)
        tray.show_notification("GitHub Copilot — enter this code", user_code)

    def _worker():
        # Sign-in and model discovery are reported separately on purpose: the
        # device flow was succeeding and saving a valid token, then a failing
        # model refresh surfaced as "Copilot login failed" and sent users off
        # re-authorising something that was never broken.
        try:
            asyncio.run(device_login(on_code=_on_code))
        except Exception as e:
            tray.show_notification("Copilot login failed", str(e))
            panel.show_copilot_error(str(e))
            return

        tray.show_notification("GitHub Copilot", "Signed in! Refreshing model list…")
        panel.show_copilot_status("✅ Signed in to GitHub Copilot.\n\nLoading the models on your plan…")
        try:
            manager.refresh_copilot_models()
        except Exception as e:
            tray.show_notification(
                "Copilot signed in — model list unavailable", str(e)
            )
            panel.show_copilot_error(
                f"Signed in successfully, but the model list could not be "
                f"loaded:\n{e}\n\nTry Tray → Model → Refresh Copilot models."
            )

    threading.Thread(target=_worker, daemon=True).start()


def _setup_logging():
    """Rotating runtime log at %LOCALAPPDATA%\\Clicky\\clicky.log — the #1
    ask from bug reports: with no log file, 'stuck on Listening' class issues
    were undiagnosable (GitHub issue #6)."""
    import logging
    from logging.handlers import RotatingFileHandler

    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Clicky"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "clicky.log", maxBytes=1_000_000, backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
        ))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        logging.getLogger("clicky").info(
            "=== Clicky starting (python %s) ===", sys.version.split()[0]
        )
    except Exception:
        pass  # logging must never block startup


def main():
    _setup_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.design import apply_theme
    apply_theme(app)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Clicky")
    app.setApplicationDisplayName("Clicky - AI Companion")
    from screen.capture import configure_displays
    configure_displays(app.screens())
    app.screenAdded.connect(lambda _screen: configure_displays(app.screens()))
    app.screenRemoved.connect(lambda _screen: configure_displays(app.screens()))
    for screen in app.screens():
        screen.geometryChanged.connect(lambda _geometry: configure_displays(app.screens()))

    # ── Core components ───────────────────────────────────────────────────────
    manager = CompanionManager()
    panel   = CompanionPanel()
    overlay = CursorOverlay()
    tray    = TrayManager()
    from PyQt6.QtCore import QTimer
    from desktop import foreground, restore
    _last_foreground = [{}]
    def _track_foreground():
        try:
            context = foreground()
            if context["pid"] != os.getpid():
                _last_foreground[0] = context
                manager._desktop_context = context
        except OSError:
            pass
    _focus_timer = QTimer(app)
    _focus_timer.timeout.connect(_track_foreground)
    _focus_timer.start(150)
    _track_foreground()

    _boards = []
    def _show_scene(scene):
        from ui.drawing_board import DrawingBoard
        board = DrawingBoard(scene)
        board.question.connect(manager.submit_text)
        board.narrate.connect(lambda text:manager._submit(manager._reply_local(text)))
        manager.sig_caption.connect(board.set_caption)
        board.show()
        _boards.append(board)
        if len(_boards) > 4:
            old = _boards.pop(0)
            manager.sig_caption.disconnect(old.set_caption)
            old.close()
            old.deleteLater()
    manager.sig_scene.connect(_show_scene)
    from drawing import example_scene
    panel.on_sketch_requested.connect(lambda: _show_scene(example_scene()))
    from ui.jobs_window import JobsWindow
    work_window = JobsWindow()
    panel.on_jobs_requested.connect(work_window.show)
    from ui.settings_window import SettingsWindow
    settings_window = SettingsWindow(manager)
    panel.on_settings_requested.connect(settings_window.show)
    settings_window.show_sketch.connect(lambda: _show_scene(example_scene()))
    settings_window.show_work.connect(work_window.show)
    from ui.connections_window import ConnectionsWindow
    connections_window = ConnectionsWindow(manager)
    settings_window.open_connections.connect(connections_window.show)
    def _review_external(proposal):
        import json
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(panel,"Review Clicky connected request",json.dumps(proposal,ensure_ascii=False,indent=2)[:10000]+"\n\nAllow this request? It may read or change data in your connected browser/app.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            manager._submit(manager.run_external(proposal))
    manager.sig_external_request.connect(_review_external)
    manager.sig_external_result.connect(connections_window.result_ready.emit)
    manager.sig_external_result.connect(lambda _result: connections_window.show())
    def _shared_message(value):
        if value['type']=='qa':
            connections_window.shared_text.appendPlainText('Shared question: '+value['q']+'\nShared answer: '+value['a']+'\n')
        else:_show_scene(value['scene'])
    manager.sig_collab_message.connect(_shared_message)
    settings_window.preview_voice.connect(lambda: manager._submit(manager._reply_local("Hello, I'm Clicky. This is my current voice.")))

    from PyQt6.QtWidgets import QLabel
    caption = QLabel()
    caption.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput)
    caption.setStyleSheet("background: #101722; color: white; padding: 14px; border-radius: 10px; font-size: 18px;")
    caption.setWordWrap(True)
    caption.setFixedWidth(620)
    def _caption(text):
        from storage import setting
        if not text or not setting('captions',True):
            caption.hide()
            return
        from PyQt6.QtGui import QCursor
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        area = screen.availableGeometry()
        caption.setText(text)
        caption.adjustSize()
        caption.move(area.center().x()-caption.width()//2,area.bottom()-caption.height()-30)
        caption.show()
        try:
            from screen.privacy import exclude_window
            exclude_window(caption)
        except OSError:
            caption.hide()
    manager.sig_caption.connect(_caption)

    def _dictation_ready(text,context):
        from PyQt6.QtWidgets import QMessageBox
        from tutor import is_sensitive_window
        try:
            current = foreground()
            if current['hwnd'] != context.get('hwnd') or is_sensitive_window(current['title']):
                raise ValueError("The destination changed or may be private")
            import uiautomation as auto
            control = auto.GetFocusedControl()
            if control is None or control.GetPropertyValue(30019):
                raise ValueError("The focused field is protected")
            if control.ControlTypeName not in {'EditControl','DocumentControl'}:
                raise ValueError("No editable field is focused")
            from pynput.keyboard import Controller
            Controller().type(text)
        except Exception as exc:
            box = QMessageBox(panel)
            box.setWindowTitle("Dictation ready")
            box.setText(f"{exc}. Your transcript is below; it was not inserted.")
            box.setDetailedText(text)
            copy = box.addButton("Copy transcript",QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Close)
            box.exec()
            if box.clickedButton() is copy:
                app.clipboard().setText(text)
    manager.sig_dictation_ready.connect(_dictation_ready)

    def _review_drive(value):
        from drive import validate_plan, describe
        from PyQt6.QtWidgets import QMessageBox
        context = dict(getattr(manager, "_drive_context", {}))
        approved = QMessageBox.question(panel, "Clicky Drive — review actions", describe(validate_plan(value)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
        if approved:
            try:
                restore(context)
            except (OSError, KeyError) as exc:
                approved = False
                tray.show_notification("Drive did not start", str(exc))
        manager.approve_drive(approved)
    manager.sig_drive_request.connect(_review_drive)
    manager.sig_drive_progress.connect(lambda message: tray.show_notification("Clicky Drive", message))

    # ── Wire signals ──────────────────────────────────────────────────────────

    # State changes → Panel + Tray + Cursor
    def _on_state(state: AppState):
        panel.set_state(state)
        tray.set_state_icon(state.name.lower())
        overlay.set_mode(STATE_TO_CURSOR_MODE.get(state, MODE_IDLE))

    manager.sig_state_changed.connect(_on_state)

    # Response streaming
    manager.sig_response_chunk.connect(panel.append_response_chunk)

    # Audio level → cursor waveform (+ panel meter)
    manager.sig_audio_level.connect(panel.set_audio_level)
    manager.sig_audio_level.connect(overlay.set_audio_level)

    # Pointing directives
    manager.sig_point_at.connect(overlay.point_at)
    manager.sig_point_hold.connect(overlay.set_point_hold)
    manager.sig_point_release.connect(overlay.release_point)

    # Whiteboard annotations (legacy per-shape signals)
    manager.sig_arrow.connect(overlay.add_arrow)
    manager.sig_circle.connect(overlay.add_circle)
    manager.sig_underline.connect(overlay.add_underline)
    manager.sig_label.connect(overlay.add_text)
    # Teaching drawings — generic shape channel with progressive animation
    manager.sig_draw.connect(overlay.add_shape)
    manager.sig_clear_drawings.connect(overlay.clear_annotations)

    # Errors. The toast names the log file because it only has room for the
    # message itself — issue #15 was reported with no traceback simply because
    # nobody knew a log existed.
    _log_hint = Path(
        os.environ.get("LOCALAPPDATA", Path.home())
    ) / "Clicky" / "clicky.log"
    manager.sig_error.connect(
        lambda e: tray.show_notification(
            "Clicky error", f"{e}\n\nFull details: {_log_hint}"
        )
    )
    manager.sig_notice.connect(lambda message: tray.show_notification('Clicky', message))

    # Panel → Manager
    panel.on_model_changed.connect(manager.set_model)
    panel.on_text_submitted.connect(manager.submit_text)
    panel.on_stop_requested.connect(manager.stop)
    manager.sig_turn_started.connect(panel.begin_turn)
    panel.on_new_chat.connect(manager.clear_history)
    panel.on_new_chat.connect(panel.clear_response)

    def _on_doc_dropped(path: str):
        ok = manager.attach_document(path)
        tray.show_notification(
            "Document Attached" if ok else "Attach failed",
            f"{path}\nAsk Clicky about it now." if ok else
            "Couldn't read that file."
        )
    panel.on_document_dropped.connect(_on_doc_dropped)

    # Tray → UI / Manager
    tray.on_show_panel.connect(panel.show)
    tray.on_hide_panel.connect(panel.hide)
    tray.on_toggle_search.connect(manager.set_web_search)
    tray.on_toggle_wake_word.connect(manager.set_wake_word)
    tray.on_toggle_slow_mode.connect(manager.set_slow_mode)
    tray.on_toggle_slow_mode.connect(overlay.set_slow_mode)
    tray.on_toggle_quiz_mode.connect(manager.set_quiz_mode)
    tray.on_toggle_privacy.connect(manager.set_privacy_guard)
    tray.on_toggle_code_mode.connect(manager.set_code_mode_auto)
    tray.on_toggle_multilang.connect(manager.set_multilang)
    tray.on_toggle_journal.connect(manager.set_journal)
    tray.on_toggle_ocr.connect(manager.set_ocr_enabled)

    # Lesson recording
    def _record_start():
        out = manager.start_recording()
        tray.show_notification(
            "Lesson Recording",
            f"Recording to:\n{out}" if out else
            "Failed — install imageio[ffmpeg]: pip install imageio imageio-ffmpeg"
        )
    def _record_stop():
        out = manager.stop_recording()
        if out:
            tray.show_notification("Lesson saved", out)
    tray.on_record_start.connect(_record_start)
    tray.on_record_stop.connect(_record_stop)
    manager.sig_recording_state.connect(
        lambda on, _path: tray.set_recording_state(on)
    )
    def _record_overlay():
        if not manager._recorder or not manager._recorder.is_recording:
            return
        from PyQt6.QtGui import QImage
        from PIL import Image
        image = overlay.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ink = Image.frombytes('RGBA',(image.width(),image.height()),image.bits().asstring(image.sizeInBytes()))
        primary = app.primaryScreen()
        scale = primary.devicePixelRatio()
        desired = (round(overlay.width()*scale), round(overlay.height()*scale))
        if ink.size != desired:ink=ink.resize(desired)
        manager._recorder._overlay = (ink, overlay.x(), overlay.y(), scale)
    _record_timer = QTimer(app)
    _record_timer.timeout.connect(_record_overlay)
    _record_timer.start(125)

    # Workflow capture
    def _wf_start():
        ok = manager.workflow_start()
        tray.show_notification(
            "Workflow Capture",
            "Recording your clicks + keys. Stop from tray when done."
            if ok else "Install pynput: pip install pynput"
        )
    def _wf_stop():
        summary = manager.workflow_stop()
        if summary:
            tray.show_notification(
                "Workflow Captured",
                "Sent to Clicky as context. Ask: 'what did I just do?'"
            )
            # Stash as an attached doc so the next question sees it
            manager._attached_docs.append(("recorded_workflow.txt", summary))
    tray.on_workflow_start.connect(_wf_start)
    tray.on_workflow_stop.connect(_wf_stop)

    # Live collab
    tray.on_collab_start.connect(manager.collab_start_host)
    def _collab_join():
        from PyQt6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(None, "Join Live Session",
                                        "Enter 6-character session code:")
        if ok and code:
            manager.collab_join(code.strip())
    tray.on_collab_join.connect(_collab_join)

    # Journal folder
    def _open_journal():
        import os, subprocess
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "Clicky")
        try:
            os.startfile(path)
        except Exception:
            subprocess.Popen(["explorer", path])
    tray.on_journal_open.connect(_open_journal)

    # Attach document (drag-drop alternative — file picker)
    def _attach_doc():
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None, "Attach a document for Clicky",
            "", "Documents (*.pdf *.docx *.txt *.md *.csv)"
        )
        if path:
            ok = manager.attach_document(path)
            tray.show_notification(
                "Document Attached",
                f"{path}\nAsk Clicky about it now." if ok else
                "Couldn't read that file."
            )
    tray.on_attach_doc.connect(_attach_doc)

    def _switch(name: str):
        manager.set_active_provider(name)
        panel.refresh_for_provider(name)       # repopulate model dropdown + badge
        tray.rebuild_menu()                    # tick mark moves to new provider
        tray.show_notification("Clicky", f"Switched to {name}")

    tray.on_switch_provider.connect(_switch)
    tray.on_stop.connect(manager.stop)
    tray.on_copilot_login.connect(lambda: _copilot_login_flow(tray, panel, manager))
    tray.on_copilot_refresh.connect(manager.refresh_copilot_models)

    # When the live model list arrives, repopulate the panel + show a toast
    def _on_copilot_models_done(count: int):
        from ai.github_copilot_provider import blocked_models
        if cfg.llm_provider() == "copilot":
            panel.refresh_for_provider("copilot")
        blocked = blocked_models()
        msg = f"{count} models are usable on your plan."
        if blocked:
            shown = ", ".join(blocked[:4]) + (" …" if len(blocked) > 4 else "")
            msg += (
                f"\n\nGitHub lists {len(blocked)} newer models as enabled "
                f"({shown}) but does not let your Copilot plan call them, so "
                f"they are hidden. Another provider (Claude, OpenAI, Gemini) "
                f"will have them."
            )
        panel.show_copilot_status("✅ Signed in to GitHub Copilot.\n\n" + msg)
        tray.show_notification(
            "GitHub Copilot",
            f"Loaded {count} usable models."
            + (f" {len(blocked)} newer ones aren't available on your plan." if blocked else ""),
        )

    def _on_copilot_models_failed(err: str):
        panel.show_copilot_error(
            f"Signed in successfully, but the model list could not be loaded:\n"
            f"{err}\n\nTry Tray → Model → Refresh Copilot models."
        )
    manager.sig_copilot_models_failed.connect(_on_copilot_models_failed)
    manager.sig_copilot_models_done.connect(_on_copilot_models_done)

    # Live model auto-refresh for Claude / OpenAI / Gemini (30-day cache).
    # Repopulate the panel whenever a refresh lands.
    def _on_models_refreshed(provider: str, count: int):
        if cfg.llm_provider() == provider:
            panel.refresh_for_provider(provider)
    manager.sig_models_refreshed.connect(_on_models_refreshed)

    # ── Ollama multi-model wiring ─────────────────────────────────────────
    tray.on_ollama_set_model.connect(manager.set_ollama_model)
    tray.on_ollama_pull.connect(manager.pull_ollama_model)
    tray.on_ollama_refresh.connect(manager.refresh_ollama_models)
    tray.on_set_mic_device.connect(manager.set_mic_device)
    manager.sig_microphone_changed.connect(tray.refresh_microphones)
    tray.on_set_response_language.connect(manager.set_response_language)
    tray.on_set_stt_language.connect(manager.set_stt_language)
    tray.on_set_custom_instructions.connect(manager.set_custom_instructions)

    # When the installed-model list arrives, push it into the tray submenu
    manager.sig_ollama_models.connect(tray.set_ollama_models)
    manager.sig_ollama_models.connect(panel.set_ollama_models)
    manager.sig_ollama_selected.connect(panel.select_ollama_model)
    panel.on_ollama_refresh_requested.connect(manager.refresh_ollama_models)

    # Surface pull progress as tray toasts so students see download status
    def _on_ollama_pull_status(name: str, status: str):
        tray.show_notification("Ollama", status)
    manager.sig_ollama_pull_status.connect(_on_ollama_pull_status)

    # First-run: poll Ollama if it's the active provider so the menu
    # actually shows installed models from the start.
    if cfg.llm_provider() == "ollama":
        manager.refresh_ollama_models()

    # Setup wizard (re-run) + diagnostics
    def _run_setup_again():
        from ui.setup_wizard import SetupWizard
        wiz = SetupWizard()
        wiz.show()
        _setup_keepalive[0] = wiz
    tray.on_run_setup.connect(_run_setup_again)

    def _open_api_keys():
        from ui.api_keys_dialog import ApiKeysDialog
        dlg = ApiKeysDialog()

        def _applied():
            # A new key can change which provider is active, so refresh every
            # surface that renders the provider name or model list.
            provider = cfg.llm_provider()
            manager.set_active_provider(provider)
            panel.refresh_for_provider(provider)
            tray.rebuild_menu()
            tray.show_notification("Clicky", f"API keys saved — using {provider}")

        dlg.keys_saved.connect(_applied)
        dlg.show()
        _setup_keepalive[1] = dlg   # keep a reference so Qt doesn't GC it
    tray.on_api_keys.connect(_open_api_keys)
    settings_window.open_keys.connect(_open_api_keys)

    def _save_diagnostics():
        import datetime, json, platform, traceback
        from ai import ollama_bootstrap as ob
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        out = Path(base) / "Clicky" / f"diagnostics-{datetime.datetime.now():%Y%m%d-%H%M%S}.txt"
        try:
            providers_d = cfg.describe()
        except Exception:
            providers_d = {}
        report = []
        report.append(f"Clicky diagnostics — {datetime.datetime.now().isoformat()}")
        report.append(f"Python: {sys.version.split()[0]}")
        report.append(f"Platform: {platform.platform()}")
        report.append(f"Active LLM: {providers_d.get('llm', '?')}")
        report.append(f"STT: {providers_d.get('stt', '?')}  TTS: {providers_d.get('tts', '?')}")
        report.append("")
        report.append("─── Ollama ───")
        try:
            report.append(f"Host: {cfg.ollama_host}")
            report.append(f"Text model:   {cfg.ollama_text_model}")
            report.append(f"Vision model: {cfg.ollama_vision_model}")
            report.append(f"Binary on PATH: {ob.is_ollama_installed()}")
            report.append(f"Server reachable: {ob.is_ollama_running()}")
            if ob.is_ollama_running():
                report.append(f"Installed models: {ob.list_installed_models()}")
        except Exception:
            report.append(traceback.format_exc())
        report.append("")
        report.append("─── GitHub Copilot ───")
        try:
            from ai.github_copilot_provider import is_authenticated, _token_path
            report.append(f"Token file: {_token_path()}  exists={_token_path().exists()}")
            report.append(f"Authenticated: {is_authenticated()}")
        except Exception:
            report.append(traceback.format_exc())
        try:
            out.write_text("\n".join(report), encoding="utf-8")
            tray.show_notification("Diagnostics saved", str(out))
            try:
                os.startfile(str(out))
            except Exception:
                pass
        except Exception as e:
            tray.show_notification("Diagnostics failed", str(e))
    tray.on_diagnostics.connect(_save_diagnostics)

    tray.on_quit.connect(lambda: (tray.hide_icon(), manager.shutdown(), app.quit()))

    # ── Global hotkey ─────────────────────────────────────────────────────────
    _shortcuts = []
    _text_shortcut = [None]
    from PyQt6.QtCore import QObject, pyqtSignal
    class ChatShortcut(QObject):
        show = pyqtSignal()
    chat_shortcut = ChatShortcut()
    chat_shortcut.show.connect(panel.show)
    def _install_shortcuts():
        from storage import setting
        import keyboard
        for shortcut in _shortcuts:
            shortcut.stop()
        _shortcuts.clear()
        if _text_shortcut[0] is not None:
            keyboard.remove_hotkey(_text_shortcut[0])
        for on_press,on_release,key in ((manager.on_hotkey_press,manager.on_hotkey_release,cfg.hotkey),
                                        (manager.begin_dictation,manager.on_hotkey_release,setting('dictation_hotkey','ctrl+alt+d'))):
            shortcut = GlobalHotkeyMonitor(on_press=on_press,on_release=on_release,hotkey=key)
            shortcut.start()
            _shortcuts.append(shortcut)
        _text_shortcut[0] = keyboard.add_hotkey(setting('text_hotkey','ctrl+alt+t'),chat_shortcut.show.emit)
    settings_window.shortcuts_changed.connect(_install_shortcuts)
    _install_shortcuts()

    # Esc = cancel current generation (kills Ollama ramble mid-stream)
    stop_key = StopHotkey(on_stop=manager.stop, key="esc")
    stop_key.start()

    # ── Show UI + start listener ──────────────────────────────────────────────
    overlay.show()        # persistent overlay (cursor follow)
    from screen.privacy import exclude_window
    for window in (overlay, panel):
        try:
            exclude_window(window)
        except OSError as exc:
            manager.sig_error.emit(f"Could not exclude Clicky's window from screen capture: {exc}")
    # Panel is hidden by default — user can open it from the tray menu if needed
    manager.start()        # begin ambient mic + wake-word scanning
    app.aboutToQuit.connect(manager.shutdown)

    providers = cfg.describe()
    _hk = "+".join(p.strip().capitalize() for p in cfg.hotkey.split("+"))
    tray.show_notification(
        "Clicky is running",
        (f"Say 'Clicky' or press {_hk}  |  LLM: {providers['llm']}"
         if cfg.ambient_mic() else
         f"Press {_hk}, ask your question, and Clicky answers when you stop "
         f"talking  |  LLM: {providers['llm']}"),
    )

    # ── First-run setup wizard ────────────────────────────────────────────────
    # Show the Ollama install / model pull walkthrough on the first launch.
    # If everything is already wired up, the helper is a no-op.
    try:
        from ui.setup_wizard import maybe_show_setup_wizard, SetupWizard

        # Force-show via env var (handy for testing).
        if os.environ.get("CLICKY_FORCE_SETUP", "").strip() in ("1", "true", "yes"):
            wiz = SetupWizard()
            wiz.show()
            _setup_keepalive[0] = wiz
        else:
            wiz = maybe_show_setup_wizard()
            if wiz is not None:
                _setup_keepalive[0] = wiz   # keep a reference so it isn't GC'd
    except Exception as e:
        print(f"[setup-wizard] skipped: {e}")

    sys.exit(app.exec())


# Module-level slots keeping references to the setup wizard [0] and the API
# keys dialog [1] alive while Qt is running (PyQt will GC them otherwise and
# the dialog will vanish).
_setup_keepalive: list = [None, None]


if __name__ == "__main__":
    main()
