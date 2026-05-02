"""
Clicky for Windows — Entry Point.
Boots Qt, spawns overlay+panel+tray, starts ambient mic listener, binds hotkey.
"""

import sys

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
        try:
            asyncio.run(device_login(on_code=_on_code))
            tray.show_notification(
                "GitHub Copilot",
                "Signed in! Refreshing model list…"
            )
            manager.refresh_copilot_models()
        except Exception as e:
            tray.show_notification("Copilot login failed", str(e))
            panel.show_copilot_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Clicky")
    app.setApplicationDisplayName("Clicky - AI Companion")

    # ── Core components ───────────────────────────────────────────────────────
    manager = CompanionManager()
    panel   = CompanionPanel()
    overlay = CursorOverlay()
    tray    = TrayManager()

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

    # Whiteboard annotations
    manager.sig_arrow.connect(overlay.add_arrow)
    manager.sig_circle.connect(overlay.add_circle)
    manager.sig_underline.connect(overlay.add_underline)
    manager.sig_label.connect(overlay.add_text)

    # Errors
    manager.sig_error.connect(
        lambda e: tray.show_notification("Clicky error", str(e))
    )

    # Panel → Manager
    panel.on_model_changed.connect(manager.set_model)

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
        if cfg.llm_provider() == "copilot":
            panel.refresh_for_provider("copilot")
        tray.show_notification(
            "GitHub Copilot",
            f"Loaded {count} models from your seat. Free models are tagged "
            f"in the Model dropdown."
        )
    manager.sig_copilot_models_done.connect(_on_copilot_models_done)

    # Live model auto-refresh for Claude / OpenAI / Gemini (30-day cache).
    # Repopulate the panel whenever a refresh lands.
    def _on_models_refreshed(provider: str, count: int):
        if cfg.llm_provider() == provider:
            panel.refresh_for_provider(provider)
    manager.sig_models_refreshed.connect(_on_models_refreshed)
    tray.on_quit.connect(lambda: (manager.shutdown(), app.quit()))

    # ── Global hotkey ─────────────────────────────────────────────────────────
    hotkey = GlobalHotkeyMonitor(
        on_press=manager.on_hotkey_press,
        on_release=manager.on_hotkey_release,
    )
    hotkey.start()

    # Esc = cancel current generation (kills Ollama ramble mid-stream)
    stop_key = StopHotkey(on_stop=manager.stop, key="esc")
    stop_key.start()

    # ── Show UI + start listener ──────────────────────────────────────────────
    overlay.show()        # persistent overlay (cursor follow)
    # Panel is hidden by default — user can open it from the tray menu if needed
    manager.start()        # begin ambient mic + wake-word scanning

    providers = cfg.describe()
    tray.show_notification(
        "Clicky is running",
        f"Say 'Clicky' or hold {cfg.hotkey}  |  LLM: {providers['llm']}",
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
