# Batch Case Digest Pipeline — Agent Instructions

> **Purpose**: Process all 31,832 Supreme Court case `.md` files into individual case digests using NotebookLM's multi-notebook parallel pipeline.
> 
> **Last updated**: 2026-02-16 12:24 PHT  
> **Architecture version**: v3 — 1:1 (one case per notebook per cycle)

---

## ⚡ Session Context (READ FIRST)

### Architecture: 1 Case → 1 Notebook → 1 Query → 1 Digest

Each notebook processes **one case at a time** in a tight loop:
```
add 1 source → query "case digest" → validate → save with metadata → delete source → next
```
All notebooks run this loop **concurrently** — true parallelism with zero contention.

### Existing Worker Notebooks (REUSE THESE)

10 notebooks created and tested. They use LIFO source management (add → query → delete) so they **never fill up**.

| Notebook | Name | ID | Status |
|----------|------|-----|--------|
| Worker 1 | Notebook1 | `9daa06dc-b783-455a-b525-3c9cd3c36b9e` | ✅ Ready |
| Worker 2 | Notebook2 | `d30bc801-da43-4e32-b044-bb1c0b6a20b4` | ✅ Ready |
| Worker 3 | Notebook3 | `942b25a4-8528-4d50-bbf9-3915af267402` | ✅ Ready |
| Worker 4 | Notebook4 | `42b27b34-ea16-4612-870b-84f9e40e296a` | ✅ Ready |
| Worker 5 | Notebook5 | `599684ce-78f3-4bd2-a8c9-45c294160dfe` | ✅ Ready |
| Worker 6 | Notebook6 | `a12b80e7-218f-438f-b7ec-411336ef40b7` | ✅ Ready |
| Worker 7 | Notebook7 | `1b9ba80e-2d16-400d-a842-c465da2cfc10` | ✅ Ready |
| Worker 8 | Notebook8 | `dd098ff4-c18c-412c-8cde-6cb685f78ec9` | ✅ Ready |
| Worker 9 | Notebook9 | `a3b742e7-db9a-4f71-8efe-06c3fb88bfe9` | ✅ Ready |
| Worker 10 | Notebook10 | `aa931c7c-a6b6-46b4-99db-843337440d3c` | ✅ Ready |
| Worker 11 | Notebook11 | `7647a1bf-31fa-4d15-84a7-6e5ddf38094f` | ✅ Ready |
| Worker 12 | Notebook12 | `cd58152e-163d-41e0-994d-e7d90ddeba75` | ✅ Ready |
| Worker 13 | Notebook13 | `c35cd867-ce15-4893-8edf-94a1a3df9cd8` | ✅ Ready |
| Worker 14 | Notebook14 | `363cba7e-15e3-4c69-ba4b-b4e78aa1e16d` | ✅ Ready |
| Worker 15 | Notebook15 | `8b2a1455-3a0e-4b16-a574-2e0568ddea36` | ✅ Ready |

> **Note**: Workers 1-3 have leftover sources from pre-LIFO test runs. These don't affect the pipeline — the `source_ids=[source_id]` parameter scopes each query to only the newly added source.

