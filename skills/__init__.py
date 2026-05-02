"""
Skill system — user-defined voice triggers + custom behaviours.

Drop a .py file into this folder. Each file exposes a SKILL dict at module
level:

    SKILL = {
        "name":        "Self Mode",
        "trigger":     r"(self ?mode|allow ?clicks|enable ?clicking)",
        "description": "Lets Clicky click for you instead of pointing.",
        "handler":     handle_self_mode,   # async fn(manager, transcript) -> str
    }

Loading happens at startup via load_all().  Triggers are tested *before*
the LLM runs — same priority as built-in 'next' / 'stop' commands.

Status: loader + interface stable; ship your own skills here.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional

# Skill dict shape (for type hints — using TypedDict would be stricter)
# {
#     "name":        str,
#     "trigger":     str,           # regex
#     "description": str,
#     "handler":     Callable[[manager, transcript], Awaitable[str]],
# }

_loaded: list[dict] = []


def _user_skills_dir() -> Path:
    """User-level skills dir at ~/.clicky/skills/ — survives reinstall."""
    return Path.home() / ".clicky" / "skills"


def load_all() -> list[dict]:
    """Discover + import every skill module in this package and ~/.clicky/skills."""
    global _loaded
    _loaded = []

    # Bundled skills (shipped with Clicky)
    here = Path(__file__).parent
    for f in here.glob("*.py"):
        if f.name.startswith("_"):
            continue
        _try_import(f)

    # User skills
    user_dir = _user_skills_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    for f in user_dir.glob("*.py"):
        _try_import(f)

    return _loaded


def _try_import(path: Path) -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            f"clicky_skill_{path.stem}", str(path)
        )
        if not spec or not spec.loader:
            return
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        skill = getattr(mod, "SKILL", None)
        if not isinstance(skill, dict):
            return
        if not all(k in skill for k in ("name", "trigger", "handler")):
            return
        skill.setdefault("description", "")
        skill["_compiled"] = re.compile(skill["trigger"], re.IGNORECASE)
        _loaded.append(skill)
    except Exception as e:
        # Don't let one bad skill kill startup. Log and skip.
        print(f"[skills] failed to load {path}: {e}")


def match(transcript: str) -> Optional[dict]:
    """Return the first skill whose trigger matches the user's utterance."""
    for s in _loaded:
        if s["_compiled"].search(transcript):
            return s
    return None


def list_skills() -> list[dict]:
    return list(_loaded)
