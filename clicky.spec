# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Clicky Windows.

Build:
    pyinstaller clicky.spec --clean --noconfirm

Output:
    dist/Clicky/Clicky.exe           ← distribute this whole folder

We use --onedir (not --onefile) because:
  • faster-whisper + ctranslate2 ship large native DLLs that onefile
    extracts to %TEMP% on every launch (slow, antivirus-triggering).
  • onedir launches in ~1s vs ~8s for onefile.
  • Inno Setup bundles the folder into a single Setup.exe anyway.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Modules that are lazy-imported by CompanionManager — PyInstaller's
#    static analysis misses them, so we list them explicitly.
hidden = [
    # Lazy LLM providers
    "ai.claude_provider",
    "ai.openai_provider",
    "ai.gemini_provider",
    "ai.ollama_provider",
    "ai.github_copilot_provider",
    "ai.element_locator",
    "ai.web_search",

    # Lazy STT providers
    "audio.stt.deepgram_stt",
    "audio.stt.openai_stt",
    "audio.stt.faster_whisper_stt",

    # Lazy TTS providers
    "audio.tts.edge_tts_provider",
    "audio.tts.openai_tts_provider",
    "audio.tts.elevenlabs_provider",

    # Indirect deps
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
]

# ── Heavy packages that ship non-Python assets (DLLs, JSON, voices).
#    collect_all grabs submodules + data files + binaries + metadata.
datas, binaries, hiddenimports = [], [], []
for pkg in (
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "edge_tts",
    "anthropic",
    "openai",
    "ollama",
    "elevenlabs",
    "tavily",
    "httpx",
    "httpcore",
    "certifi",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass  # package not installed — that path is optional anyway

hiddenimports += hidden
hiddenimports += collect_submodules("PyQt6")


a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Shave size: Clicky never uses these heavy libs.
    excludes=[
        "matplotlib", "scipy", "pandas", "tkinter",
        "notebook", "jupyter", "IPython",
        "torch.distributions", "torch.onnx",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Clicky",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                    # UPX often triggers Windows Defender
    console=False,                # no terminal window for released builds
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico" if __import__("os").path.exists("assets/icon.ico") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Clicky",
)
