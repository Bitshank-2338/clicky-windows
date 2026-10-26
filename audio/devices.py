"""Select stable microphone identities and normalize capture to mono 16 kHz."""
import numpy as np
import sounddevice as sd

from audio.capture import SAMPLE_RATE, resample_pcm


def input_devices():
    hosts = sd.query_hostapis()
    return [dict(info, index=index, host_name=hosts[info['hostapi']]['name'])
            for index, info in enumerate(sd.query_devices()) if info['max_input_channels'] > 0]


def identity(info):
    return {'name': info['name'], 'hostapi': info['host_name']}


def recommended_inputs(devices):
    # Keep one driver per exact name; all driver alternatives remain available.
    chosen = {}
    for info in devices:
        key = info['name'].casefold()
        if key not in chosen or 'WASAPI' in info['host_name'].upper():
            chosen[key] = info
    return list(chosen.values())


def resolve_input(device=None, saved=None):
    devices = input_devices()
    warning = ''
    if saved == {'default': True}:
        device, saved = None, None
    if saved:
        found = next((item for item in devices if identity(item) == saved), None)
        if found:
            return found, warning
        warning = 'Your saved microphone is unavailable. Using the Windows default; choose a microphone in Settings.'
        device = None
    if device is not None and device >= 0:
        found = next((item for item in devices if item['index'] == device), None)
        if found:
            return found, warning
        warning = 'The selected microphone is unavailable. Using the Windows default.'
    hosts = sd.query_hostapis()
    default = next((host['default_input_device'] for host in hosts
                    if 'WASAPI' in host['name'].upper() and host['default_input_device'] >= 0), sd.default.device[0])
    found = next((item for item in devices if item['index'] == default), None)
    if not found:
        raise OSError('No default microphone is available. Connect one and enable desktop microphone access in Windows Settings.')
    return found, warning


def open_input_stream(callback, device=None, saved=None):
    info, warning = resolve_input(device, saved)
    native = int(info['default_samplerate'])
    channels = min(2, int(info['max_input_channels']))
    formats = dict.fromkeys([(SAMPLE_RATE, 1), (native, 1), (native, channels), (48000, 1), (44100, 1), (48000, channels), (44100, channels)])
    last_error = None
    for rate, count in formats:
        stream = None
        def convert(indata, frames, time_info, status, capture_rate=rate):
            mono = indata
            if mono.ndim == 2:
                # Some stereo inputs put the microphone only on the right channel.
                active = np.argmax(np.sum(mono.astype(np.float32) ** 2, axis=0))
                mono = mono[:, active]
            if capture_rate != SAMPLE_RATE:
                mono = np.frombuffer(resample_pcm(mono.tobytes(), capture_rate), dtype=np.int16)
            callback(mono.reshape(-1, 1), len(mono), time_info, status)
        try:
            stream = sd.InputStream(device=info['index'], samplerate=rate, channels=count,
                                    dtype='int16', blocksize=rate * 30 // 1000, callback=convert)
            stream.start()
            return stream, info, warning
        except Exception as exc:
            last_error = exc
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
    raise OSError(f"Cannot open {info['name']} ({info['host_name']}). Check Windows microphone permissions, mute and exclusive-mode use by other apps. Select Windows default or another driver in Settings. Restart Clicky after removing audio drivers. ({type(last_error).__name__})") from last_error
