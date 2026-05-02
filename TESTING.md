# Clicky — Feature Testing Guide

How to verify every feature works. Go top-to-bottom; each section is independent.

---

## 0. Prerequisites

```bash
python main.py
```

✅ Blue dot appears in system tray (bottom-right of taskbar)  
✅ `Clicky is running` toast notification appears  
✅ Blue triangle overlay floats next to your cursor  

---

## 1. Push-to-Talk (PTT)

1. Hold **Ctrl + Alt + Space**
2. Say *"What page am I on?"*
3. Release the keys

✅ Overlay waveform animates while you speak  
✅ Overlay switches to "thinking" spinner  
✅ Clicky describes the current page/app  
✅ TTS speaks the answer  

---

## 2. Wake Word

1. Do NOT press any hotkey
2. Say **"Clicky"** then immediately *"what time is it?"*

✅ Blue buddy reacts after you say "Clicky"  
✅ Clicky answers the question  

---

## 3. Esc to Stop

1. Hold **Ctrl + Alt + Space**, ask *"explain the entire history of the internet"* (long answer)
2. Wait 2 seconds into the response
3. Press **Esc**

✅ TTS stops immediately  
✅ Overlay returns to idle state  

---

## 4. Pixel-Perfect Pointing

> Requires `ANTHROPIC_API_KEY` in `.env`

1. Open any browser to google.com
2. Hold **Ctrl + Alt + Space**, say *"where is the search bar?"*

✅ Blue buddy flies via bezier arc to the search bar  
✅ Pulsing highlight ring appears around it  
✅ Speech bubble shows "search bar"  
✅ Clicky says *"That's the Google search bar"* (or similar)  
✅ Buddy returns to cursor after TTS ends  

**Also test:**
- *"where is the sign in button?"*
- *"where is the address bar?"*

---

## 5. Slow Mode (Teacher Pace)

1. Right-click tray → **Tutor Mode → Slow Mode: OFF** → turns ON
2. Ask *"where is the search bar?"* again

✅ Flight arc is noticeably slower (~2.5s vs ~1.5s)  
✅ Buddy dwells longer before returning  

3. Turn Slow Mode back OFF

---

## 6. Multi-Step Lesson

1. Open a video in VLC or any video player
2. Ask *"how do I take a screenshot in Windows?"*

✅ Clicky gives Step 1, ends with *"say 'next' when ready"*  
3. Say **"next"**  
✅ Step 2 delivered without a new LLM call  
4. Continue until done  

---

## 7. Repeat Command

1. Ask any question (e.g., *"what is on my screen?"*)
2. Wait for it to finish speaking
3. Say **"repeat"** or **"say that again"**

✅ Clicky replays the last TTS without querying the LLM again  

---

## 8. Web Search

1. Ask *"what is the weather in Mumbai today?"* or *"who won the last IPL match?"*

✅ Panel shows `[1]`, `[2]` citation references  
✅ Answer reflects current real-world data (not 2023 training cutoff)  

---

## 9. Provider Switching

1. Right-click tray → **Model: claude** → pick **openai** (if `OPENAI_API_KEY` set)
2. Ask *"what's on screen?"*

✅ Toast: *"Switched to openai"*  
✅ Panel badge changes to GPT-4o  
✅ Model dropdown repopulates with OpenAI models  
✅ Clicky answers using the new provider  

3. Switch back to Claude  

---

## 10. GitHub Copilot (Free Models)

> Skip if you don't have Copilot

1. Tray → **Model → Sign in to GitHub Copilot…**
2. Visit `github.com/login/device`, enter the code shown in terminal
3. Toast confirms sign-in
4. Tray → **Model → copilot**

✅ Model dropdown shows `gpt-4o-mini (free)`, `gpt-4o`, `claude-3.5-sonnet`, etc.  
✅ Free models listed first  
✅ Ask a question — gets answered via Copilot  

---

## 11. Panel UI

1. Right-click tray → **Show Panel**

✅ Panel appears bottom-right  
✅ Provider badge shows active provider  
✅ Model dropdown has correct models  
✅ Status dot and label match current state  

2. Ask a question while watching panel  
✅ Response streams into the panel text area  
3. Click **—** button  
✅ Panel hides  
4. Double-click tray icon  
✅ Panel reappears  

---

## 12. Drag & Drop Document Context

1. Show Panel (tray → Show Panel)
2. Find any PDF or DOCX file in Explorer
3. Drag it onto the Clicky panel

✅ Toast: *"Document Attached"*  
4. Ask *"summarise what's in the document I just gave you"*  
✅ Clicky summarises the file contents  

**Alternative:** Tray → Journal → Attach document… → pick a file  

---

## 13. Knowledge Journal

