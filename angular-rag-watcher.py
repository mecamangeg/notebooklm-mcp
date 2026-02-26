# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "watchdog>=6.0.0",
#   "winotify>=1.1.0",
# ]
# ///
"""Angular RAG Watcher — Auto-convert + Auto-upload to NotebookLM.

Watches C:\\PROJECTS\\robsky-angular\\src for ANY source code change,
re-converts the affected bundle to .md, uploads it to a NotebookLM
notebook, and fires a batched Windows toast notification.

Own venv via PEP 723 inline script metadata — run with:
  uv run angular-rag-watcher.py --notebook-id <UUID>

Architecture mirrors codebase-indexer-local/scripts/watch.ts:
  - watchdog FileSystemEventHandler (recursive, cross-platform)
  - 800 ms debounce  — waits for saves to settle
  - Sequential op queue  — no race conditions
  - Content-hash deduplication  — skip re-upload if unchanged
  - Circuit breaker  — stops hammering on repeated API failures
  - Batched toast notifications (2 s window)  — no spam
  - Startup reconciliation — syncs stale .md files on launch
  - Graceful shutdown — drain queue, print stats on Ctrl+C

Usage:
  uv run angular-rag-watcher.py --notebook-id <UUID>
  uv run angular-rag-watcher.py --notebook-id <UUID> --convert-only
  uv run angular-rag-watcher.py --notebook-id <UUID> --no-toast
  uv run angular-rag-watcher.py --notebook-id <UUID> --debounce 1200
  uv run angular-rag-watcher.py --notebook-id <UUID> --no-startup-sync
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── UTF-8 stdout/stderr on Windows ──────────────────────────────────────
for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── notebooklm_mcp lives in src/ next to this script ──────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "src"))

# ── Shared core utilities (no duplication with runner) ──────────────────
from angular_rag_core import (
    SOURCE_EXTENSIONS as SOURCE_EXTS,
    EXCLUDE_PATTERNS,
    _EXCLUDE_RE,
    CDP_PROBE_PORTS as _CDP_PORTS,
    SourceFile as _SrcFile,
    SourceBundle,
    detect_role as _role,
    ext_to_language as _lang,
    extract_ts_symbols as _symbols,
    component_stem as _component_stem,
    safe_name_from_stem as _safe_name,
    compute_content_hash,
    check_upload_status as _check_upload_status,
    record_upload as _record_upload,
    build_bundle_for_file,
    build_bundle_from_stem_map,
    build_stem_map,
    build_markdown as _build_bundle_md,
    find_notebooklm_page as _find_nb_page,
    refresh_cookies as _core_refresh_cookies,
)

# ═══════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════

_LOG_DIR = Path.home() / ".notebooklm-mcp"
_LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = _LOG_DIR / "angular-rag-watcher.log"

_logger = logging.getLogger("rag_watcher")
_logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(message)s", datefmt="%H:%M:%S"
))
_logger.addHandler(_fh)

_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(message)s"))
if hasattr(_ch.stream, "reconfigure"):
    try:
        _ch.stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
_logger.addHandler(_ch)


def log(emoji: str, msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    getattr(_logger, level, _logger.info)(f"[{ts}] {emoji}  {msg}")


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

DEFAULT_PROJECT = r"C:\PROJECTS\robsky-angular"
DEFAULT_OUT_DIR = str(_HERE / "ANGULAR-RAG-SOURCES")

# SOURCE_EXTS, _CDP_PORTS, EXCLUDE_PATTERNS are imported from angular_rag_core

DEBOUNCE_MS             = 800
TOAST_DEBOUNCE_MS       = 2000
CIRCUIT_FAIL_THRESHOLD  = 5
CIRCUIT_RECOVERY_S      = 30
MAX_RETRIES             = 3
INITIAL_BACKOFF_S       = 1.0
MAX_BACKOFF_S           = 15.0
SOURCE_WAIT_S           = 2      # wait after upload so NLM can index
REFRESH_EVERY_N         = 15    # proactive cookie refresh every N uploads
REFRESH_EVERY_S         = 600   # or every 10 minutes

os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

# ═══════════════════════════════════════════════════════════════════
# WINDOWS TOAST NOTIFICATIONS
# Primary: PowerShell WinRT (no COM/Start Menu registration needed)
# Fallback: winotify → win10toast → silent
# ═══════════════════════════════════════════════════════════════════

import subprocess as _subprocess

_toast_backend = "powershell"  # always available on Windows 10+
_win10toast_obj = None

# Keep winotify/win10toast available as runtime fallbacks
try:
    from winotify import Notification as _WiNotif, audio as _WiAudio
except ImportError:
    _WiNotif = None  # type: ignore
try:
    from win10toast import ToastNotifier as _W10T
    _win10toast_obj = _W10T()
except ImportError:
    pass


# PowerShell snippet that fires a WinRT toast using the Explorer app ID.
# Using Explorer's AUMID bypasses the requirement for a registered Start
# Menu shortcut with a COM GUID (which unregistered Python scripts lack).
_PS_TOAST_TMPL = r"""
$xml = @"
<toast><visual><binding template='ToastGeneric'>
  <text>{title}</text>
  <text>{body}</text>
