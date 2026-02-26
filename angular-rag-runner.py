"""Angular Source-to-Markdown Converter + NotebookLM RAG Runner.

PHASE 1 — Convert:
  Walks the Angular project's src/ directory, discovers all essential source
  files (.ts, .html, .scss/.css), and converts each — or a logical group
  (component + template + styles + spec) — into a rich Markdown document.
  Each .md file contains:
    - A metadata header (file path, component role, last-modified date)
    - ALL constituent files as fenced code blocks with syntax highlighting
  Output is written to --output-dir (default: ANGULAR-RAG-SOURCES/)

PHASE 2 — Upload (optional, requires NotebookLM auth):
  Reads every generated .md from the output directory and uploads it as a
  TEXT source to a designated NotebookLM notebook.  Imports notebooklm_mcp
  DIRECTLY (no MCP subprocess) for zero-overhead API calls.
  Default: BATCH mode — sends all delta sources in ONE RPC call.
  Legacy:  --sequential  for one-by-one upload with per-file progress.

PHASE 3 — Query (optional):
  Query the notebook directly from the CLI after uploading.
  Uses the same direct-import path (no MCP overhead).

Usage examples:
  # Convert only (local, no API calls)
  python angular-rag-runner.py --convert-only
  python angular-rag-runner.py --convert-only --project C:\\PROJECTS\\my-angular-app

  # Convert + upload to 1 notebook (batch mode — DEFAULT, fastest)
  python angular-rag-runner.py --notebook-ids <UUID>

  # Convert + upload to 3 notebooks in parallel (fan-out)
  python angular-rag-runner.py --notebook-ids <UUID1>,<UUID2>,<UUID3>

  # Upload only (skip conversion, re-use previously generated .md files)
  python angular-rag-runner.py --upload-only --notebook-ids <UUID1>,<UUID2>,<UUID3>

  # Force sequential upload (legacy, one-by-one with ETA)
  python angular-rag-runner.py --notebook-ids <UUID> --sequential

  # Dry run: show what would be done without making any changes
  python angular-rag-runner.py --dry-run

  # Query: races all 3 notebooks in parallel, returns first answer
  python angular-rag-runner.py --notebook-ids <UUID1>,<UUID2>,<UUID3> --query "How does AuthService work?"

  # Granular control
  python angular-rag-runner.py --notebook-ids <UUID1>,<UUID2>,<UUID3> --bundle-strategy component

Output layout (bundle-strategy=component, the default):
  ANGULAR-RAG-SOURCES/
    app.component.md                 # app.ts + app.css
    app.routes.md                    # app.routes.ts + app.routes.server.ts
    app.config.md                    # app.config.ts + app.config.server.ts
    services__chat.service.md        # chat.service.ts
    services__auth.service.md        # auth.service.ts
    components__chat__chat-area.md   # chat-area.ts
    ...

Performance architecture (zero MCP overhead):
  - Direct module import: sys.path.insert → imports src/ directly, no subprocess
  - .fn() bypass: calls FastMCP-decorated functions without the MCP JSON-RPC layer
  - Client singleton: get_client() reuses the httpx connection pool across all calls
  - Batch RPC: single batchexecute call for all delta sources (default mode)
  - Lazy imports: angular_rag_core and notebooklm_mcp only loaded when needed
  - Auth recovery callback: mid-flight cookie refresh without process restart

Auth resilience (same patterns as the other runners):
  - Multi-port CDP probe (9222, 9223, 9000) — compatible with Antigravity IDE
  - Auto-launch Chrome if no NotebookLM page is found
  - Mid-flight auth recovery callback registered at startup (not just on upload)
  - Disk-based auth.json fallback if CDP unavailable
  - Proactive cookie refresh every N uploads or M seconds
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Force UTF-8 on Windows stdout/stderr so emoji in print() don't crash
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Path setup ──────────────────────────────────────────────────────
# Allow importing notebooklm_mcp directly from src/ (same as other runners)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ═══════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════

LOG_DIR = Path.home() / ".notebooklm-mcp"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "angular-rag-runner.log"

logger = logging.getLogger("angular_rag_runner")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logger.addHandler(_fh)

# stderr StreamHandler is intentionally NOT added at module level.
# --verbose in main() adds it so scripts/CI can source this cleanly (exit 0).
_ch = logging.StreamHandler(sys.stderr)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(message)s"))
if hasattr(_ch.stream, "reconfigure"):
    try:
        _ch.stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Mirror server logs to our log file so we can diagnose API failures
for _slog in ("notebooklm_mcp.server", "notebooklm_mcp.api_client"):
    _sl = logging.getLogger(_slog)
    _sl.setLevel(logging.DEBUG)
    _sl.addHandler(_fh)

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Force auth from cached token (same env-var as all other runners)
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

# Default Angular project root
DEFAULT_PROJECT_ROOT = r"C:\PROJECTS\robsky-angular"

# Default output directory for generated Markdown files
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "ANGULAR-RAG-SOURCES")

# NotebookLM source wait time after each sequential upload (text sources are fast)
SOURCE_WAIT_SECONDS = 2

# Upload retry / backoff config
MAX_UPLOAD_RETRIES = 3
UPLOAD_BACKOFF_BASE = 15

# Proactive cookie refresh settings
REFRESH_INTERVAL_UPLOADS = 15   # Refresh every N uploads
REFRESH_INTERVAL_SECONDS = 600  # Or every 10 minutes

# Bundle strategies
BUNDLE_STRATEGIES = ("component", "flat", "single")

# ═══════════════════════════════════════════════════════════════════
# SHARED CORE — LAZY IMPORT
# angular_rag_core is only imported when actually needed (convert / upload).
# This means --help, --dry-run, and --query-only paths pay ZERO import cost
# for the CDP/auth stack or the heavy file-scanner machinery.
# ═══════════════════════════════════════════════════════════════════

_core = None  # populated on first call to _load_core()


def _load_core():
    """Lazy-import angular_rag_core the first time it is needed.

    Pattern from notebooklm-mcp-runner.py line 287:
      'Import here to avoid loading everything at startup'
    """
    global _core, silent_refresh_cookies
    if _core is not None:
        return _core
    import angular_rag_core as _m
    _core = _m
    # Re-bind the module-level alias so auth code in this file always works
    silent_refresh_cookies = _m.refresh_cookies
    return _core


# Thin wrappers — each delegates to the lazy-loaded core module.
# Callers use these names; the actual import happens on first use.
def _get_core_attr(name):
    return getattr(_load_core(), name)


def discover_source_files(project_root, include_specs=False):
    return _load_core().discover_source_files(project_root, include_specs=include_specs)


def build_bundles(files, strategy):
    return _load_core().build_bundles(files, strategy)


def _build_markdown(bundle, project_name):
    return _load_core().build_markdown(bundle, project_name)


def _check_upload_status_loaded(md_path, content, log_cache):
    return _load_core().check_upload_status_loaded(md_path, content, log_cache)


def _load_upload_log(path):
    return _load_core().load_upload_log(path)


def _record_upload(md_path, log_path, source_id, content, log_cache):
    return _load_core().record_upload(md_path, log_path, source_id, content, log_cache)


def silent_refresh_cookies(*args, **kwargs):
    """Placeholder — replaced by _load_core() with the real implementation."""
    _load_core()  # triggers re-bind of this name
    return silent_refresh_cookies(*args, **kwargs)




# ═══════════════════════════════════════════════════════════════════
# UTILITY HELPERS  (runner-local only)
# ═══════════════════════════════════════════════════════════════════

def _format_eta(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {int(s)}s"
    else:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h)}h {int(m)}m"


# ═══════════════════════════════════════════════════════════════════
# PHASE 1 — CONVERSION ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════

def convert_project(
    project_root: str,
    output_dir: str,
    strategy: str = "component",
    include_specs: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Discover, bundle, and convert all Angular source files to Markdown.

    Returns a list of absolute paths to all generated (or already-existing)
    Markdown files sorted alphabetically.
    """
    project_name = Path(project_root).name
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  ANGULAR RAG CONVERTER")
    print(f"  Project  : {project_root}")
    print(f"  Output   : {output_dir}")
    print(f"  Strategy : {strategy}")
    print(f"  Specs    : {'included' if include_specs else 'excluded'}")
    print(f"{'='*60}\n")

    # Step 1: Discover (via core)
    print("  🔍 Discovering source files...")
    files = discover_source_files(project_root, include_specs=include_specs)
    print(f"     Found {len(files)} source files\n")

    if not files:
        print("  ⚠️  No source files found — check project root and extension filters.")
        return []

    # Step 2: Bundle (via core)
    bundles = build_bundles(files, strategy)
    print(f"  📦 Created {len(bundles)} bundle(s) using strategy '{strategy}'\n")

    # Step 3: Convert — parallel render via ThreadPoolExecutor (OPT-4)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    generated: list[str] = []
    skipped = 0

    if dry_run:
        for i, bundle in enumerate(bundles, 1):
            out_path = os.path.join(output_dir, bundle.output_filename)
            print(f"  [{i:3d}/{len(bundles)}] DRY-RUN: Would write {bundle.output_filename} "
                  f"({len(bundle.files)} files, {bundle.total_bytes:,} bytes)")
            generated.append(out_path)
        print(f"\n  ✅ Conversion complete: {len(generated)} markdown files → {output_dir}\n")
        return sorted(generated)

    # Non-dry-run: render in parallel, write sequentially to avoid FS contention
    def _render(bundle: SourceBundle) -> tuple[SourceBundle, str]:
        return bundle, _build_markdown(bundle, project_name)

    max_workers = min(8, len(bundles))
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_render, b): b for b in bundles}
        results: dict[str, str] = {}  # output_path → md_content
        for fut in as_completed(futures):
            bundle, md = fut.result()
            out_path = os.path.join(output_dir, bundle.output_filename)
            results[out_path] = (bundle, md)

    for i, bundle in enumerate(bundles, 1):
        out_path = os.path.join(output_dir, bundle.output_filename)
        if os.path.exists(out_path) and not force:
            generated.append(out_path)
            skipped += 1
            continue
        bundle_obj, md = results[out_path]
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(md)
            generated.append(out_path)
            print(f"  [{i:3d}/{len(bundles)}] ✅ {bundle.output_filename:60s} "
                  f"({len(bundle.files)} files, {len(md):,} chars)")
        except Exception as e:
            logger.error("Failed to write %s: %s", out_path, e, exc_info=True)
            print(f"  [{i:3d}/{len(bundles)}] ❌ {bundle.output_filename} — {e}", file=sys.stderr)

    if skipped:
        print(f"\n  ℹ️  {skipped} bundle(s) already existed — use --force to regenerate.")

    print(f"\n  ✅ Conversion complete: {len(generated)} markdown files → {output_dir}\n")
    return sorted(generated)