1. Have a 3–4 question conversation with Clicky
2. Say *"what did we cover today?"*

✅ Clicky summarises today's Q&A from the local journal  

3. Say *"what did we cover this week?"*  
✅ Weekly digest  

**Check the database:**
```
%LOCALAPPDATA%\Clicky\journal.db
```

---

## 14. Quiz Mode

1. Open a website or document with visible content
2. Tray → **Tutor Mode → Quiz Mode: OFF** → turns ON
3. Hold **Ctrl + Alt + Space**, say *"quiz me"*

✅ Clicky asks YOU a question about what's on screen  
✅ Answer it — Clicky evaluates in one sentence  
✅ Next question follows automatically  

4. Turn Quiz Mode OFF  

---

## 15. Code Mode

1. Open VS Code or any IDE
2. Tray → **Tutor Mode → Code Mode (auto): ON**
3. Ask *"explain what this code does"*

✅ Response uses code blocks with language tags  
✅ Explanation is more technical / step-by-step  

---

## 16. Multilingual

1. Tray → **Tutor Mode → Multilingual: ON**
2. Ask a question in Hindi: *"मेरी स्क्रीन पर क्या है?"*

✅ Clicky detects Hindi  
✅ Responds in Hindi  
✅ TTS voice switches to a Hindi voice  

3. Try French: *"qu'est-ce qu'il y a sur mon écran?"*  
✅ Same behaviour in French  

---

## 17. OCR Fallback

> Requires Tesseract binary installed

1. Open a page with small/dense text (e.g., a legal document, footnotes)
2. Ask *"read the fine print"* or *"what does the small text say?"*

✅ Clicky runs OCR on the screenshot  
✅ Extracts text the vision model might have missed  

---

## 18. Whiteboard Annotations

1. Ask a question where Clicky would point at multiple things, e.g.:
   *"show me where the menu bar and the address bar are"*

✅ Arrows or circles drawn on screen  
✅ Annotations fade out after ~4 seconds  

---

## 19. Lesson Recording

1. Tray → **Lesson Recording → Start recording**

✅ Toast: *"Recording to: C:\Users\...\recordings\lesson_....mp4"*  

2. Ask 2–3 questions  
3. Tray → **Lesson Recording → Stop recording**  

✅ Toast: *"Lesson saved"*  
4. Open `%LOCALAPPDATA%\Clicky\recordings\`  
✅ MP4 file exists  
✅ `_transcript.md` file exists with all Q&A  

---

## 20. Workflow Capture

1. Tray → **Workflow Capture → Start capturing my clicks**

✅ Toast: *"Recording your clicks + keys…"*  

2. Do 5–10 actions: click around, type something, switch tabs
3. Tray → **Workflow Capture → Stop + send to Clicky**
4. Ask *"what did I just do?"*

✅ Clicky narrates your workflow step by step  

---

## 21. Privacy Guard

1. Tray → **Tutor Mode → Privacy Guard: ON** (should be on by default)
2. Open KeePass, Bitwarden, or any app with "login" / "password" in the title
3. Ask Clicky anything

✅ Clicky says it skipped the screenshot for privacy  
✅ No screenshot taken of your password manager  

---

## 22. Per-App Memory

1. Ask Clicky something in Chrome: *"what's on screen?"*
2. Switch to VS Code
3. Ask: *"what were we just talking about?"*

✅ Clicky has separate context — it won't mention the Chrome content  
✅ Each app has its own conversation history  

---

## 23. Skills System

1. Copy `skills/example_self_mode.py` to `~/.clicky/skills/my_skill.py`
2. Restart Clicky
3. Say the trigger phrase from the skill

✅ Skill fires its custom handler  
✅ Custom response returned  

---

## 24. Voice Picker

1. Say *"change voice to Jenny"*

✅ TTS voice switches to `en-US-JennyNeural`  

2. Ask a question  
✅ New voice speaks the answer  

---

## 25. Tray Journal Folder

1. Tray → **Journal → Open journal folder**

✅ Explorer opens `%LOCALAPPDATA%\Clicky\`  
✅ You can see `journal.db` and recordings  

---

## Quick Smoke Test (5 minutes)

Run this sequence to verify core features fast:

```
1. python main.py                    → tray icon appears
2. Hold hotkey → "what's on screen?" → answer spoken
3. Esc during response               → stops immediately
4. Say "Clicky, where is [element]"  → buddy flies to it
5. Tray → Quiz Mode ON → "quiz me"   → quiz starts
6. Tray → Quiz Mode OFF
7. Drag a PDF onto panel             → toast confirms attach
8. Ask "summarise the document"      → summary spoken
9. Say "what did we cover today?"    → journal summary
10. Tray → Quit Clicky               → clean exit
```

All 10 steps passing = Clicky is fully functional.
