# Multi-Notebook Upload & Deduplication — Issues & Fixes

**Date:** 2026-02-26  
**Scope:** `angular-rag-runner.py`, `angular-rag-watcher.py`  
**Feature:** Multi-notebook parallel upload + race query across 3 mirrored NotebookLM notebooks

---

## Background

The original scripts used a single `--notebook-id` argument and wrote one shared `upload-log.json`.
This session refactored both scripts to support `--notebook-ids` (comma-separated) with:

- **Runner:** parallel fan-out upload (ThreadPoolExecutor) + race query (first notebook to answer wins)
- **Watcher:** sequential fan-out on each file change
- **Per-notebook dedup logs:** `upload-log-<nb_id[:8]>.json` per notebook, independent content-hash tracking

---

## Issue 1 — `NameError: name 'notebook_id' is not defined`

### Symptom
```
NameError: name 'notebook_id' is not defined
File "angular-rag-runner.py", line 663, in upload_markdown_files_batch
    print(f"  Notebook : {notebook_id[:8]}...")
```

### Root Cause
During the refactor of `upload_markdown_files_batch` to multi-notebook, a `multi_replace_file_content`
chunk silently failed. The new per-notebook `_upload_to_notebook` inner function was inserted, but the
**old single-notebook block was never removed**. That block contained:
```python
print(f"  Notebook : {notebook_id[:8]}...")  # notebook_id no longer exists
```
The old param was renamed to `notebook_ids: list[str]` (plural).

### Fix
Manually identified the stale block (the old header + single-notebook dry-run + `"sending batch"` loop)
between lines 659–684 and removed it entirely, leaving only the new multi-notebook body intact.

### Files changed
- `angular-rag-runner.py` — removed stale single-notebook summary block inside `upload_markdown_files_batch`

---

## Issue 2 — 120 Duplicate Sources in NB1 (Migration Bug)

### Symptom
NotebookLM notebook `robsky-angular-sourcecode` (117e47ed) showed **120 sources instead of 40**
after the first multi-notebook upload run.

### Root Cause
The old system tracked uploads in a single `upload-log.json`.
The new system uses per-notebook `upload-log-<nb_id[:8]>.json` files.

On the first run with the new system:
1. `upload-log-117e47ed.json` did not exist (empty / new file)
2. `_check_upload_status_loaded` returned `"new"` for all 40 files
3. All 40 were uploaded on top of the **existing 40** already in the notebook from prior runs
4. Result: 40 old + 40 new = **80 sources** (then ran again during testing = **120**)

NB2 and NB3 were freshly created, so they correctly received 40 each on first run.

### Fix — Pre-flight Sync
Added a pre-flight sync step at the top of `_upload_to_notebook()`:

```python
if not log_cache and not force:
    existing = get_notebook_sources(client, nb_id)
    angular = {s["title"]: s["id"] for s in existing
               if str(s.get("title", "")).startswith("[Angular]")}
    if angular:
        # Seed log_cache with existing source IDs + current content hash
        for md_path, content in file_contents:
            title = f"[Angular] {Path(md_path).stem...}"
            if title in angular:
                _record_upload(md_path, log_path, angular[title], content, log_cache)
```

**Result:** When the per-notebook log is empty, the runner now:
1. Queries the actual notebook sources via `get_notebook_sources()`
2. Matches them by `[Angular] <title>` prefix
3. Seeds `log_cache` with their source IDs + current content hash
4. Classification then correctly identifies them as `skip` (hash unchanged) or `update` (hash changed)

### Immediate Cleanup
Ran `--clear-existing --force` to wipe the 120-source mess and re-upload cleanly:
```
[117e47ed] Deleted 120 source(s). → new=40 done
[b0376e17] Deleted 40 source(s).  → new=40 done
[493bbdb5] Deleted 40 source(s).  → new=40 done
```

### Files changed
- `angular-rag-runner.py` — `_upload_to_notebook()`: added pre-flight sync block

---

## Issue 3 — `--force` Created 80 Duplicates Per Notebook

### Symptom
After running `--force`, each notebook ended up with **80 sources** (40 dupes each) instead of
a clean 40.

### Root Cause — Attempt 1 (wrong fix)
First attempted fix: when `force=True`, check `log_cache` for existing source IDs and treat them as
`update` (delete + re-upload) instead of blindly `new`.

This still failed because sources uploaded via **batch mode** are recorded as `"batch-unknown"` in
the log — the `notebook_add_text_batch` RPC does not always return individual source IDs reliably.

```python
# Wrong fix — unreliable because old_sid is often "batch-unknown"
_, old_sid = _check_upload_status_loaded(md_path, content, log_cache)
if old_sid and old_sid not in ("batch-unknown",):
    entry["_old_source_id"] = old_sid  # delete before re-upload
    sources_update.append(entry)
else:
    sources_new.append(entry)  # still creates dupe if old source exists!
```

