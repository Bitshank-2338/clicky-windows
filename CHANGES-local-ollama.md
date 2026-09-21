# Local Ollama changes

Goal: run Clicky fully local (Ollama LLM, faster-whisper STT, offline TTS), with a typed-input option.

| File | Change |
|---|---|
| `audio/tts/local_tts_provider.py` (new) | Offline TTS via Windows SAPI (`pyttsx3`), plays through existing cancellable playback. |
| `audio/tts/off_tts_provider.py` (new) | Silent TTS. Answers show in the panel only. |
| `config.py` | `tts_provider()` honors `CLICKY_TTS` = `local` / `off` / `edge_tts` / `openai` / `elevenlabs`. |
| `companion_manager.py` | `_get_tts()` handles `local` and `off`. `CLICKY_WEB_SEARCH=0` disables web search. New `ask_text()` runs the normal pipeline from typed text and skips STT. |
| `ui/panel.py` | Text box in the panel. New `on_text_submitted` signal. |
| `main.py` | Connects `panel.on_text_submitted` to `manager.ask_text`. |
| `screen/capture.py` | `CLICKY_IMG_WIDTH` sets screenshot width sent to the LLM. |
| `ai/ollama_provider.py` | `OLLAMA_NUM_PREDICT` caps answer length. |
| `ai/model_registry.py` | Gemini list: all `gemini*` / `gemma-3+` marked vision. Hides non-chat models (image, music, robotics, TTS, video, deep-research, antigravity, computer-use). |
| `ai/gemini_provider.py` | API key sent in `x-goog-api-key` header (not the URL). Retries 429/5xx, then falls back to `gemini-2.5-flash`. |
| `main.py` (logging) | `httpx` logger set to WARNING so URLs and keys stay out of `clicky.log`. |
| `ai/fallback_provider.py` (new), `companion_manager.py` `_get_llm()` | Cloud LLM (Claude/OpenAI/Gemini/Copilot) failing before any output falls back to local Ollama. `CLICKY_FALLBACK_OLLAMA=0` disables. |
| `requirements.txt` | Added `pyttsx3`. |
| `run_clicky_background.bat`, `start_clicky.vbs` (new) | Hidden launcher with auto-restart. |
| `.env.example` | Documents the new variables. |

Example local `.env` (not committed):

```
CLICKY_ACTIVE_LLM=ollama
OLLAMA_VISION_MODEL=qwen2.5vl:3b
OLLAMA_TEXT_MODEL=qwen2.5vl:3b
OLLAMA_KEEP_ALIVE=9999h
CLICKY_STT=faster_whisper
CLICKY_TTS=off
CLICKY_MIC_MODE=hotkey
CLICKY_IMG_WIDTH=768
CLICKY_WEB_SEARCH=0
OLLAMA_NUM_PREDICT=350
```
