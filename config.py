import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load env files in priority order. .env.local overrides .env (Next.js convention,
# which is how many users — including this one — keep their real keys).
_HERE = Path(__file__).parent
for _name in (".env", ".env.local"):
    _p = _HERE / _name
    if _p.exists():
        load_dotenv(_p, override=True)


DEFAULT_SYSTEM_PROMPT = """You are Clicky, a VISUAL AI tutor running on Windows. You live
next to the user's cursor. Your job is to *show*, not just tell.

{{CONTEXT}}

HARD RULES (never break):
  1. LOCATE QUESTIONS ("where is X", "how do I click Y", "show me X", "find X"):
     Point at it and explain in ONE sentence. If it's not visible, say so
     plainly instead of guessing.

  2. MULTI-STEP TASKS (export, install, configure, setup, etc.):
     Describe ONLY the next single step, then end with "Say 'next' when
     ready." Never dump a numbered list of 5 steps in one response.

  3. VISION: describe only what is ACTUALLY in the screenshot. Trust your
     eyes over the user's words.

  4. WEB SEARCH: when search results appear, use them as your primary
     source and give a direct answer — never say "I don't know" if the
     results contain real facts. Today is {{TODAY}}.

  5. PUBLIC figures, celebrities, companies, products — answer freely.
     Never refuse with "I can't identify people" — these are public figures
     with public information available.

STYLE: warm, concise, teacher-y. 1-2 sentences per step. No markdown bullets
unless genuinely listing options."""


# Technical rules Clicky needs to actually draw on screen and point at
# elements correctly. Always appended after the user-editable prompt above
# — kept separate because breaking this syntax breaks pointing/drawing, and
# most users have no reason to touch it.
_TECHNICAL_RULES = """

COORDINATE SYSTEM (applies to every tag below): coordinates are NORMALIZED
0-1000 relative to the screenshot. x=0 is the LEFT edge, x=1000 the RIGHT
edge; y=0 is the TOP, y=1000 the BOTTOM. The exact centre of the screen is
500,500. Sizes/radii use the same scale (100 = 10% of screen width).

POINTING: when you need to point at something, emit EXACTLY ONE tag
[POINT:x,y:label:screen1] using normalized coordinates and a 1-3 word label,
using any DETECTED ELEMENT coordinate provided above verbatim if given.

DRAWING TAGS (coords normalized 0-1000, trailing :color always optional):
  [LINE:x1,y1->x2,y2:color]         straight line
  [ARROW:x1,y1->x2,y2:color]        line with arrowhead (points at x2,y2)
  [CIRCLE:x,y,r:label:color]        ring; label optional
  [RECT:x1,y1,x2,y2:color]          rectangle by opposite corners
  [POLY:x1,y1 x2,y2 x3,y3:color]    closed shape, 3+ points (triangles!)
  [TEXT:x,y:content:color:size]     text; size s|m|l (default m)
  [ANGLE:x,y,s,rot:color]           right-angle marker at corner (x,y)
  [CLEAR]                           wipe all drawings
Colors: blue red green yellow orange purple white cyan (default blue).
For real UI elements use anchors instead of guessing coordinates:
  [CIRCLE:@Save button]  [UNDERLINE:@File menu]  — resolved pixel-perfectly.

TEACHING WITH DRAWINGS: when explaining something visible on screen (a
figure, chart, diagram, equation, code), draw ON it — trace edges, label
parts, add helper lines — interleaving tags with your spoken words in the
order a teacher draws on a whiteboard. Place TEXT next to what it names,
never covering it. Use up to ~10 shapes for a full lesson, 1-2 for a quick
highlight.

ACCURACY DISCIPLINE: if DETECTED FIGURES are listed above, copy those
vertex numbers into your tags EXACTLY. Only estimate coordinates for things
not listed. When estimating: fix the figure's bounding box first, derive
every endpoint from it, and reuse IDENTICAL numbers for shared vertices.

NARRATION SYNC: Clicky speaks your response sentence by sentence and draws
each sentence's tags WHILE saying that sentence — put every tag immediately
after the words that describe it, spread across the lesson (1-2 tags per
sentence), never dump all tags at the start or end."""


@dataclass
class Config:
    # LLM
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY") or None)
    google_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or None)
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    # Legacy single-model knob — still respected as a fallback for both slots
    # below. New users should prefer OLLAMA_VISION_MODEL / OLLAMA_TEXT_MODEL.
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2-vision"))
    # Two-slot model selection: vision = screen-aware queries, text = Code Mode
    # / journal Q&A / no-screenshot replies. Either can be overridden at runtime
    # via cfg.set_ollama_model("vision"|"text", name).
    ollama_vision_model: str = field(default_factory=lambda: os.getenv("OLLAMA_VISION_MODEL", "") or os.getenv("OLLAMA_MODEL", "llama3.2-vision"))
    ollama_text_model:   str = field(default_factory=lambda: os.getenv("OLLAMA_TEXT_MODEL", "") or "llama3.2:3b")

    # LM Studio — local OpenAI-compatible server (Developer tab → Start Server).
    # No key needed. Leave LMSTUDIO_MODEL empty to use whatever's loaded.
    lmstudio_host: str = field(default_factory=lambda: os.getenv("LMSTUDIO_HOST", "http://localhost:1234/v1"))
    lmstudio_model: str = field(default_factory=lambda: os.getenv("LMSTUDIO_MODEL", ""))

    # STT
    deepgram_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY") or None)
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "base"))
    # ISO code (e.g. "de", "en"). Empty = auto-detect language per utterance.
    whisper_language: str = field(default_factory=lambda: os.getenv("WHISPER_LANGUAGE", ""))
    # sounddevice input device index. Empty/unset = system default mic.
    mic_device_index: Optional[int] = field(default_factory=lambda: (
        int(v) if (v := os.getenv("MIC_DEVICE_INDEX", "").strip()) else None
    ))
    # Fixed reply language (ISO 639-1, e.g. "de"). Empty = auto-detect per
    # message (can mix languages if transcription is inconsistent).
    response_language: str = field(default_factory=lambda: os.getenv("RESPONSE_LANGUAGE", ""))
    # User-defined scope/rules appended to every system prompt (e.g. "only
    # help with Excel, refuse anything else"). Empty = no restriction.
    custom_instructions: str = field(default_factory=lambda: os.getenv(
        "CUSTOM_INSTRUCTIONS", DEFAULT_SYSTEM_PROMPT
    ).replace("\\n", "\n"))

    # TTS
    elevenlabs_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY") or None)
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", ""))

    # Search
    tavily_api_key: Optional[str] = field(default_factory=lambda: os.getenv("TAVILY_API_KEY") or None)

    # App
    # Push-to-talk. Two-key modifier combo — no clash with app shortcuts and
    # easier to hold than a 3-key chord. Override with CLICKY_HOTKEY in .env.
    hotkey: str = field(default_factory=lambda: os.getenv("CLICKY_HOTKEY", "ctrl+win"))

    def llm_provider(self) -> str:
        """Returns the active LLM provider (runtime override > priority chain).

        Priority chain: Claude > OpenAI > GitHub Copilot > Gemini > Ollama.
        """
        override = os.environ.get("CLICKY_ACTIVE_LLM", "").strip().lower()
        if override in self.available_llm_providers():
            return override
        if self.anthropic_api_key:
            return "claude"
        if self.openai_api_key:
            return "openai"
        try:
            from ai.github_copilot_provider import is_authenticated as _gh_ok
            if _gh_ok():
                return "copilot"
        except Exception:
            pass
        if self.google_api_key:
            return "gemini"
        return "ollama"

    def available_llm_providers(self) -> list[str]:
        """All providers the user can switch to right now."""
        out = []
        if self.anthropic_api_key:
            out.append("claude")
        if self.openai_api_key:
            out.append("openai")
        try:
            from ai.github_copilot_provider import is_authenticated as _gh_ok
            if _gh_ok():
                out.append("copilot")
        except Exception:
            pass
        if self.google_api_key:
            out.append("gemini")
        out.append("ollama")     # always available if the daemon is running
        out.append("lmstudio")   # always available if the local server is running
        return out

    def set_active_llm(self, name: str) -> None:
        """Runtime switch — next query uses this provider. Persisted to .env."""
        name = name.lower()
        os.environ["CLICKY_ACTIVE_LLM"] = name
        # Write to .env so the choice survives restarts
        env_path = _HERE / ".env"
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True) if env_path.exists() else []
            key = "CLICKY_ACTIVE_LLM"
            found = False
            for i, line in enumerate(lines):
                if line.startswith(key + "=") or line.startswith(key + " ="):
                    lines[i] = f"{key}={name}\n"
                    found = True
                    break
            if not found:
                lines.append(f"\n{key}={name}\n")
            env_path.write_text("".join(lines), encoding="utf-8")
        except Exception:
            pass  # non-fatal — runtime switch still works via os.environ

    def stt_provider(self) -> str:
        # Allow explicit override via env (so users can force whisper_cpp etc.)
        forced = os.getenv("CLICKY_STT", "").strip().lower()
        if forced in ("deepgram", "openai", "whisper_cpp", "faster_whisper"):
            return forced
        if self.deepgram_api_key:
            return "deepgram"
        if self.openai_api_key:
            return "openai"
        # Prefer whisper.cpp (GPU-accelerated, same engine as Handy) when the
        # pywhispercpp package is installed; otherwise fall back to faster-whisper.
        try:
            import pywhispercpp  # noqa: F401
            return "whisper_cpp"
        except ImportError:
            return "faster_whisper"

    def tts_provider(self) -> str:
        if self.elevenlabs_api_key:
            return "elevenlabs"
        if self.openai_api_key:
            return "openai"
        return "edge_tts"

    def search_provider(self) -> str:
        if self.tavily_api_key:
            return "tavily"
        return "duckduckgo"

    def describe(self) -> dict:
        """Human-readable summary of active providers for the setup panel."""
        return {
            "llm": self.llm_provider(),
            "stt": self.stt_provider(),
            "tts": self.tts_provider(),
            "search": self.search_provider(),
            "ollama_model": self.ollama_model,
            "ollama_vision_model": self.get_ollama_model("vision"),
            "ollama_text_model":   self.get_ollama_model("text"),
            "lmstudio_host": self.lmstudio_host,
            "lmstudio_model": self.lmstudio_model or "(auto — whatever's loaded)",
        }

    # ── Ollama runtime model selection ───────────────────────────────────

    def get_ollama_model(self, kind: str = "vision") -> str:
        """Return the active model for the given kind ("vision" | "text").

        Reads runtime override from CLICKY_OLLAMA_VISION_MODEL /
        CLICKY_OLLAMA_TEXT_MODEL first, then the dataclass field, then the
        legacy single-model knob.
        """
        env_key = "CLICKY_OLLAMA_VISION_MODEL" if kind == "vision" else "CLICKY_OLLAMA_TEXT_MODEL"
        runtime = os.environ.get(env_key, "").strip()
        if runtime:
            return runtime
        return self.ollama_vision_model if kind == "vision" else self.ollama_text_model

    def set_ollama_model(self, kind: str, name: str) -> None:
        """Runtime switch for vision/text Ollama model. Persists for the session."""
        if kind not in ("vision", "text"):
            return
        env_key = "CLICKY_OLLAMA_VISION_MODEL" if kind == "vision" else "CLICKY_OLLAMA_TEXT_MODEL"
        os.environ[env_key] = (name or "").strip()
        # Mirror onto the dataclass so describe() picks it up immediately
        if kind == "vision":
            self.ollama_vision_model = name
        else:
            self.ollama_text_model = name


# Singleton
cfg = Config()