# ═══════════════════════════════════════════════════════════════════
# AUTH — COOKIE REFRESH & RECOVERY
# ═══════════════════════════════════════════════════════════════════

# ── Auth refresh tracking (runner-local) ─────────────────────────
_last_refresh_time: float = 0.0
_auth_callback_registered: bool = False  # guard — register only once


def should_refresh(uploads_since_refresh: int) -> bool:
    """Check if it's time for a proactive cookie refresh."""
    if uploads_since_refresh >= REFRESH_INTERVAL_UPLOADS:
        return True
    if _last_refresh_time > 0 and (time.time() - _last_refresh_time) > REFRESH_INTERVAL_SECONDS:
        return True
    return False


def _auth_recovery_callback() -> bool:
    """Mid-flight auth recovery — invoked by NotebookLM pipeline threads.

    Thread-safe coordination is handled by server.py (leader election +
    generation counter) so only ONE thread fires the callback even when
    15 parallel threads all detect auth expiry simultaneously.
    """
    print("\n  🔑 [mid-flight] Thread detected expired auth, refreshing...", file=sys.stderr)
    success = silent_refresh_cookies()
    if success:
        # Force server singleton to reload with fresh cookies
        try:
            from notebooklm_mcp import server as _srv
            _srv.reset_client()
        except Exception:
            pass
        print("  🔑 [mid-flight] ✅ Done — threads will resume with fresh auth", file=sys.stderr)
    else:
        print("  🔑 [mid-flight] ❌ Could not refresh cookies", file=sys.stderr)
    return success


