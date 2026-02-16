# Batch Case Digest Pipeline — Agent Instructions

> **Purpose**: Process all 31,832 Supreme Court case `.md` files into individual case digests using NotebookLM's multi-notebook parallel pipeline.
> 
> **Last updated**: 2026-02-16 11:35 PHT

---

## ⚡ Session Context (READ FIRST)

### Existing Worker Notebooks (REUSE THESE)
These 3 notebooks were created and tested. They use LIFO source management — sources are auto-deleted after each batch, so they **never fill up**.

| Notebook | ID | Status |
|----------|-----|--------|
| Worker 1 | `9daa06dc-b783-455a-b525-3c9cd3c36b9e` | ✅ Tested, clean |
| Worker 2 | `d30bc801-da43-4e32-b044-bb1c0b6a20b4` | ✅ Tested, clean |
| Worker 3 | `942b25a4-8528-4d50-bbf9-3915af267402` | ✅ Tested, clean |
| Worker 4 | `42b27b34-ea16-4612-870b-84f9e40e296a` | ✅ User-provided |
| Worker 5 | `599684ce-78f3-4bd2-a8c9-45c294160dfe` | ✅ User-provided |

### Production Progress
**Nothing has been processed yet.** All previous runs were tests saved in `C:\PROJECTS\notebooklm-mcp\2013\` (v2-test, v3-test, multi-notebook-test, lifo-test). Production output goes to `C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\`.

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
6. **Run pipeline**:
   ```
   notebooklm.notebook_digest_multi
     notebook_ids: ["9daa06dc-b783-455a-b525-3c9cd3c36b9e", "d30bc801-da43-4e32-b044-bb1c0b6a20b4", "942b25a4-8528-4d50-bbf9-3915af267402", "42b27b34-ea16-4612-870b-84f9e40e296a", "599684ce-78f3-4bd2-a8c9-45c294160dfe"]
     file_paths: [... all files from step 4 ...]
     output_dir: "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\{YEAR}\{MM}_{Mon}"
     batch_size: 3
   ```
7. **Verify** output count matches input count
8. **Move to next month** and repeat from step 4

### Important Operational Notes

- **MCP Tool**: Use `notebooklm.notebook_digest_multi` via the lazy-mcp proxy (`mcp_lazy-mcp_execute_tool`)
- **Timeout**: The proxy has a 300s timeout for notebooklm. Large months (100+ files) may need multiple calls — the resume feature auto-skips completed files
- **Auth expires**: NotebookLM cookies expire periodically. If you get "Cookies have expired", run `notebooklm-mcp-auth` in terminal and have the user log in
- **LIFO cleanup**: Sources are deleted after each batch query. The 3 worker notebooks never accumulate sources — reuse them indefinitely
- **Batch size**: Default 3 cases per query. NotebookLM handles multi-case queries well (tested: produces separate digests with `---` separators)



## Directory Layout

### Source (input)
```
C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\
  └── {YEAR}\           (1996–2025, 30 years)
        └── {MM}_{Mon}\  (e.g. 01_Jan, 02_Feb, ... 12_Dec)
              └── *.md    (case decision files)
```

### Destination (output)
```
C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\
  └── {YEAR}\
        └── {MM}_{Mon}\
              └── {filename}-case-digest.md
