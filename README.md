# Clicky for Windows ðŸ”µ

> **An AI teaching companion that lives next to your cursor.**
> Ask it anything about your screen â€” it points, explains, and guides you step-by-step, like a real tutor sitting beside you.

Clicky is a Windows port of [farzaa/clicky](https://github.com/farzaa/clicky) (originally macOS/SwiftUI). Built with **Python 3.11+ and PyQt6**, runs fully in the background, works with every major AI provider.

---

## Hi, this is Clicky ðŸ‘‹

[![Watch the demo](assets/clicky-demo.gif)](https://youtu.be/WYY9yJHDaEU)

> ðŸŽ¬ **[Watch full demo on YouTube â†’](https://youtu.be/WYY9yJHDaEU)**

Clicky is a little AI buddy that **lives next to your cursor**. You hold a hotkey, ask it something about your screen, and it talks back â€” pointing at buttons, walking you through steps, drawing arrows on your screen. Think of it as having a patient tutor sitting beside you while you learn anything: video editing, coding, a new app, whatever.

No more Alt-Tab to ChatGPT. No more typing out descriptions of what's on your screen. Just hold **Ctrl + Win**, speak, and Clicky handles the rest.

Works **100% offline** with Ollama, or plug in your Claude / OpenAI / Gemini / GitHub Copilot key for the full experience.

---

## What it looks like

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Your screen (browser, IDE, Premiere, etc.) â”‚
â”‚                                             â”‚
â”‚          ðŸ”µâ—‚  â† Clicky blue buddy           â”‚
â”‚          (floats beside your real cursor)   â”‚
â”‚                                             â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”               â”‚
â”‚  â”‚  Clicky  [Claude]    â€”   â”‚  â† panel      â”‚
â”‚  â”‚  â— Thinkingâ€¦             â”‚               â”‚
â”‚  â”‚  "The search bar is      â”‚               â”‚
â”‚  â”‚   right here â†—"          â”‚               â”‚
â”‚  â”‚  Model: claude-sonnet-4â€¦ â”‚               â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

The blue triangle sits **35 px right / 25 px below** your real cursor. When you ask it to point at something it **flies** to that element via a smooth bezier arc (teacher pace), dwells with a pulsing highlight ring, then flies back.

---

## Feature List

### ðŸŽ™ï¸ Voice Activation
- Hold **Ctrl + Win** to push-to-talk
- Say **"Clicky"** for hands-free wake word
- Press **Esc** to stop any response or TTS mid-stream

### ðŸ‘ï¸ Screen Aware
- Full multi-monitor screenshot on every query
- Describes only what it sees â€” never hallucinates
- Detects active window title for per-app memory

### ðŸŽ¯ Pixel-Perfect Pointing
- **Two-stage grid locator** works with *any* vision LLM â€” Claude, Copilot, OpenAI, Gemini, Ollama
- Stage 1: draws a numbered 12Ã—8 grid on the screenshot, LLM picks the cell
- Stage 2: zooms into that 3Ã—3 cell area, runs a 6Ã—6 fine-grid pass for sub-cell precision
- Bezier arc flight with configurable teacher pace
- Pulsing highlight ring + speech bubble label on the target
- Works on any DPI scale (4K, HiDPI, multi-monitor setups)

### ðŸ§‘â€ðŸ« Real Tutor Behaviour
- **Locate queries** â†’ points + 1-sentence explanation (no generic text directions)
- **Multi-step tasks** â†’ breaks into steps, says "Say 'next' when ready"
- **"Next"** / **"Continue"** â†’ advances lesson without a new LLM call
- **"Repeat"** â†’ replays the last answer via TTS without re-querying
- **"Stop"** / **"Cancel"** â†’ cancels generation instantly

### ðŸŒ Web Search (Real-Time Data)
- DuckDuckGo HTML scrape + concurrent page fetch â€” **no API key needed**
- Optional Tavily upgrade for deeper results
- Responses grounded in today's data with `[1]`, `[2]` citations
- Always knows today's date â€” never gives stale answers

### ðŸ”„ Multi-Provider LLM (Runtime Switching)
| Provider | How to unlock |
|---|---|
| **Claude** (Anthropic) | `ANTHROPIC_API_KEY` in `.env` |
| **OpenAI GPT-4o** | `OPENAI_API_KEY` in `.env` |
| **GitHub Copilot** | Free for students â€” device-flow login via tray |
| **Gemini** | `GOOGLE_API_KEY` in `.env` |
| **Ollama** (local) | Run `ollama serve` â€” free, always available |

Priority chain (auto-detected): **Claude â†’ OpenAI â†’ Copilot â†’ Gemini â†’ Ollama**

Switch mid-session from the system tray â€” takes ~1 second, no restart.

### ðŸ“‹ Live Model Lists (Auto-Refreshed)
- Claude, OpenAI, Gemini: live model list fetched from vendor APIs, **30-day cache**
- GitHub Copilot: live `/models` endpoint with billing multiplier, **6-hour cache**
- Free Copilot models auto-prioritised (no premium quota burned by default)
- Panel model dropdown always reflects the actual available models for your account

### ðŸ”Š Multi-Provider TTS
| Provider | Quality | Key needed |
|---|---|---|
| **ElevenLabs** | Premium voice clone | `ELEVENLABS_API_KEY` |
| **OpenAI TTS** | High quality | `OPENAI_API_KEY` |
| **Edge TTS** | Free, 400+ voices | None |

### ðŸ—£ï¸ Multi-Provider STT
| Provider | Speed | Key needed |
|---|---|---|
| **Deepgram** | Fast, accurate | `DEEPGRAM_API_KEY` |
| **OpenAI Whisper** | Very accurate | `OPENAI_API_KEY` |
| **whisper.cpp** | 3-5Ã— faster local (Handy engine) | None (`pip install pywhispercpp`) |
| **Faster-Whisper** | Local, free fallback | None |

### ðŸ§  Per-App Memory
- Separate conversation history per active application
- Context never bleeds between Premiere, VS Code, Chrome, etc.
- History cap: last 20 messages per app

### ðŸ“ Knowledge Journal + Spaced Repetition
- Every Q&A automatically logged to a local SQLite database
- Ask **"what did we cover today?"** â†’ summary of today's session
- Ask **"what did we cover this week?"** â†’ weekly digest
- **SM-2 spaced repetition** â€” Clicky reminds you to review topics at optimal intervals (1 â†’ 3 â†’ 7 â†’ 14 â†’ 30 â†’ 60 â†’ 120 days)
- Say **"quiz me on what I should review"** â†’ flashcard session from your journal
- Journal stored at `%LOCALAPPDATA%\Clicky\journal.db`

### ðŸ“„ Document Context (Drag & Drop)
- Drag a **PDF, DOCX, TXT, MD, CSV, or code file** onto the Clicky panel
- Clicky reads it and uses it as context for your next questions
- Or use: **Tray â†’ Journal â†’ Attach documentâ€¦** for a file picker
- Supports multi-file: attach several docs and ask cross-document questions

### ðŸ” OCR Fallback (Fine Print)
- When query mentions "fine print", "small text", "read that", etc., Clicky runs **Tesseract OCR** on the screenshot
- Extracts text that's too small or low-contrast for the LLM's vision to read
- Requires: Tesseract binary from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
- Gracefully skipped if Tesseract isn't installed

### ðŸ’» Code Mode (Auto-Detect)
- Detects VS Code, Cursor, IntelliJ, PyCharm, Vim, Neovim, Sublime, etc. by window title
- Automatically injects a **code-specialist system prompt addendum**: prefer code blocks, include language tags, explain algorithms step by step
- Toggle: **Tray â†’ Tutor Mode â†’ Code Mode (auto)**

### ðŸŽ“ Tutor Modes (Tray â†’ Tutor Mode)
| Toggle | What it does |
|---|---|
| **Slow Mode** | 1.7Ã— slower bezier flight + longer dwell â€” students can follow the pointer |
| **Quiz Mode** | Clicky asks YOU questions instead of answering; evaluates in one sentence |
| **Privacy Guard** | Skips screenshot when password manager / banking window detected |
| **Code Mode (auto)** | Code-specialist prompt when IDE is active |
| **Multilingual** | Auto-detects language, responds in kind, switches TTS voice |
| **OCR Fallback** | Runs Tesseract on screenshots when fine text is mentioned |

### ðŸŒ Multilingual Auto-Detect
- Detects query language via `langdetect` + Unicode script heuristics
- Responds in the same language automatically
- Switches Edge TTS voice to match (Hindi â†’ HiRA-Neha, French â†’ fr-FR-DeniseNeural, etc.)
- 15+ languages supported: EN, HI, FR, DE, ES, PT, AR, ZH, JA, KO, RU, IT, NL, PL, TR
- Toggle: **Tray â†’ Tutor Mode â†’ Multilingual**

### ðŸŽ¬ Lesson Recording (MP4 + Transcript)
- Records screen at 8 fps as an MP4 alongside a Markdown transcript of all Q&A
- Start: **Tray â†’ Lesson Recording â†’ Start recording**
- Stop: tray menu â†’ produces `lesson_YYYY-MM-DD_HH-MM.mp4` + `lesson_YYYY-MM-DD_HH-MM_transcript.md`
- Saved to `%LOCALAPPDATA%\Clicky\recordings\`

### ðŸ–Šï¸ Whiteboard Annotations
- Clicky can draw directly on your screen as it explains:
  - `[ARROW:x1,y1->x2,y2]` â€” animated arrow between two points
  - `[CIRCLE:x,y,r:label]` â€” pulsing circle with optional label
  - `[UNDERLINE:x,y,w]` â€” underline beneath text
  - `[LABEL:x,y:text]` â€” floating text label
- Annotations fade out after ~4 seconds automatically
- Cleared automatically on the next query

### ðŸ–±ï¸ Workflow Capture
- Records your mouse clicks and keyboard strokes while you work
- Start: **Tray â†’ Workflow Capture â†’ Start capturing my clicks**
- Stop: **Tray â†’ Workflow Capture â†’ Stop + send to Clicky**
- Ask: **"What did I just do?"** â†’ Clicky narrates your workflow step-by-step
- Requires `pynput` (included in requirements.txt)

### ðŸŽ¤ Voice Picker
- Switch TTS voice mid-session: say **"change voice to [voice name]"**
- Edge TTS voices: `AvaNeural`, `JennyNeural`, `GuyNeural`, `AriaNeural`, etc.
- Use `python -c "from audio.tts.edge_tts_provider import EdgeTTSProvider; print(EdgeTTSProvider.list_voices_sync())"` to list all 400+ voices

### ðŸ”’ Privacy Guard (on by default)
Detects sensitive windows and skips the screenshot entirely:
- Password managers: KeePass, Bitwarden, 1Password, LastPass, Authenticator
- Sensitive pages: `login`, `sign in`, `banking`, `.env` files, `credit card`

### ðŸ› ï¸ Skills System (User-Extensible)
Create your own voice triggers â€” no pull request needed:

```python
# ~/.clicky/skills/my_skill.py
import asyncio

SKILL = {
    "name": "open_calculator",
    "trigger": r"(open|launch|start) calculator",
    "description": "Opens Windows Calculator",
    "handler": open_calc,
}

async def open_calc(transcript: str, manager) -> str:
    import subprocess
    subprocess.Popen("calc.exe")
    return "Opening calculator for you."
```

Place skill files in `~/.clicky/skills/` â€” Clicky auto-loads on startup.

---

## Installation

### Prerequisites
- Windows 10 / 11 (64-bit)
- Python 3.11, 3.12, or 3.14
- A working microphone

### 1. Clone
```bash
git clone https://github.com/Bitshank-2338/clicky-windows.git
cd clicky-windows
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API keys
Create `.env` in the project root (copy from `.env.example`):

```env
# â”€â”€ LLM (add whichever you have â€” at least one required) â”€â”€
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# â”€â”€ STT (all optional â€” falls back to Faster-Whisper) â”€â”€â”€â”€â”€
DEEPGRAM_API_KEY=...

# â”€â”€ TTS (all optional â€” falls back to Edge TTS) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...

# â”€â”€ Web Search (optional â€” falls back to DuckDuckGo) â”€â”€â”€â”€â”€â”€
TAVILY_API_KEY=...

# â”€â”€ Ollama (local AI) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2-vision

# â”€â”€ Customise â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CLICKY_HOTKEY=ctrl+win
WHISPERCPP_MODEL=base.en
```

### 4. GitHub Copilot (free for students)
```
Tray â†’ Model â†’ Sign in to GitHub Copilotâ€¦
â†’ visit github.com/login/device â†’ enter code shown in terminal
```

Token cached at `%LOCALAPPDATA%\Clicky\github_token.json`. Default model = `gpt-4o-mini` (free tier).

### 5. Run
```bash
python main.py
```

A blue dot appears in your system tray. Clicky is now running.

---

## Zero-Cost Setup (100% Free)

No API keys at all â€” uses local AI, local STT, free TTS:

```env
OLLAMA_VISION_MODEL=qwen2-vl:7b
OLLAMA_TEXT_MODEL=qwen2.5-coder:7b
```

1. Install [Ollama](https://ollama.ai) â†’ run `ollama serve`
2. Pull models: `ollama pull qwen2-vl:7b && ollama pull qwen2.5-coder:7b`
3. `pip install -r requirements.txt`
4. `python main.py`

Clicky uses **two Ollama model slots**: a vision model for screen-aware questions (pointing, "what's on screen?") and a text model for Code Mode / journal Q&A. Switch between them at any time from the tray: **Tray â†’ Ollama â†’ Vision model / Text model**.

**Recommended free models (Tray â†’ Ollama â†’ Pull recommendedâ€¦):**

| Slot | Model | Size | Good for |
|---|---|---|---|
| Vision | `qwen2-vl:7b` | 5 GB | Screen reading, pointing â€” best quality |
| Vision | `llama3.2-vision:11b` | 8 GB | Alternative vision model |
| Vision | `llava:7b` | 4 GB | Fastest option |
| Text | `qwen2.5-coder:7b` | 4 GB | Code questions â€” excellent |
| Text | `llama3.2:3b` | 2 GB | Tiny, fits any GPU |
| Text | `mistral:7b` | 4 GB | General Q&A |

**Limitations vs paid:** Slower responses, web search uses DuckDuckGo only.

---

## Distribution â€” Single .exe Installer

For sharing with friends without Python:

```bash
# 1. Generate icon
python assets/make_icon.py

# 2. Build
pip install pyinstaller
pyinstaller clicky.spec --clean --noconfirm

# 3. Distribute
# â†’ dist/Clicky/  (entire folder)
# â†’ or build Setup.exe with Inno Setup using installer.iss
```

The `dist/Clicky/Clicky.exe` runs on any Windows machine without Python. Include a `.env` file next to the exe with your API keys, or set them as system environment variables.

See [BUILD.md](BUILD.md) for full packaging instructions including Inno Setup installer.

---

## Usage

### Voice Commands
| Say | Action |
|---|---|
| *"Where is the search bar?"* | Points at it + 1-sentence explanation |
| *"How do I export this video?"* | Step-by-step lesson mode |
| *"What's on screen?"* | Screen description |
| *"Search for [topic]"* | Web search + cited answer |
| *"next"* / *"continue"* | Advance to next lesson step |
| *"repeat"* | Replay last answer via TTS |
| *"stop"* / *"cancel"* | End current lesson |
| *"quiz me"* | Quiz mode on current screen |
| *"what did we cover today?"* | Today's journal summary |
| *"what should I review?"* | Spaced repetition flashcards |
| *"what did I just do?"* | Workflow capture narration |
| *"change voice to Jenny"* | Switch TTS voice |

### Keyboard
| Key | Action |
|---|---|
| `Ctrl + Win` (hold) | Push-to-talk |
| `Esc` | Stop response / TTS immediately |

### Tray Menu
Right-click the tray icon â†’ full menu including:
- Provider switcher (Claude / OpenAI / Copilot / Gemini / Ollama)
- Tutor Mode submenus
- Lesson Recording controls
- Workflow Capture controls
- Journal (view folder, attach doc)
- Show/Hide Panel

---

## Architecture

```
main.py
  â”œâ”€â”€ CompanionManager          # async state machine + orchestrator
  â”‚     â”œâ”€â”€ AmbientListener     # always-on mic + wake-word
  â”‚     â”œâ”€â”€ STT provider        # Deepgram / OpenAI Whisper / whisper.cpp / Faster-Whisper
  â”‚     â”œâ”€â”€ screen.capture      # multi-monitor JPEG (physical px + DPI metadata)
  â”‚     â”œâ”€â”€ tutor.py            # classifiers, privacy guard, window detection
  â”‚     â”œâ”€â”€ tutor_features/
  â”‚     â”‚     â”œâ”€â”€ journal.py        # SQLite Q&A log + SM-2 spaced repetition
  â”‚     â”‚     â”œâ”€â”€ pdf_context.py    # PDF/DOCX/TXT text extraction
  â”‚     â”‚     â”œâ”€â”€ ocr.py            # Tesseract OCR fallback
  â”‚     â”‚     â”œâ”€â”€ code_mode.py      # IDE detection + code prompt addendum
  â”‚     â”‚     â”œâ”€â”€ lesson_recorder.py # MP4 + transcript recording
  â”‚     â”‚     â”œâ”€â”€ multilang.py      # langdetect + Edge TTS voice switching
  â”‚     â”‚     â”œâ”€â”€ workflow_capture.py # pynput click/key recorder
  â”‚     â”‚     â””â”€â”€ collab.py         # live session skeleton (WebRTC)
  â”‚     â”œâ”€â”€ skills/             # user-extensible voice triggers
  â”‚     â”œâ”€â”€ ai.web_search       # DuckDuckGo + Tavily + citation builder
  â”‚     â”œâ”€â”€ ai.element_locator  # Claude Computer Use â†’ exact (x, y) pixel
  â”‚     â”œâ”€â”€ ai.model_registry   # live model lists with 30-day cache
  â”‚     â”œâ”€â”€ LLM provider        # Claude / OpenAI / Copilot / Gemini / Ollama
  â”‚     â””â”€â”€ TTS provider        # ElevenLabs / OpenAI / Edge TTS
  â”œâ”€â”€ CursorOverlay             # transparent click-through Qt window
  â”‚     â”œâ”€â”€ Blue triangle buddy (spring-follows cursor)
  â”‚     â”œâ”€â”€ Bezier arc flight   (teacher-pace pointing)
  â”‚     â”œâ”€â”€ Highlight ring      (pulsing circle on detected element)
  â”‚     â”œâ”€â”€ Speech bubble       (label while dwelling)
  â”‚     â”œâ”€â”€ Whiteboard annotations (arrows, circles, underlines, labels)
  â”‚     â”œâ”€â”€ Waveform bars       (listening state)
  â”‚     â””â”€â”€ Spinner arc         (thinking state)
  â”œâ”€â”€ CompanionPanel            # optional chat panel with model dropdown
  â””â”€â”€ TrayManager               # system tray + full context menu
```

### Coordinate Pipeline (Pixel-Perfect Pointing)
```
Screenshot â†’ JPEG (1280px max, for LLM tokens)
                â”‚
                â–¼
Claude Computer Use analyses screenshot
â†’ returns (x, y) in Computer-Use space (1280px wide)
                â”‚
                â–¼
element_locator.py converts:
  CU space â†’ physical monitor pixels
           â†’ + monitor origin (multi-monitor offset)
           â†’ Ã· DPI scale (HiDPI correction)
           = logical screen pixels
                â”‚
                â–¼
overlay.point_at(logical_x, logical_y)  â† correct position on any screen
```

---

## File Structure

```
clicky-windows/
â”œâ”€â”€ main.py                      # entry point â€” boots Qt, wires all signals
â”œâ”€â”€ companion_manager.py         # async orchestrator + state machine
â”œâ”€â”€ config.py                    # env loading, provider detection, priority chain
â”œâ”€â”€ tutor.py                     # classifiers, privacy guard, prompt builder
â”œâ”€â”€ hotkey.py                    # global hotkey + Esc stop
â”‚
â”œâ”€â”€ ai/
â”‚   â”œâ”€â”€ base_provider.py         # BaseLLMProvider ABC
â”‚   â”œâ”€â”€ claude_provider.py       # Anthropic Claude
â”‚   â”œâ”€â”€ openai_provider.py       # OpenAI GPT-4o
â”‚   â”œâ”€â”€ gemini_provider.py       # Google Gemini (via httpx)
â”‚   â”œâ”€â”€ ollama_provider.py       # Local Ollama
â”‚   â”œâ”€â”€ github_copilot_provider.py  # Copilot OAuth + live /models
â”‚   â”œâ”€â”€ element_locator.py       # Computer Use â†’ pixel coords
â”‚   â”œâ”€â”€ model_registry.py        # live model lists, 30-day cache
â”‚   â””â”€â”€ web_search.py            # DuckDuckGo + Tavily + citations
â”‚
â”œâ”€â”€ audio/
â”‚   â”œâ”€â”€ ambient_listener.py      # always-on mic + wake-word
â”‚   â”œâ”€â”€ capture.py               # PCM capture
â”‚   â”œâ”€â”€ playback.py              # cancellable audio (threading.Event)
â”‚   â”œâ”€â”€ stt/
â”‚   â”‚   â”œâ”€â”€ faster_whisper_stt.py
â”‚   â”‚   â”œâ”€â”€ whisper_cpp_stt.py   # pywhispercpp (optional, 3-5Ã— faster)
â”‚   â”‚   â”œâ”€â”€ openai_stt.py
â”‚   â”‚   â””â”€â”€ deepgram_stt.py
â”‚   â””â”€â”€ tts/
â”‚       â”œâ”€â”€ edge_tts_provider.py
â”‚       â”œâ”€â”€ openai_tts_provider.py
â”‚       â””â”€â”€ elevenlabs_provider.py
â”‚
â”œâ”€â”€ screen/
â”‚   â””â”€â”€ capture.py               # multi-monitor JPEG + DPI metadata
â”‚
â”œâ”€â”€ tutor_features/
â”‚   â”œâ”€â”€ journal.py               # SQLite Q&A log + SM-2 spaced repetition
â”‚   â”œâ”€â”€ pdf_context.py           # PDF/DOCX/TXT extraction
â”‚   â”œâ”€â”€ ocr.py                   # Tesseract OCR fallback
â”‚   â”œâ”€â”€ code_mode.py             # IDE detection + code prompt addendum
â”‚   â”œâ”€â”€ lesson_recorder.py       # MP4 + transcript
â”‚   â”œâ”€â”€ multilang.py             # language detection + voice switching
â”‚   â”œâ”€â”€ workflow_capture.py      # click/keystroke recorder
â”‚   â””â”€â”€ collab.py                # live session skeleton
â”‚
â”œâ”€â”€ skills/
â”‚   â”œâ”€â”€ __init__.py              # skill loader + trigger matcher
â”‚   â””â”€â”€ example_self_mode.py     # example skill
â”‚
â”œâ”€â”€ ui/
â”‚   â”œâ”€â”€ overlay.py               # CursorOverlay â€” all drawing + annotations
â”‚   â”œâ”€â”€ panel.py                 # CompanionPanel â€” chat + model dropdown
â”‚   â”œâ”€â”€ tray.py                  # TrayManager â€” tray icon + full menu
â”‚   â””â”€â”€ design.py                # shared colours, fonts, constants
â”‚
â”œâ”€â”€ assets/
â”‚   â”œâ”€â”€ make_icon.py             # generates icon.ico
â”‚   â””â”€â”€ icon.ico                 # (generated)
â”‚
â”œâ”€â”€ .env                         # your API keys (not committed)
â”œâ”€â”€ requirements.txt             # all Python dependencies
â”œâ”€â”€ clicky.spec                  # PyInstaller build spec
â”œâ”€â”€ installer.iss                # Inno Setup installer script
â”œâ”€â”€ build.bat                    # one-click build script
â”œâ”€â”€ BUILD.md                     # full build + packaging guide
â””â”€â”€ LICENSE                      # MIT
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | â€” | Claude LLM + Computer Use pointing |
| `OPENAI_API_KEY` | â€” | GPT-4o LLM + Whisper STT + OpenAI TTS |
| `GOOGLE_API_KEY` | â€” | Gemini LLM |
| `DEEPGRAM_API_KEY` | â€” | Deepgram STT |
| `ELEVENLABS_API_KEY` | â€” | ElevenLabs TTS |
| `ELEVENLABS_VOICE_ID` | â€” | Your ElevenLabs voice clone ID |
| `TAVILY_API_KEY` | â€” | Tavily search (upgrades DuckDuckGo) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2-vision` | Legacy single-model fallback |
| `OLLAMA_VISION_MODEL` | *(empty)* | Ollama model for screen-aware tasks (pointing, describe screen) |
| `OLLAMA_TEXT_MODEL` | *(empty)* | Ollama model for Code Mode + journal Q&A |
| `CLICKY_HOTKEY` | `ctrl+win` | Global push-to-talk combo |
| `CLICKY_STT` | *(auto)* | Force STT: `deepgram`/`openai`/`whisper_cpp`/`faster_whisper` |
| `CLICKY_ACTIVE_LLM` | *(auto)* | Force LLM: `claude`/`openai`/`copilot`/`gemini`/`ollama` |
| `WHISPER_MODEL` | `base` | Faster-Whisper model (`tiny`/`base`/`small`/`medium`) |
| `WHISPERCPP_MODEL` | `base.en` | whisper.cpp model size |

---

## Troubleshooting

**Clicky doesn't hear me**
â†’ Check default microphone in Windows Sound settings
â†’ Upgrade to Deepgram for better accuracy in noisy rooms

**"Thinkingâ€¦" forever with Ollama**
â†’ Run `ollama serve` in a terminal first
â†’ Run `ollama pull llama3.2-vision` to download the model
â†’ Press Esc to cancel

**Pointing at wrong location**
â†’ Make sure your active LLM supports vision (Copilot gpt-4o, Claude, Gemini 1.5+, or a vision Ollama model)
â†’ For Ollama: set a vision model via **Tray â†’ Ollama â†’ Vision model**
â†’ The universal two-stage grid locator works with every vision provider â€” no Anthropic key required

**GitHub Copilot auth fails**
â†’ Re-run: Tray â†’ Model â†’ Sign in to GitHub Copilotâ€¦
â†’ Check `%LOCALAPPDATA%\Clicky\github_token.json` exists

**Esc doesn't stop audio**
â†’ Make sure `sounddevice` is installed (`pip install sounddevice`)
â†’ Check that no other app has exclusive access to the audio device

**OCR returns nothing**
â†’ Install Tesseract binary from https://github.com/UB-Mannheim/tesseract/wiki
â†’ Add `C:\Program Files\Tesseract-OCR\` to your system PATH

**Lesson recording fails**
â†’ `pip install imageio imageio-ffmpeg`
â†’ ffmpeg binary is bundled with imageio-ffmpeg â€” no separate install needed

**Panel doesn't appear**
â†’ Right-click tray icon â†’ Show Panel
â†’ Or double-click the tray icon

---

## Contributing

Clicky is open to contributors from **anywhere in the world**. Whether you're a student who uses it every day, a developer who wants to add a feature, or someone who speaks a language we haven't supported yet â€” you're welcome here.

### Ways to contribute

- ðŸ› **Bug reports** â€” open an [Issue](https://github.com/Bitshank-2338/clicky-windows/issues) with steps to reproduce
- ðŸ’¡ **Feature ideas** â€” open an Issue tagged `enhancement`
- ðŸŒ **Translations** â€” add your language to `tutor_features/multilang.py`
- ðŸ”Œ **New LLM / STT / TTS providers** â€” follow the pattern in `ai/base_provider.py`
- ðŸ› ï¸ **Skills** â€” share your custom voice-trigger skills in a PR
- ðŸ“š **Docs** â€” better explanations, screenshots, GIFs

### How to send a pull request

```bash
# 1. Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/clicky-windows.git
cd clicky-windows

# 2. Create a branch
git checkout -b feat/your-feature-name

# 3. Make your changes, then commit
git add .
git commit -m "feat: describe what you added"

# 4. Push + open a PR against main
git push origin feat/your-feature-name
```

### Code style

- Python 3.11+ â€” type hints encouraged, `async/await` for I/O
- Keep providers self-contained in `ai/`, `audio/stt/`, `audio/tts/`
- New features belong in `tutor_features/` â€” one file per feature
- All cross-thread UI updates go through `pyqtSignal` â€” no direct widget calls from threads
- Test locally with `python main.py` before opening a PR

### First-time contributor?

Look for Issues tagged **`good first issue`** â€” these are small, well-scoped tasks that don't require deep knowledge of the codebase. Just comment "I'll take this" and we'll help you get started.

---

## Credits

- Original concept & macOS app: [farzaa/clicky](https://github.com/farzaa/clicky)
- Windows port: Shashank Singh
- Pointing engine: [Anthropic Computer Use API](https://docs.anthropic.com/en/docs/computer-use)
- Local STT: [whisper.cpp](https://github.com/ggerganov/whisper.cpp) via [pywhispercpp](https://github.com/abdeladim-s/pywhispercpp) (same engine as [Handy](https://github.com/cjpais/Handy))
- Free web search: DuckDuckGo HTML + [Tavily](https://tavily.com)
- Local AI: [Ollama](https://ollama.ai)

---

## License

MIT â€” see [LICENSE](LICENSE)
