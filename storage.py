"""Per-user atomic settings and Windows-protected credentials."""
import ctypes
import json
import os
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path

_lock = threading.RLock()


def data_dir() -> Path:
    path = Path(os.getenv("CLICKY_DATA_DIR") or Path(os.getenv("LOCALAPPDATA", Path.home())) / "Clicky")
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def setting(name: str, default=None):
    with _lock:
        return read_json(data_dir() / "settings.json", {}).get(name, default)


def set_setting(name: str, value) -> None:
    with _lock:
        path = data_dir() / "settings.json"
        values = read_json(path, {})
        values[name] = value
        atomic_write(path, json.dumps(values, ensure_ascii=False).encode("utf-8"))


def _protect(content: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise OSError("Clicky's credential store requires Windows DPAPI")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(content)
    incoming = Blob(len(content), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel32.LocalFree(outgoing.data)


def credentials() -> dict:
    path = data_dir() / "credentials.bin"
    with _lock:
        return json.loads(_protect(path.read_bytes(), decrypt=True)) if path.exists() else {}


def set_credential(name: str, value: str) -> None:
    with _lock:
        values = credentials()
        # Empty values override legacy .env keys as well as removing saved secrets.
        values[name] = value
        atomic_write(data_dir() / "credentials.bin", _protect(json.dumps(values).encode("utf-8")))
