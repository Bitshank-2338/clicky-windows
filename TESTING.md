# Clicky â€” Feature Testing Guide

How to verify every feature works. Go top-to-bottom; each section is independent.

---

## 0. Prerequisites

```bash
python main.py
```

âœ… Blue dot appears in system tray (bottom-right of taskbar)  
âœ… `Clicky is running` toast notification appears  
âœ… Blue triangle overlay floats next to your cursor  

---

## 1. Push-to-Talk (PTT)

1. Hold **Ctrl + Win**
2. Say *"What page am I on?"*
3. Release the keys

âœ… Overlay waveform animates while you speak  
âœ… Overlay switches to "thinking" spinner  
âœ… Clicky describes the current page/app  
âœ… TTS speaks the answer  

---

## 2. Wake Word

1. Do NOT press any hotkey
2. Say **"Clicky"** then immediately *"what time is it?"*

âœ… Blue buddy reacts after you say "Clicky"  
âœ… Clicky answers the question  

---

## 3. Esc to Stop

1. Hold **Ctrl + Win**, ask *"explain the entire history of the internet"* (long answer)
2. Wait 2 seconds into the response
3. Press **Esc**

âœ… TTS stops immediately  
âœ… Overlay returns to idle state  

---

## 4. Pixel-Perfect Pointing

> Requires `ANTHROPIC_API_KEY` in `.env`

1. Open any browser to google.com
2. Hold **Ctrl + Win**, say *"where is the search bar?"*

âœ… Blue buddy flies via bezier arc to the search bar  
âœ… Pulsing highlight ring appears around it  
âœ… Speech bubble shows "search bar"  
âœ… Clicky says *"That's the Google search bar"* (or similar)  
âœ… Buddy returns to cursor after TTS ends  

**Also test:**
- *"where is the sign in button?"*
- *"where is the address bar?"*

---

## 5. Slow Mode (Teacher Pace)

1. Right-click tray â†’ **Tutor Mode â†’ Slow Mode: OFF** â†’ turns ON
2. Ask *"where is the search bar?"* again

âœ… Flight arc is noticeably slower (~2.5s vs ~1.5s)  
âœ… Buddy dwells longer before returning  

3. Turn Slow Mode back OFF

---

## 6. Multi-Step Lesson

1. Open a video in VLC or any video player
2. Ask *"how do I take a screenshot in Windows?"*

âœ… Clicky gives Step 1, ends with *"say 'next' when ready"*  
3. Say **"next"**  
âœ… Step 2 delivered without a new LLM call  
4. Continue until done  

---

## 7. Repeat Command

1. Ask any question (e.g., *"what is on my screen?"*)
2. Wait for it to finish speaking
3. Say **"repeat"** or **"say that again"**

âœ… Clicky replays the last TTS without querying the LLM again  

---

## 8. Web Search

1. Ask *"what is the weather in Mumbai today?"* or *"who won the last IPL match?"*

âœ… Panel shows `[1]`, `[2]` citation references  
âœ… Answer reflects current real-world data (not 2023 training cutoff)  

---

## 9. Provider Switching

1. Right-click tray â†’ **Model: claude** â†’ pick **openai** (if `OPENAI_API_KEY` set)
2. Ask *"what's on screen?"*

âœ… Toast: *"Switched to openai"*  
âœ… Panel badge changes to GPT-4o  
âœ… Model dropdown repopulates with OpenAI models  
âœ… Clicky answers using the new provider  

3. Switch back to Claude  

---

## 10. GitHub Copilot (Free Models)

> Skip if you don't have Copilot

1. Tray â†’ **Model â†’ Sign in to GitHub Copilotâ€¦**
2. Visit `github.com/login/device`, enter the code shown in terminal
3. Toast confirms sign-in
4. Tray â†’ **Model â†’ copilot**

âœ… Model dropdown shows `gpt-4o-mini (free)`, `gpt-4o`, `claude-3.5-sonnet`, etc.  
âœ… Free models listed first  
âœ… Ask a question â€” gets answered via Copilot  

---

## 11. Panel UI

1. Right-click tray â†’ **Show Panel**

âœ… Panel appears bottom-right  
âœ… Provider badge shows active provider  
âœ… Model dropdown has correct models  
âœ… Status dot and label match current state  

2. Ask a question while watching panel  
âœ… Response streams into the panel text area  
3. Click **â€”** button  
âœ… Panel hides  
4. Double-click tray icon  
âœ… Panel reappears  

---

## 12. Drag & Drop Document Context

1. Show Panel (tray â†’ Show Panel)
2. Find any PDF or DOCX file in Explorer
3. Drag it onto the Clicky panel

âœ… Toast: *"Document Attached"*  
4. Ask *"summarise what's in the document I just gave you"*  
âœ… Clicky summarises the file contents  

**Alternative:** Tray â†’ Journal â†’ Attach documentâ€¦ â†’ pick a file  

---

## 13. Knowledge Journal

1. Have a 3â€“4 question conversation with Clicky
2. Say *"what did we cover today?"*

âœ… Clicky summarises today's Q&A from the local journal  

