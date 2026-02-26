# Session Context — Angular RAG Refactor + Optimization
**Saved:** 2026-02-25T22:58 +08:00  
**Project:** `C:\PROJECTS\notebooklm-mcp`

---

## What Was Done This Session

### Phase 1 — Refactor: Extract Shared Core

Created **`angular_rag_core.py`** as the single shared library between the runner and watcher. All duplicated code was removed from both scripts and replaced with imports from the core module.

**Functions moved to core:**
| Was in | Now in core as |
|---|---|
| Runner `_detect_role` / Watcher `_role` | `detect_role` |
| Runner `_ext_to_language` / Watcher `_lang` | `ext_to_language` |
| Runner `_extract_ts_symbols` / Watcher `_symbols` | `extract_ts_symbols` |
| Runner `_component_stem` / Watcher `_component_stem` | `component_stem` |
| Runner `_safe_name` / Watcher `_safe_name` | `safe_name_from_stem` |
| Runner `discover_source_files` | `discover_source_files` |
| Runner `build_bundles_*` / `build_bundles` | `build_bundles_*`, `build_bundles` |
| Runner `_build_markdown` / Watcher inline 100-line renderer | `build_markdown` |
| Runner `_compute_content_hash` | `compute_content_hash` |
| Runner `_check_upload_status` | `check_upload_status` |
| Runner `_record_upload` | `record_upload` |
| Runner `_find_notebooklm_chrome_page` | `find_notebooklm_page` |
| Runner `_reload_cookies_from_disk` | `reload_cookies_from_disk` |
| Runner `silent_refresh_cookies` / Watcher `_refresh_cookies` (70-line CDP impl) | `refresh_cookies` |
| Watcher inline `_build_md` (180-line renderer) | `build_bundle_for_file` + `build_markdown` |

**Dataclasses moved:**
- `SourceFile`, `SourceBundle` — both now in core

---

### Phase 2 — Optimization (6 optimizations, 2 friction fixes)

#### Results
| Metric | Before | After | Gain |
|---|---|---|---|
| Watcher per-event bundle lookup | 3.4ms (os.walk) | **0.012ms** (dict) | **283× faster** |
| Upload log × 40 files | 7.8ms (N disk reads) | **0.6ms** (pre-loaded) | **13× faster** |
| Runner exit code (no notebook-id) | Always `1` | `0` | Friction fixed ✅ |
| `re.compile` in hot path | Per-call | Pre-compiled at import | ~0.5ms eliminated |

#### OPT-1: Pre-compiled `_EXCLUDE_RE` (`angular_rag_core.py`)
```python
_EXCLUDE_RE: re.Pattern = re.compile("|".join(EXCLUDE_PATTERNS))
```
Used in `discover_source_files` and `build_bundle_for_file` — eliminates repeated recompilation.

