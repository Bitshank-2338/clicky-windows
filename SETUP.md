# Clicky for Windows — Setup Guide

## Prerequisites

- Python 3.11+
- Ollama installed (https://ollama.com) — for student/free mode
- `llama3.2-vision` model pulled: `ollama pull llama3.2-vision`

## Install

```bash
cd clicky-windows

# Student version (free, no API keys needed)
pip install -r requirements-student.txt

# Full version (all providers)
pip install -r requirements.txt
```

> **PyAudio on Windows** may need: `pip install pipwin && pipwin install pyaudio`

## Configure

```bash
copy .env.example .env
# Edit .env and add any API keys you have
# Everything is optional — Ollama is the free fallback
```

## Run

```bash
python main.py
```

A floating panel appears in the bottom-right corner.
The Clicky icon appears in your system tray.

**Hold `Ctrl+Alt+Space`** to speak. Release to send.

## Provider Priority (auto-detected)

| Priority | LLM | STT | TTS |
|----------|-----|-----|-----|
| 1st | Claude (ANTHROPIC_API_KEY) | Deepgram (DEEPGRAM_API_KEY) | ElevenLabs (ELEVENLABS_API_KEY) |
| 2nd | OpenAI (OPENAI_API_KEY) | OpenAI Whisper (OPENAI_API_KEY) | OpenAI TTS (OPENAI_API_KEY) |
| Free | Ollama (local) | faster-whisper (local) | edge-tts (free, no key) |

## Phases Remaining

- [ ] Phase 4: Cursor overlay pointing animation (UI complete, coordinate mapping pending)
- [ ] Phase 5: Web search grounding (Tavily/DuckDuckGo wired in, needs testing)
- [ ] Phase 6: PyInstaller .exe packaging + installer