def _ensure_auth_callback_registered():
    """Register the auth recovery callback with server.py — idempotent.

    Pattern from notebooklm-mcp-runner.py lines 395-398:
      Register at startup (not just before upload) so mid-flight recovery
      works even in --upload-only mode without a preceding Phase 1.
    """
    global _auth_callback_registered
    if _auth_callback_registered:
        return
    try:
        from notebooklm_mcp.server import set_auth_recovery_callback
        set_auth_recovery_callback(_auth_recovery_callback)
        _auth_callback_registered = True
        logger.debug("Auth recovery callback registered")
    except ImportError:
        pass  # notebooklm_mcp not available — convert-only mode is fine


# ═══════════════════════════════════════════════════════════════════
# PHASE 2 — UPLOAD ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════

def upload_markdown_files(
    md_files: list[str],
    notebook_id: str,
    output_dir: str,
    cleanup: bool = True,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Upload generated Markdown files to a NotebookLM notebook.

    Smart per-bundle upsert logic (content-hash based):
      skip   — same bundle name + same content hash → nothing changed
      update — same bundle name + different content hash → delete old source, re-upload
      new    — no prior record → upload fresh

    Returns a summary dict.
    """
    global _last_refresh_time

    upload_log_path = os.path.join(output_dir, "upload-log.json")

    # Filter to only .md files
    md_files = [f for f in md_files if f.endswith(".md") and os.path.exists(f)]

    if not md_files:
        print("  ⚠️  No Markdown files to upload.")
        return {"status": "error", "error": "No .md files found"}

    # Pre-load the log ONCE (OPT-5: avoids re-reading the file for every single file)
    _log_cache: dict = _load_upload_log(upload_log_path)

    print(f"\n{'='*60}")
    print(f"  ANGULAR RAG UPLOADER  (smart upsert mode)")
    print(f"  Notebook : {notebook_id[:8]}...")
    print(f"  Files    : {len(md_files)}")
    print(f"{'='*60}\n")

    if dry_run:
        print("  DRY-RUN MODE — no API calls will be made.\n")
        for md in md_files:
            try:
                content = Path(md).read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
            status, old_sid = _check_upload_status_loaded(md, content, _log_cache)
            tag = {
                "skip":   "SKIP   (content unchanged)",
                "update": f"UPDATE (stale source {old_sid[:8] if old_sid else 'unknown'}... → delete + re-upload)",
                "new":    "NEW    (upload fresh)",
            }.get(status, status)
            print(f"  {tag} → {os.path.basename(md)}")
        return {"status": "dry_run"}

    # Lazy import — only pay the import cost when actually uploading.
    # Pattern: direct module import via sys.path (no MCP subprocess overhead).
    from notebooklm_mcp.server import get_client
    _ensure_auth_callback_registered()

    total = len(md_files)
    uploaded = 0
    updated  = 0
    skipped  = 0
    failed   = 0
    uploads_since_refresh = 0
    start_time = time.time()
    file_times = []

    for i, md_path in enumerate(md_files, 1):
        file_start = time.time()
        basename = os.path.basename(md_path)

        # Proactive cookie refresh
        if should_refresh(uploads_since_refresh):
            print(f"\n  ⏰ Proactive cookie refresh (after {uploads_since_refresh} uploads)...")
            if silent_refresh_cookies():
                uploads_since_refresh = 0

        # Read the Markdown content first (needed for hash check)
        try:
            with open(md_path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except Exception as e:
            logger.error("Cannot read %s: %s", md_path, e)
            print(f"  [{i:3d}/{total}] ❌ Cannot read {basename}: {e}", file=sys.stderr)
            failed += 1
            continue

        # ── Smart dedup check (uses pre-loaded cache — OPT-5) ─────────
        if not force:
            status, old_source_id = _check_upload_status_loaded(md_path, content, _log_cache)
        else:
            status, old_source_id = "new", None  # --force bypasses hash check

        if status == "skip":
            print(f"  [{i:3d}/{total}] ⏭️  SKIP   (content unchanged)  {basename}")
            skipped += 1
            continue

        client = get_client()

        # ── Delete stale source if this is an update ───────────────
        if status == "update" and old_source_id:
            try:
                client.delete_source(old_source_id)
                print(f"  [{i:3d}/{total}] 🗑️  Deleted stale source: {basename} ({old_source_id[:8]}...)")
            except Exception as e:
                logger.warning("Could not delete stale source %s for %s: %s",
                               old_source_id[:8], basename, e)
                # Non-fatal — still proceed with upload (may create a duplicate in edge cases)

        # ── Upload (with retry) ────────────────────────────────────
        source_id = None
        for attempt in range(1, MAX_UPLOAD_RETRIES + 1):
            try:
                title = Path(md_path).stem.replace("__", " / ").replace("_", " ")
                result = client.add_text_source(
                    notebook_id,
                    text=content,
                    title=f"[Angular] {title}",
                )
                if result:
                    source_id = result.get("id", "unknown")
                    break
                else:
                    logger.warning("[%s] add_text_source returned None (attempt %d)", basename, attempt)
                    if attempt < MAX_UPLOAD_RETRIES:
                        time.sleep(10)
                        silent_refresh_cookies()
            except Exception as e:
                logger.error("[%s] Upload failed (attempt %d): %s", basename, attempt, e, exc_info=True)
                if attempt < MAX_UPLOAD_RETRIES:
                    err_str = str(e).lower()
                    if any(kw in err_str for kw in ["expired", "auth", "401", "403"]):
                        print(f"  [{i:3d}/{total}] Auth error — refreshing cookies...", file=sys.stderr)
                        silent_refresh_cookies()
                    else:
                        backoff = UPLOAD_BACKOFF_BASE * (2 ** (attempt - 1))
                        print(f"  [{i:3d}/{total}] Error — backing off {backoff}s...", file=sys.stderr)
                        time.sleep(backoff)
                else:
                    print(f"  [{i:3d}/{total}] ❌ FAILED after {MAX_UPLOAD_RETRIES} attempts: {basename}",
                          file=sys.stderr)
                    failed += 1
                    break

        if source_id:
            _record_upload(md_path, upload_log_path, source_id, content, _log_cache)
            uploads_since_refresh += 1
            time.sleep(SOURCE_WAIT_SECONDS)

            file_elapsed = time.time() - file_start
            file_times.append(file_elapsed)
            remaining = total - i
            avg = sum(file_times) / len(file_times) if file_times else 0
            eta = _format_eta(avg * remaining) if remaining > 0 else "done"

            if status == "update":
                updated += 1
                label = "🔄 UPDATED"
            else:
                uploaded += 1
                label = "✅ UPLOADED"

            print(
                f"  [{i:3d}/{total}] {label}  {basename[:52]:52s} "
                f"| {file_elapsed:.1f}s | ETA: {eta}"
            )

    # ── Final summary ──────────────────────────────────────────────
    total_elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  🏁 UPLOAD COMPLETE")
    print(f"  Uploaded (new)   : {uploaded}")
    print(f"  Updated (replace): {updated}")
    print(f"  Skipped          : {skipped} (content unchanged)")
    print(f"  Failed           : {failed}")
    print(f"  Time             : {_format_eta(total_elapsed)}")
    if file_times:
        print(f"  Avg/file         : {_format_eta(sum(file_times)/len(file_times))}")
    print(f"  Log              : {upload_log_path}")
    print(f"{'='*60}")

    return {
        "status": "success" if failed == 0 else "partial",
        "mode": "sequential",
        "uploaded": uploaded,
        "updated":  updated,
        "skipped":  skipped,
        "failed":   failed,
        "total_elapsed": total_elapsed,
    }


# ═══════════════════════════════════════════════════════════════════
# PHASE 2 — BATCH UPLOAD (FAST PATH)
# ═══════════════════════════════════════════════════════════════════

def upload_markdown_files_batch(
    md_files: list[str],
    notebook_ids: list[str],
    output_dir: str,
    dry_run: bool = False,
    force: bool = False,
    source_prefix: str = "[Angular]",
) -> dict:
    """Upload Markdown files to N notebooks in parallel using one batch RPC per notebook.

    Architecture:
      1. Read all file contents ONCE upfront (shared across all notebooks)
      2. Per-notebook worker: classify (own upload-log) → delete stale → batch RPC → record
      3. ThreadPoolExecutor fans out to all notebooks simultaneously
      4. Aggregated summary printed at the end

    Each notebook gets its own upload-log-<nb_id[:8]>.json for independent dedup.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Filter to only .md files that exist
    md_files = [f for f in md_files if f.endswith(".md") and os.path.exists(f)]
    if not md_files:
        print("  ⚠️  No Markdown files to upload.")
        return {"status": "error", "error": "No .md files found"}

    # ── Step 1: Read all file contents ONCE (shared across all notebook workers) ──
    print(f"  📖 Reading {len(md_files)} markdown files...")
    file_contents: list[tuple[str, str]] = []   # (md_path, content)
    unreadable: list[str] = []
    for md_path in md_files:
        try:
            content = Path(md_path).read_text(encoding="utf-8", errors="replace")
            file_contents.append((md_path, content))
        except Exception as e:
            logger.error("Cannot read %s: %s", md_path, e)
            unreadable.append(md_path)

    print(f"\n{'='*60}")
    print(f"  ANGULAR RAG UPLOADER  [MULTI-NOTEBOOK BATCH — parallel fan-out]")
    print(f"  Notebooks: {len(notebook_ids)}  " + "  ".join(nb[:8]+"..." for nb in notebook_ids))
    print(f"  Files    : {len(file_contents)} readable  ({len(unreadable)} unreadable)")
    print(f"{'='*60}\n")

    if dry_run:
        print("  DRY-RUN MODE — no API calls will be made.\n")
        for nb_id in notebook_ids:
            log_path  = os.path.join(output_dir, f"upload-log-{nb_id[:8]}.json")
            log_cache = _load_upload_log(log_path)
            skip = update = new = 0
            for md_path, content in file_contents:
                if force:
                    new += 1
                else:
                    s, _ = _check_upload_status_loaded(md_path, content, log_cache)
                    if s == "skip":   skip   += 1
                    elif s == "update": update += 1
                    else:             new    += 1
            print(f"  [{nb_id[:8]}...] skip={skip} update={update} new={new}")
        return {"status": "dry_run"}

    # Lazy import — direct module import, zero MCP subprocess overhead.
    # .fn() bypass skips the FastMCP validation/serialization wrapper.
    from notebooklm_mcp.server import get_client, notebook_add_text_batch
    _ensure_auth_callback_registered()
    client = get_client()

    # ── Step 2: Per-notebook worker (classify → delete stale → batch RPC → record) ──
    def _upload_to_notebook(nb_id: str) -> dict:
        log_path  = os.path.join(output_dir, f"upload-log-{nb_id[:8]}.json")
        log_cache = _load_upload_log(log_path)
        tag       = f"[{nb_id[:8]}]"

        # ── Pre-flight sync: when log is empty, seed from actual notebook contents ──
        # This prevents duplicates when switching from the old single-log system
        # or when adding a new notebook to an existing pipeline.
        if not log_cache and not force:
            try:
                existing = get_notebook_sources(client, nb_id)
                angular  = {s["title"]: s["id"] for s in existing
                            if str(s.get("title", "")).startswith(source_prefix)}
                if angular:
                    print(f"  {tag} 🔍 Empty log — found {len(angular)} existing {source_prefix} "
                          f"sources in notebook. Seeding log to prevent duplicates...")
                    for md_path, content in file_contents:
                        stem  = Path(md_path).stem.replace("__", " / ").replace("_", " ")
                        title = f"{source_prefix} {stem}"
                        if title in angular:
                            src_id = angular[title]
                            # Only seed if we have a real source ID that can be deleted.
                            # batch-unknown IDs cannot be individually deleted, so we do NOT seed
                            # them — the file stays classified as 'new', which is safe (no stale
                            # copy to delete). Seeding with batch-unknown would cause 'update'
                            # classification, and the failed delete would leave a duplicate.
                            if src_id and src_id != "batch-unknown":
                                _record_upload(md_path, log_path, src_id,
                                               content, log_cache)
                    print(f"  {tag} ✅ Log seeded — {len([v for v in log_cache.values() if v])} "
                          f"entries. Classifying...")
            except Exception as e:
                logger.warning("%s Pre-flight sync failed (continuing without): %s", tag, e)

        sources_skip:   list[str]  = []
        sources_update: list[dict] = []
        sources_new:    list[dict] = []

        if force:
            # --force: bulk-clear ALL [source_prefix] sources from this notebook before
            # re-uploading. Individual source IDs in the log may be stale or
            # "batch-unknown", so per-source delete is unreliable and creates dupes.
            try:
                cleared = clear_angular_sources(client, nb_id, prefix=source_prefix)
                if cleared:
                    print(f"  {tag} Cleared {cleared} existing {source_prefix} sources (--force)")
            except Exception as e:
                logger.warning("%s Could not pre-clear (--force): %s", tag, e)
            log_cache.clear()  # reset so all files are classified as new
            for md_path, content in file_contents:
                title = Path(md_path).stem.replace("__", " / ").replace("_", " ")
                sources_new.append({"text": content, "title": f"{source_prefix} {title}",
                                    "_path": md_path})
        else:
            for md_path, content in file_contents:
                title = Path(md_path).stem.replace("__", " / ").replace("_", " ")
                entry = {"text": content, "title": f"{source_prefix} {title}", "_path": md_path}
                st, old_sid = _check_upload_status_loaded(md_path, content, log_cache)
                if st == "skip":
                    sources_skip.append(os.path.basename(md_path))
                elif st == "update":
                    entry["_old_source_id"] = old_sid
                    sources_update.append(entry)
                else:
                    sources_new.append(entry)

        pending = sources_update + sources_new
        print(f"  {tag} skip={len(sources_skip)} update={len(sources_update)} "
              f"new={len(sources_new)} → sending {len(pending)} sources")

        if not pending:
            return {"notebook_id": nb_id, "status": "success",
                    "uploaded": 0, "updated": 0, "skipped": len(sources_skip),
                    "failed": len(unreadable)}

        # Delete stale sources
        # For sources whose ID is "batch-unknown" (the batch RPC didn't return individual IDs),
        # we cannot call delete_source() with a junk string — it silently fails and leaves the
        # old copy in the notebook, creating a duplicate when we re-upload.
        # Fix: do a live title-match delete against the notebook for those entries.
        unknown_titles = [s["title"] for s in sources_update
                          if s.get("_old_source_id") in (None, "batch-unknown", "unknown")]
        if unknown_titles:
            try:
                # Fetch live sources and delete ALL copies matching these titles
                live_sources = get_notebook_sources(client, nb_id)
                for live_src in live_sources:
                    if live_src["title"] in unknown_titles:
                        try:
                            client.delete_source(live_src["id"])
                            logger.debug("%s Title-deleted stale '%s' (%s)",
                                         tag, live_src["title"][:50], live_src["id"][:8])
                        except Exception as e:
                            logger.warning("%s Could not title-delete %s: %s",
                                           tag, live_src["id"][:8], e)
            except Exception as e:
                logger.warning("%s Live title-match delete failed: %s", tag, e)
        for s in sources_update:
            old_sid = s.get("_old_source_id")
            if old_sid and old_sid not in ("batch-unknown", "unknown"):
                try:
                    client.delete_source(old_sid)
                except Exception as e:
                    logger.warning("%s Could not delete stale %s: %s", tag, old_sid[:8], e)

        # Batch RPC with retry
        api_sources = [{"text": s["text"], "title": s["title"]} for s in pending]
        results = None
        for attempt in range(1, MAX_UPLOAD_RETRIES + 1):
            try:
                print(f"  {tag} 🚀 batch attempt {attempt}/{MAX_UPLOAD_RETRIES} "
                      f"({len(api_sources)} sources)...")
                result = notebook_add_text_batch.fn(notebook_id=nb_id, sources=api_sources)
                if result and result.get("status") == "success":
                    results = result
                    break
                if attempt < MAX_UPLOAD_RETRIES:
                    silent_refresh_cookies()
                    time.sleep(5)
            except Exception as e:
                logger.error("%s Batch attempt %d failed: %s", tag, attempt, e, exc_info=True)
                if attempt < MAX_UPLOAD_RETRIES:
                    err_str = str(e).lower()
                    if any(kw in err_str for kw in ["expired", "auth", "401", "403"]):
                        silent_refresh_cookies()
                    else:
                        time.sleep(UPLOAD_BACKOFF_BASE * (2 ** (attempt - 1)))

        if not results:
            return {"notebook_id": nb_id, "status": "error",
                    "error": "Batch failed after all retries",
                    "uploaded": 0, "updated": 0, "failed": len(pending)}

        # Record results
        added = results.get("sources_added", [])
        uploaded_count = 0
        for i, src_info in enumerate(added):
            if i < len(pending):
                sid = (src_info.get("id", "unknown") if isinstance(src_info, dict)
                       else str(src_info))
                _record_upload(pending[i]["_path"], log_path, sid,
                               pending[i]["text"], log_cache)
                uploaded_count += 1
        for i in range(len(added), len(pending)):
            _record_upload(pending[i]["_path"], log_path, "batch-unknown",
                           pending[i]["text"], log_cache)
            uploaded_count += 1

        updated_count = min(len(sources_update), uploaded_count)
        new_count = max(0, uploaded_count - updated_count)
        print(f"  {tag} ✅ done — new={new_count} updated={updated_count}")
        return {"notebook_id": nb_id, "status": "success",
                "uploaded": new_count, "updated": updated_count,
                "skipped": len(sources_skip), "failed": len(unreadable)}

    # ── Step 3: Fan-out to all notebooks in parallel ──
    start_time = time.time()
    nb_results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(notebook_ids),
                            thread_name_prefix="nb-upload") as exe:
        futures = {exe.submit(_upload_to_notebook, nb_id): nb_id
                   for nb_id in notebook_ids}
        for fut in as_completed(futures):
            nb_id = futures[fut]
            try:
                nb_results[nb_id] = fut.result()
            except Exception as e:
                nb_results[nb_id] = {"notebook_id": nb_id, "status": "error",
                                     "error": str(e)}

    elapsed = time.time() - start_time

    # ── Step 4: Aggregate summary ──
    total_uploaded = sum(r.get("uploaded", 0) for r in nb_results.values())
    total_updated  = sum(r.get("updated",  0) for r in nb_results.values())
    total_skipped  = sum(r.get("skipped",  0) for r in nb_results.values())
    total_failed   = sum(r.get("failed",   0) for r in nb_results.values())
    any_error = any(r.get("status") == "error" for r in nb_results.values())

    print(f"\n{'='*60}")
    print(f"  🏁 BATCH UPLOAD COMPLETE  ({len(notebook_ids)} notebooks in {_format_eta(elapsed)})")
    for nb_id, r in nb_results.items():
        st = "✅" if r.get("status") == "success" else "❌"
        print(f"  {st} [{nb_id[:8]}...] "
              f"new={r.get('uploaded',0)} updated={r.get('updated',0)} "
              f"skipped={r.get('skipped',0)} failed={r.get('failed',0)}"
              + (f" ERR:{r.get('error','')}" if r.get("status") == "error" else ""))
    print(f"  {'─'*48}")
    print(f"  TOTAL  new={total_uploaded} updated={total_updated} "
          f"skipped={total_skipped} failed={total_failed}")
    print(f"  Speed  : {(total_uploaded+total_updated) / max(elapsed,0.1):.1f} "
          f"sources/sec (across all notebooks)")
    print(f"{'='*60}")

    return {
        "status":        "error" if any_error else "success",
        "mode":          "batch-multi",
        "notebooks":     len(notebook_ids),
        "uploaded":      total_uploaded,
        "updated":       total_updated,
        "skipped":       total_skipped,
        "failed":        total_failed,
        "total_elapsed": elapsed,
        "per_notebook":  nb_results,
    }


