# Session Handover — YouTube Context Extractor
**Date:** 2026-02-25  
**Project:** `C:\PROJECTS\notebooklm-mcp`  
**Status:** All changes committed and tested ✅

---

## What Was Done This Session

### 1. Source Control Cleanup (across all projects)
Reduced pending changes from **1,788 → ~206** (88.5% reduction) by adding `.gitignore` rules across multiple repos.

| Repo | Files Excluded | What They Were |
|---|---|---|
| `robsky-ai-vertex` | ~1,428 | `SUPERVISED FINE TUNING/ACCOUNTING_RAW_ANSWERS/`, `CURATED-ACCOUNTING/documents/`, `CURATED-TAX/documents/` |
| `sc-scraping` | ~200+ | `FINAL-2/markdown/`, `FINAL-2/metadata/`, scraper output dirs. Also committed removal of 188 previously-tracked FINAL-2 files. **Note:** sc-scraping `.gitignore` was corrupted (UTF-16 encoding) — rewrote it entirely in UTF-8. |
| `notebooklm-mcp` | ~1,413 | `with-generated-SYLLABI/`, `cases with all different opinions.../` |
| `accounting-team` | ~30 | `docs/IFRS-references/` |

Also added `OUTPUT/` and `YOUTUBE-CONTEXTS/` to `notebooklm-mcp/.gitignore`.

---

### 2. Cookie Auto-Refresh Fix (`youtube-context-runner.py`)

**Root cause:** `silent_refresh_cookies()` hardcoded `CDP_DEFAULT_PORT = 9222` but the quickstart was telling users to run Chrome on port **9223**. The refresh always silently failed.

**Fix applied:**
- Added `_CDP_PROBE_PORTS = [9222, 9223, 9000]` — probes all three ports in order
- Added `_find_notebooklm_chrome_page(probe_ports)` helper
- `silent_refresh_cookies()` now accepts `cdp_port=None` (auto-probe) or explicit port
- Added **auto-launch fallback**: if no Chrome page found on any port, launches Chrome with the persistent profile at `~/.notebooklm-mcp/chrome-profile`
- Added `--cdp-port` CLI argument to `youtube-context-runner.py`
- Updated quickstart: Chrome should use **port 9222** (not 9223 — Antigravity IDE is on port 9000, not 9222)
- Updated Chrome launch command to use persistent profile (`--user-data-dir=$env:USERPROFILE\.notebooklm-mcp\chrome-profile`) so login is remembered

---

### 3. Output Path & Naming (`youtube-context-runner.py`)

**Before:**
```
YOUTUBE-CONTEXTS/{video-id}/context-extraction.md
```

**After:**
```
OUTPUT/{actual YouTube video title}.md
```

**Changes made:**
- `DEFAULT_OUTPUT_ROOT` changed from `YOUTUBE-CONTEXTS/` → `OUTPUT/`
- Added `fetch_youtube_title(video_id)` — uses `httpx` to scrape `<title>` tag from `youtube.com/watch?v=...`, strips ` - YouTube` suffix, HTML-entity-decodes
- Added `make_safe_filename(text)` — preserves spaces & mixed case, only strips Windows-illegal chars (`\ / : * ? " < > |`). Max 120 chars.
- Output is now flat: `OUTPUT/How to evaluate agents in practice.md`
- Skip-if-exists check now also scans `OUTPUT/` for any `.md` file whose header contains the video ID (handles title-named files correctly)
- `fetch_youtube_title()` uses `<title>` tag as primary (most reliable), `og:title` as fallback

**Verified with:** `https://youtu.be/vuBvf7ZRKTA` → `How to evaluate agents in practice.md` ✅

---

### 4. Batch Processor — NEW FILE (`youtube-batch.py`)

**Location:** `C:\PROJECTS\notebooklm-mcp\youtube-batch.py`

**Purpose:** Check which videos from a list are already extracted and run extraction only for pending ones.

**Key features:**
- Parses any list format: numbered (`1. Title URL`), titled (`Title URL`), URL-only, with `?si=...` params, `&t=317s` timestamps — all handled
- Deduplicates by video ID
- Checks `OUTPUT/` by scanning `.md` header blocks for the video ID (finds files regardless of title changes)
- Shows clear status table before doing anything
- Skips already-extracted; runs `youtube-context-runner.py` sequentially for pending ones
- Prints final summary (success/skipped/failed)