### Production Progress
**Nothing has been processed yet.** All previous runs were tests saved in `C:\PROJECTS\notebooklm-mcp\2013\`. Production output goes to `C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\`.

### Quick Start (Fresh Session)

1. **Read this file** for full context
2. **Check auth**: `notebooklm.check_auth_status` — if expired, run `notebooklm-mcp-auth` in terminal
3. **Pick the next year/month** to process (start from 1996/01_Jan)
4. **List source files**:
   ```powershell
   $year = "1996"; $month = "01_Jan"
   $src = "C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\$year\$month"
   $files = (Get-ChildItem $src -File -Filter "*.md").FullName
   Write-Output "$($files.Count) files to process"
   ```
5. **Check progress** (resume support):
   ```powershell
   $dst = "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\$year\$month"
   $done = if (Test-Path $dst) { (Get-ChildItem $dst -File -Filter "*-case-digest.md").Count } else { 0 }
   Write-Output "Done: $done / $($files.Count)"
   ```
6. **Run pipeline** (10 notebooks):
   ```
   notebooklm.notebook_digest_multi
     notebook_ids: ["9daa06dc-b783-455a-b525-3c9cd3c36b9e", "d30bc801-da43-4e32-b044-bb1c0b6a20b4", "942b25a4-8528-4d50-bbf9-3915af267402", "42b27b34-ea16-4612-870b-84f9e40e296a", "599684ce-78f3-4bd2-a8c9-45c294160dfe", "a12b80e7-218f-438f-b7ec-411336ef40b7", "1b9ba80e-2d16-400d-a842-c465da2cfc10", "dd098ff4-c18c-412c-8cde-6cb685f78ec9", "a3b742e7-db9a-4f71-8efe-06c3fb88bfe9", "aa931c7c-a6b6-46b4-99db-843337440d3c"]
     file_paths: [... all files from step 4 ...]
     output_dir: "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\{YEAR}\{MM}_{Mon}"
   ```
7. **Verify** output count matches input count
8. **Move to next month** and repeat from step 4

### Important Operational Notes

- **MCP Tool**: Use `notebooklm.notebook_digest_multi` via the lazy-mcp proxy (`mcp_lazy-mcp_execute_tool`)
- **Timeout**: The proxy has a 300s timeout. Large months (100+ files) may need multiple calls — resume auto-skips completed valid files
- **Auth expires**: If you get "Cookies have expired", run `notebooklm-mcp-auth` in terminal
- **LIFO cleanup**: Sources are deleted after each case. Notebooks never accumulate sources — reuse indefinitely
- **batch_size**: Always 1 (hardcoded). Each case is processed individually for maximum reliability
- **Install changes**: After editing `server.py`, you MUST run `uv tool install --force --reinstall "C:\PROJECTS\notebooklm-mcp"`. The `--reinstall` flag is required or changes won't take effect

---

## Architecture: v3 — 1:1 Processing

### Processing Flow (per notebook)
```
┌─────────────────────────────────────────────────────────┐
│  For each case file assigned to this notebook:          │
│                                                         │
│  1. READ source file + parse YAML frontmatter           │
│  2. ADD 1 source (the case text)                        │
│  3. QUERY with source_ids=[that_one_source]             │
│     → NotebookLM sees only 1 source                    │
│  4. VALIDATE response (≥2 markers, ≥300 chars)          │
│  5. EXTRACT SHORT_TITLE from first line of response     │
│  6. BUILD output: frontmatter (with corrected title)    │
│     + digest body                                       │
│  7. SAVE to .md file                                    │
│  8. DELETE that 1 source (back to 0)                    │
│  9. → Next case file                                    │
└─────────────────────────────────────────────────────────┘
```

### Why 1:1 Instead of Batching

| Issue | Batch approach (v1-v2) | 1:1 approach (v3) |
|-------|----------------------|-------------------|
| Split mismatch | Regex splitting failed 10-30% of the time | **No splitting needed** |
| Partial saves | Truncated digests saved as "partial" | **Only validated digests saved** |
| Resume skips bad files | `>100 bytes` check let corrupt files pass | **Content validation (structure markers)** |
| Per-case isolation | Errors in one case could affect batch | **Complete isolation** |

---

## Reliability Features

### 1. Content-Validated Resume
On re-run, the pipeline skips a file **only if** the existing digest passes validation:
- File exists AND is ≥500 bytes
- Contains at least 2 of: `CAPTION`, `FACTS`, `ISSUE`, `RULING`

This means truncated, corrupt, or empty files are **automatically reprocessed** on resume.

### 2. Response Validation Before Save
Before writing any digest to disk, the response is validated:
- Must contain at least 2 structural markers (CAPTION, FACTS, ISSUE, RULING)
- Must be at least 300 characters long

If validation fails, the file is marked `failed` and NO file is written — guaranteeing that only valid digests exist on disk.

### 3. LIFO Source Cleanup in `finally` Block
The source deletion happens in a `finally` block, meaning it **always executes** even if:
- The query fails
- Validation fails
- An exception is thrown
- The process is interrupted

This prevents source accumulation under any failure scenario.

### 4. Retry with Backoff
Each query retries up to 3 times (configurable) with 2-second delays between attempts. This handles transient NotebookLM API flakes like "No answer returned".

### 5. Power Failure / Crash Recovery
- Each digest is saved immediately after validation — no batch accumulation
- On restart, resume picks up exactly where it left off
- No rework: valid files are skipped, invalid/missing files are (re)processed
- Source cleanup ensures notebooks aren't polluted

---

## Metadata Preservation & Short Title Correction

### Source YAML Frontmatter
Source `.md` files contain YAML frontmatter with 13 fields:
```yaml
---
doc_id: "55710"
docket_number: "G.R. No. 173926"
title: "HEIRS OF LORENZO BUENSUCESO, REPRESENTED BY GERMAN BUENSUCESO..."
abridged_title: "Heirs of Lorenzo Buensuceso,, et al. vs. Lovy Perez, Substituted by..."
decision_date: "March 06, 2013"
ponente: "BRION, J"
division: "SECOND DIVISION"
doc_type: "Decision"
phil_citation: "705 Phil. 460"
scra_citation: ""
word_count: 4491
source_url: "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/55710"
citation_format: "G.R. No. 173926, March 06, 2013"
---
```

### What the Pipeline Does
1. **Parses** the YAML frontmatter from the source file
2. **Asks NotebookLM** to generate a corrected short title (via `SHORT_TITLE:` instruction)
3. **Updates** `abridged_title` in the frontmatter with the corrected version
4. **Writes** the output file with the updated frontmatter + digest body

### Short Title Correction Examples

| Original `abridged_title` | Corrected by NotebookLM |
|---|---|
| `Heirs of Lorenzo Buensuceso,, et al. vs. Lovy Perez, Substituted by Erlinda Perez-hernandez` | **Heirs of Buensuceso v. Perez** |
| `Manalangdemigillo vs. Trade and Investment Development Corp...` | **Manalang-Demigillo v. TIDCORP** |
| `Philippine National Bank vs. Hydro Resources Contractors Corp.` | **PNB v. Hydro Resources** |
| `Marcelino B. Agoy vs. NLRC, Eureka Personnel Management Services, Inc., Et. al.` | **Agoy v. NLRC** |

### Output Format
```markdown
---
doc_id: 55710
docket_number: "G.R. No. 173926"
title: "HEIRS OF LORENZO BUENSUCESO..."
abridged_title: "Heirs of Buensuceso v. Perez"    ← corrected
decision_date: "March 06, 2013"
ponente: "BRION, J"
division: "SECOND DIVISION"
doc_type: "Decision"
phil_citation: "705 Phil. 460"
scra_citation: ""
word_count: 4491
source_url: "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/55710"
citation_format: "G.R. No. 173926, March 06, 2013"
---

