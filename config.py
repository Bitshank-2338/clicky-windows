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

    # STT
    deepgram_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY") or None)
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "base"))

    # TTS
    elevenlabs_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY") or None)
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", ""))

    # Search
    tavily_api_key: Optional[str] = field(default_factory=lambda: os.getenv("TAVILY_API_KEY") or None)

    # App
    hotkey: str = field(default_factory=lambda: os.getenv("CLICKY_HOTKEY", "ctrl+alt+space"))

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
        out.append("ollama")   # always available if the daemon is running
        return out

    def set_active_llm(self, name: str) -> None:
        """Runtime switch — next query uses this provider."""
        os.environ["CLICKY_ACTIVE_LLM"] = name.lower()

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
