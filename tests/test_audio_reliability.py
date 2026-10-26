import asyncio
import io
import wave
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest


@pytest.fixture
def microphones(monkeypatch):
    import audio.devices as module
    devices = [
        dict(name='USB microphone', hostapi=0, max_input_channels=2, default_samplerate=48000),
        dict(name='Speakers', hostapi=0, max_input_channels=0, default_samplerate=48000),
        dict(name='USB microphone', hostapi=1, max_input_channels=2, default_samplerate=48000),
        dict(name='Headset', hostapi=1, max_input_channels=1, default_samplerate=44100),
    ]
    hosts = [dict(name='MME', default_input_device=0), dict(name='Windows WASAPI', default_input_device=2)]
    monkeypatch.setattr(module.sd, 'query_devices', lambda: devices)
    monkeypatch.setattr(module.sd, 'query_hostapis', lambda: hosts)
    return module, devices


def test_microphone_identity_survives_index_changes(microphones):
    module, devices = microphones
    saved = module.identity(module.input_devices()[2])
    devices.insert(0, dict(name='New virtual input', hostapi=0, max_input_channels=1, default_samplerate=16000))
    selected, warning = module.resolve_input(3, saved)
    assert selected['name'] == 'Headset' and selected['index'] == 4 and not warning


def test_missing_mic_falls_back_with_notice_and_default_overrides_old_index(microphones):
    module, _ = microphones
    selected, warning = module.resolve_input(0, {'name': 'Removed Voicemeeter', 'hostapi': 'MME'})
    assert selected['index'] == 2 and 'unavailable' in warning
    assert module.resolve_input(0, {'default': True})[0]['index'] == 2
    assert [item['index'] for item in module.recommended_inputs(module.input_devices())] == [2, 3]


def test_start_failure_closes_stream_and_retries_native_stereo(microphones, monkeypatch):
    module, _ = microphones
    attempts, received = [], []
    class Stream:
        def __init__(self, **kwargs):
            self.options, self.closed = kwargs, False
            attempts.append(self)
        def start(self):
            if self.options['samplerate'] != 48000 or self.options['channels'] != 2:
                raise OSError('unsupported format at stream start')
            right_only = np.column_stack([np.zeros(1440, dtype=np.int16), np.full(1440, 1000, dtype=np.int16)])
            self.options['callback'](right_only, 1440, None, None)
        def close(self):self.closed = True
    monkeypatch.setattr(module.sd, 'InputStream', Stream)
    stream, info, _ = module.open_input_stream(lambda pcm, *args:received.append(pcm.copy()))
    assert all(item.closed for item in attempts[:-1]) and not stream.closed
    assert info['index'] == 2
    assert received[0].shape == (480, 1) and np.all(received[0] == 1000)


def test_failed_listener_can_retry_and_stop_failure_still_closes(monkeypatch):
    from audio.ambient_listener import AmbientListener, Mode
    import audio.devices as devices
    open_stream = Mock(side_effect=OSError('permission denied'))
    monkeypatch.setattr(devices, 'open_input_stream', open_stream)
    listener = AmbientListener(lambda level:None, lambda:None, ambient=True)
    with pytest.raises(OSError):listener.start()
    assert not listener._running and listener._stream is None
    with pytest.raises(OSError):listener.start_recording()
    assert not listener._running and listener._mode is Mode.STANDBY
    stream = Mock()
    stream.stop.side_effect = OSError('unplugged')
    open_stream.side_effect = None
    open_stream.return_value = stream, {'name':'USB', 'host_name':'Windows WASAPI'}, ''
    listener.start()
    listener.stop()
    stream.close.assert_called_once()


def test_quiet_microphone_is_normalized_before_gating():
    from audio.capture import capture_problem, pcm16_to_wav
    pcm = np.full(16000, 100, dtype=np.int16).tobytes()
    assert not capture_problem(pcm)
    assert 'silence' in capture_problem(bytes(32000))
    assert 'No microphone audio' in capture_problem(b'')
    with wave.open(io.BytesIO(pcm16_to_wav(pcm))) as audio:
        decoded = np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16)
    assert np.max(np.abs(decoded)) > 100


def test_ambient_toggle_can_recover_from_mic_open_error(monkeypatch):
    from audio.ambient_listener import AmbientListener
    import audio.devices as devices
    monkeypatch.setattr(devices, 'open_input_stream', Mock(side_effect=OSError('permission denied')))
    listener = AmbientListener(lambda level:None, lambda:None, ambient=False)
    listener.start()
    with pytest.raises(OSError):listener.set_ambient(True)
    assert not listener.ambient and listener._stream is None


