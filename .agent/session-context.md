# NotebookLM MCP — Session Context (2026-02-16 12:50 PHT)

> **Purpose**: Handoff document for continuing work in a fresh session.
> **Read this FIRST** before doing anything else.

---

## Project Overview

This project is a **NotebookLM MCP server** (`notebooklm-mcp`) that provides MCP tools to interact with Google NotebookLM's internal APIs. The primary use case is the **Batch Case Digest Pipeline** — processing ~31,832 Philippine Supreme Court case `.md` files into structured case digests using NotebookLM as the LLM backend.

### Key Paths

| Item | Path |
|------|------|
| **Project root** | `C:\PROJECTS\notebooklm-mcp` |
| **Main source** | `C:\PROJECTS\notebooklm-mcp\src\notebooklm_mcp\server.py` |
| **Pipeline docs** | `C:\PROJECTS\notebooklm-mcp\docs\batch-case-digest-pipeline.md` |
| **Known issues** | `C:\PROJECTS\notebooklm-mcp\docs\KNOWN_ISSUES.md` |
| **Source cases** | `C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\{YEAR}\{MM}_{Mon}\*.md` |
| **Output digests** | `C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\{YEAR}\{MM}_{Mon}\` |
| **Test outputs** | `C:\PROJECTS\notebooklm-mcp\2013\` (v2-test, v3-test, final-test, scale-test-jan) |
| **Installed location** | `C:\Users\Michael\AppData\Roaming\uv\tools\notebooklm-mcp-server\` |

### Git Status
- **Branch**: `main`
- **Remote**: `https://github.com/mecamangeg/notebooklm-mcp.git`
- **Last commit**: `3607e30` — "docs: add 15 notebooks, performance benchmarks, timeout and file path warnings"
- **Clean**: Yes, all changes committed and pushed

---

## Architecture: v3 — 1:1 Processing

Each notebook processes **one case at a time** in a tight loop:
```
add 1 source → query (with source_ids=[that_source]) → validate → save with metadata → delete source → next
```
All 15 notebooks run this loop **concurrently**.

### Key Functions in `server.py`

| Function | Lines (approx) | Purpose |
|----------|-------|---------|
| `DEFAULT_DIGEST_QUERY` | ~2099-2140 | Prompt template with SHORT_TITLE instruction |
| `notebook_digest_multi` | ~2520-2560 | Main entry point — distributes files across notebooks |
| `_is_digest_valid` | ~2591-2608 | Content-validated resume check (≥2 markers + ≥500 bytes) |
| `_log_progress` | ~2625 | Thread-safe progress logger |
| `_process_notebook_chunk` | ~2630-2810 | Core loop — per-notebook file processing |

### Key Design Decisions
1. **batch_size=1**: Eliminates regex split failures (was 10-30% failure rate with batch_size=3)
2. **Content-validated resume**: Checks CAPTION/FACTS/ISSUE/RULING markers, not just file size
3. **Validate before save**: ≥2 markers + ≥300 chars required before writing to disk
4. **LIFO in `finally`**: Source deletion always runs, even on error
5. **Frontmatter preservation**: Regex-based parser (`^---\s*\r?\n(.*?)\r?\n---\s*\r?\n`) handles `---` in body text
6. **SHORT_TITLE extraction**: NotebookLM generates corrected `abridged_title` via prompt instruction
7. **Progress reporting**: Thread-safe timestamped log to stderr + included in final JSON output
8. **Rate limit monitoring**: `elapsed_seconds`, `total_queries`, `queries_per_minute` in summary

---

## All 15 Worker Notebooks

These are permanent — reusable indefinitely via LIFO source management.

| # | Name | ID |
|---|------|-----|
| 1 | Notebook1 | `9daa06dc-b783-455a-b525-3c9cd3c36b9e` |
| 2 | Notebook2 | `d30bc801-da43-4e32-b044-bb1c0b6a20b4` |
| 3 | Notebook3 | `942b25a4-8528-4d50-bbf9-3915af267402` |
| 4 | Notebook4 | `42b27b34-ea16-4612-870b-84f9e40e296a` |
| 5 | Notebook5 | `599684ce-78f3-4bd2-a8c9-45c294160dfe` |
| 6 | Notebook6 | `a12b80e7-218f-438f-b7ec-411336ef40b7` |
| 7 | Notebook7 | `1b9ba80e-2d16-400d-a842-c465da2cfc10` |
| 8 | Notebook8 | `dd098ff4-c18c-412c-8cde-6cb685f78ec9` |
| 9 | Notebook9 | `a3b742e7-db9a-4f71-8efe-06c3fb88bfe9` |
| 10 | Notebook10 | `aa931c7c-a6b6-46b4-99db-843337440d3c` |
| 11 | Notebook11 | `7647a1bf-31fa-4d15-84a7-6e5ddf38094f` |
| 12 | Notebook12 | `cd58152e-163d-41e0-994d-e7d90ddeba75` |
| 13 | Notebook13 | `c35cd867-ce15-4893-8edf-94a1a3df9cd8` |
| 14 | Notebook14 | `363cba7e-15e3-4c69-ba4b-b4e78aa1e16d` |
| 15 | Notebook15 | `8b2a1455-3a0e-4b16-a574-2e0568ddea36` |

