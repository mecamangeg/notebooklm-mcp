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

> 💡 **Auto-refresh**: On every run the script automatically re-extracts fresh cookies
> from any open Chrome window that has `notebooklm.google.com` loaded. It probes ports
> **9222 → 9223 → 9000** in order. If Chrome isn't open, it auto-launches a headless
> Chrome instance using the persistent profile at `~/.notebooklm-mcp/chrome-profile`.
> Manual re-auth is only needed when your Google session has fully expired.

**To manually re-authenticate:**

1. Open Chrome (if not already open). No need to close regular Chrome windows.

2. Run:
```powershell
cd C:\PROJECTS\notebooklm-mcp
.\.venv\Scripts\python.exe -m notebooklm_mcp.auth_cli --port 9222 --no-auto-launch
```

   > ℹ️ Port 9222 is Chrome's standard CDP port. Antigravity IDE uses port 9000,
   > so there is no conflict.

3. In a **separate PowerShell window**, launch Chrome on port 9222:
```powershell
Start-Process "chrome.exe" -ArgumentList `
  "--remote-debugging-port=9222", `
  "--remote-allow-origins=*", `
  "--user-data-dir=$env:USERPROFILE\.notebooklm-mcp\chrome-profile", `
  "https://notebooklm.google.com"
```

   > 💡 Using `--user-data-dir` pointing to the **persistent notebooklm profile** means
   > you only need to log in once — the session is saved across auth runs.

4. Log into your Google account in the Chrome window that opens (first time only).

5. The auth tool will detect the login automatically and print:
```
✅ SUCCESS! Cookies: 23 extracted
```

6. Close that Chrome window when done.

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

💾 Saved to: OUTPUT\How to evaluate agents in practice.md
🏁 EXTRACTION COMPLETE — 7/7 sections — Time: 461s
```

**Total time: ~7–8 minutes** per video (most of that is NotebookLM thinking).

---

## Step 3 — Batch Processing (multiple videos)

Use `youtube-batch.py` to check status and extract a list of videos at once.
It automatically **skips videos already in `OUTPUT/`** — no duplicates.

### Check status only (no extraction)

```powershell
cd C:\PROJECTS\notebooklm-mcp
.\.venv\Scripts\python.exe youtube-batch.py --check --text @"
1. How to build an accuracy pipeline   https://www.youtube.com/watch?v=SHe6ylu_f1Q
2. how to evaluate agents in practice  https://youtu.be/vuBvf7ZRKTA
3. google adk tutorial                 https://www.youtube.com/watch?v=wgOCzHXKw4c
4. Unifying AI experience              https://www.youtube.com/watch?v=045PaTtW2YQ
"@
```

**Output:**
```
========================================================================
  📋  YouTube Batch Status  —  4 videos
      ✅ Already extracted: 1   ⏳ Pending: 3
========================================================================
   1. ⏳  How to build an accuracy pipeline (SHe6ylu_f1Q)
   2. ✅  how to evaluate agents in practice (vuBvf7ZRKTA)
          📄 How to evaluate agents in practice.md
   3. ⏳  google adk tutorial (wgOCzHXKw4c)
   4. ⏳  Unifying AI experience (045PaTtW2YQ)
========================================================================
(--check mode: no extraction run)
```

### Extract unprocessed videos from a list file

Save your list as `my-list.txt` (any format — numbered, titled, URL-only — all work):
```
1. How to build an accuracy pipeline   https://www.youtube.com/watch?v=SHe6ylu_f1Q
2. how to evaluate agents in practice  https://youtu.be/vuBvf7ZRKTA
3. google adk tutorial                 https://www.youtube.com/watch?v=wgOCzHXKw4c
```

Then run:
```powershell
.\.venv\Scripts\python.exe youtube-batch.py --file my-list.txt
```

Already-extracted videos are **automatically skipped**. The rest are processed sequentially.

### Batch CLI options

```
--file PATH       Read URL list from a text file
--text TEXT       Inline text block (use PowerShell here-string @"..."@)
--urls URL ...    Pass one or more URLs directly as arguments
--stdin           Read URL list from stdin (for piping)
--check           Show status table only — no extraction runs
--force           Re-extract even already-extracted videos
--output-dir DIR  Override output folder (default: OUTPUT\)
--cdp-port PORT   Chrome CDP port for cookie refresh
--no-cleanup      Keep transcript source in notebook after extraction
--no-cookie-refresh  Skip Chrome CDP cookie refresh
```

### Recognised URL formats

```
1. Some Video Title   https://www.youtube.com/watch?v=XXXXXXXXXXX&t=317s
Video Title   https://youtu.be/XXXXXXXXXXX?si=abc123
https://youtu.be/XXXXXXXXXXX
https://www.youtube.com/watch?v=XXXXXXXXXXX
```
Blank lines, `#` comment lines, and duplicate video IDs are silently ignored.

---

## Output

Results are saved to:
```
C:\PROJECTS\notebooklm-mcp\OUTPUT\{video title}.md
```

**Example:**
```
OUTPUT\How to evaluate agents in practice.md
OUTPUT\Build a multi-agent AI app with Google Cloud.md
```

The filename is the **actual YouTube video title** (filesystem-safe, preserving spaces and casing).
If the title cannot be fetched, the video ID is used as fallback.

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
--output-dir   Root folder for outputs (default: OUTPUT\ next to the script)
--output-file  Explicit output file path (overrides --output-dir)
--no-cleanup   Keep the transcript source in the notebook after extraction
--force        Re-extract even if the output file already exists
--cdp-port     Chrome DevTools port for cookie refresh (default: auto-probe 9222, 9223, 9000)
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

### Cookie auto-refresh is failing / "No NotebookLM page found"
The script probes CDP ports **9222, 9223, 9000** looking for a Chrome tab with
`notebooklm.google.com` open. If none is found it tries to auto-launch Chrome
using `~/.notebooklm-mcp/chrome-profile` (a persistent profile). If auto-launch
fails, open Chrome manually:
```powershell
Start-Process "chrome.exe" -ArgumentList `
  "--remote-debugging-port=9222", `
  "--remote-allow-origins=*", `
  "--user-data-dir=$env:USERPROFILE\.notebooklm-mcp\chrome-profile", `
  "https://notebooklm.google.com"
```
Then re-run the extractor. If Chrome is on a non-standard port, use `--cdp-port`:
```powershell
.\.venv\Scripts\python.exe youtube-context-runner.py --url "..." --cdp-port 9223
```

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