def test_silent_capture_is_reported_without_transcription():
    from companion_manager import CompanionManager
    manager = SimpleNamespace(_listener=SimpleNamespace(stop_recording=lambda:bytes(32000)),
        _live_audio=None, _live_stt_future=None, sig_error=Mock(), _emit_state=Mock(),
        _dictating=True, _get_stt=Mock(side_effect=AssertionError('Do not transcribe silence')))
    asyncio.run(CompanionManager._end_capture_and_process(manager))
    assert 'silence' in manager.sig_error.emit.call_args.args[0]
    assert not manager._dictating and manager._current_task is None


def test_edge_403_uses_local_voice_once_and_stops_it(monkeypatch):
    import audio.tts.edge_tts_provider as edge
    import audio.tts.sapi_tts_provider as sapi
    class Forbidden(Exception):status = 403
    attempts, spoken, notices = [], [], []
    class Remote:
        def __init__(self, *args, **kwargs):attempts.append(args)
        async def stream(self):
            raise Forbidden('a server URL should not reach the user')
            yield
    class Local:
        async def speak(self, text):spoken.append(text)
        stop = Mock()
    monkeypatch.setattr(edge.edge_tts, 'Communicate', Remote)
    monkeypatch.setattr(sapi, 'SapiTTSProvider', Local)
    provider = edge.EdgeTTSProvider(on_fallback=notices.append)
    async def run():
        await provider.speak('First sentence.')
        await provider.speak('Second sentence.')
    asyncio.run(run())
    provider.stop()
    assert len(attempts) == len(notices) == 1 and 'HTTP 403' in notices[0]
    assert 'server URL' not in notices[0]
    assert spoken == ['First sentence.', 'Second sentence.']
    Local.stop.assert_called_once()


def test_capture_changes_state_before_slow_transcription():
    from companion_manager import CompanionManager, AppState
    states = []
    class STT:
        async def transcribe(self, pcm):
            assert states[-1] is AppState.THINKING
            raise asyncio.TimeoutError
    manager = SimpleNamespace(_listener=SimpleNamespace(stop_recording=lambda:np.full(16000, 1000, dtype=np.int16).tobytes()),
        _live_audio=None, _live_stt_future=None, sig_error=Mock(), _emit_state=states.append,
        _dictating=False, _get_stt=lambda:STT())
    asyncio.run(CompanionManager._end_capture_and_process(manager))
    assert states[-1] is AppState.IDLE
    assert 'timed out' in manager.sig_error.emit.call_args.args[0]


def test_edge_cancellation_does_not_fallback(monkeypatch):
    import audio.tts.edge_tts_provider as edge
    class Remote:
        async def stream(self):
            raise asyncio.CancelledError
            yield
    monkeypatch.setattr(edge.edge_tts, 'Communicate', lambda *args, **kwargs:Remote())
    provider = edge.EdgeTTSProvider()
    with pytest.raises(asyncio.CancelledError):asyncio.run(provider.speak('Cancelled'))
    assert provider._fallback is None


def test_edge_playback_error_does_not_retry_with_other_voice(monkeypatch):
    import audio.tts.edge_tts_provider as edge
    class Remote:
        async def stream(self):yield {'type':'audio', 'data':b'audio'}
    async def broken_playback(data):raise OSError('output device missing')
    monkeypatch.setattr(edge.edge_tts, 'Communicate', lambda *args, **kwargs:Remote())
    monkeypatch.setattr(edge, 'play_mp3_async', broken_playback)
    provider = edge.EdgeTTSProvider()
    with pytest.raises(OSError):asyncio.run(provider.speak('Hello'))
    assert provider._fallback is None


def test_settings_microphone_test_releases_input(qt_app, microphones, monkeypatch):
    from ui.settings_window import SettingsWindow
    import audio.ambient_listener as module
    calls = []
    class Listener:
        device_name = 'Test microphone'
        def __init__(self, *args, **kwargs):calls.append(self)
        def start_recording(self):pass
        def stop_recording(self):return np.full(16000, 1000, dtype=np.int16).tobytes()
        stop = Mock()
    monkeypatch.setattr(module, 'AmbientListener', Listener)
    settings = SettingsWindow(Mock())
    assert not calls
    settings.test_microphone()
    settings.finish_microphone_test()
    assert 'Audio received' in settings.mic_status.text()
    assert settings._mic_listener is None
    Listener.stop.assert_called_once()
    settings.close()