I. CAPTION
**HEIRS OF BUENSUCESO v. PEREZ**, G.R. No. 173926, March 6, 2013, 705 Phil. 460, Brion, J.

II. FACTS
[Concise recitation of material facts]

III. ISSUE/S
W/N [issue statement]

IV. RULING
**YES/NO.** [Holding with ratio decidendi]
```

---

## Directory Layout

### Source (input)
```
C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\
  └── {YEAR}\           (1996–2025, 30 years)
        └── {MM}_{Mon}\  (e.g. 01_Jan, 02_Feb, ... 12_Dec)
              └── *.md    (case decision files with YAML frontmatter)
```

### Destination (output)
```
C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\
  └── {YEAR}\
        └── {MM}_{Mon}\
              └── {filename}-case-digest.md  (frontmatter + digest)
```

---

## Scale & Performance

| Metric | Value |
|--------|-------|
| Total files | ~31,832 |
| Notebooks | 15 (concurrent) |
| Per-doc wall time | ~5.7s (effective) |
| Batch of 15 files | ~47s |
| Est. full corpus (15 NB) | **~10 hours** |

### Performance Benchmarks (2026-02-16)

| Architecture | Notebooks | Files | Wall Time | Per Doc | Success Rate |
|-------------|-----------|-------|-----------|---------|-------------|
| Batch (v1, batch_size=3) | 3 | 9 | 55s | ~6s | **70-90%** (split errors) |
| 1:1 (v3, batch_size=1) | 10 | 10 | 57s | ~5.7s | **100%** |
| **1:1 (v3, 15 notebooks)** | **15** | **15** | **47s** | **~3.1s** | **100%** |

---

## Pipeline Tool Reference

### `notebook_digest_multi` (RECOMMENDED)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notebook_ids` | `list[str]` | required | List of notebook UUIDs (use 15) |
| `file_paths` | `list[str]` | required | Absolute paths to source `.md` files |
| `output_dir` | `str` | required | Where to save digest files |
| `query_template` | `str` | Madera format | Case digest prompt (includes SHORT_TITLE instruction) |
| `batch_size` | `int` | 1 | Not used (kept for API compat, always processes 1 at a time) |
| `max_retries` | `int` | 3 | Retry attempts per query |
| `delay` | `float` | 1.0 | Seconds between staggered notebook starts |

**Key features**:
- **1:1 processing**: One case per notebook per cycle (no batching/splitting)
- **LIFO source management**: Add → query → save → delete per case
- **Content-validated resume**: Skips only genuinely complete digests (checks structural markers)
- **Response validation**: Only saves digests that pass quality checks
- **Metadata preservation**: YAML frontmatter from source files carried to output
- **Short title correction**: NotebookLM generates corrected `abridged_title`
- **Progress reporting**: Timestamped log to stderr with per-file success/failure status
- **Rate limit monitoring**: Tracks queries/minute and total queries in summary
- **Per-query retry**: Up to 3 attempts with 2s backoff

### ⚠️ Critical: MCP Proxy Timeout (300s)
The lazy-mcp proxy has a 300-second timeout. For >15 files, the MCP call will timeout before returning a response. **However, all digests are saved incrementally to disk — you lose only the summary JSON, not the work.**

