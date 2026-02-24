# YouTube Context Extractor — Quickstart

Extracts structured knowledge from any YouTube video using NotebookLM as the AI engine.

**How it works:**
1. Downloads the video's transcript via `youtube-transcript-api`
2. Injects it as a text source into your NotebookLM notebook
3. Configures the chat: **goal = custom**, **role = context extractor**, **response = longer**
4. Fires 7 targeted queries (overview, concepts, technical details, examples, insights, Q&A, resources)
5. Saves a structured `.md` file with the full extracted knowledge

---

## Prerequisites

- Python venv at `C:\PROJECTS\notebooklm-mcp\.venv` (already set up)
- `youtube-transcript-api` installed in the venv (already installed)
- A Google account with access to [NotebookLM](https://notebooklm.google.com)
- The designated notebook: `a7d3b9c8-f255-4442-834d-e0bbbe30ec8f`

---

## Step 1 — Authenticate (first time, or when cookies expire)

Cookies expire roughly every **48–72 hours**. You'll see this error when they do:
```
FATAL: Cannot authenticate: Cookies have expired. Please re-authenticate.
```

**To re-authenticate:**

1. Close ALL regular Chrome windows (keep Antigravity IDE open — it's Electron, not Chrome)

2. Run:
```powershell
cd C:\PROJECTS\notebooklm-mcp
.\.venv\Scripts\python.exe -m notebooklm_mcp.auth_cli --port 9223 --no-auto-launch
```

   > ⚠️ Port 9223 is used to avoid conflict with the Antigravity IDE's CDP on port 9222.

3. In a **separate PowerShell window**, launch Chrome on port 9223:
```powershell
Start-Process "chrome.exe" -ArgumentList `
  "--remote-debugging-port=9223", `
  "--remote-allow-origins=http://localhost:9223", `
  "--user-data-dir=C:\Temp\chrome-notebooklm-auth", `
  "https://notebooklm.google.com"
```

4. Log into your Google account in the Chrome window that opens

5. The auth tool will detect the login automatically and print:
```
✅ SUCCESS! Cookies: 23 extracted
```

6. Close that Chrome window when done

---

## Step 2 — Run the extractor

```powershell
cd C:\PROJECTS\notebooklm-mcp
.\.venv\Scripts\python.exe youtube-context-runner.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Example:**
```powershell
.\.venv\Scripts\python.exe youtube-context-runner.py --url "https://www.youtube.com/watch?v=TokTTzq5rtg"
```

The script will print live progress:
```
📝 Fetching transcript for video: TokTTzq5rtg...
✅ Transcript fetched: 227 segments, 10,284 chars, lang=en-US
⚙️  Configuring chat (goal=custom, response=longer)...
⚙️  Chat configured ✅
📄 Adding transcript as text source (10,595 chars)...
✅ Source added: Transcript: TokTTzq5rtg
⏳ Waiting 10s for NotebookLM to index the transcript...
✅ Ready.

🔍 Starting extraction (7 queries)...

  [1/7] Video Overview & Key Topics...        ✅ 6784 chars
  [2/7] Core Concepts & Explanations...       ✅ 8102 chars
  [3/7] Technical Details, Code & Impl...     ✅ 7885 chars
  [4/7] Examples, Demonstrations...           ✅ 6646 chars
  [5/7] Key Insights, Tips & Best Practices   ✅ 7777 chars
  [6/7] Q&A, FAQs & Clarifications...         ✅ 6076 chars
  [7/7] Resources, References & Next Steps    ✅ 6806 chars

💾 Saved to: YOUTUBE-CONTEXTS\TokTTzq5rtg\context-extraction.md
🏁 EXTRACTION COMPLETE — 7/7 sections — Time: 461s
```

**Total time: ~7–8 minutes** per video (most of that is NotebookLM thinking).

---

## Output

Results are saved to:
```
C:\PROJECTS\notebooklm-mcp\YOUTUBE-CONTEXTS\{video-id}\context-extraction.md
```

The file contains 7 structured sections:

| Section | What it covers |
|---------|---------------|
| **Video Overview & Key Topics** | Main topic, speaker, outline, conclusion |
| **Core Concepts & Explanations** | Every term, framework, definition with explanations |
| **Technical Details, Code & Implementation** | Code, commands, architecture, step-by-step |
| **Examples, Demonstrations & Use Cases** | Every demo walkthrough and use case |
| **Key Insights, Tips & Best Practices** | Expert advice, tips, pitfalls to avoid |
| **Q&A, FAQs & Clarifications** | Q&A pairs, caveats, "what if" scenarios |
| **Resources, References & Next Steps** | Books, links, repos, recommended follow-ups |

---

## CLI Options

```
--url          YouTube URL (required). Supports watch?v=, youtu.be/, shorts/, embed/
--notebook-id  NotebookLM notebook UUID (default: a7d3b9c8-f255-4442-834d-e0bbbe30ec8f)
--output-dir   Root folder for outputs (default: YOUTUBE-CONTEXTS\ next to the script)
--output-file  Explicit output path (overrides --output-dir)
--no-cleanup   Keep the transcript source in the notebook after extraction
--force        Re-extract even if the output file already exists
--no-cookie-refresh  Skip the initial Chrome CDP cookie refresh attempt
```

**Examples:**
```powershell
# Basic extraction
.\.venv\Scripts\python.exe youtube-context-runner.py --url "https://youtu.be/abc123"

# Save to a custom folder
.\.venv\Scripts\python.exe youtube-context-runner.py --url "..." --output-dir "D:\MyVideos"

# Re-run a previously extracted video
.\.venv\Scripts\python.exe youtube-context-runner.py --url "..." --force

# Keep the source in the notebook for further manual querying
.\.venv\Scripts\python.exe youtube-context-runner.py --url "..." --no-cleanup
```

---

## Troubleshooting

### "Cookies have expired"
Re-run Step 1 (auth). Cookies last ~48–72 hours.

### "No transcript available for this video"
The video has transcripts disabled or is not in a supported language. Try a different video. Auto-generated captions (even without manual subtitles) usually work.

### Answers look thin / generic
This can happen if the video is very short or has very sparse transcripts. The quality of the extraction directly reflects the quality of the transcript. Check the transcript char count in the output — anything under 2,000 chars will produce limited results.

### Script finds old output and skips
The skip-if-exists check requires the file to be `>1KB` AND contain at least 3 section headers. Use `--force` to override.

### Auth tool hangs waiting for login
The Chrome window opened on a blank page or failed to reach NotebookLM. Close it and re-run the `Start-Process` command to open a fresh Chrome window.

---

## Notes

- **Why text source instead of URL?** NotebookLM's URL source for YouTube only scrapes the page HTML (which is just the site footer). The transcript must be downloaded separately and injected as pasted text so NotebookLM has real video content.
- **The designated notebook** (`a7d3b9c8-...`) is cleared of old sources at the start of each run, so it stays clean automatically.
- **Logs** are written to `C:\Users\Michael\.notebooklm-mcp\youtube-context-runner.log` for debugging.
