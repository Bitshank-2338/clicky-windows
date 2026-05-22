# Contributing to Clicky

Thanks for your interest in contributing to Clicky! This guide will help you get started.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/clicky-windows.git
   cd clicky-windows
   ```
3. **Create a virtual environment** (Python 3.11+):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-student.txt
   ```
4. **Install Ollama** (optional, for local AI):
   Download from [ollama.com](https://ollama.com) and pull a model:
   ```bash
   ollama pull llama3.2:3b
   ```

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes
3. Test locally by running:
   ```bash
   python main.py
   ```
4. Commit with a clear message:
   ```bash
   git commit -m "feat: describe what you added"
   ```
5. Push and open a Pull Request

## Commit Message Convention

We follow a lightweight conventional format:

| Prefix   | Use for                        |
|----------|--------------------------------|
| `feat:`  | New feature                    |
| `fix:`   | Bug fix                        |
| `docs:`  | Documentation only             |
| `refactor:` | Code change (no new feature, no fix) |
| `test:`  | Adding or updating tests       |
| `chore:` | Build, deps, CI changes        |

## Project Structure

```
clicky-windows/
  main.py                  # Entry point
  companion_manager.py     # Core AI orchestration
  config.py                # Settings & env loading
  hotkey.py                # Global hotkey listener
  ai/                      # LLM providers + pointer + search
  audio/                   # Capture, STT, TTS
  screen/                  # Screenshot capture
  ui/                      # PyQt6 overlay + tray
  tutor_features/          # Journal, PDF, OCR, lessons
  skills/                  # Pluggable skill modules
  assets/                  # Icon and resources
```

## What to Contribute

- **Bug fixes** — check the [Issues](https://github.com/Bitshank-2338/clicky-windows/issues) tab
- **New AI providers** — add a new file in `ai/` implementing `BaseLLMProvider`
- **New TTS/STT engines** — add in `audio/tts/` or `audio/stt/`
- **UI improvements** — overlay and tray live in `ui/`
- **Documentation** — README, setup guides, tutorials

## Code Style

- Python 3.11+ with type hints where practical
- `async/await` for IO-bound operations
- `snake_case` for functions and variables
- `PascalCase` for classes
- Keep functions short and focused

## Reporting Bugs

Open an issue with:
1. What you expected to happen
2. What actually happened
3. Steps to reproduce
4. Your OS version and Python version

## Questions?

Open a [Discussion](https://github.com/Bitshank-2338/clicky-windows/discussions) or reach out at **shashanksingh2338@gmail.com**.