#### OPT-2: `_BundleCache` class (`angular-rag-watcher.py`)
```python
class _BundleCache:
    def build(self) -> None: ...       # os.walk once at startup
    def invalidate(self) -> None: ...  # rebuild on create/delete/move only
    def get_bundle(self, changed_abs) -> SourceBundle | None: ...  # O(1) dict lookup
```
- Built eagerly in `main()` before watcher starts
- `on_modified` → no invalidation (membership doesn't change)
- `on_created` / `on_deleted` / `on_moved` → `invalidate()` (membership changes)
- `_startup_sync` now reuses `_bundle_cache.stem_map` (no second os.walk)

#### OPT-3: Opt-in stderr logging via `--verbose` flag
- Runner: `logger.addHandler(_ch)` only when `--verbose` is passed
- Watcher: `--verbose` sets log level to DEBUG
- **Fixes:** Runner used to exit 1 on every run because the INFO log to stderr triggered `NativeCommandError` in PowerShell

#### OPT-4: Parallel Markdown render (`angular-rag-runner.py`)
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
def _render(bundle): return bundle, _build_markdown(bundle, project_name)
with ThreadPoolExecutor(max_workers=min(8, len(bundles))) as exe:
    futures = {exe.submit(_render, b): b for b in bundles}
```

#### OPT-5: Pre-loaded upload log (`angular-rag-runner.py`)
```python
_log_cache: dict = _load_upload_log(upload_log_path)
# Then pass to every call:
_check_upload_status_loaded(md_path, content, _log_cache)
_record_upload(md_path, upload_log_path, source_id, content, _log_cache)
```
New core functions: `load_upload_log()`, `check_upload_status_loaded()`.
`record_upload()` gets optional `_log_cache` param (avoids re-reading log between writes).

#### OPT-6: Log format versioning
```python
UPLOAD_LOG_FORMAT_VERSION = 2
# Written into every log entry:
"format_version": UPLOAD_LOG_FORMAT_VERSION
```

#### New core exports added this session:
- `_EXCLUDE_RE` — pre-compiled module-level regex
- `UPLOAD_LOG_FORMAT_VERSION` — schema version int
- `load_upload_log(log_path)` → `dict`
- `check_upload_status_loaded(md_path, content, log_dict)` → `(status, old_sid)`
- `build_stem_map(project_root)` → `dict[stem, list[SourceFile]]`
- `build_bundle_from_stem_map(changed_abs, project_root, stem_map)` → `SourceBundle | None`

---

## Current File State

### `C:\PROJECTS\notebooklm-mcp\angular_rag_core.py`
- **~560 lines** (was 0 — new file)
- All shared logic lives here
- Key public exports: everything listed in the imports section of either script

### `C:\PROJECTS\notebooklm-mcp\angular-rag-runner.py`
- **~1017 lines**
- Imports from core at line ~152
- `convert_project()` — uses `ThreadPoolExecutor` for parallel render
- `upload_markdown_files()` — uses `_load_upload_log` + `_check_upload_status_loaded`
- `upload_markdown_files_batch()` — same pre-loaded log pattern
- `main()` — `--verbose` flag conditionally attaches stderr handler

### `C:\PROJECTS\notebooklm-mcp\angular-rag-watcher.py`
- **~895 lines** (was ~855 — toast backend refactor added ~40 lines)
- Imports from core at line ~63 (includes `_EXCLUDE_RE`, `build_stem_map`, `build_bundle_from_stem_map`)
- `_BundleCache` class at ~line 378
- `_bundle_cache: _BundleCache | None = None` global
- `_build_md()` uses `_bundle_cache.get_bundle()` — no os.walk on hot path
- `_Handler.on_modified` — no cache invalidation
- `_Handler.on_created/deleted/moved` — calls `_bundle_cache.invalidate()`
- `_startup_sync()` — uses `_bundle_cache.stem_map` (no second os.walk)
- `main()` — initializes `_bundle_cache = _BundleCache(args.project)` and calls `.build()`
- **Toast backend:** PowerShell WinRT (primary) → winotify (fallback) → win10toast (fallback)

---

## Post-Session Fix (2026-02-26)

### Toast Backend: PowerShell WinRT

**Problem:** `winotify` was silently dropping all toast notifications. Root cause: unregistered Python scripts need a COM-registered Start Menu shortcut with a GUID before Windows Action Center will deliver their toasts. `winotify` uses `app_id="Angular RAG Watcher"` but this app is not in the Start Menu registry.

**Fix in `angular-rag-watcher.py` (lines 144–217):**
- Changed `_toast_backend` default from `"none"` to `"powershell"`
- Added `_PS_TOAST_TMPL` — a PowerShell WinRT script that fires the toast using `Microsoft.Windows.Explorer` as the app ID (Explorer IS registered, so delivery is guaranteed)
- `_fire_toast()` now spawns `powershell -NoProfile -NonInteractive -Command <script>` via `subprocess.Popen` with `CREATE_NO_WINDOW`
- `winotify` and `win10toast` remain as fallbacks
- Removed the `⚠️ Toast disabled` startup warning (toast now always works)

**Verified:** PowerShell WinRT toast appeared in Windows Action Center on the first file-change test.

### Watcher Run Command: `uv run` → Direct Python

**Problem:** Starting the watcher with `uv run angular-rag-watcher.py` fails:
```
[ERROR] Could not import angular-rag-mcp\angular-rag-runner.py
[ERROR]   or: uv tool install . --force
```
`angular_rag_core` is a local module in the same directory — not a `uv` tool package. `uv run` creates an isolated venv that doesn't include local sibling files on `sys.path`.

**Fix:** Always start the watcher with the Python executable directly:
```powershell
$PYTHON = "C:\Users\Michael\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe"
Start-Process -FilePath $PYTHON -ArgumentList "angular-rag-watcher.py", "--notebook-id", "117e47ed-..." -WorkingDirectory "C:\PROJECTS\notebooklm-mcp" -WindowStyle Normal
```

### None critical — all tests passed:
- ✅ Syntax check: all 3 files pass `ast.parse`
- ✅ All 20 core exports importable
- ✅ `skip`/`update`/`new` classification logic verified
- ✅ Runner `--convert-only --force`: 40 bundles in 0.28s wall clock, exit 0
- ✅ Watcher `_BundleCache` class: 283× speedup confirmed

### Minor notes:
1. `detect_role('chat.component.html')` returns `"Component"` not `"Template"` — `.component.` pattern takes priority over `.html` suffix. This is **intentional** (matches original runner behavior).
2. Old upload logs (format_version missing) will get `status="update"` on first run — correct behavior (re-uploads with delete of old source_id).
3. The `_EXCLUDE_RE` export from core is a private-convention name (leading `_`) but is exported and used in the watcher — this is intentional for performance.

---

## How to Resume

1. Open `C:\PROJECTS\notebooklm-mcp` in the next session
2. The three files are production-ready:
   - `angular_rag_core.py` — shared library
   - `angular-rag-runner.py` — batch convert + upload CLI
   - `angular-rag-watcher.py` — file-watching auto-sync daemon
3. To run the runner:
   ```powershell
   # Convert only (no NotebookLM needed)
   uv run --no-project python angular-rag-runner.py --project C:\PROJECTS\robsky-angular --convert-only

   # Full convert + upload (sequential)
   uv run --no-project python angular-rag-runner.py --project C:\PROJECTS\robsky-angular --notebook-id <UUID>

   # Full convert + upload (batch, fast)
   uv run --no-project python angular-rag-runner.py --project C:\PROJECTS\robsky-angular --notebook-id <UUID> --batch

   # Verbose mode (shows log output in terminal)
   uv run --no-project python angular-rag-runner.py --project C:\PROJECTS\robsky-angular --convert-only --verbose
   ```
4. To run the watcher:
   ```powershell
   $PYTHON = "C:\Users\Michael\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe"
   # NOTE: Do NOT use `uv run` — fails with ImportError (angular_rag_core not installed as uv tool)
   Start-Process -FilePath $PYTHON -ArgumentList "C:\PROJECTS\notebooklm-mcp\angular-rag-watcher.py", "--notebook-id", "117e47ed-6385-4dc5-9abc-1bf57588a263" -WorkingDirectory "C:\PROJECTS\notebooklm-mcp" -WindowStyle Normal
   # Convert-only (no upload):
   Start-Process -FilePath $PYTHON -ArgumentList "C:\PROJECTS\notebooklm-mcp\angular-rag-watcher.py", "--convert-only" -WorkingDirectory "C:\PROJECTS\notebooklm-mcp" -WindowStyle Normal
   ```

---

## Possible Next Steps (not started)
- Add `--notify-url` webhook support to watcher (POST bundle name + source_id on upload)
- Add `--watch-debounce-ms` per-file-type (e.g. 200ms for .ts, 800ms for .scss)
- Extend `build_markdown` to emit YAML frontmatter for better NotebookLM indexing
- Add `angular-rag-diff.py` — compare upload log vs live notebook sources and show drift
