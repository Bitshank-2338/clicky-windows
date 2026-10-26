"""One capture policy for the assistant, OCR, recordings and browser previews."""
import ctypes
import os
from ctypes import wintypes

from tutor import is_sensitive_window


def sensitive_rectangles() -> list[tuple[int, int, int, int]]:
    """Conservatively redact visible sensitive top-level windows on every display."""
    if os.name != "nt":
        raise OSError("Screen privacy inspection requires Windows")
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    rects = []
    errors = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        try:
            if user.IsWindowVisible(hwnd) and not user.IsIconic(hwnd):
                title = ctypes.create_unicode_buffer(4096)
                user.GetWindowTextW(hwnd, title, len(title))
                if is_sensitive_window(title.value):
                    rect = wintypes.RECT()
                    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    rects.append((rect.left, rect.top, rect.right, rect.bottom))
        except Exception as exc:
            errors.append(exc)
        return True

    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    if not user.EnumWindows(visit, 0) or errors:
        raise OSError("Privacy inspection failed; screenshot withheld")
    return rects


def redact(image, left: int, top: int, rectangles=None):
    from PIL import ImageDraw
    rectangles = sensitive_rectangles() if rectangles is None else rectangles
    draw = ImageDraw.Draw(image)
    for x1, y1, x2, y2 in rectangles:
        box = (max(0, x1 - left), max(0, y1 - top), min(image.width, x2 - left), min(image.height, y2 - top))
        if box[2] > box[0] and box[3] > box[1]:
            draw.rectangle(box, fill="black")
    return image


def exclude_window(widget, excluded=True):
    if os.name == "nt":
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        if not user.SetWindowDisplayAffinity(int(widget.winId()), 0x11 if excluded else 0):
            raise ctypes.WinError(ctypes.get_last_error())
