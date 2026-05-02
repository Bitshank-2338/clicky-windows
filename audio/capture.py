import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS    = 1
BLOCK_SIZE  = 1024


class MicCapture:
    """
    Real-time microphone capture using sounddevice (PortAudio wrapper).
    No C compilation required — ships prebuilt wheels on Windows.
    """

    def __init__(
        self,
        on_audio_chunk: Callable[[bytes], None],
        on_level: Callable[[float], None],
    ):
        self._on_chunk = on_audio_chunk
        self._on_level = on_level
        self._stream: Optional[sd.InputStream] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        if not self._running:
            return
        pcm_bytes = indata.tobytes()
        pcm_float = indata.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(pcm_float ** 2)))
        self._on_level(rms)
        self._on_chunk(pcm_bytes)


def pcm16_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wraps raw PCM16 bytes in a WAV container."""
    import struct
    channels = 1
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm_data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, channels, sample_rate,
        byte_rate, block_align, bits,
        b"data", data_size,
    )
    return header + pcm_data
