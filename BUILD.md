# Building Clicky.exe for Windows

Two ways to package Clicky for your friend's laptop:

| Method | Output | Size | Install | Best for |
|---|---|---|---|---|
| **Portable folder** | `dist\Clicky\` | ~400-600 MB | Copy the folder, double-click `Clicky.exe` | Quick testing, USB stick |
| **Setup installer** | `Setup-Clicky.exe` | ~200-400 MB | Double-click, Next, Finish | Polished distribution |

---

## Quick build (portable folder)

```bat
build.bat
```

That's it. After 2-5 minutes:
```
dist\Clicky\Clicky.exe    â† hand this whole folder to your friend
```

Your friend:
1. Copies the `Clicky` folder anywhere on their PC
2. (Optional) creates `.env` next to `Clicky.exe` with their API keys â€” see `.env.example`
3. Double-clicks `Clicky.exe`
4. Tray icon appears, Clicky is running

**No Python needed on their machine.** Everything is bundled.

---

## Full installer (`Setup-Clicky.exe`)

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php) (free)
2. Run:
   ```bat
   build.bat installer
   ```
3. Output: `dist\Setup-Clicky.exe` â€” a single self-extracting installer

Your friend runs `Setup-Clicky.exe`:
- Pick install location (default: `C:\Program Files\Clicky`)
- Choose: desktop shortcut? launch on Windows startup?
- Next â†’ Install â†’ Finish
- Uninstall works through Windows Settings like any other app

---

## What gets bundled

| Component | Bundled? | Notes |
|---|---|---|
| Python runtime | âœ… | Embedded â€” no install needed |
| PyQt6 | âœ… | UI framework |
| faster-whisper + ctranslate2 | âœ… | Local STT (free fallback) |
| edge-tts | âœ… | Free Windows TTS (always available) |
| anthropic / openai / google SDKs | âœ… | LLM clients |
| Your `.env` | âŒ | **Must be added post-install** (security) |
| Ollama server | âŒ | Friend installs separately if they want local AI |

---

## First-run checklist for your friend

When they launch `Clicky.exe` the first time:

1. **Windows SmartScreen warning** (blue popup)
   - Click "More info" â†’ "Run anyway"
   - This is normal for unsigned .exe files. To fix permanently, code-sign with a certificate (~$100/year).

2. **Microphone permission** (Windows pops up)
   - Click "Yes" â€” needed for voice input

3. **Tray icon** appears bottom-right
   - Right-click it â†’ see the menu
   - If no tray icon, check that the process is running in Task Manager

4. **Test it**:
   - Hold `Ctrl + Win`, say "what's on my screen"
   - If silent â†’ check `.env` has at least one API key, OR install Ollama locally

---

## Troubleshooting the build

**`pyinstaller: command not found`**
```bat
pip install pyinstaller
```

**`Failed to collect faster_whisper`**
```bat
pip install --upgrade faster-whisper ctranslate2
```
Then re-run `build.bat`.

**`ImportError: DLL load failed` at runtime on friend's PC**
- Friend needs [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) (usually already installed on Windows 10/11)

**Antivirus flags Clicky.exe**
- False positive â€” PyInstaller bundles are sometimes flagged because they self-extract
- Add an exclusion for the install folder, or code-sign the binary

**Build is 600 MB â€” too large**
- Most of that is `torch` (pulled in by `faster-whisper`)
- For the smallest build, edit `requirements.txt`: remove `faster-whisper`, keep only `edge-tts` + `anthropic` + `openai` â†’ drops to ~150 MB
- Friend loses local STT, must use Deepgram/OpenAI Whisper via API instead

**Build is slow (5+ min)**
- Normal first time â€” PyInstaller analyses every import
- Subsequent builds are faster if you don't `rmdir /s /q build`

---

## Signing the installer (optional)

To avoid the Windows SmartScreen warning, you need an **Authenticode code-signing certificate**:

1. Buy one from Sectigo / DigiCert / SSL.com (~$80-400/year)
2. After `build.bat`, sign both files:
   ```bat
   signtool sign /f mycert.pfx /p PASSWORD /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\Clicky\Clicky.exe
   signtool sign /f mycert.pfx /p PASSWORD /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\Setup-Clicky.exe
   ```

For testing with friends this is overkill â€” just tell them to click "Run anyway".

---

## Directory layout after build

```
clicky-windows/
â”œâ”€â”€ build/              â† PyInstaller scratch (safe to delete)
â””â”€â”€ dist/
    â”œâ”€â”€ Clicky/         â† portable folder â€” give this to friends
    â”‚   â”œâ”€â”€ Clicky.exe
    â”‚   â”œâ”€â”€ _internal/  â† bundled Python + libs (~500 MB)
    â”‚   â”œâ”€â”€ .env.example
    â”‚   â”œâ”€â”€ LICENSE
    â”‚   â””â”€â”€ README.md
    â””â”€â”€ Setup-Clicky.exe â† single-file installer (if you built with installer flag)
```
