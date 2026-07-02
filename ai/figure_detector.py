"""
Local geometric-figure detector — the "eyes" behind Clicky's drawing accuracy.

Vision LLMs are unreliable at pixel localization (especially small local
models), so Clicky doesn't trust them with coordinates. This module finds
geometric figures (triangles, rectangles, circles, polygons) on the screen
with classic OpenCV contour analysis and hands the LLM their EXACT vertices,
pre-normalized to the 0-1000 tag coordinate space. The LLM only has to echo
numbers — which every model can do — and the manager additionally snaps any
sloppy stroke endpoints to the nearest detected vertex.

Runs entirely on CPU in ~50-150 ms on a 1280-wide screenshot. If OpenCV is
not installed, detection silently returns nothing and Clicky falls back to
pure LLM localization.
"""

from __future__ import annotations

import base64
import io
import logging
import math
from dataclasses import dataclass
from typing import List, Tuple

log = logging.getLogger("clicky.figures")


@dataclass
class Figure:
    kind: str                            # "triangle" | "quad" | "circle" | "poly"
    vertices: List[Tuple[int, int]]      # normalized 0-1000 (empty for circle)
    center: Tuple[int, int]              # normalized 0-1000
    radius: int                          # normalized x-units (circles only)
    bbox: Tuple[int, int, int, int]      # normalized (l, t, r, b)


def detect_figures(base64_jpeg: str, max_figures: int = 4) -> List[Figure]:
    """Find prominent geometric figures in a screenshot JPEG.

    Coordinates are returned normalized 0-1000 relative to the image, ready
    for prompt injection and for _denorm() on the manager side.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        log.debug("opencv not installed — figure detection disabled")
        return []

    try:
        img = Image.open(io.BytesIO(base64.b64decode(base64_jpeg))).convert("L")
        gray = np.array(img)
    except Exception as e:
        log.debug("figure detect decode failed: %s", e)
        return []

    H, W = gray.shape
    if W < 100 or H < 100:
        return []

    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    min_area = W * H * 0.002          # ignore icons / noise
    max_area = W * H * 0.55           # ignore the window frame itself

    def _norm_pt(px: float, py: float) -> Tuple[int, int]:
        return (int(round(px / W * 1000)), int(round(py / H * 1000)))

    figs: List[Figure] = []
    seen: set = set()
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        peri = cv2.arcLength(c, True)
        if peri <= 0:
            continue
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        n = len(approx)
        x, y, w, h = cv2.boundingRect(c)

        # Dedupe inner/outer edges of the same stroke (Canny doubles lines)
        key = (x // 15, y // 15, w // 15, h // 15, min(n, 6))
        if key in seen:
            continue

        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
        circularity = 4 * math.pi * area / (peri * peri)

        if n == 3:
            kind = "triangle"
        elif n == 4 and circularity < 0.82:
            kind = "quad"
        elif circularity > 0.82:
            kind, approx = "circle", []
        elif 5 <= n <= 8:
            kind = "poly"
        else:
            continue

        seen.add(key)
        verts = [_norm_pt(p[0][0], p[0][1]) for p in approx]
        radius = int(round(math.sqrt(area / math.pi) / W * 1000)) if kind == "circle" else 0
        figs.append(Figure(
            kind=kind,
            vertices=verts,
            center=_norm_pt(cx, cy),
            radius=radius,
            bbox=(*_norm_pt(x, y), *_norm_pt(x + w, y + h)),
        ))

    # Largest figures first — those are what the user is looking at
    figs.sort(key=lambda f: -(f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    figs = figs[:max_figures]
    if figs:
        log.info("figure detect: %s", [(f.kind, f.vertices or f.center) for f in figs])
    return figs


def figures_prompt(figs: List[Figure]) -> str:
    """Render detected figures as a prompt block the LLM copies coords from."""
    if not figs:
        return ""
    lines = [
        "\n\nDETECTED FIGURES (found by Clicky's local vision, coordinates are "
        "EXACT and already normalized 0-1000 — when teaching about one of "
        "these, you MUST build your drawing tags from these vertices verbatim "
        "instead of estimating):"
    ]
    for i, f in enumerate(figs, 1):
        if f.kind == "circle":
            lines.append(
                f"  {i}. circle: center=({f.center[0]},{f.center[1]}), "
                f"radius={f.radius}"
            )
        else:
            vs = " ".join(f"({x},{y})" for x, y in f.vertices)
            lines.append(f"  {i}. {f.kind}: vertices {vs}")
    return "\n".join(lines) + "\n"


__all__ = ["Figure", "detect_figures", "figures_prompt"]
