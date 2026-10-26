"""
Multi-monitor screenshot helper.

The tricky part is keeping THREE coordinate systems straight:

  1. PHYSICAL  — what mss.grab() returns. Real GPU pixels. e.g. 2560x1440.
  2. LOGICAL   — what the OS / Qt cursor uses after DPI scaling. e.g. 1707x960
                 on a 150%-DPI 2560x1440 display.
  3. DOWNSCALED — what we send to the LLM (1280-wide JPEG to keep tokens low).

The overlay plots in LOGICAL coordinates. The element-detector model sees the
downscaled image. So `detect_element` must return coords in LOGICAL space, with
the monitor's logical-origin offset applied for multi-monitor setups.

ScreenShot now carries every number needed to convert between them.
"""

import base64
import ctypes
import io
from dataclasses import dataclass
from typing import List

import mss
import mss.tools
from PIL import Image
from screen.privacy import redact, sensitive_rectangles

_display_layout = []


def configure_displays(screens):
    """Snapshot Qt's logical geometries on its main thread before capture workers run."""
    global _display_layout
    _display_layout = [(s.name(), s.geometry().x(), s.geometry().y(),
                        s.geometry().width(), s.geometry().height(), s.devicePixelRatio()) for s in screens]


def _display_geometry(monitor):
    # Qt/Windows retain physical monitor origins; scale only the local displacement.
    for _, x, y, width, height, scale in _display_layout:
        if x == monitor["left"] and y == monitor["top"]:
            return x, y, scale
    return monitor["left"], monitor["top"], _query_dpi_scale(monitor)


@dataclass
class ScreenShot:
    index: int

    # Downscaled image actually sent to the LLM
    width: int            # downscaled width (pixels in JPEG)
    height: int           # downscaled height
    base64_jpeg: str

    # Real (physical) monitor size and origin in mss virtual-screen coords
    physical_width: int
    physical_height: int
    physical_left: int    # mss-reported origin (physical px)
    physical_top: int

    # DPI scale (physical / logical). 1.0 on normal displays, 1.5 on 150% DPI.
    dpi_scale: float

    # Convenience: where this monitor's top-left sits in LOGICAL screen space
    logical_left: int
    logical_top: int


def _query_dpi_scale(monitor=None) -> float:
    """Best-effort DPI scale for the primary monitor.
    Returns 1.0 if anything goes wrong."""
    try:
        # GetDpiForSystem returns DPI as integer (96 = 100%, 144 = 150%)
        u = ctypes.windll.user32
        if monitor:
            from ctypes import wintypes
            u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            u.MonitorFromPoint.restype = wintypes.HANDLE
            handle = u.MonitorFromPoint(wintypes.POINT(monitor["left"] + 1, monitor["top"] + 1), 2)
            dx, dy = wintypes.UINT(), wintypes.UINT()
            sh = ctypes.windll.shcore
            sh.GetDpiForMonitor.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]
            if sh.GetDpiForMonitor(handle, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
                return dx.value / 96.0
        gdfs = getattr(u, "GetDpiForSystem", None)
        if gdfs:
            return max(1.0, gdfs() / 96.0)
        # Fallback: ratio of GetSystemMetrics(physical) vs (logical)
        return 1.0
    except Exception:
        return 1.0


def capture_all_screens(max_width: int = 1280, privacy_guard: bool = True, preferred_point=None) -> List[ScreenShot]:
    """Capture all monitors. Each ScreenShot carries everything needed
    to convert detection coords back into logical screen space."""
    rectangles = sensitive_rectangles() if privacy_guard else []
    results = []
    with mss.mss() as sct:
        # mss monitor index 0 is the combined virtual screen; 1+ are real monitors
        monitors = list(sct.monitors[1:])
        try:
            from ctypes import wintypes
            point = wintypes.POINT()
            if preferred_point:
                point.x, point.y = preferred_point
            if preferred_point or ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                monitors.sort(key=lambda m: not (m["left"] <= point.x < m["left"] + m["width"] and m["top"] <= point.y < m["top"] + m["height"]))
        except AttributeError:
            pass
        for i, monitor in enumerate(monitors, start=1):
            logical_left, logical_top, dpi = _display_geometry(monitor)
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

            phys_w, phys_h = img.width, img.height
            phys_left = int(monitor.get("left", 0))
            phys_top  = int(monitor.get("top",  0))
            if privacy_guard:
                redact(img, phys_left, phys_top, rectangles + sensitive_rectangles())

            # Downscale only the JPEG we send to the LLM — keep physical numbers intact
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize(
                    (max_width, int(img.height * ratio)),
                    Image.Resampling.LANCZOS,
                )

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

            results.append(ScreenShot(
                index=i,
                width=img.width,
                height=img.height,
                base64_jpeg=encoded,
                physical_width=phys_w,
                physical_height=phys_h,
                physical_left=phys_left,
                physical_top=phys_top,
                dpi_scale=dpi,
                logical_left=logical_left,
                logical_top=logical_top,
            ))

    return results


def capture_primary() -> ScreenShot:
    """Capture only the primary monitor."""
    screens = capture_all_screens()
    return next((s for s in screens if s.physical_left == 0 and s.physical_top == 0), screens[0] if screens else None)


def screen_count() -> int:
    with mss.mss() as sct:
        return len(sct.monitors) - 1  # subtract virtual combined monitor
