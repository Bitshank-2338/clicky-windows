"""
Tutor-layer helpers: active window detection, privacy masking, "next" detection,
and locate-query classification. Kept out of companion_manager.py so the
orchestrator stays readable.
"""

from __future__ import annotations

import ctypes
import re
from ctypes import wintypes


# ── Active-window title (for per-app context memory) ─────────────────────────

def active_window_title() -> str:
    try:
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return ""
        n = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value or ""
    except Exception:
        return ""


def app_key(title: str) -> str:
    """Reduce a noisy window title to a stable per-app key.

    Examples:
      "Premiere Pro - project.prproj"  -> "Premiere Pro"
      "YouTube — Google Chrome"        -> "Google Chrome"
      "VS Code — main.py"              -> "VS Code"
    """
    if not title:
        return "desktop"
    # Take the right-most app name chunk (usually after last "-" or "—")
    parts = re.split(r"\s[-—–|]\s", title)
    return (parts[-1] if parts else title).strip()[:48] or "desktop"


# ── Locate-query classification ──────────────────────────────────────────────

LOCATE_RE = re.compile(
    r"\b(where\s+(is|do|can|should)|how\s+do\s+i\s+(click|find|open|access|use|get\s+to)|"
    r"point\s+(at|to)|show\s+me\s+(the|where)|click\s+(the|on)|find\s+the|"
    r"locate\s+the|highlight\s+the)\b",
    re.IGNORECASE,
)

MULTISTEP_RE = re.compile(
    r"\b(how\s+(do\s+i|to)\s+(export|install|configure|set\s*up|setup|publish|"
    r"deploy|enable|disable|build|launch|download|upload|record))\b",
    re.IGNORECASE,
)

NEXT_RE = re.compile(r"^\s*(next|continue|go\s*on|keep\s*going|what'?s?\s*next)[\s.!?]*$",
                     re.IGNORECASE)

STOP_RE = re.compile(r"^\s*(stop|quit|cancel|never\s*mind|nevermind)[\s.!?]*$",
                     re.IGNORECASE)


def is_locate(q: str) -> bool:
    return LOCATE_RE.search(q) is not None


def is_multistep(q: str) -> bool:
    return MULTISTEP_RE.search(q) is not None


def is_next(q: str) -> bool:
    return NEXT_RE.match(q or "") is not None


def is_stop(q: str) -> bool:
    return STOP_RE.match(q or "") is not None


# ── New voice classifiers ────────────────────────────────────────────────────

REPEAT_RE = re.compile(
    r"^\s*(repeat|say\s+(it|that)\s*again|say\s+again|once\s+more|"
    r"what\s+(did\s+you|d['’]you)\s+say)[\s.!?]*$",
    re.IGNORECASE,
)

JOURNAL_TODAY_RE = re.compile(
    r"\bwhat\s+(did|have)\s+i\s+(learn|learned|asked)\s+(today|so\s+far)\b",
    re.IGNORECASE,
)

JOURNAL_WEEK_RE = re.compile(
    r"\bwhat\s+(did|have)\s+i\s+(learn|learned)\s+(this\s+week|recently|"
    r"in\s+the\s+past\s+week)\b",
    re.IGNORECASE,
)

QUIZ_REVIEW_RE = re.compile(
    r"\b(quiz\s+me|review\s+me|test\s+me)(\s+on\s+(what\s+i\s+learned|my\s+notes))?\b",
    re.IGNORECASE,
)


def is_repeat(q: str) -> bool:
    return REPEAT_RE.match(q or "") is not None


def is_journal_today(q: str) -> bool:
    return JOURNAL_TODAY_RE.search(q or "") is not None


def is_journal_week(q: str) -> bool:
    return JOURNAL_WEEK_RE.search(q or "") is not None


def is_quiz_review(q: str) -> bool:
    return QUIZ_REVIEW_RE.search(q or "") is not None


# ── Privacy guard — block sensitive windows from being screenshotted ──────────

PRIVACY_BLOCKLIST = (
    r"\b(password|credential|secret|keepass|bitwarden|1password|lastpass|"
    r"authenticator|banking|sign\s*in|login|\.env)\b"
)
_PRIVACY_RE = re.compile(PRIVACY_BLOCKLIST, re.IGNORECASE)


def is_sensitive_window(title: str) -> bool:
    return bool(title) and _PRIVACY_RE.search(title) is not None