3. Say *"what did we cover this week?"*  
âœ… Weekly digest  

**Check the database:**
```
%LOCALAPPDATA%\Clicky\journal.db
```

---

## 14. Quiz Mode

1. Open a website or document with visible content
2. Tray â†’ **Tutor Mode â†’ Quiz Mode: OFF** â†’ turns ON
3. Hold **Ctrl + Win**, say *"quiz me"*

âœ… Clicky asks YOU a question about what's on screen  
âœ… Answer it â€” Clicky evaluates in one sentence  
âœ… Next question follows automatically  

4. Turn Quiz Mode OFF  

---

## 15. Code Mode

1. Open VS Code or any IDE
2. Tray â†’ **Tutor Mode â†’ Code Mode (auto): ON**
3. Ask *"explain what this code does"*

âœ… Response uses code blocks with language tags  
âœ… Explanation is more technical / step-by-step  

---

## 16. Multilingual

1. Tray â†’ **Tutor Mode â†’ Multilingual: ON**
2. Ask a question in Hindi: *"à¤®à¥‡à¤°à¥€ à¤¸à¥à¤•à¥à¤°à¥€à¤¨ à¤ªà¤° à¤•à¥à¤¯à¤¾ à¤¹à¥ˆ?"*

âœ… Clicky detects Hindi  
âœ… Responds in Hindi  
âœ… TTS voice switches to a Hindi voice  

3. Try French: *"qu'est-ce qu'il y a sur mon Ã©cran?"*  
âœ… Same behaviour in French  

---

## 17. OCR Fallback

> Requires Tesseract binary installed

1. Open a page with small/dense text (e.g., a legal document, footnotes)
2. Ask *"read the fine print"* or *"what does the small text say?"*

âœ… Clicky runs OCR on the screenshot  
âœ… Extracts text the vision model might have missed  

---

## 18. Whiteboard Annotations

1. Ask a question where Clicky would point at multiple things, e.g.:
   *"show me where the menu bar and the address bar are"*

âœ… Arrows or circles drawn on screen  
âœ… Annotations fade out after ~4 seconds  

---

## 19. Lesson Recording

1. Tray â†’ **Lesson Recording â†’ Start recording**

âœ… Toast: *"Recording to: C:\Users\...\recordings\lesson_....mp4"*  

2. Ask 2â€“3 questions  
3. Tray â†’ **Lesson Recording â†’ Stop recording**  

âœ… Toast: *"Lesson saved"*  
4. Open `%LOCALAPPDATA%\Clicky\recordings\`  
âœ… MP4 file exists  
âœ… `_transcript.md` file exists with all Q&A  

---

## 20. Workflow Capture

1. Tray â†’ **Workflow Capture â†’ Start capturing my clicks**

âœ… Toast: *"Recording your clicks + keysâ€¦"*  

2. Do 5â€“10 actions: click around, type something, switch tabs
3. Tray â†’ **Workflow Capture â†’ Stop + send to Clicky**
4. Ask *"what did I just do?"*

âœ… Clicky narrates your workflow step by step  

---

## 21. Privacy Guard

1. Tray â†’ **Tutor Mode â†’ Privacy Guard: ON** (should be on by default)
2. Open KeePass, Bitwarden, or any app with "login" / "password" in the title
3. Ask Clicky anything

âœ… Clicky says it skipped the screenshot for privacy  
âœ… No screenshot taken of your password manager  

---

## 22. Per-App Memory

1. Ask Clicky something in Chrome: *"what's on screen?"*
2. Switch to VS Code
3. Ask: *"what were we just talking about?"*

âœ… Clicky has separate context â€” it won't mention the Chrome content  
âœ… Each app has its own conversation history  

---

## 23. Skills System

1. Copy `skills/example_self_mode.py` to `~/.clicky/skills/my_skill.py`
2. Restart Clicky
3. Say the trigger phrase from the skill

âœ… Skill fires its custom handler  
âœ… Custom response returned  

---

## 24. Voice Picker

1. Say *"change voice to Jenny"*

âœ… TTS voice switches to `en-US-JennyNeural`  

2. Ask a question  
âœ… New voice speaks the answer  

---

## 25. Tray Journal Folder

1. Tray â†’ **Journal â†’ Open journal folder**

âœ… Explorer opens `%LOCALAPPDATA%\Clicky\`  
âœ… You can see `journal.db` and recordings  

---

## Quick Smoke Test (5 minutes)

Run this sequence to verify core features fast:

```
1. python main.py                    â†’ tray icon appears
2. Hold hotkey â†’ "what's on screen?" â†’ answer spoken
3. Esc during response               â†’ stops immediately
4. Say "Clicky, where is [element]"  â†’ buddy flies to it
5. Tray â†’ Quiz Mode ON â†’ "quiz me"   â†’ quiz starts
6. Tray â†’ Quiz Mode OFF
7. Drag a PDF onto panel             â†’ toast confirms attach
8. Ask "summarise the document"      â†’ summary spoken
9. Say "what did we cover today?"    â†’ journal summary
10. Tray â†’ Quit Clicky               â†’ clean exit
```

All 10 steps passing = Clicky is fully functional.