</binding></visual></toast>
"@
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
[void][Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom,ContentType=WindowsRuntime]
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = New-Object Windows.UI.Notifications.ToastNotification($doc)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Microsoft.Windows.Explorer').Show($toast)
"""


def _fire_toast(title: str, body: str):
    try:
        # Primary: PowerShell WinRT — works without any app registration
        ps = _PS_TOAST_TMPL.format(
            title=title.replace("'", "&#39;").replace('"', "&quot;"),
            body=body.replace("'", "&#39;").replace('"', "&quot;"),
        )
        _subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL,
            creationflags=_subprocess.CREATE_NO_WINDOW,
        )
        return
    except Exception as e:
        _logger.debug("PowerShell toast failed: %s — trying fallbacks", e)

    # Fallback 1: winotify
    try:
        if _WiNotif is not None:
            n = _WiNotif(app_id="Angular RAG Watcher", title=title, msg=body, duration="short")
            n.set_audio(_WiAudio.Default, loop=False)
            n.show()
            return
    except Exception as e:
        _logger.debug("winotify toast failed: %s", e)

    # Fallback 2: win10toast
    try:
        if _win10toast_obj:
            _win10toast_obj.show_toast(title, body, duration=4, threaded=True)
    except Exception as e:
        _logger.debug("win10toast failed: %s", e)


@dataclass
class _ToastBatch:
    """Accumulates events over TOAST_DEBOUNCE_MS then fires ONE toast."""
    converted: list[str] = field(default_factory=list)
    uploaded:  list[str] = field(default_factory=list)
    errors:    list[str] = field(default_factory=list)
    _timer: Optional[threading.Timer] = field(default=None, repr=False)
    _lock:  threading.Lock = field(default_factory=threading.Lock, repr=False)
    enabled: bool = True

    def queue(self, kind: str, name: str):
        if not self.enabled:
            return
        with self._lock:
            getattr(self, kind).append(name)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(TOAST_DEBOUNCE_MS / 1000, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self):
        with self._lock:
            lines = []
            for lst, label in [
                (self.converted, "📝 Converted"),
                (self.uploaded,  "🚀 Uploaded → NotebookLM"),
                (self.errors,    "⚠️ Errors"),
            ]:
                if lst:
                    n = len(lst)
                    lines.append(f"{label}: {n} file{'s' if n > 1 else ''}")
                    for f in lst[:3]:
                        lines.append(f"  · {f}")
                    if n > 3:
                        lines.append(f"  · +{n - 3} more")
            self.converted.clear(); self.uploaded.clear(); self.errors.clear()
            self._timer = None
        if lines:
            _fire_toast("🔄 Angular RAG Updated", "\n".join(lines))


_toast = _ToastBatch()

# ═══════════════════════════════════════════════════════════════════
# CONTENT HASH TRACKER  (skip re-upload when content unchanged)
# ═══════════════════════════════════════════════════════════════════

_HASH_CACHE = _LOG_DIR / "angular-watcher-hashes.json"


class _HashTracker:
    def __init__(self):
        self._h: dict[str, str] = {}
        try:
            if _HASH_CACHE.exists():
                self._h = json.loads(_HASH_CACHE.read_text(encoding="utf-8"))
                log("💾", f"Hash cache: {len(self._h)} entries loaded")
        except Exception:
            pass

    @staticmethod
    def _digest(s: str) -> str:
        return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]

    def has_changed(self, key: str, content: str) -> bool:
        new_h = self._digest(content)
        if self._h.get(key) == new_h:
            return False
        self._h[key] = new_h
        return True

    def remove(self, key: str):
        self._h.pop(key, None)

    def flush(self):
        try:
            _HASH_CACHE.write_text(json.dumps(self._h, indent=2), encoding="utf-8")
        except Exception as e:
            _logger.debug("Hash cache write failed: %s", e)


_tracker = _HashTracker()

# ═══════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════

class _CircuitBreaker:
    CLOSED = "CLOSED"; OPEN = "OPEN"; HALF_OPEN = "HALF_OPEN"

    def __init__(self):
        self._state = self.CLOSED
        self._fail_count = 0
        self._last_fail = 0.0
        self.trips = 0

    def is_open(self) -> bool:
        if self._state == self.CLOSED:
            return False
        if time.time() - self._last_fail > CIRCUIT_RECOVERY_S:
            self._state = self.HALF_OPEN
            log("🔄", "Circuit HALF_OPEN — probing", "warning")
            return False
        return True

    def ok(self):
        if self._state == self.HALF_OPEN:
            log("✅", "Circuit CLOSED — recovered")
        self._fail_count = 0
        self._state = self.CLOSED

    def fail(self, err: Exception):
        self._fail_count += 1
        self._last_fail = time.time()
        if self._fail_count >= CIRCUIT_FAIL_THRESHOLD and self._state != self.OPEN:
            self._state = self.OPEN
            self.trips += 1
            log("🔴", f"Circuit OPEN after {self._fail_count} failures (trip #{self.trips}). "
                f"Cooldown {CIRCUIT_RECOVERY_S}s. Last: {err}", "error")

    @property
    def state(self):
        return self._state


_circuit = _CircuitBreaker()

# ═══════════════════════════════════════════════════════════════════
# OPERATION QUEUE  (sequential, de-duplicating)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class _FileOp:
    abs_path: str
    kind: str        # "change" | "delete"
    ts: float = field(default_factory=time.time)


class _OpQueue:
    def __init__(self):
        self._q: list[_FileOp] = []
        self._lock = threading.Lock()
        self._idle = threading.Event()
        self._idle.set()
        self._stop = threading.Event()
        self.processed = 0
        self.dropped = 0
        threading.Thread(target=self._loop, daemon=True, name="op-queue").start()

    def enqueue(self, op: _FileOp):
        with self._lock:
            for i, existing in enumerate(self._q):
                if existing.abs_path == op.abs_path:
                    self._q[i] = op   # replace with newer event
                    return
            self._q.append(op)
        self._idle.clear()

    def drain(self, timeout: float = 30.0):
        self._idle.wait(timeout=timeout)

    def stop(self):
        self._stop.set()

    @property
    def length(self):
        with self._lock:
            return len(self._q)

    def _loop(self):
        while not self._stop.is_set():
            op = None
            with self._lock:
                if self._q:
                    op = self._q.pop(0)
            if op:
                try:
                    _execute(op)
                    self.processed += 1
                    _circuit.ok()
                except Exception as e:
                    _circuit.fail(e)
                    self.dropped += 1
                    _stats["errors"] += 1
                    log("💀", f"Permanently failed: {Path(op.abs_path).name} — {e}", "error")
                    _toast.queue("errors", Path(op.abs_path).name)
                finally:
                    with self._lock:
                        if not self._q:
                            self._idle.set()
            else:
                time.sleep(0.05)


_queue = _OpQueue()

_stats = {
    "converted": 0, "uploaded": 0, "skipped": 0,
    "errors": 0, "retries": 0, "start": time.time(),
}
_uploads_since_refresh = 0
_last_refresh_t: float = 0.0
_args_ref: argparse.Namespace | None = None   # set in main()

# ═══════════════════════════════════════════════════════════════════
# BUNDLE CACHE  (OPT-1: O(1) stem lookup vs O(n) os.walk per event)
# ═══════════════════════════════════════════════════════════════════

class _BundleCache:
    """Caches the stem→[SourceFile] map so per-event lookup is O(1) dict access.

    Build at startup, then invalidate ONLY on file created/deleted/moved events.
    MODIFIED events never change bundle membership — just re-read siblings from cache.
    """

    def __init__(self, project_root: str) -> None:
        self._project_root = project_root
        self._stem_map: dict[str, list] = {}
        self._lock = threading.RLock()
        self._built = False

    def build(self) -> None:
        """(Re)build the stem map from disk. Threadsafe."""
        t0 = time.perf_counter()
        stem_map = build_stem_map(self._project_root)
        with self._lock:
            self._stem_map = stem_map
            self._built = True
        elapsed = (time.perf_counter() - t0) * 1000
        log("📦", f"Bundle cache built: {len(stem_map)} stems in {elapsed:.0f}ms")

    def invalidate(self) -> None:
        """Rebuild after a file is created, deleted, or moved."""
        log("📦", "Bundle cache invalidated — rebuilding...", "debug")
        self.build()

    @property
    def stem_map(self) -> dict:
        with self._lock:
            if not self._built:
                self.build()
            return self._stem_map

    def get_bundle(self, changed_abs: str) -> "SourceBundle | None":
        """O(1) cache lookup. Falls back to os.walk if stem not found."""
        with self._lock:
            if not self._built:
                self.build()
            bundle = build_bundle_from_stem_map(changed_abs, self._project_root, self._stem_map)
        if bundle is None:
            # Fallback: new file not yet in cache — use slow path then rebuild
            bundle = build_bundle_for_file(changed_abs, self._project_root)
            if bundle:
                self.invalidate()  # rebuild so next event is fast again
        return bundle


_bundle_cache: _BundleCache | None = None  # initialized in main()


# ═══════════════════════════════════════════════════════════════════
# BUNDLE BUILDER  (thin watcher adapter over angular_rag_core)
# ═══════════════════════════════════════════════════════════════════

def _build_md(project: str, changed_abs: str) -> tuple[str, str] | None:
    """Return (out_path, md_content) for the bundle that owns changed_abs.
    Uses the _BundleCache for O(1) lookup — no os.walk on hot path.
    """
    bundle = _bundle_cache.get_bundle(changed_abs) if _bundle_cache else None
    if not bundle:
        log("⚠️", f"No bundle found for: {changed_abs}", "warning")
        return None

    proj_name = Path(project).name
    out_path  = os.path.join(
        DEFAULT_OUT_DIR if not _args_ref else _args_ref.output_dir,
        f"{bundle.name}.md",
    )
    return out_path, _build_bundle_md(bundle, proj_name)


# ═══════════════════════════════════════════════════════════════════
# AUTH HELPERS  (thin wrapper over angular_rag_core.refresh_cookies)
# ═══════════════════════════════════════════════════════════════════


def _refresh_cookies() -> bool:
    """Re-extract cookies from Chrome via CDP. Delegates to angular_rag_core."""
    global _last_refresh_t
    ok = _core_refresh_cookies(probe_ports=_CDP_PORTS, auto_launch=True)
    if ok:
        _last_refresh_t = time.time()
        log("🍪", "Cookies refreshed via CDP")
    return ok


def _upload(md_path: str, notebook_ids: list[str], output_dir: str):
    """Upload one .md file to ALL target notebooks sequentially.

    Each notebook gets its own upload-log-<nb_id[:8]>.json so content-hash
    dedup works independently per notebook (a file synced to NB1 but not yet
    to NB2 will still be uploaded to NB2).
    """
    global _uploads_since_refresh, _last_refresh_t

    if (_uploads_since_refresh >= REFRESH_EVERY_N or
            (_last_refresh_t > 0 and time.time() - _last_refresh_t > REFRESH_EVERY_S)):
        log("⏰", f"Proactive cookie refresh (after {_uploads_since_refresh} uploads)...")
        if _refresh_cookies():
            _uploads_since_refresh = 0

    basename = Path(md_path).name
    content  = Path(md_path).read_text(encoding="utf-8")
    title    = Path(md_path).stem.replace("__", " / ").replace("_", " ")

    from notebooklm_mcp.server import get_client
    client = get_client()

    for nb_id in notebook_ids:
        log_path = str(Path(output_dir) / f"upload-log-{nb_id[:8]}.json")
        tag      = f"[{nb_id[:8]}]"

        # Smart dedup: skip if content hasn't changed for THIS notebook
        status, old_sid = _check_upload_status(md_path, content, log_path)
        if status == "skip":
            log("⏭️", f"SKIP (unchanged) {tag}: {basename}")
            continue

        # Delete stale source before re-uploading
        if status == "update" and old_sid:
            try:
                client.delete_source(old_sid)
                log("🗑️", f"Deleted stale source {tag}: {basename} ({old_sid[:8]}...)")
            except Exception as e:
                _logger.warning("Could not delete stale %s %s: %s", tag, old_sid[:8], e)

        result = client.add_text_source(nb_id, text=content, title=f"[Angular] {title}")
        if not result:
            raise RuntimeError(f"add_text_source returned None for {basename} {tag}")

        _record_upload(md_path, log_path, result.get("id", "unknown"), content)
        _stats["uploaded"] += 1
        _uploads_since_refresh += 1
        action = "Updated" if status == "update" else "Uploaded"
        log("🚀", f"{action} {tag}: {basename}")
        _toast.queue("uploaded", basename)



# ═══════════════════════════════════════════════════════════════════
# EXECUTE (with retry + circuit breaker)
# ═══════════════════════════════════════════════════════════════════

def _execute(op: _FileOp):
    if _circuit.is_open():
        raise RuntimeError(f"Circuit OPEN — skipping {Path(op.abs_path).name}")

    args = _args_ref
    last_err: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if op.kind == "change":
                result = _build_md(args.project, op.abs_path)
                if result is None:
                    return
                out_path, md = result

                # Dedup: skip if content unchanged
                safe = _safe_name(_component_stem(
                    os.path.relpath(op.abs_path, os.path.join(args.project, "src")
                    ).replace("\\", "/")))
                if not _tracker.has_changed(safe, md):
                    _stats["skipped"] += 1
                    log("⏭️", f"Skipped (unchanged): {Path(out_path).name}", "debug")
                    return

                # Write .md
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                Path(out_path).write_text(md, encoding="utf-8")
                _stats["converted"] += 1
                log("✏️", f"Converted → {Path(out_path).name}  ({len(md):,} chars)")
                _toast.queue("converted", Path(out_path).name)

                # Upload
                if args.notebook_ids and not args.convert_only:
                    time.sleep(SOURCE_WAIT_S)
                    _upload(out_path, args.notebook_ids, args.output_dir)

            elif op.kind == "delete":
                src_root = os.path.join(args.project, "src")
                try:
                    rel = os.path.relpath(op.abs_path, src_root).replace("\\", "/")
                    _tracker.remove(_safe_name(_component_stem(rel)))
                    log("🗑️", f"Deleted from tracker: {Path(op.abs_path).name}")
                except ValueError:
                    pass
            return

        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if any(x in msg for x in ["enoent", "file not found"]):
                raise
            if attempt < MAX_RETRIES:
                backoff = min(INITIAL_BACKOFF_S * 2 ** attempt, MAX_BACKOFF_S)
                delay   = backoff + random.uniform(0, backoff * 0.3)
                _stats["retries"] += 1
                log("🔁", f"Retry {attempt+1}/{MAX_RETRIES} in {delay:.1f}s — {e}", "warning")
                # Auth errors: refresh immediately
                if any(x in msg for x in ["expired", "auth", "401", "403"]):
                    _refresh_cookies()
                else:
                    time.sleep(delay)

    raise last_err or RuntimeError("Unknown failure")


# ═══════════════════════════════════════════════════════════════════
# FILE SYSTEM WATCHER
# ═══════════════════════════════════════════════════════════════════

_debounce: dict[str, threading.Timer] = {}
_dlock    = threading.Lock()


def _debounce_enqueue(abs_path: str, kind: str):
    with _dlock:
        t = _debounce.pop(abs_path, None)
        if t:
            t.cancel()

        def _fire():
            with _dlock:
                _debounce.pop(abs_path, None)
            _queue.enqueue(_FileOp(abs_path=abs_path, kind=kind))
            log("📁", f"Queued [{kind}]: {Path(abs_path).name}")

        timer = threading.Timer(DEBOUNCE_MS / 1000, _fire)
        timer.daemon = True
        _debounce[abs_path] = timer
        timer.start()


def _is_watched(abs_path: str) -> bool:
    ext = Path(abs_path).suffix.lower()
    return (ext in SOURCE_EXTS
            and not abs_path.endswith(".spec.ts")
            and not _EXCLUDE_RE.search(abs_path.replace("\\", "/")))


try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class _Handler(FileSystemEventHandler):
        def on_created(self, e):
            if not e.is_directory and _is_watched(e.src_path):
                if _bundle_cache:
                    _bundle_cache.invalidate()  # new file changes bundle membership
                _debounce_enqueue(e.src_path, "change")

        def on_modified(self, e):
            if not e.is_directory and _is_watched(e.src_path):
                _debounce_enqueue(e.src_path, "change")  # no cache invalidation needed

        def on_deleted(self, e):
            if not e.is_directory and _is_watched(e.src_path):
                if _bundle_cache:
                    _bundle_cache.invalidate()  # removed file changes bundle membership
                _debounce_enqueue(e.src_path, "delete")

        def on_moved(self, e):
            if not e.is_directory:
                if _is_watched(e.src_path) or _is_watched(e.dest_path):
                    if _bundle_cache:
                        _bundle_cache.invalidate()  # move changes membership
                if _is_watched(e.src_path):
                    _debounce_enqueue(e.src_path, "delete")
                if _is_watched(e.dest_path):
                    _debounce_enqueue(e.dest_path, "change")

except ImportError:
    log("❌", "watchdog not installed. Run: uv pip install watchdog", "error")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# STARTUP SYNC
# ═══════════════════════════════════════════════════════════════════

def _startup_sync(project: str, output_dir: str):
    """Queue any bundles whose .md is missing or older than source files.
    Uses the _BundleCache stem_map — avoids a second os.walk.
    """
    log("🔍", "Startup sync — checking for stale bundles...")

    # Reuse already-built cache; if not ready yet, build now
    stem_map = _bundle_cache.stem_map if _bundle_cache else {}
    queued = 0

    for stem, files in stem_map.items():
        safe   = _safe_name(stem)
        md_out = os.path.join(output_dir, f"{safe}.md")
        stale  = not os.path.exists(md_out)
        if not stale:
            md_t  = os.path.getmtime(md_out)
            stale = any(os.path.getmtime(f.abs_path) > md_t for f in files)
        if stale:
            _queue.enqueue(_FileOp(abs_path=files[0].abs_path, kind="change"))
            queued += 1

    if queued:
        log("📋", f"Startup sync: {queued} bundle(s) queued for update")
        _toast.queue("converted", f"{queued} bundles (startup sync)")
    else:
        log("✅", "Startup sync: all bundles up-to-date")


# ═══════════════════════════════════════════════════════════════════
# HEARTBEAT
# ═══════════════════════════════════════════════════════════════════

def _heartbeat(interval_s: float):
    while True:
        time.sleep(interval_s)
        elapsed = int(time.time() - _stats["start"])
        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)
        log("💓", f"[{h:02d}:{m:02d}:{s:02d}] "
            f"converted={_stats['converted']} uploaded={_stats['uploaded']} "
            f"skipped={_stats['skipped']} errors={_stats['errors']} "
            f"retries={_stats['retries']} queue={_queue.length} "
            f"circuit={_circuit.state}")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    global _args_ref, _last_refresh_t, _bundle_cache

    parser = argparse.ArgumentParser(
        description="Watch Angular src/ and auto-convert + upload changes to NotebookLM."
    )
    parser.add_argument("--project",         default=DEFAULT_PROJECT,
                        help=f"Angular project root (default: {DEFAULT_PROJECT})")
    parser.add_argument("--output-dir",      default=DEFAULT_OUT_DIR,
                        help=f"Output .md directory (default: {DEFAULT_OUT_DIR})")
    parser.add_argument("--notebook-ids",    metavar="UUID[,UUID2,UUID3]",
                        help="One or more NotebookLM UUIDs (comma-separated). "
                             "Each changed .md is uploaded to ALL listed notebooks. "
                             "Example: --notebook-ids uuid1,uuid2,uuid3")
    # Legacy alias
    parser.add_argument("--notebook-id",     metavar="UUID",
                        help=argparse.SUPPRESS)
    parser.add_argument("--convert-only",    action="store_true",
                        help="Only convert to .md — skip NotebookLM upload")
    parser.add_argument("--debounce",        type=int, default=DEBOUNCE_MS,
                        help=f"File-save debounce in ms (default: {DEBOUNCE_MS})")
    parser.add_argument("--no-toast",        action="store_true",
                        help="Disable Windows toast notifications")
    parser.add_argument("--no-startup-sync", action="store_true",
                        help="Skip startup reconciliation scan")
    parser.add_argument("--verbose",         action="store_true",
                        help="Also print DEBUG log messages to console")

    args = parser.parse_args()
    _args_ref = args

    # ── Resolve notebook IDs (--notebook-ids takes precedence over --notebook-id) ──
    _raw = args.notebook_ids or args.notebook_id or ""
    args.notebook_ids = [nb.strip() for nb in _raw.split(",") if nb.strip()]
    args.notebook_id  = args.notebook_ids[0] if args.notebook_ids else None  # compat

    if args.verbose:
        _logger.setLevel(logging.DEBUG)

    if args.no_toast:
        _toast.enabled = False

    if not args.notebook_ids and not args.convert_only:
        args.convert_only = True
        log("ℹ️", "No --notebook-ids given — running in convert-only mode")

    src_dir = os.path.join(args.project, "src")
    if not os.path.isdir(src_dir):
        log("❌", f"Source directory not found: {src_dir}", "error")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Build bundle cache ──────────────────────────────────────────
    _bundle_cache = _BundleCache(args.project)
    _bundle_cache.build()  # eager build so first event is instant

    print(f"\n{'='*64}")
    print(f"  🔭  ANGULAR RAG WATCHER")
    print(f"  Watching   : {src_dir}")
    print(f"  Output     : {args.output_dir}")
    if args.notebook_ids:
        for nb_id in args.notebook_ids:
            print(f"  Notebook   : {nb_id[:8]}...")
    else:
        print(f"  Notebook   : none (convert-only)")
    print(f"  Debounce   : {args.debounce} ms")
    print(f"  Toast      : {'disabled' if args.no_toast else _toast_backend}")
    print(f"  Venv       : own (PEP 723 inline deps via uv run)")
    print(f"  Log        : {LOG_FILE}")
    print(f"{'='*64}\n")

    # ── Auth setup ─────────────────────────────────────────────────
    if args.notebook_ids and not args.convert_only:
        log("🔐", f"Setting up auth for {len(args.notebook_ids)} notebook(s)...")
        try:
            from notebooklm_mcp.server import set_auth_recovery_callback
            set_auth_recovery_callback(lambda: _refresh_cookies())
            log("✅", "Auth recovery callback registered")
        except ImportError:
            log("❌", "notebooklm_mcp not found — run from C:\\PROJECTS\\notebooklm-mcp\\", "error")
            log("❌", "  or: uv tool install . --force", "error")
            sys.exit(1)

        log("🍪", "Initial cookie refresh...")
        if _refresh_cookies():
            log("✅", "Fresh cookies ready")
            _last_refresh_t = time.time()
        else:
            log("⚠️", "Could not refresh from Chrome — using cached cookies", "warning")
            _last_refresh_t = time.time()

    # ── Startup sync ───────────────────────────────────────────────
    if not args.no_startup_sync:
        _startup_sync(args.project, args.output_dir)

    # ── Start watching ─────────────────────────────────────────────
    handler  = _Handler()
    observer = Observer()
    observer.schedule(handler, src_dir, recursive=True)
    observer.start()
    log("🟢", f"Watching {src_dir}  (Ctrl+C to stop)")

    threading.Thread(target=_heartbeat, args=(900,), daemon=True).start()

    if _toast_backend != "none" and not args.no_toast:
        _fire_toast(
            "🔭 Angular RAG Watcher Started",
            f"Watching {Path(src_dir).name}/\n"
            f"{len(args.notebook_ids)} notebook(s)" if args.notebook_ids else "Convert-only mode"
        )

    # ── Main loop ──────────────────────────────────────────────────
    try:
        while observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        log("\n🛑", "Shutting down — draining queue...")
    finally:
        observer.stop()
        _queue.drain(timeout=30)
        observer.join()
        _queue.stop()
        _tracker.flush()

        elapsed = int(time.time() - _stats["start"])
        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)

        print(f"\n{'='*64}")
        print(f"  🏁  WATCHER SESSION COMPLETE")
        print(f"  Converted  : {_stats['converted']}")
        print(f"  Uploaded   : {_stats['uploaded']}")
        print(f"  Skipped    : {_stats['skipped']} (content unchanged)")
        print(f"  Errors     : {_stats['errors']}")
        print(f"  Retries    : {_stats['retries']}")
        print(f"  Processed  : {_queue.processed}  |  Dropped: {_queue.dropped}")
        print(f"  Circuit    : {_circuit.trips} trip(s)")
        print(f"  Uptime     : {h:02d}:{m:02d}:{s:02d}")
        print(f"{'='*64}")

        if _toast_backend != "none" and not args.no_toast:
            _fire_toast("🛑 Angular RAG Watcher Stopped",
                        f"Converted: {_stats['converted']} | "
                        f"Uploaded: {_stats['uploaded']} | "
                        f"Errors: {_stats['errors']}")


if __name__ == "__main__":
    _logger.info("Watcher started — log: %s", LOG_FILE)
    try:
        main()
    except Exception as e:
        _logger.critical("FATAL", exc_info=True)
        print(f"\nFATAL: {e}")
        traceback.print_exc()
        sys.exit(1)
