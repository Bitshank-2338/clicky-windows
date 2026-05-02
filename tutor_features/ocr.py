"""
OCR fallback for fine print.

When a screenshot has tiny text the LLM struggles to read (code in an IDE,
spreadsheet cells, error messages buried in logs), we run Tesseract on the
relevant region and inject the extracted text into the system prompt.

Cheap heuristic: trigger when the user's question mentions exact text like
'what does the error say', 'read the line', 'what's in the cell', etc.

Setup:
    pip install pytesseract pillow
    + install Tesseract OCR binary:
      https://github.com/UB-Mannheim/tesseract/wiki
"""

from __future__ import annotations

import io
import re
from typing import Optional

from PIL import Image

OCR_TRIGGER_RE = re.compile(
    r"\b(read|what does|what is|recite)\s+"
    r"(it|that|this|the\s+(text|line|error|message|code|cell|paragraph))\b",
    re.IGNORECASE,
)


def needs_ocr(query: str) -> bool:
    return OCR_TRIGGER_RE.search(query) is not None


def run_ocr(jpeg_bytes: bytes) -> str:
    """Return the extracted text from a JPEG screenshot, or empty string."""
    try:
        import pytesseract   # type: ignore
    except ImportError:
        return ""
    try:
        img = Image.open(io.BytesIO(jpeg_bytes))
        text = pytesseract.image_to_string(img)
        return (text or "").strip()
    except pytesseract.TesseractNotFoundError:
        return ""
    except Exception:
        return ""


def format_for_prompt(text: str) -> str:
    if not text.strip():
        return ""
    return (
        f"\n\n[OCR-EXTRACTED TEXT FROM SCREEN]\n{text[:8000]}\n"
        "Use the OCR text above when quoting exact strings the user is asking "
        "about. The screenshot may be blurry; OCR is more reliable for fine print."
    )