# ═══════════════════════════════════════════════════════════════════
# NOTEBOOK MANAGEMENT HELPERS
# ═══════════════════════════════════════════════════════════════════

def get_notebook_sources(client, notebook_id: str) -> list[dict]:
    """Return [{id, title}] for all sources currently in the notebook."""
    try:
        notebook_data = client.get_notebook(notebook_id)
        if not notebook_data:
            return []
        source_ids = []
        if isinstance(notebook_data, list) and len(notebook_data) >= 1:
            nb_info = notebook_data[0] if isinstance(notebook_data[0], list) else notebook_data
            sources_data = nb_info[1] if len(nb_info) > 1 else []
            if isinstance(sources_data, list):
                for src in sources_data:
                    if isinstance(src, list) and len(src) >= 2:
                        sid_wrapper = src[0]
                        sid = sid_wrapper[0] if isinstance(sid_wrapper, list) and sid_wrapper else None
                        title = src[1] if len(src) > 1 else "Untitled"
                        if sid:
                            source_ids.append({"id": sid, "title": title})
        return source_ids
    except Exception as e:
        logger.warning("get_notebook_sources failed: %s", e)
        return []


def clear_angular_sources(client, notebook_id: str, prefix: str = "[Angular]") -> int:
    """Delete all sources whose title starts with `prefix` from the notebook."""
    sources = get_notebook_sources(client, notebook_id)
    angular_sources = [s for s in sources if s["title"].startswith(prefix)]
    deleted = 0
    for src in angular_sources:
        try:
            client.delete_source(src["id"])
            deleted += 1
            print(f"    🗑️  Deleted: {src['title'][:60]}")
        except Exception as e:
            logger.warning("Failed to delete source %s: %s", src["id"][:8], e)
    return deleted