Workaround for large batches:
1. Pass all files in one call
2. If it times out, check disk: `(Get-ChildItem $dst -File -Filter "*-case-digest.md").Count`
3. Re-run the same call — resume skips completed files
4. Repeat until all files are processed

### ⚠️ Critical: File Path Resolution
**Always resolve file paths from disk** using `Get-ChildItem`, never manually type them. Filenames in this corpus contain commas, periods, ampersands, and parentheses that are easily mistyped. The pipeline will report "File not found" for any path mismatch.

---

## Error Recovery

| Scenario | What happens | Action |
|----------|-------------|--------|
| **Timeout** | Completed digests are saved; incomplete cases have no file | Re-run same command — resume skips valid files |
| **Auth expired** | Returns "Cookies have expired" | Run `notebooklm-mcp-auth`, log in, retry |
| **"No answer returned"** | Query retries 3 times; if all fail, marked `failed` | Re-run picks it up |
| **Response fails validation** | No file written, marked `failed` | Re-run picks it up |
| **Save error (disk)** | Exception caught, marked `failed` | Fix disk issue, re-run |
| **Power failure / crash** | Valid saves persist; incomplete cases have no file | Re-run picks up exactly where it left off |
| **Notebook source limit** | N/A — LIFO keeps 0-1 sources per notebook | Same notebooks work indefinitely |

---

## Execution Checklist

```
[ ] 1996 (778 files, 12 months)
[ ] 1997 (926 files, 12 months)
[ ] 1998 (812 files, 12 months)
[ ] 1999 (1158 files, 12 months)
[ ] 2000 (1524 files, 12 months)
[ ] 2001 (1359 files, 12 months)
[ ] 2002 (1150 files, 12 months)
[ ] 2003 (1194 files, 12 months)
[ ] 2004 (1336 files, 12 months)
[ ] 2005 (1457 files, 12 months)
[ ] 2006 (1458 files, 12 months)
[ ] 2007 (1424 files, 12 months)
[ ] 2008 (1442 files, 12 months)
[ ] 2009 (1429 files, 12 months)
[ ] 2010 (1270 files, 12 months)
[ ] 2011 (986 files, 12 months)
[ ] 2012 (958 files, 11 months)
[ ] 2013 (957 files, 11 months)
[ ] 2014 (1028 files, 12 months)
[ ] 2015 (989 files, 11 months)
[ ] 2016 (1088 files, 12 months)
[ ] 2017 (1002 files, 11 months)
[ ] 2018 (1075 files, 12 months)
[ ] 2019 (1091 files, 12 months)
[ ] 2020 (1071 files, 11 months)
[ ] 2021 (1039 files, 12 months)
[ ] 2022 (567 files, 11 months)
[ ] 2023 (604 files, 10 months)
[ ] 2024 (384 files, 10 months)
[ ] 2025 (276 files, 10 months)
```

---

## Developer Notes

### Installing Code Changes
After editing `server.py`, you **must** use this exact command:
```powershell
Stop-Process -Name "notebooklm-mcp" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
uv tool install "C:\PROJECTS\notebooklm-mcp" --force --reinstall
```

> ⚠️ **`--reinstall` is mandatory.** Without it, `uv tool install --force` uses cached build artifacts and does NOT pick up code changes from the local path.

### Scaling to 15 Notebooks
To increase parallelism, create 5 more notebooks:
```
notebooklm.notebook_create → title: "Notebook11" through "Notebook15"
```
Then add their IDs to the `notebook_ids` list. The pipeline auto-distributes files across all provided notebooks.

---

## Changelog

### v3.0 — 2026-02-16 (Current)
- **1:1 architecture**: One case per notebook per cycle (eliminates split mismatch errors)
- **10 parallel notebooks**: 2x more than v2
- **Content-validated resume**: Checks CAPTION/FACTS/ISSUE/RULING markers, not just file size
- **Response validation before save**: Prevents corrupt/truncated digests from being written
- **LIFO cleanup in `finally` block**: Source always deleted, even on error
- **Metadata preservation**: YAML frontmatter from source files preserved in output
- **Short title correction**: NotebookLM generates corrected `abridged_title`
- **max_retries bumped to 3**: Reduces transient API failure rate
- **Removed regex splitting**: No `re` import needed; no parsing errors possible

### v2.0 — 2026-02-16 (Deprecated)
- Multi-notebook parallel processing
- Batch size 3 (regex splitting — fragile)
- LIFO source management
- Resume based on file size >100 bytes

### v1.0 — 2026-02-16 (Deprecated)
- Single notebook processing
- Sequential queries
- No resume support
