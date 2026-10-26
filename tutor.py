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


def app_key(title: str, hwnd=None) -> str:
    """Reduce a noisy window title to a stable per-app key.

    Examples:
      "Premiere Pro - project.prproj"  -> "Premiere Pro"
      "YouTube — Google Chrome"        -> "Google Chrome"
      "VS Code — main.py"              -> "VS Code"
    """
    if not title:
        return "desktop"
    try:
        import os
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = wintypes.HWND
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId(hwnd or u.GetForegroundWindow(), ctypes.byref(pid))
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid.value)
        if handle:
            try:
                buf = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(buf))
                kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
                if kernel.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    return os.path.basename(buf.value).lower()
            finally:
                kernel.CloseHandle(handle)
    except (AttributeError, OSError):
        pass
    parts = re.split(r"\s[-—–|]\s", title)
    for part in parts:
        if re.search(r"\b(code|chrome|firefox|edge|premiere|word|excel|notepad)\b", part, re.I):
            return part.strip()[:48]
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
    return LOCATE_RE.search(q or "") is not None or re.search(
        r"कहाँ|कहां|दिखाओ|बताओ.*बटन|\bkahan\b|\bdikhao\b|\bwhere.*button\b", q or "", re.I
    ) is not None


def is_multistep(q: str) -> bool:
    return MULTISTEP_RE.search(q) is not None


def is_next(q: str) -> bool:
    return NEXT_RE.match(q or "") is not None or (q or "").strip().lower() in {"आगे", "अगला", "aage", "agla"}


def is_stop(q: str) -> bool:
    return STOP_RE.match(q or "") is not None or (q or "").strip().lower() in {"रुको", "बंद करो", "ruko", "band karo"}


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

# ── Identity questions ────────────────────────────────────────────────────────
# OpenAI / Claude refuse to identify people in images even when the answer is
# trivially in their training data. So when the user asks "who is X" / "tell me
# about X" / "what does X do" — we strip the screenshot and answer from text +
# web search. is_identity_question() returns True when:
#   • the query starts with a who/what-is question word, AND
#   • the rest looks like a proper noun (a person/thing name, not a generic word)
#
# False on things like "who is on my screen", "what is this", "who am I" — those
# legitimately want the screenshot.
IDENTITY_RE = re.compile(
    r"^\s*"
    r"(who\s+(is|are|was|were)|"
    r"tell\s+me\s+about|"
    r"what\s+(is|does|do)|"
    r"info\s+(about|on)|"
    r"how\s+old\s+is)"
    r"\s+"
    # require what follows to NOT be a screen-referring phrase
    r"(?!"
    r"this|that|it|my\s+screen|on\s+(my\s+)?screen|going\s+on|"
    r"happening|the\s+screen|here|i\s|i\b)"
    r".+",
    re.IGNORECASE,
)


def is_identity_question(q: str) -> bool:
    """Only explicit named-person questions may omit screen context."""
    if not q or re.search(r"\b(this|that|screen|code|error|button|here|wrong|my|on)\b", q, re.I):
        return False
    return re.match(r"^\s*(?:who (?:is|was)|how old is)\s+\S", q, re.I) is not None


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
    r"authenticator|banking|sign\s*in|login)\b|(?<![\w])\.env(?:\b|$)"
)
_PRIVACY_RE = re.compile(PRIVACY_BLOCKLIST, re.IGNORECASE)


def is_sensitive_window(title: str) -> bool:
    return bool(title) and _PRIVACY_RE.search(title) is not None


def target_name(query: str) -> str:
    """Remove request words before comparing with accessibility element names."""
    query = re.sub(r"[?.!]+$", "", query.strip())
    query = re.sub(r"^(?:(?:where\s+(?:is|are)|where's|show\s+me|point\s+(?:at|to)|click(?:\s+on)?|find|locate|highlight|how\s+(?:do|can)\s+i\s+(?:find|click|open|access))\s+)(?:the\s+)?", "", query, flags=re.I)
    query = re.sub(r"\s*(?:kahan(?:\s+hai)?|कहाँ(?:\s+है)?|कहां(?:\s+है)?|दिखाओ)\s*$", "", query, flags=re.I).strip()
    return re.sub(r"\s+(?:button|icon|field|bar|menu|बटन)$", "", query, flags=re.I).strip()
