import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tutor import is_identity_question, is_locate, is_sensitive_window, target_name


@pytest.mark.parametrize("title", [".env - Visual Studio Code", ".env.local - Code", "Bitwarden", "login - Chrome"])
def test_sensitive_titles(title):
    assert is_sensitive_window(title)


@pytest.mark.parametrize("query", ["what is wrong with this code", "what is this button", "who is on my screen"])
def test_screen_queries_keep_vision(query):
    assert not is_identity_question(query)


def test_named_identity_can_use_text():
    assert is_identity_question("who is Ada Lovelace")


def test_pointer_understands_natural_question():
    from ai.hybrid_pointer import _score_match, _normalize
    assert _score_match(target_name("where is the Save button?"), "Save", "ButtonControl") >= 0.5
    assert is_locate("Save button kahan hai")
    assert target_name("Save button kahan hai") == "Save"
    assert _normalize("सहेजें")


def test_redaction_clips_to_monitor():
    from PIL import Image
    from screen.privacy import redact
    image = Image.new("RGB", (100, 100), "white")
    redact(image, -100, 0, [(-150, 20, -50, 60), (50, 50, 70, 80)])
    assert image.getpixel((25, 40)) == (0, 0, 0)
    assert image.getpixel((80, 40)) == (255, 255, 255)


def test_quiz_does_not_capture_sensitive_window(monkeypatch):
    import companion_manager as module
    monkeypatch.setattr(module, "active_window_title", lambda: "Bitwarden")
    capture = Mock(side_effect=AssertionError("Must not capture"))
    monkeypatch.setattr(module, "capture_all_screens", capture)
    replies = []
    async def reply(text):
        replies.append(text)
    manager = SimpleNamespace(_state=module.AppState.IDLE, _privacy_guard=True,
                              _emit_state=lambda value: None, _reply_local=reply)
    asyncio.run(module.CompanionManager._kickoff_quiz(manager))
    capture.assert_not_called()
    assert "private" in replies[0]


def test_review_waits_for_answer(monkeypatch):
    import companion_manager as module
    monkeypatch.setattr(module.journal, "due_for_review", lambda limit: [{"id": 5, "question": "Q", "answer": "A"}])
    grade = Mock()
    monkeypatch.setattr(module.journal, "mark_reviewed", grade)
    async def reply(text):
        pass
    manager = SimpleNamespace(_reply_local=reply)
    asyncio.run(module.CompanionManager._spaced_review(manager))
    grade.assert_not_called()
    assert manager._pending_review["id"] == 5


def test_secret_save_failure_does_not_change_runtime(monkeypatch):
    import config
    cfg = config.Config()
    before = cfg.anthropic_api_key
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(config, "set_credential", fail)
    with pytest.raises(OSError):
        cfg.set_api_key("ANTHROPIC_API_KEY", "test-secret")
    assert cfg.anthropic_api_key == before


def test_credentials_are_encrypted_on_disk():
    import os
    if os.name != "nt":
        pytest.skip("Windows DPAPI")
    from storage import set_credential, credentials, data_dir
    set_credential("sample", "not-a-real-key")
    assert credentials()["sample"] == "not-a-real-key"
    assert b"not-a-real-key" not in (data_dir() / "credentials.bin").read_bytes()


def test_mixed_dpi_uses_local_displacement():
    from screen.capture import ScreenShot
    from companion_manager import CompanionManager
    shot = ScreenShot(1, 1280, 720, "", 2560, 1440, -2560, 0, 2, -2560, 0)
    manager = SimpleNamespace(_shot=lambda index: shot)
    assert CompanionManager._denorm(manager, 500, 500) == (-1920, 360)
    assert CompanionManager._norm(manager, -1920, 360) == (500, 500)


def test_settings_survive_reload():
    from storage import set_setting, setting
    set_setting("web_search", False)
    set_setting("journal", False)
    assert setting("web_search") is False
    assert setting("journal") is False


def test_tray_preferences_use_per_user_store(monkeypatch):
    import companion_manager as module
    from storage import setting
    for field in ('custom_instructions', 'response_language', 'whisper_language'):
        monkeypatch.setattr(module.cfg, field, getattr(module.cfg, field))
    manager = SimpleNamespace(sig_error=Mock(), _stt=object())
    module.CompanionManager.set_custom_instructions(manager, 'Help with\nmy own Clicky')
    module.CompanionManager.set_response_language(manager, 'hi')
    module.CompanionManager.set_stt_language(manager, 'hi')
    assert setting('CUSTOM_INSTRUCTIONS') == 'Help with\nmy own Clicky'
    assert setting('RESPONSE_LANGUAGE') == setting('WHISPER_LANGUAGE') == 'hi'
    assert manager._stt is None
    manager.sig_error.emit.assert_not_called()
