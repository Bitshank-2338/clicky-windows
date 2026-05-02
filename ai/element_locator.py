"""
Port of ElementLocationDetector.swift — uses Claude's Computer Use API to find
the exact pixel coordinate of a UI element the user is asking about.

Only runs when ANTHROPIC_API_KEY is set. Returns (x, y) in the full screenshot's
original pixel space so the overlay can fly to it.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx
from PIL import Image

from config import cfg


# Anthropic-recommended Computer Use resolutions (matched by aspect ratio)
_CU_RESOLUTIONS = (
    (1024, 768,  1024 / 768),   # 4:3
    (1280, 800,  1280 / 800),   # 16:10
    (1366, 768,  1366 / 768),   # 16:9
)

_API_URL = "https://api.anthropic.com/v1/messages"
_BETA_HEADER = "computer-use-2025-11-24"


@dataclass
class Detected:
    x: int             # in original screenshot pixel space
    y: int
    screen_index: int


def _pick_resolution(w: int, h: int) -> Tuple[int, int]:
    ar = w / max(1, h)
    best = (1280, 800)
    smallest = float("inf")
    for rw, rh, rar in _CU_RESOLUTIONS:
        d = abs(ar - rar)
        if d < smallest:
            smallest = d
            best = (rw, rh)
    return best


def _resize_jpeg(jpeg_bytes: bytes, tw: int, th: int) -> bytes:
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    resized = img.resize((tw, th), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def detect_element(
    *,
    screenshot_jpeg_b64: str,
    original_width: int,           # downscaled JPEG width
    original_height: int,          # downscaled JPEG height
    screen_index: int,
    user_question: str,
    model: str = "claude-sonnet-4-6",
    physical_width: int | None = None,
    physical_height: int | None = None,
    physical_left: int = 0,
    physical_top: int = 0,
    dpi_scale: float = 1.0,
) -> Optional[Detected]:
    """Detect a UI element and return its position in **logical screen
    coordinates** (the same coordinate space Qt's QCursor.pos() uses), with
    the monitor's origin offset already applied.

    The model sees a 1024/1280/1366-wide version of the screenshot; we scale
    its returned coordinate back through:

        Computer-Use space  →  downscaled JPEG space  →  physical monitor px
                            →  + monitor origin  →  logical screen px
    """
    api_key = cfg.anthropic_api_key
    if not api_key:
        return None

    # Default: assume the JPEG is at native physical resolution
    if physical_width is None:
        physical_width = original_width
    if physical_height is None:
        physical_height = original_height

    tw, th = _pick_resolution(original_width, original_height)
    jpeg_bytes = base64.b64decode(screenshot_jpeg_b64)
    resized_bytes = _resize_jpeg(jpeg_bytes, tw, th)
    resized_b64 = base64.b64encode(resized_bytes).decode("ascii")

    user_prompt = (
        f'The user asked this question while looking at their screen: "{user_question}"\n\n'
        "Look at the screenshot. If there is a specific UI element (button, link, "
        "menu item, text field, icon, etc.) that the user should interact with or "
        "is asking about, click on that element.\n\n"
        "If the question is purely conceptual (e.g., \"what does HTML mean?\") and "
        "there's no specific element to point to, just respond with text saying "
        "\"no specific element\"."
    )

    body = {
        "model": model,
        "max_tokens": 256,
        "tools": [{
            "type": "computer_20251124",
            "name": "computer",
            "display_width_px": tw,
            "display_height_px": th,
        }],
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": resized_b64,
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": _BETA_HEADER,
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(_API_URL, json=body, headers=headers)
            if r.status_code >= 400:
                return None
            data = r.json()
    except Exception:
        return None

    # Find a tool_use block with coordinate
    for block in data.get("content", []):
        if block.get("type") != "tool_use":
            continue
        coord = (block.get("input") or {}).get("coordinate")
        if not coord or len(coord) != 2:
            continue
        cu_x, cu_y = float(coord[0]), float(coord[1])
        cu_x = max(0.0, min(cu_x, tw))
        cu_y = max(0.0, min(cu_y, th))

        # Stage 1: Computer-Use space → physical monitor pixels
        # (skip the downscaled-JPEG step entirely — the ratio is the same)
        px = cu_x / tw * physical_width
        py = cu_y / th * physical_height

        # Stage 2: physical monitor px → physical virtual-screen px
        # (apply the monitor's origin offset so monitor-2 coords don't land
        # on monitor-1)
        vx = px + physical_left
        vy = py + physical_top

        # Stage 3: physical → logical (Qt cursor space)
        scale = dpi_scale if dpi_scale > 0 else 1.0
        lx = int(round(vx / scale))
        ly = int(round(vy / scale))
        return Detected(x=lx, y=ly, screen_index=screen_index)

    return None