```

The output mirrors the source structure exactly. Each digest file has the suffix `-case-digest.md`.

---

## Scale

| Year Range | Years | Approx Files | Est. Time (5 notebooks) |
|------------|-------|-------------|------------------------|
| 1996–2000  | 5     | ~5,198      | ~35 min                |
| 2001–2005  | 5     | ~6,496      | ~43 min                |
| 2006–2010  | 5     | ~7,023      | ~47 min                |
| 2011–2015  | 5     | ~4,918      | ~33 min                |
| 2016–2020  | 5     | ~5,327      | ~36 min                |
| 2021–2025  | 5     | ~2,870      | ~19 min                |
| **Total**  | **30**| **~31,832** | **~3.5 hours**         |

*Estimates based on benchmark: ~3.6s per doc with 5 notebooks (projected from 6s/doc with 3 notebooks).*

---

## Prerequisites

### 1. Authentication
Before starting, verify cookies are fresh:
```
notebooklm.check_auth_status
```
If expired, run in terminal:
```powershell
notebooklm-mcp-auth
```
Log in to Google in the Chrome window that opens. Wait for "SUCCESS" message.

### 2. Create 3 Worker Notebooks
Create 5 dedicated notebooks for the pipeline. These are **permanently reusable** — the pipeline uses LIFO source management (add → query → delete) so notebooks never accumulate sources.

```
notebooklm.notebook_create  →  title: "Digest Worker 1"
notebooklm.notebook_create  →  title: "Digest Worker 2"
notebooklm.notebook_create  →  title: "Digest Worker 3"
notebooklm.notebook_create  →  title: "Digest Worker 4"
notebooklm.notebook_create  →  title: "Digest Worker 5"
```

Save the 5 notebook IDs. You will reuse them **for the entire 31,832-file run**.

> **Source Lifecycle (LIFO)**: Each batch cycle adds `batch_size` sources, queries them, saves digests, then **immediately deletes** those sources. The notebook never exceeds `batch_size` sources at any time, well under the 50-source limit.

### 3. Verify Output Directory Exists
```powershell
mkdir "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS" -Force
```

---

## Processing Strategy

### Work Unit = One Month Folder
Process **one month at a time**. This keeps batches manageable (50–130 files per month) and maps cleanly to the directory structure.

### Recommended Approach: Month by Month

For each month folder:

1. **List available files**:
   ```powershell
   $src = "C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\{YEAR}\{MM}_{Mon}"
   $files = (Get-ChildItem $src -File -Filter "*.md").FullName
   $files.Count
   ```

2. **Check how many are already done** (resume support):
   ```powershell
   $dst = "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\{YEAR}\{MM}_{Mon}"
   $done = if (Test-Path $dst) { (Get-ChildItem $dst -File -Filter "*-case-digest.md").Count } else { 0 }
   Write-Output "Done: $done / $($files.Count)"
   ```

3. **Run the pipeline**:
   ```
   notebooklm.notebook_digest_multi
     notebook_ids: ["{ID1}", "{ID2}", "{ID3}"]
     file_paths: [... all .md files in this month ...]
     output_dir: "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\{YEAR}\{MM}_{Mon}"
     batch_size: 3
   ```

4. **Verify output count matches input count**.

5. **Move to next month**.

---

## Pipeline Tool Reference

### `notebook_digest_multi` (RECOMMENDED — fastest)

Distributes files across multiple notebooks. Each notebook processes its share concurrently.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notebook_ids` | `list[str]` | required | List of notebook UUIDs (use 5 for optimal throughput) |
| `file_paths` | `list[str]` | required | Absolute paths to source `.md` files |
| `output_dir` | `str` | required | Where to save digest files |
| `query_template` | `str` | Madera format | Case digest prompt template |
| `batch_size` | `int` | 3 | Cases queried per API call |
| `max_retries` | `int` | 2 | Retry attempts per batch |
| `delay` | `float` | 1.0 | Seconds between thread starts |

**Performance**: ~3.6s per doc with 5 notebooks (~6s with 3).

**Key features**:
- **LIFO source management**: Add → query → save → delete per batch. Notebooks never accumulate sources.
- **No source limit**: Same 3 notebooks can process unlimited files (never exceeds `batch_size` sources).
- **Resume on re-run**: Skips files whose digest already exists (>100 bytes). Safe to re-run after timeout.
- **Per-batch retry**: Failed queries retry up to `max_retries` times.
- **Incremental saves**: Each digest is saved immediately — partial results survive timeouts.