### Fix — Bulk Clear Before Force Re-upload
Replaced per-source delete with a **bulk `clear_angular_sources()` call** at the top of the `--force`
branch in `_upload_to_notebook()`:

```python
if force:
    # Bulk-clear ALL [Angular] sources from this notebook before re-uploading.
    # Per-source delete is unreliable because batch-uploaded IDs are often "batch-unknown".
    try:
        cleared = clear_angular_sources(client, nb_id)
        if cleared:
            print(f"  {tag} Cleared {cleared} existing [Angular] sources (--force)")
    except Exception as e:
        logger.warning("%s Could not pre-clear (--force): %s", tag, e)
    log_cache.clear()  # reset so all files are classified as new
    for md_path, content in file_contents:
        title = Path(md_path).stem.replace("__", " / ").replace("_", " ")
        sources_new.append({"text": content, "title": f"[Angular] {title}", "_path": md_path})
```

**Result:** `--force` now atomically wipes all `[Angular]`-prefixed sources from the notebook, resets
the log, then re-uploads all 40 cleanly. No duplicates possible.

### Files changed
- `angular-rag-runner.py` — `_upload_to_notebook()`: replaced per-source force path with bulk clear

---

## Issue 4 — Stale Old Single-Notebook Batch Body Left in Function

### Symptom
After inserting the new multi-notebook `_upload_to_notebook` inner function, the function still had
the **entire old single-notebook loop** below it (delete stale → batch RPC → record loop), which also
contained the `notebook_id` (singular) reference.

### Root Cause
`multi_replace_file_content` for chunk 3 (replacing the function body) only inserted the new code at
the insertion point but did not remove the old code below it. Both bodies coexisted in the file.

### Fix
Read the full function body (lines 612–777) and replaced the entire section with only the correct
multi-notebook implementation.

### Files changed
- `angular-rag-runner.py` — `upload_markdown_files_batch`: replaced entire function body

---

## Final Architecture — Deduplication System (3 Layers)

| Layer | Where | Mechanism |
|---|---|---|
| **Per-notebook upload log** | `upload-log-<nb_id[:8]>.json` | SHA-256 content hash per bundle. Skip if hash matches — 0 API calls. |
| **Pre-flight sync** | `_upload_to_notebook()` on empty log | Queries actual notebook sources via API, seeds log by title match. Handles migration and new-notebook onboarding. |
| **Force bulk-clear** | `_upload_to_notebook()` with `--force` | Calls `clear_angular_sources()` atomically before re-upload. Avoids unreliable per-source ID deletes. |

---

## E2E Test Results (2026-02-26 — Final Round)

| Test | Description | Key Output | Result |
|---|---|---|---|
| **T0 Baseline** | Live API check before tests | `angular=40 dupes=0` x3 | PASS |
| **T1 Idempotency** | Second run, no file changes | `skipped=120, 0s, 0 API calls` | PASS |
| **T2 Pre-flight sync** | Delete NB2 log, re-run | `Empty log — found 40 → Seeding → skip=40` | PASS |
| **T3 Force re-upload** | `--force` across all 3 NBs | `Cleared 40 x3 → new=40 x3, no dupes` | PASS |
| **T4 Idempotency after force** | Run immediately after T3 | `skipped=120, 0s` | PASS |
| **Final API verify** | Ground truth via `get_notebook()` | `angular=40 dupes=0 OVERALL: ALL PASS` | PASS |

---

## Key Operational Rules (Derived from Fixes)

1. **Never use `--force` without expecting a full clear + re-upload.** It calls `clear_angular_sources()`
   per notebook — all `[Angular]` sources will be deleted and re-uploaded.

2. **Per-notebook logs are independent.** Adding a 4th notebook will trigger pre-flight sync on first
   run for that notebook only — existing notebooks are unaffected.

3. **`batch-unknown` source IDs** are written when `notebook_add_text_batch` does not return individual
   source IDs in its response. This is expected for large batches. The upload IS recorded (content hash
   is saved), but the source cannot be individually deleted later — only bulk clear works.

4. **The UI source count may lag** behind the actual notebook data. Always use the API
   (`get_notebook_sources()`) to verify true source counts, not the NotebookLM card UI.

---

## Related Files

| File | Change |
|---|---|
| `angular-rag-runner.py` | Multi-notebook batch upload + race query + pre-flight sync + force bulk-clear |
| `angular-rag-watcher.py` | Sequential fan-out to multiple notebooks on file change |
| `ANGULAR-RAG-SOURCES/upload-log-117e47ed.json` | Per-notebook dedup log (NB1) |
| `ANGULAR-RAG-SOURCES/upload-log-b0376e17.json` | Per-notebook dedup log (NB2) |
| `ANGULAR-RAG-SOURCES/upload-log-493bbdb5.json` | Per-notebook dedup log (NB3) |
| `C:\PROJECTS\robsky-angular\.agent\workflows\notebooklm-rag-query.md` | Updated workflow with 3-NB architecture, dedup table, E2E results |