---

## Validated Benchmarks

| Test | Notebooks | Files | Wall Time | Per Doc | Success Rate |
|------|-----------|-------|-----------|---------|-------------|
| v2 batch (batch_size=3) | 3 | 9 | 55s | ~6s | 70-90% |
| v3 1:1 (10 notebooks) | 10 | 10 | 57s | ~5.7s | **100%** |
| **v3 1:1 (15 notebooks)** | **15** | **15** | **47s** | **~3.1s** | **100%** |

All tests confirmed:
- ✅ Metadata preservation (all 13 YAML frontmatter fields)
- ✅ Short title correction (NotebookLM generates corrected `abridged_title`)
- ✅ Content-validated resume (only genuinely complete digests skipped)
- ✅ Progress reporting (timestamped log)
- ✅ Rate limit monitoring (queries/minute in summary)

---

## Critical Operational Knowledge

### 1. Installing Code Changes
```powershell
Stop-Process -Name "notebooklm-mcp" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
uv tool uninstall notebooklm-mcp-server
uv cache clean notebooklm-mcp-server
uv tool install "C:\PROJECTS\notebooklm-mcp"
```
> ⚠️ `uv tool install --force` alone does NOT pick up code changes. You MUST uninstall+reinstall, or use `--force --reinstall` together.

### 2. MCP Proxy Timeout (300s)
The lazy-mcp proxy has a 300-second timeout. For >15 files, the MCP call will timeout before returning a response. **However, all digests are saved incrementally to disk.** Workaround:
1. Pass all files in one call
2. If it times out, check disk count
3. Re-run the same call — resume skips completed files
4. Repeat until done

### 3. File Path Resolution
**ALWAYS resolve file paths from disk** using `Get-ChildItem`. Never manually type filenames. The corpus filenames contain commas, periods, ampersands, and parentheses that are easily mistyped. The pipeline reports "File not found" for any path mismatch.

### 4. Authentication & Cookie Troubleshooting

NotebookLM has **no official API** — it uses reverse-engineered browser cookies. There are 3 auth methods:

#### Method A: Auto Mode (recommended — what we used)
```powershell
notebooklm-mcp-auth
```
- Creates a dedicated Chrome profile at `~/.notebooklm-mcp/chrome-profile/`
- Launches Chrome with remote debugging on port 9222
- Navigates to `notebooklm.google.com`, waits for login
- Extracts all 16 cookies + CSRF token + session ID
- Saves to `~/.notebooklm-mcp/auth.json`
- **Prerequisite**: Chrome must be **completely closed** first (not just minimized — fully quit)
- Subsequent runs skip login (profile persists Google session)

#### Method B: File Mode (if auto mode fails)
```powershell
notebooklm-mcp-auth --file
```
Manual extraction steps:
1. Open Chrome → `https://notebooklm.google.com` → log in
2. F12 → **Network** tab → filter `batchexecute`
3. Click any notebook to trigger a request
4. Click the `batchexecute` request → **Request Headers** → find `cookie:`
5. Right-click the cookie **value** (not the header name!) → **Copy value**
6. Paste into a `.txt` file, save
7. Provide the path when prompted

#### Method C: Environment Variable (manual fallback)
```powershell
$env:NOTEBOOKLM_COOKIES = "SID=xxx; HSID=xxx; SSID=xxx; APISID=xxx; SAPISID=xxx; ..."
```

#### Required Cookies (all 5 must be present)
`SID`, `HSID`, `SSID`, `APISID`, `SAPISID`

#### Token Storage Locations
```
~/.notebooklm-mcp/
├── auth.json           ← Cached cookies, CSRF, session ID
└── chrome-profile/     ← Persistent Chrome profile (stays logged in)
```

#### Common Auth Problems

| Problem | Symptom | Fix |
|---------|---------|-----|
| Chrome still running | `"Chrome is running but without remote debugging"` | Fully quit Chrome (Ctrl+Q / taskbar quit), retry |
| Cookies expired | `"Cookies have expired"` or 401/403 | Re-run `notebooklm-mcp-auth` |
| Missing required cookies | `"missing required cookies"` | Copied partial value — need all 5 required cookies |
| Stale BL version | API calls fail with weird errors | Set `$env:NOTEBOOKLM_BL` (see below) |
| Antigravity IDE Chrome | Chrome opens with wrong branding | Use `--file` mode |
| Cookie format wrong | Copied `cookie: SID=...` with header prefix | Copy value only, not `cookie:` prefix |