### `notebook_digest_pipeline` (single notebook fallback)

Same as above but uses only 1 notebook. Use if multi-notebook is unavailable.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notebook_id` | `str` | required | Single notebook UUID |
| `file_paths` | `list[str]` | required | Absolute paths |
| `output_dir` | `str` | required | Output directory |
| `batch_size` | `int` | 3 | Cases per query |
| `parallel` | `int` | 2 | Concurrent query threads |

**Performance**: ~15s per doc with 1 notebook.

---

## Handling Large Months (50+ files)

**No special handling needed.** The pipeline uses LIFO source management — sources are deleted after each batch query. The same 3 notebooks can process any number of files without hitting the 50-source limit.

Just pass all files in a single call:
```
notebooklm.notebook_digest_multi
  notebook_ids: ["{ID1}", "{ID2}", "{ID3}", "{ID4}", "{ID5}"]   ← same 5 notebooks always
  file_paths: [... all 130 files ...]
  output_dir: "..."
  batch_size: 3
```

The pipeline internally cycles per notebook: add 3 → query → save → delete 3 → add next 3 → ... (all 5 notebooks in parallel)

---

## Execution Checklist

Use this checklist to track progress year-by-year:

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

## Example: Processing January 2013

```
# Step 1: List source files
$src = "C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2013\01_Jan"
$files = (Get-ChildItem $src -File -Filter "*.md").FullName
# Result: 87 files

# Step 2: Use the same 5 worker notebooks (created once, reused forever)

# Step 3: Process ALL 87 files in one call (LIFO handles source cleanup)
notebooklm.notebook_digest_multi
  notebook_ids: ["9daa06dc-...", "d30bc801-...", "942b25a4-...", "f849b21c-...", "5ee19729-..."]
  file_paths: [all 87 file paths]
  output_dir: "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\2013\01_Jan"
  batch_size: 3

# Internally: each notebook processes ~18 files
#   add 3 → query → save 3 → delete 3 → add next 3 → ... (6 cycles each)
#   Total: ~6 batch queries × 20s / 5 notebooks = ~24s

# Step 4: Verify
$done = (Get-ChildItem "C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS\2013\01_Jan" -File).Count
# Expected: 87
```

---

## Error Recovery

| Scenario | What happens | Action |
|----------|-------------|--------|
| **Timeout** | Pipeline saves partial results | Re-run same command — resume skips completed files |
| **Auth expired** | Returns "Cookies have expired" | Run `notebooklm-mcp-auth`, log in, retry |
| **Notebook source limit** | N/A — LIFO auto-cleanup keeps notebooks under limit | Same 3 notebooks work indefinitely |
| **Split mismatch** | Batch response can't be split | Entry marked `partial` — re-run with `batch_size: 1` for those files |
| **Network error** | Per-batch retry kicks in | Automatic — up to `max_retries` attempts |

---

## Output Format

Each digest follows the **Atty. Madera** case digest format:

```markdown
I. CAPTION
**PARTY A v. PARTY B**, G.R. No. XXXXX, Date, Phil. Citation, Ponente, J.

II. FACTS
[Concise recitation of material facts]

III. ISSUE/S
W/N [issue statement]

IV. RULING
**YES/NO.** [Holding with ratio decidendi]
```

---

## Performance Benchmarks

| Method | Tool | Docs | Wall Time | Per Doc | Speedup |
|--------|------|------|-----------|---------|---------|
| Sequential | `notebook_digest_pipeline` (v2) | 6 | ~230s | ~38s | 1x |
| Batch + Parallel | `notebook_digest_pipeline` (v3) | 6 | 92s | ~15s | 2.5x |
| **Multi-Notebook** | **`notebook_digest_multi`** | **9** | **55s** | **~6s** | **6.3x** |

*Benchmarked 2026-02-16 with 3 notebooks, batch_size=3.*
