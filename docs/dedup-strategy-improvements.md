# Deduplication Strategy Improvements (2026-02-26)

> Applied to `angular_rag_core.py` based on web research into production
> content-addressed deduplication, idempotent file upload patterns, and
> distributed file sync best practices.

---

## Changes Applied

### 1. Hash Space Extended: 16 → 32 hex chars (128-bit)

**File:** `angular_rag_core.py` — `compute_content_hash()`

**Before:**
```python
return hashlib.sha256(content.encode()).hexdigest()[:16]  # 64-bit space
```

**After:**
```python
return hashlib.sha256(content.encode()).hexdigest()[:32]  # 128-bit space
```

**Why:** Research confirmed SHA-256 birthday collision probability at 64-bit truncation
becomes non-trivial as source counts grow (e.g., 10,000 files → ~10⁻¹⁰ per pair).
At 128-bit (32 hex chars), collision probability is ~10⁻³⁸ even for millions of files —
effectively zero for any foreseeable scale.

**One-time migration:** Existing logs with 16-char hashes are treated as stale on first run
→ one-time re-upload of all sources. After that, new 32-char hashes are stable.

---

### 2. `batch-unknown` Skip Optimization

**File:** `angular_rag_core.py` — `check_upload_status_loaded()`

**Before:** If `source_id = "batch-unknown"`, the function returned `("update", None)` even
when the content hash was unchanged. This triggered the `unknown_titles` live-title-match path —
an extra API round-trip per affected file on every run.

**After:**
```python
# Hash match → content is identical → always skip, even if source_id is
# 'batch-unknown'. The remote content is guaranteed unchanged; no API call needed.
if stored_hash and stored_hash == current_hash:
    return "skip", None
```

**Why:** Content-addressed storage invariant: if the hash matches, the content is identical
regardless of what ID was used to upload it. Triggering a live-title API call is wasteful
when we already know the content hasn't changed. This eliminates spurious API calls for all
sources that were batch-uploaded (which store `batch-unknown` as a side-effect of the
batch upload response format).

**Impact:** Reduces API calls from O(batch-unknown count) to 0 on unchanged-content runs.

---

### 3. Atomic Log Writes (Crash-Safe)

**File:** `angular_rag_core.py` — `record_upload()`

**Before:**
```python
with open(upload_log_path, "w", encoding="utf-8") as fh:
    json.dump(log, fh, indent=2)
```

**After:**
```python
# Atomic write: write to .tmp then os.replace() — crash-safe
tmp_path = upload_log_path + ".tmp"
with open(tmp_path, "w", encoding="utf-8") as fh:
    json.dump(log, fh, indent=2)
os.replace(tmp_path, upload_log_path)
```

**Why:** The previous write was non-atomic. If the process was killed mid-write
(e.g., OOM, Ctrl+C, power loss), the log file would be partially written →
invalid JSON → `load_upload_log()` returns `{}` → entire next run re-uploads
all 40 × 3 = 120 sources unnecessarily.

`os.replace()` is guaranteed atomic on POSIX and nearly atomic on Windows
(uses `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`). The log is either fully
written or untouched — never in a corrupt intermediate state.

---

### 4. `--source-prefix` — Test-Isolated Source Titles

**File:** `angular-rag-runner.py` — `upload_markdown_files_batch()`, `clear_angular_sources()`, pre-flight sync

**Added:**
```
--source-prefix PREFIX   (default: [Angular])
```

**Why:** The E2E stress test (`test_dedup_e2e.py`) uploads sources using the same notebooks
as production. Without a prefix override, test sources would be titled `[Angular] ...` and
indistinguishable from real sources — causing false baseline checks and leaving junk in the
notebooks after test failures.

With `--source-prefix [AngularTest]`, the test suite:
- Safely co-exists with real `[Angular]` production sources
- Cleans up after itself (only deletes `[AngularTest]` sources)
- Can be run repeatedly without side effects on the real corpus

**Propagated to:**
- Pre-flight log seeding (searches for `source_prefix` sources, not hard-coded `[Angular]`)
- Bulk-clear in `--force` mode (clears `source_prefix` sources only)
- Title construction for both `sources_new` and `sources_update` batches
- `clear_angular_sources()` now takes `prefix=` kwarg (default `"[Angular]"`)

---

## Test Results After Changes

| Suite | Tests | Result |
|-------|-------|--------|
| `test_dedup.py` (T0–T4) | 30/30 | ✅ ALL PASS |
| `stress_test_dedup.py` (T5–T9) | 4 pass, 1 skip | ✅ ALL PASS |
| `test_dedup_e2e.py` (T0–T9, 10-file) | 10/10 | ✅ ALL PASS (×2 consecutive runs) |

### Key numbers (post-upgrade)
- **Idempotent skip speed:** avg ~4s for 10 files across 3 notebooks (0 API calls)
- **First upload (10 files × 3 NBs):** ~35s (batch RPC)
- **Force re-upload (10 files × 3 NBs, clear + fresh):** ~45-48s
- **Cleanup (30 sources deleted):** ~34s
- **Hash collision risk:** reduced from 64-bit to 128-bit space
- **batch-unknown API calls eliminated:** 0 unnecessary live-title-match calls on unchanged content
- **Crash safety:** atomic writes guaranteed via `os.replace()`
- **Test isolation:** `--source-prefix [AngularTest]` prevents test sources from mixing with real `[Angular]` sources

---

## What Was NOT Changed (and why)

| Consideration | Decision |
|---|---|
| Full SHA-256 (64 hex chars) | Overkill — 32 chars (128-bit) is sufficient for millions of files |
| Additional non-cryptographic hash (e.g., FNV-64) | Not needed — performance is already dominated by API calls, not hashing |
| Distributed locks for concurrent log access | Not needed — each notebook has its own log file, written by one thread |
| Server-side idempotency keys | Not applicable — NotebookLM API doesn't support idempotency keys |
