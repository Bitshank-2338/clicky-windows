# Clicky 1.6 preview — original Windows features

This preview extends this project's Python/Qt architecture. It does not include code, assets, prompts, account services or binaries from official HeyClicky.

## What changed

- **Clicky Sketch:** an original JSON lesson format and native Qt renderer. Includes charts, arithmetic function graphs, lines/shapes, rotatable cube/sphere wireframes and keyboard-accessible follow-up buttons. Save/reopen lessons with narration, replay their voice, and export PNGs.
- **Clicky Drive:** the model proposes bounded desktop actions. You review a readable plan before input starts. Coordinates are tied to the captured display; expired/changed screens are rejected. Esc cancels; unexpected mouse movement stops the next action; held inputs are released on cancellation. Typing refuses protected/unverifiable fields. No model-generated shell code is executed.
- **Typed chat and local history:** a composer, Stop/New controls and bounded per-app conversation storage. Settings includes a history viewer. New clears conversation history; the separate study journal remains available.
- **Work and routines:** persistent background answer jobs, saved Markdown results, pause/resume/retry, recovery after interrupted runs, and 15-minute/hourly/daily intervals. These are model answering/writing jobs, not unattended desktop or browser automation. They run only while Clicky is open and the PC is awake.
- **Browser Link:** an original Chromium extension with explicit pairing to a loopback-only service. Read the selected page and its visible controls; review requests to open/back/click/fill/scroll. Element references require a matching snapshot epoch. Password fields and sensitive page titles are refused. The extension must currently be loaded unpacked by the user.
- **Custom app tools:** configure HTTPS or localhost Streamable HTTP MCP endpoints (protocol 2025-06-18), store bearer tokens with Windows protection, list tools, review tool calls, and attach results to chat. Model-proposed calls also require review. This is not a hosted integration catalog; OAuth and stdio transports are not implemented.
- **Trusted-LAN sharing:** the old collaboration stub has been replaced with opt-in peer sessions for Q&A and Sketch data. A random link authenticates peers; browser-origin connections and remote-control messages are rejected. LAN traffic is unencrypted: use only on a trusted network. No public signaling/NAT traversal service is included.
- **Dictation:** a separate hold shortcut sends recognized text to the same verified, non-password editable field. If focus changes or cannot be checked, the transcript is shown with an explicit Copy option instead.
- **Voice and settings:** Windows speech is available offline. Local AI defaults to local recognition and local voice, even if cloud keys exist. Cloud recognition/voice can be selected explicitly. Speech speed, voice, captions, shortcuts and behavior toggles are configurable. Narration starts on completed sentences while the answer continues streaming. Deepgram optionally streams microphone PCM with live partials; it falls back to a same-provider upload if the live stream fails.
- **Recording:** saved videos now have a narration track. Capture redacts sensitive windows; Clicky's own drawing layer is composited separately. Raw video, WAV and transcript are preserved if export fails. Output is `%LOCALAPPDATA%\Clicky\recordings\`.
- **Documents:** image attachments, DOCX table text, bounded XLSX cell/formula reading and scanned-page OCR fallback. Attachment sizes and per-turn context are bounded. Text extraction still does not preserve a document's original visual layout.
- **Updates:** explicit checks against this project's GitHub releases. Downloads require a GitHub SHA-256 digest and are verified before offering to quit and open the installer. Nothing is downloaded or installed automatically.

## Audit fixes

The regression suite covers sensitive Quiz Mode, `.env` titles, screen-question misclassification, whole-question pointer matching, multilingual/Hinglish intents, review grading, protected key persistence, mixed-DPI coordinate math, streaming narration/cancellation, structured response parsing, graph-code rejection, Drive input release, browser pairing, persistent jobs/conversations, document tables, narrated MP4 export, local speech generation, MCP sessions and startup wiring.

Privacy decisions now apply to screenshot, OCR and recording paths. All visible sensitive-titled windows are redacted, not only the foreground one. Workflow capture never keeps typed characters. Web search is off by default and, when enabled, is limited to queries requesting search/current facts. Key saves are atomic and Windows-protected; failures are visible instead of falsely reporting success. Legacy developer `.env` files remain supported and are **not automatically deleted or encrypted**.

## Where to start

1. Run `python main.py` from an environment containing the requirements.
2. Open the panel from the tray, or press Ctrl+Alt+T. Type a question or use your talk shortcut.
3. Press **Sketch** to explore the sample scene. Ask for a graph or 3D explanation to create one from a model response.
4. Try a small task such as “click the Save button for me.” Read the Drive plan before allowing it; keep Esc available.
5. Open **Settings → Getting started** for the feature guide. **Work & routines** manages background answers; **Settings → Browser and app connections** manages the browser, MCP and peer sessions.

## Verification and practical limits

Audio corrections: native-rate/stereo microphone fallback now handles failures that happen when a stream starts, closes failed streams and allows a retry. The selector groups duplicate driver entries, keeps driver alternatives available and saves microphone name/driver rather than a volatile device number. Old numeric selections use Windows default until a microphone is selected again. Missing saved devices fall back to Windows default with a notice. Settings → Microphone includes a local three-second level test that never saves or uploads audio. Quiet audio is normalized before noise gating; absent/silent capture and empty recognition get readable feedback.

Edge voice now requires `edge-tts>=7.3.0` for the updated service handshake. If the service refuses a request, times out or returns no audio, Clicky switches that provider instance to offline Windows speech and shows one notice. Later sentences do not repeatedly hit the failed service. Applying Voice settings retries the chosen provider. Cancellation stays cancellable, and output-device failures are reported without resynthesizing the answer.

Packaging correction: exclude an unrelated `icuuc.dll` discovered on the build machine's PATH. Qt uses the Windows ICU API; the foreign library has incompatible exports and prevented startup. Upgrades remove the stale bundled DLL. A `--smoke-test` executable mode now checks Qt window creation and Sketch rendering without microphone, global hooks or network services; the build script requires it to pass.

Run `python -m pytest tests -q`, `node tests/browser_extension.test.js` and `python -m pip check`. CI runs on Windows. Tests use synthetic screens, fake input controllers and local servers; they do not click personal apps, capture your desktop, call paid providers or modify external accounts.

Still requiring live acceptance testing: real microphone/Bluetooth devices, mixed-DPI hardware, full-screen games, a manually installed browser extension and real third-party MCP servers/accounts. Privacy Guard recognizes window titles; it cannot identify every secret in an ordinary document. Captions are sentence-timed, not word-aligned. Local Whisper remains batch recognition; live partials currently require Deepgram. The 3D renderer is a lightweight wireframe teaching engine, not a general GPU scene engine. Updates cannot provide code signing without a publisher certificate. Hosted billing, referrals and cloud account sync are intentionally outside this local-first preview.

## Engineering references

- [Windows display-affinity API](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)
- [Windows credential protection](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [Chrome isolated script execution](https://developer.chrome.com/docs/extensions/reference/api/scripting)
- [Deepgram language/model support](https://developers.deepgram.com/docs/models-languages-overview)

Community research informed the local/cloud boundary and runtime stop controls: [Shipping Local Speech-to-Text in a Desktop AI Assistant: What We Learned Bundling whisper.cpp](https://dev.to/cernalo/shipping-local-speech-to-text-in-a-desktop-ai-assistant-what-we-learned-bundling-whispercpp-jh4) and [Human Approval Gates for Irreversible Agent Actions](https://dev.to/makaminski1337/human-approval-gates-for-irreversible-agent-actions-3k5d). These are practitioner accounts, not substitutes for the tests or platform specifications.