**Key commands:**
```powershell
cd C:\PROJECTS\notebooklm-mcp

# Check status only
.\.venv\Scripts\python.exe youtube-batch.py --check --text @"
1. How to build accuracy pipeline  https://www.youtube.com/watch?v=SHe6ylu_f1Q&t=317s
2. how to evaluate agents          https://youtu.be/vuBvf7ZRKTA?si=AMLncQ9FjbmAbaYO
3. google adk tutorial             https://www.youtube.com/watch?v=wgOCzHXKw4c
4. Unifying AI experience          https://www.youtube.com/watch?v=045PaTtW2YQ
"@

# Extract unprocessed from a file
.\.venv\Scripts\python.exe youtube-batch.py --file my-list.txt

# Force re-extract everything
.\.venv\Scripts\python.exe youtube-batch.py --file my-list.txt --force
```

---

## Key Files Changed This Session

| File | Change |
|---|---|
| `youtube-context-runner.py` | Cookie auto-refresh (multi-port probe + auto-launch), OUTPUT dir, title-based filenames, `--cdp-port` arg |
| `youtube-batch.py` | **NEW** — batch status checker & extractor |
| `YOUTUBE-CONTEXT-QUICKSTART.md` | Updated: port 9222, persistent Chrome profile, OUTPUT path, Step 3 batch section |
| `.gitignore` | Added `OUTPUT/`, `YOUTUBE-CONTEXTS/` |
| `robsky-ai-vertex/.gitignore` | Added SFT/curated data directories |
| `sc-scraping/.gitignore` | Rewrote from UTF-16 to UTF-8, added scraper output dirs |
| `notebooklm-mcp/.gitignore` | Added syllabi output dirs |
| `accounting-team/.gitignore` | Added IFRS references dir |

---

## Architecture Notes

### Cookie Refresh Flow
```
Run script
  → silent_refresh_cookies(cdp_port=None, auto_launch=True)
    → _find_notebooklm_chrome_page([9222, 9223, 9000])
      → found?  YES → extract cookies → save → reset_client()
      → found?  NO  → launch_chrome(9222) → wait 5s → retry
                    → still no? → warn, use cached cookies
```

### Output File Resolution
```
--url given
  → extract_video_id(url)          # e.g. vuBvf7ZRKTA
  → fetch_youtube_title(video_id)  # e.g. "How to evaluate agents in practice"
  → make_safe_filename(title)      # strips \/:*?"<>|, collapses spaces
  → OUTPUT/{safe_name}.md          # e.g. OUTPUT/How to evaluate agents in practice.md
```

### Batch Dedup Check
```
For each video_id in list:
  → scan OUTPUT/*.md
  → read first 1024 bytes of each file
  → if video_id in header → mark as DONE, record filename
```

---

## Pending / Next Steps

- The `YOUTUBE-CONTEXTS/` folder (old output dir) may have old extracted files — can be deleted or migrated manually
- `--batch` mode could eventually support parallel extraction (currently sequential to avoid NotebookLM rate limits)
- NotebookLM BL token (`NOTEBOOKLM_BL`) may need updating periodically (currently: `boq_labs-tailwind-frontend_20260212.13_p0`)
- Consider adding a `--dry-run` flag to `youtube-batch.py` that prints what *would* be extracted without running anything (same as `--check` but different name for intuition)

---

## Quick Reference — Running the Tools

```powershell
cd C:\PROJECTS\notebooklm-mcp

# Single video
.\.venv\Scripts\python.exe youtube-context-runner.py --url "https://youtu.be/VIDEO_ID"

# Batch check (no extraction)
.\.venv\Scripts\python.exe youtube-batch.py --check --file my-list.txt

# Batch extract (unprocessed only)
.\.venv\Scripts\python.exe youtube-batch.py --file my-list.txt

# Manual cookie re-auth (when session expires)
Start-Process "chrome.exe" -ArgumentList "--remote-debugging-port=9222", "--remote-allow-origins=*", "--user-data-dir=$env:USERPROFILE\.notebooklm-mcp\chrome-profile", "https://notebooklm.google.com"
.\.venv\Scripts\python.exe -m notebooklm_mcp.auth_cli --port 9222 --no-auto-launch
```