#### BL Version String
The `bl` (build label) parameter is hardcoded in `api_client.py` as `boq_labs-tailwind-frontend_20251221.14_p0`. When Google deploys new frontend versions, override with:
```powershell
$env:NOTEBOOKLM_BL = "boq_labs-tailwind-frontend_YYYYMMDD.XX_p0"
```
Find current value: Chrome DevTools → Network → any `batchexecute` request → look for `bl=` in the URL.

#### How Our Setup Works (lazy-mcp config)
The notebooklm server is registered in `C:\Tools\lazy-mcp\config.json` (line 100-109). It launches `notebooklm-mcp.exe` with **no env vars** — relies entirely on `~/.notebooklm-mcp/auth.json`. The other engineer must run `notebooklm-mcp-auth` at least once on their machine.

### 5. MCP Tool Access
The pipeline is accessed via the lazy-mcp proxy:
```
mcp_lazy-mcp_execute_tool
  tool_path: "notebooklm.notebook_digest_multi"
  arguments: { notebook_ids: [...], file_paths: [...], output_dir: "..." }
```

---

## Production Status

### What's Done
- ✅ v3 architecture (1:1 processing) — stable and validated
- ✅ 15 worker notebooks created and tested
- ✅ Metadata preservation + short title correction
- ✅ Content-validated resume
- ✅ Progress reporting + rate limit monitoring
- ✅ Robust frontmatter parser (regex-based)
- ✅ Documentation updated (`docs/batch-case-digest-pipeline.md`, `docs/KNOWN_ISSUES.md`)
- ✅ All code committed and pushed to `main`

### What's NOT Done — Production Run
**Zero production digests have been generated.** All runs were tests in `C:\PROJECTS\notebooklm-mcp\2013\`. The production run should:

1. Start from `1996/01_Jan` and proceed month-by-month
2. Output to `C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\{YEAR}\{MM}_{Mon}\`
3. Use all 15 notebooks
4. Follow the Quick Start in `docs/batch-case-digest-pipeline.md`

### Estimated Time
~31,832 files × ~3.1s/doc effective = **~10 hours total** (with 15 notebooks running continuously).

---

## Resolved Bugs (for reference)

1. **Split mismatch** → Switched to 1:1 architecture (batch_size=1)
2. **Truncated digests saved** → Validate before save + content-validated resume
3. **Source leak on error** → LIFO cleanup in `finally` block
4. **Output dir race condition** → `os.makedirs(exist_ok=True)` before each save
5. **uv install cache trap** → Must use `--force --reinstall` or uninstall+reinstall
6. **Frontmatter `---` in body** → Regex-based parser instead of `split("---", 2)`
7. **File path mismatch** → Always resolve from disk, never hand-type
8. **Runner `FunctionTool` error** → Access original function via `.fn` in `FastMCP`

---

## v2.0-multi-corpus (2026-02-16)

Added support for e-SCRA corpus profile.

### Changes
- **Auto-detection**: Probes frontmatter for `source_type: "SCRA"` (e-SCRA) vs `doc_id` (e-Library).
- **Field Mapping**: e-SCRA uses `short_title` for clean titles, e-Library uses `abridged_title`.
- **Standalone Runner**: `notebooklm-mcp-runner.py` for high-throughput volume processing without MCP proxy timeouts.
- **Improved Paths**: Always use disk-resolved absolute paths to avoid encoding/mismatch errors.

### Production Run Status
- **Volume_001**: 195 files. In progress.
- **Volumes completed**: 0/1026
- **Total files processed**: ~50 / 53,351

---

## Test Artifacts on Disk

| Directory | Contents | Status |
|-----------|----------|--------|
| `2013/v2-test/` | Early batch tests | Archived |
| `2013/v3-test/` | 1:1 architecture tests | Archived |
| `2013/multi-notebook-test/` | Multi-notebook tests | Archived |
| `2013/lifo-test/` | LIFO cleanup tests | Archived |
| `2013/final-test/` | 10/10 validation run with metadata | ✅ Reference |
| `2013/scale-test-jan/` | 15/15 scale test (Jan 2013) | ✅ Reference |
| `2013/jan_paths.json` | Actual Jan 2013 file paths from disk | Utility |
| `2013/run_scale_test.py` | Python scale test runner (doesn't work — FunctionTool not callable) | Utility |
| `CASE-DIGESTS/` | Empty — production output directory | Ready |

---

## Quick Reference: Starting the Production Run

```powershell
# 1. Check auth
# notebooklm.check_auth_status

# 2. Get files for a month
$year = "1996"; $month = "01_Jan"
$src = "C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\$year\$month"
$files = @(Get-ChildItem $src -File -Filter "*.md" | ForEach-Object { $_.FullName })
Write-Output "$($files.Count) files"

# 3. Run pipeline (via MCP tool)
# notebooklm.notebook_digest_multi
#   notebook_ids: [all 15 IDs]
#   file_paths: [resolved from step 2]
#   output_dir: "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\$year\$month"

# 4. Check progress
$dst = "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\$year\$month"
(Get-ChildItem $dst -File -Filter "*-case-digest.md").Count

# 5. Repeat steps 3-4 until count matches, then next month
```