# ═══════════════════════════════════════════════════════════════════
# PHASE 3 — QUERY (direct API, no MCP overhead)
# ═══════════════════════════════════════════════════════════════════

def query_notebook(
    notebook_ids: list[str],
    query: str,
    max_retries: int = 3,
    backoff_base: int = 20,
) -> dict:
    """Race N notebooks in parallel — return whichever answers first.

    Fires one client.query() thread per notebook simultaneously.
    The first thread to return a non-empty answer wins; the others
    are left to complete in the background (threads can't be killed
    mid-flight but their results are simply ignored).

    Returns {status, answer, notebook_id, elapsed} or {status, error}.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Lazy import — only pay the cost when querying
    from notebooklm_mcp.server import get_client
    _ensure_auth_callback_registered()

    print(f"\n{'='*60}")
    print(f"  NOTEBOOK QUERY  [racing {len(notebook_ids)} notebooks in parallel]")
    print(f"  Notebooks: " + "  ".join(nb[:8]+"..." for nb in notebook_ids))
    print(f"  Query    : {query[:80]}{'...' if len(query) > 80 else ''}")
    print(f"{'='*60}\n")

    client    = get_client()
    _done     = threading.Event()   # set by winner thread
    start     = time.time()

    def _query_one(nb_id: str) -> dict:
        for attempt in range(1, max_retries + 1):
            if _done.is_set():
                return {"status": "cancelled", "notebook_id": nb_id}
            try:
                result = client.query(nb_id, query_text=query)
                if result and result.get("answer"):
                    return {"status": "success", "answer": result["answer"],
                            "notebook_id": nb_id}
                if attempt < max_retries:
                    time.sleep(backoff_base * (2 ** (attempt - 1)))
                    silent_refresh_cookies()
            except Exception as e:
                logger.warning("[%s] query attempt %d failed: %s", nb_id[:8], attempt, e)
                if attempt < max_retries:
                    time.sleep(backoff_base)
        return {"status": "error", "error": "no answer after retries", "notebook_id": nb_id}

    first_answer: dict | None = None
    with ThreadPoolExecutor(max_workers=len(notebook_ids), thread_name_prefix="nb-query") as exe:
        futures = {exe.submit(_query_one, nb_id): nb_id for nb_id in notebook_ids}
        for fut in as_completed(futures):
            result = fut.result()
            if result.get("status") == "success" and first_answer is None:
                first_answer = result
                _done.set()   # signal other threads to abort early
                elapsed = time.time() - start
                winner  = result["notebook_id"]
                print(f"  ✅ Answer from [{winner[:8]}...] in {elapsed:.1f}s\n")
                print(f"{result['answer']}\n")
                # Don't break — let as_completed drain so threads finish cleanly

    if first_answer:
        return {**first_answer, "elapsed": time.time() - start}

    print(f"  ❌ All {len(notebook_ids)} notebooks returned no answer.", file=sys.stderr)
    return {"status": "error", "error": "All notebooks returned empty or error", "answer": ""}


# ═══════════════════════════════════════════════════════════════════
# DRY-RUN SUMMARY
# ═══════════════════════════════════════════════════════════════════

def print_dry_run_summary(
    project_root: str,
    output_dir: str,
    strategy: str,
    include_specs: bool,
    notebook_id: Optional[str],
):
    """Show exactly what convert+upload would do without side effects."""
    project_name = Path(project_root).name
    print(f"\n{'='*60}")
    print(f"  DRY RUN SUMMARY")
    print(f"  Project  : {project_root}")
    print(f"  Strategy : {strategy}")
    print(f"  Specs    : {'included' if include_specs else 'excluded'}")
    if notebook_id:
        print(f"  Notebook : {notebook_id[:8]}...")
    print(f"{'='*60}")

    files = discover_source_files(project_root, include_specs=include_specs)
    bundles = build_bundles(files, strategy)

    total_bytes = sum(b.total_bytes for b in bundles)
    total_files = sum(len(b.files) for b in bundles)

    print(f"\n  Source files found  : {len(files)}")
    print(f"  Bundles (= NLM src) : {len(bundles)}")
    print(f"  Total source size   : {total_bytes:,} bytes ({total_bytes / 1024:.1f} KB)")
    print(f"\n  Bundle breakdown:\n")

    for i, b in enumerate(bundles, 1):
        file_list = ", ".join(f.extension for f in b.files[:5])
        if len(b.files) > 5:
            file_list += f", +{len(b.files)-5} more"
        print(f"  {i:3d}. {b.output_filename:55s} [{b.role:20s}] {b.total_bytes:8,}B  ({file_list})")

    print(f"\n  Output dir: {output_dir}")
    print(f"  Estimated NotebookLM sources: {len(bundles)}")
    if total_bytes > 500_000:
        print(f"\n  ⚠️  Total size {total_bytes/1024:.0f} KB — consider 'flat' or 'single' strategy if uploads fail.")
    print()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    global _last_refresh_time

    parser = argparse.ArgumentParser(
        description=(
            "Angular source-to-Markdown converter and NotebookLM RAG uploader.\n"
            "Phase 1: converts Angular src/ files to rich Markdown bundles.\n"
            "Phase 2: uploads them to a NotebookLM notebook as TEXT sources."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Source / output ──
    parser.add_argument(
        "--project", default=DEFAULT_PROJECT_ROOT, metavar="DIR",
        help=f"Angular project root (default: {DEFAULT_PROJECT_ROOT})",
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR, metavar="DIR",
        help=f"Directory for generated Markdown files (default: {DEFAULT_OUTPUT_DIR})",
    )

    # ── Bundle strategy ──
    parser.add_argument(
        "--bundle-strategy", choices=BUNDLE_STRATEGIES, default="component",
        help="How to bundle source files into Markdown documents "
             "(component=group by feature [default], flat=one per file, single=all-in-one)",
    )

    # ── Filtering ──
    parser.add_argument(
        "--include-specs", action="store_true", default=False,
        help="Include .spec.ts unit test files (excluded by default)",
    )

    # ── Phase control ──
    parser.add_argument(
        "--convert-only", action="store_true",
        help="Only run Phase 1 (convert to Markdown). Skip NotebookLM upload.",
    )
    parser.add_argument(
        "--upload-only", action="store_true",
        help="Skip Phase 1 (conversion). Only upload existing .md files from --output-dir.",
    )
    parser.add_argument(
        "--notebook-ids", metavar="UUID[,UUID2,UUID3]",
        help="One or more NotebookLM UUIDs (comma-separated). "
             "Upload fans out to all in parallel; query races all and returns first answer. "
             "Example: --notebook-ids uuid1,uuid2,uuid3",
    )
    # Legacy alias kept for backward compatibility
    parser.add_argument(
        "--notebook-id", metavar="UUID",
        help=argparse.SUPPRESS,  # hidden — use --notebook-ids instead
    )

    # ── Upload options ──
    parser.add_argument(
        "--no-cleanup", action="store_true",
        help="After uploading, do NOT delete the source from NotebookLM "
             "(default: keep in notebook permanently).",
    )
    parser.add_argument(
        "--source-prefix", default="[Angular]", metavar="PREFIX",
        help="Title prefix added to every uploaded source (default: [Angular]). "
             "Use a different prefix (e.g. [AngularTest]) to isolate test uploads.",
    )
    parser.add_argument(
        "--clear-existing", action="store_true",
        help="Before uploading, delete all existing [Angular] sources from the notebook.",
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="LEGACY: upload sources one-by-one with per-file ETA progress. "
             "Default is batch mode (single RPC call, 10x faster). "
             "Use this only when debugging individual source failures.",
    )
    # ── Query options ──
    parser.add_argument(
        "--query", metavar="QUESTION",
        help="After uploading (or standalone with --upload-only), query the notebook "
             "directly using the NotebookLM API. Prints the answer to stdout. "
             "Example: --query \"How does AuthService handle token refresh?\"",
    )

    # ── General ──
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without writing files or calling APIs.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-generate/re-upload even if output already exists.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print log messages to stderr (default: log file only).",
    )
    parser.add_argument(
        "--refresh-every", type=int, default=REFRESH_INTERVAL_UPLOADS,
        help=f"Auto-refresh cookies every N uploads (default: {REFRESH_INTERVAL_UPLOADS})",
    )

    args = parser.parse_args()

    # ── Resolve notebook IDs (--notebook-ids takes precedence over legacy --notebook-id) ──
    _raw_ids = args.notebook_ids or args.notebook_id or ""
    notebook_ids: list[str] = [nb.strip() for nb in _raw_ids.split(",") if nb.strip()]
    # Expose as a simple attribute for the rest of main()
    args._notebook_ids = notebook_ids
    # Keep args.notebook_id pointing at first ID so old code paths still work
    args.notebook_id = notebook_ids[0] if notebook_ids else None

    # OPT-3: Only attach stderr StreamHandler when explicitly requested
    if args.verbose:
        logger.addHandler(_ch)
        for _slog in ("notebooklm_mcp.server", "notebooklm_mcp.api_client"):
            logging.getLogger(_slog).addHandler(_ch)

    # ── Validation ──
    if args.upload_only and not notebook_ids:
        parser.error("--upload-only requires --notebook-ids")

    if not args.convert_only and not args.upload_only and not notebook_ids:
        # Default mode: convert only (no upload)
        args.convert_only = True

    # ── Dry-run summary ──
    if args.dry_run:
        print_dry_run_summary(
            project_root=args.project,
            output_dir=args.output_dir,
            strategy=args.bundle_strategy,
            include_specs=args.include_specs,
            notebook_id=args.notebook_id,
        )
        if notebook_ids and not args.convert_only:
            existing_md = sorted(Path(args.output_dir).glob("*.md")) if os.path.isdir(args.output_dir) else []
            if existing_md:
                print(f"  {len(existing_md)} existing .md files → {len(notebook_ids)} notebook(s).\n")
        return

    # ── Phase 1: Convert ──
    md_files: list[str] = []
    if not args.upload_only:
        md_files = convert_project(
            project_root=args.project,
            output_dir=args.output_dir,
            strategy=args.bundle_strategy,
            include_specs=args.include_specs,
            dry_run=args.dry_run,
            force=args.force,
        )

    # ── Phase 2: Upload ──
    if not args.convert_only and notebook_ids:
        # If we skipped conversion, pick up existing .md files
        if args.upload_only:
            md_files = sorted(
                str(p) for p in Path(args.output_dir).glob("*.md")
                if not p.name.startswith("upload-log")
            )
            if not md_files:
                print(f"  ⚠️  No .md files found in {args.output_dir}")
                print("       Run without --upload-only first to generate them.")
                return

        # ── Auth setup (registered at startup, before any API call) ──
        try:
            _ensure_auth_callback_registered()
            from notebooklm_mcp.server import get_client
            print(f"  ✅ Auth recovery callback registered  ({len(notebook_ids)} notebook(s))")
        except ImportError:
            print(f"  ❌ Cannot import notebooklm_mcp — is it installed?", file=sys.stderr)
            print(f"     Run: uv tool install . --force", file=sys.stderr)
            sys.exit(1)

        # Initial cookie refresh (proactive — before first API call)
        print("  🍪 Performing initial cookie refresh...")
        if silent_refresh_cookies():
            print("     ✅ Starting with fresh cookies.\n")
        else:
            print("     ⚠️  Could not refresh from Chrome — using cached cookies.\n")
        _last_refresh_time = time.time()

        # Optional: clear existing Angular sources from ALL notebooks
        if args.clear_existing:
            pfx = getattr(args, "source_prefix", "[Angular]")
            print(f"  🧹 Clearing existing {pfx} sources from {len(notebook_ids)} notebook(s)...")
            for nb_id in notebook_ids:
                try:
                    client = get_client()
                    deleted = clear_angular_sources(client, nb_id, prefix=pfx)
                    print(f"     [{nb_id[:8]}...] Deleted {deleted} source(s).")
                except Exception as e:
                    print(f"  ⚠️  [{nb_id[:8]}...] Could not clear: {e}", file=sys.stderr)
            print()

        # Run upload — BATCH (parallel fan-out, default) or SEQUENTIAL (debug)
        if getattr(args, "sequential", False):
            print("  ℹ️  Sequential mode (--sequential). Uploading to each notebook one-by-one.\n")
            for nb_id in notebook_ids:
                print(f"  → Uploading to [{nb_id[:8]}...]")
                upload_markdown_files(
                    md_files=md_files,
                    notebook_id=nb_id,
                    output_dir=args.output_dir,
                    cleanup=not args.no_cleanup,
                    dry_run=args.dry_run,
                    force=args.force,
                )
        else:
            upload_markdown_files_batch(
                md_files=md_files,
                notebook_ids=notebook_ids,
                output_dir=args.output_dir,
                dry_run=args.dry_run,
                force=args.force,
                source_prefix=getattr(args, "source_prefix", "[Angular]"),
            )

    # ── Phase 3: Query ──
    if args.query and notebook_ids:
        # Initial cookie refresh if we haven't already done one this session
        if _last_refresh_time == 0.0:
            print("  🍪 Performing initial cookie refresh...")
            if silent_refresh_cookies():
                print("     ✅ Starting with fresh cookies.\n")
            else:
                print("     ⚠️  Using cached cookies.\n")
            _last_refresh_time = time.time()

        query_notebook(
            notebook_ids=notebook_ids,
            query=args.query,
        )
    elif args.query and not notebook_ids:
        print("  ⚠️  --query requires --notebook-ids", file=sys.stderr)


if __name__ == "__main__":
    logger.info("Angular RAG runner started — log: %s", LOG_FILE)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        print("\n\nInterrupted! Any generated files are saved. Re-run to resume.")
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL ERROR", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
