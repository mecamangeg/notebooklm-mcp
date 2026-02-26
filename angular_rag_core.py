"""angular_rag_core.py — Shared utilities for angular-rag-runner and angular-rag-watcher.

Import from both scripts instead of duplicating code.

Exports
-------
Constants
  SOURCE_EXTENSIONS, EXCLUDE_EXTENSIONS, EXCLUDE_PATTERNS, CDP_PROBE_PORTS

Dataclasses
  SourceFile, SourceBundle

Classification
  detect_role(rel_path) -> str
  ext_to_language(ext)  -> str
  extract_ts_symbols(source) -> list[str]
  component_stem(rel_path) -> str
  safe_name_from_stem(stem) -> str

Hashing / upload log
  compute_content_hash(content) -> str
  check_upload_status(md_path, content, log_path) -> ("skip"|"update"|"new", source_id|None)
  record_upload(md_path, log_path, source_id, content)

Discovery / bundling / conversion
  discover_source_files(project_root, include_specs) -> list[SourceFile]
  build_bundles_component(files) -> list[SourceBundle]
  build_bundles_flat(files)      -> list[SourceBundle]
  build_bundles_single(files)    -> list[SourceBundle]
  build_bundles(files, strategy) -> list[SourceBundle]
  build_markdown(bundle, project_name) -> str
  build_bundle_for_file(changed_abs, project_root) -> SourceBundle | None

CDP auth (shared between runner + watcher)
  find_notebooklm_page(probe_ports) -> (port, page_dict) | (None, None)
  reload_cookies_from_disk(force)   -> bool
  refresh_cookies(probe_ports, auto_launch) -> bool
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

SOURCE_EXTENSIONS: set[str] = {".ts", ".html", ".scss", ".css"}
EXCLUDE_EXTENSIONS: set[str] = {".js", ".map", ".d.ts", ".json", ".lock", ".md"}

EXCLUDE_PATTERNS: list[str] = [
    r"\.spec\.ts$",
    r"node_modules",
    r"dist[/\\]",
    r"\.angular[/\\]",
    r"coverage[/\\]",
    r"__pycache__",
    r"ANGULAR-RAG-SOURCES",
]

# Pre-compiled once at module load — eliminates repeated re.compile() in hot paths
_EXCLUDE_RE: re.Pattern = re.compile("|".join(EXCLUDE_PATTERNS))

# Upload log format version — bump when schema changes
UPLOAD_LOG_FORMAT_VERSION = 2

CDP_PROBE_PORTS: list[int] = [9222, 9223, 9000]

# Upload log dedup constants
_STALE_SOURCE_IDS = frozenset({"unknown", "batch-unknown"})

# ── Module-level auth state (shared, thread-safe via GIL for simple reads) ──
_auth_file_mtime: float = 0.0
_chrome_launched: bool  = False


# ═══════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════

@dataclass
class SourceFile:
    """A single source file discovered in the Angular project."""
    abs_path:  str    # Absolute path on disk
    rel_path:  str    # Relative to project src/  (always forward slashes)
    extension: str    # e.g. ".ts"
    is_spec:   bool   # True if file ends with .spec.ts
    size_bytes: int
    mtime: float      # Last-modified timestamp


@dataclass
class SourceBundle:
    """A logical group of source files that becomes ONE NotebookLM source."""
    name:          str               # Safe filename stem (no extension)
    display_title: str               # Human-readable title for the source
    role:          str               # e.g. "Component", "Service", "Model"
    files: list[SourceFile] = field(default_factory=list)

    @property
    def output_filename(self) -> str:
        return f"{self.name}.md"

    @property
    def total_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files)


# ═══════════════════════════════════════════════════════════════
# CLASSIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════

def detect_role(rel_path: str) -> str:
    """Classify a file's Angular role based on its path/name."""
    lower = rel_path.lower().replace("\\", "/")
    if ".service."    in lower: return "Service"
    if ".component."  in lower: return "Component"
    if ".pipe."       in lower: return "Pipe"
    if ".guard."      in lower: return "Guard"
    if ".resolver."   in lower: return "Resolver"
    if ".interceptor." in lower: return "Interceptor"
    if ".module."     in lower: return "Module"
    if ".directive."  in lower: return "Directive"
    if ".routes."     in lower: return "Routes"
    if ".config."     in lower: return "Config"
    if "model" in lower or "types" in lower or ".types." in lower:
        return "Model/Types"
    if "util"       in lower: return "Utility"
    if "environment" in lower: return "Environment Config"
    if lower.endswith(".html"):                          return "Template"
    if lower.endswith(".scss") or lower.endswith(".css"): return "Styles"
    if lower.endswith(".spec.ts"):                       return "Unit Test"
    return "Source"


def ext_to_language(ext: str) -> str:
    """Map a file extension to its Markdown fenced-code language identifier."""
    return {
        ".ts":   "typescript",
        ".html": "html",
        ".scss": "scss",
        ".css":  "css",
        ".json": "json",
        ".js":   "javascript",
        ".md":   "markdown",
    }.get(ext, "text")


def extract_ts_symbols(source: str) -> list[str]:
    """Regex-based extraction of exported symbols from TypeScript source.
    Returns up to 20 names (classes, interfaces, functions, consts, types, enums)."""
    patterns = [
        r"export\s+(?:abstract\s+)?class\s+(\w+)",
        r"export\s+interface\s+(\w+)",
        r"export\s+(?:async\s+)?function\s+(\w+)",
        r"export\s+(?:const|let|var)\s+(\w+)",
        r"export\s+type\s+(\w+)",
        r"export\s+enum\s+(\w+)",
        r"@(?:Component|Injectable|Pipe|Directive|NgModule)\s*\(",
    ]
    symbols: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, source):
            if m.lastindex and m.group(1) not in symbols:
                symbols.append(m.group(1))
    return symbols[:20]


def component_stem(rel_path: str) -> str:
    """Return the grouping key that maps related files to the same bundle.

    Examples:
      app/components/chat/chat-area/chat-area.ts   → app/components/chat/chat-area
      app/components/chat/chat-area/chat-area.html → app/components/chat/chat-area
      app/services/chat.service.ts                 → app/services/chat.service
      app/app.ts                                   → app/app
      app/app.routes.ts                            → app/app.routes
    """
    if not rel_path or rel_path.strip() in ("", ".", "./", ".\\"):
        return ""
    rel  = rel_path.replace("\\", "/")
    path = Path(rel)
    if not path.name:
        return rel.rstrip("/")
    stem = str(path.with_suffix("")).replace("\\", "/")
    # If the file stem matches its parent directory name, group at folder level.
    if path.stem.lower() == path.parent.name.lower():
        return str(path.parent.as_posix())
    return stem


def safe_name_from_stem(stem: str) -> str:
    """Convert a component stem like 'app/services/chat.service'
    to a safe .md filename stem like 'services__chat.service'."""
    safe = re.sub(r"[/\\]+", "__", stem)
    if safe.startswith("app__"):
        safe = safe[len("app__"):]
    return safe


# ═══════════════════════════════════════════════════════════════
# CONTENT HASH / UPLOAD LOG
# ═══════════════════════════════════════════════════════════════

def compute_content_hash(content: str) -> str:
    """SHA-256 (first 32 hex chars = 128 bits) of Markdown content.

    128-bit space gives collision probability ~1-in-10^38 for 40 files —
    astronomically safe while still being compact in the JSON log.
    Extended from 16 to 32 hex chars (2026-02-26) for improved safety
    at scale when source count grows beyond 40.
    Backward-compat: old 16-char hashes stored in logs will no longer match
    the new 32-char hashes and will be treated as 'update' on first run
    after upgrade — a one-time re-upload of all sources.
    """
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:32]


def load_upload_log(log_path: str) -> dict:
    """Load the upload log from disk once. Returns empty dict on any error.
    Pass the result to check_upload_status_loaded to avoid repeated disk reads."""
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return {}


def check_upload_status_loaded(
    md_path: str,
    content: str,
    log: dict,
) -> tuple[str, str | None]:
    """Like check_upload_status but operates on a pre-loaded log dict.
    Use this in batch paths to avoid reading the log file N times.

    Key invariant (research-derived):
      If content_hash matches, the remote source is identical to the local file
      regardless of what source_id is stored (including 'batch-unknown').
      Returning 'skip' in that case eliminates a spurious live-title-match API
      call that would otherwise fire every run for batch-uploaded sources.
    """
    entry = log.get(os.path.basename(md_path))
    if not entry:
        return "new", None
    current_hash = compute_content_hash(content)
    stored_hash  = entry.get("content_hash")
    # Hash match → content is identical → always skip, even if source_id is
    # 'batch-unknown'. The remote content is guaranteed unchanged; no API call needed.
    if stored_hash and stored_hash == current_hash:
        return "skip", None
    # Hash mismatch → content changed. Only provide the old source_id for
    # targeted delete if it's a real (non-stale) ID.
    old_sid   = entry.get("source_id")
    stale_sid = old_sid if old_sid not in (None, *_STALE_SOURCE_IDS) else None
    return "update", stale_sid


def check_upload_status(
    md_path: str,
    content: str,
    upload_log_path: str,
) -> tuple[str, str | None]:
    """Per-bundle dedup check based on content hash.

    Returns (status, old_source_id) where status is one of:
      "skip"   — same bundle name + same content hash → nothing changed
      "update" — same bundle name + DIFFERENT hash    → delete old source, re-upload
      "new"    — no prior record                      → upload fresh

    old_source_id is set only for "update" (so caller can delete it).
    """
    try:
        if not os.path.exists(upload_log_path):
            return "new", None
        with open(upload_log_path, "r", encoding="utf-8") as fh:
            log = json.load(fh)
        entry = log.get(os.path.basename(md_path))
        if not entry:
            return "new", None

        current_hash = compute_content_hash(content)
        stored_hash  = entry.get("content_hash")  # may be absent in old-format logs

        if stored_hash and stored_hash == current_hash:
            return "skip", None

        old_sid   = entry.get("source_id")
        stale_sid = old_sid if old_sid not in (None, *_STALE_SOURCE_IDS) else None
        return "update", stale_sid
    except Exception:
        return "new", None


def record_upload(
    md_path: str,
    upload_log_path: str,
    source_id: str,
    content: str = "",
    _log_cache: dict | None = None,
) -> None:
    """Record a successful upload in the log, with content hash for future dedup.

    Uses atomic temp-file + os.replace() write to prevent JSON corruption if
    the process crashes mid-write (research pattern: 'atomic file update').
    """
    try:
        # Use caller-supplied cache dict if provided (avoids extra disk read)
        log: dict = _log_cache if _log_cache is not None else load_upload_log(upload_log_path)
        key = os.path.basename(md_path)
        entry = {
            "source_id":      source_id,
            "uploaded_at":    time.time(),
            "md_path":        md_path,
            "content_hash":   compute_content_hash(content) if content else "",
            "format_version": UPLOAD_LOG_FORMAT_VERSION,
        }
        log[key] = entry
        if _log_cache is not None:
            _log_cache[key] = entry
        # Atomic write: write to .tmp then os.replace() — crash-safe
        tmp_path = upload_log_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=2)
        os.replace(tmp_path, upload_log_path)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# FILE DISCOVERY
# ═══════════════════════════════════════════════════════════════

def discover_source_files(
    project_root: str,
    include_specs: bool = False,
    allowed_exts: set[str] | None = None,
    explicit_files: set[str] | None = None,
) -> list[SourceFile]:
    """Walk src/ inside the Angular project and collect all source files."""
    src_root = os.path.join(project_root, "src")
    if not os.path.isdir(src_root):
        src_root = project_root  # fallback

    exclude_re = _EXCLUDE_RE  # use pre-compiled module-level regex (OPT-1)
    results: list[SourceFile] = []

    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [
            d for d in dirnames
            if not exclude_re.search(os.path.join(dirpath, d).replace("\\", "/"))
        ]
        for fname in filenames:
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, src_root).replace("\\", "/")
            ext      = Path(fname).suffix.lower()

            _exts = allowed_exts if allowed_exts is not None else SOURCE_EXTENSIONS
            if ext not in _exts:
                continue
            
            # If a custom allowed_exts explicitly adds an extension that is normally excluded, let it through.
            if ext not in _exts and any(abs_path.endswith(ex) for ex in EXCLUDE_EXTENSIONS):
                continue

            is_spec = fname.endswith(".spec.ts")

            # _EXCLUDE_RE contains \.spec\.ts$ — skip that pattern when include_specs=True
            # so we test the path against the other exclusion patterns separately.
            if exclude_re.search(rel_path):
                # Allow spec files through if include_specs is set
                if is_spec and include_specs:
                    pass  # do not skip — fall through to the append below
                else:
                    continue

            if is_spec and not include_specs:
                continue

            stat = os.stat(abs_path)
            results.append(SourceFile(
                abs_path=abs_path,
                rel_path=rel_path,
                extension=ext,
                is_spec=is_spec,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
            ))

    # Append any explicitly listed files (e.g., config files mapped out from the root)
    if explicit_files:
        _exts = allowed_exts if allowed_exts is not None else SOURCE_EXTENSIONS
        for fp in explicit_files:
            if not os.path.isfile(fp):
                continue
            fname = os.path.basename(fp)
            ext = Path(fname).suffix.lower()
            if ext not in _exts:
                if any(fp.endswith(ex) for ex in EXCLUDE_EXTENSIONS):
                    continue
            try:
                rel_path = os.path.relpath(fp, project_root).replace("\\", "/")
            except ValueError:
                rel_path = fname
            stat = os.stat(fp)
            abs_path = os.path.abspath(fp)
            # Make sure we don't duplicate files found by os.walk in src_root
            if not any(f.abs_path == abs_path for f in results):
                results.append(SourceFile(
                    abs_path=abs_path,
                    rel_path=rel_path,
                    extension=ext,
                    is_spec=fname.endswith(".spec.ts"),
                    size_bytes=stat.st_size,
                    mtime=stat.st_mtime,
                ))

    results.sort(key=lambda f: f.rel_path)
    return results


# ═══════════════════════════════════════════════════════════════
# BUNDLING
# ═══════════════════════════════════════════════════════════════

def build_bundles_component(files: list[SourceFile]) -> list[SourceBundle]:
    """Group files by component/service/feature into bundles (default strategy)."""
    groups: dict[str, list[SourceFile]] = {}
    for f in files:
        key = component_stem(f.rel_path)
        groups.setdefault(key, []).append(f)

    bundles = []
    for key, group_files in sorted(groups.items()):
        parts   = key.split("/")
        display = " / ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        safe    = safe_name_from_stem(key)
        bundles.append(SourceBundle(
            name=safe,
            display_title=display,
            role=detect_role(key),
            files=sorted(group_files, key=lambda f: f.extension),
        ))
    return bundles


def build_bundles_flat(files: list[SourceFile]) -> list[SourceBundle]:
    """One bundle per source file (maximum granularity)."""
    bundles = []
    for f in files:
        stem = Path(f.rel_path).with_suffix("").as_posix()
        safe = safe_name_from_stem(stem)
        bundles.append(SourceBundle(
            name=safe,
            display_title=f.rel_path,
            role=detect_role(f.rel_path),
            files=[f],
        ))
    return bundles


def build_bundles_single(files: list[SourceFile]) -> list[SourceBundle]:
    """All files in ONE bundle — maximum context for small projects."""
    return [SourceBundle(
        name="angular-full-codebase",
        display_title="Complete Angular Codebase",
        role="Full Codebase",
        files=files,
    )]


def build_bundles(files: list[SourceFile], strategy: str) -> list[SourceBundle]:
    """Route to the correct bundling strategy."""
    if strategy == "flat":
        return build_bundles_flat(files)
    elif strategy == "single":
        return build_bundles_single(files)
    else:
        return build_bundles_component(files)


# ═══════════════════════════════════════════════════════════════
# MARKDOWN GENERATION
# ═══════════════════════════════════════════════════════════════

def build_markdown(bundle: SourceBundle, project_name: str) -> str:
    """Convert a SourceBundle into a rich Markdown document for NotebookLM."""
    lines: list[str] = []

    # ── Document header ───────────────────────────────────────
    lines += [
        f"# {bundle.display_title}", "",
        "## Metadata", "",
        "| Field | Value |", "|-------|-------|",
        f"| **Project** | `{project_name}` |",
        f"| **Role** | {bundle.role} |",
        f"| **Bundle** | `{bundle.name}` |",
        f"| **Files** | {len(bundle.files)} |",
        f"| **Total size** | {bundle.total_bytes:,} bytes |",
        f"| **Generated** | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |",
        f"| **Source** | Angular / TypeScript |",
        "",
        "## Files in this Bundle", "",
    ]
    for f in bundle.files:
        lines.append(f"- `{f.rel_path}` ({f.size_bytes:,} bytes, {detect_role(f.rel_path)})")
    lines.append("")

    # ── Per-file sections ─────────────────────────────────────
    for f in bundle.files:
        try:
            source = Path(f.abs_path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            source = f"[ERROR: Could not read file — {e}]"

        role      = detect_role(f.rel_path)
        mtime_str = datetime.fromtimestamp(f.mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        lines += [
            "---", "",
            f"## `{f.rel_path}`", "",
            "| Field | Value |", "|-------|-------|",
            f"| **Role** | {role} |",
            f"| **Extension** | `{f.extension}` |",
            f"| **Last modified** | {mtime_str} |",
            f"| **Size** | {f.size_bytes:,} bytes |",
        ]
        if f.extension == ".ts" and source:
            syms = extract_ts_symbols(source)
            if syms:
                lines.append(f"| **Exports** | `{'`, `'.join(syms)}` |")
        lines += ["", f"```{ext_to_language(f.extension)}", source.rstrip(), "```", ""]

    return "\n".join(lines)


def build_stem_map(
    project_root: str,
    include_specs: bool = False,
    allowed_exts: set[str] | None = None,
    explicit_files: set[str] | None = None,
) -> dict[str, list[SourceFile]]:
    """Build a stem→files mapping from all discovered source files.

    Used by the watcher to cache bundle membership at startup.
    Subsequent per-event lookups become O(1) dict access instead of O(n) os.walk.
    """
    files = discover_source_files(
        project_root, include_specs=include_specs, allowed_exts=allowed_exts, explicit_files=explicit_files)
    stem_map: dict[str, list[SourceFile]] = {}
    for f in files:
        stem = component_stem(f.rel_path)
        stem_map.setdefault(stem, []).append(f)
    return stem_map


def build_bundle_from_stem_map(
    changed_abs: str,
    project_root: str,
    stem_map: dict[str, list[SourceFile]],
) -> SourceBundle | None:
    """O(1) bundle lookup using a pre-built stem map (watcher cache path).

    Returns a SourceBundle for changed_abs without any os.walk.
    The stem_map must be refreshed when files are created or deleted.
    """
    src_root = os.path.join(project_root, "src")
    try:
        rel_changed = os.path.relpath(changed_abs, src_root).replace("\\", "/")
    except ValueError:
        return None
    stem  = component_stem(rel_changed)
    files = stem_map.get(stem)
    if not files:
        return None
    safe = safe_name_from_stem(stem)
    return SourceBundle(
        name=safe,
        display_title=stem.split("/")[-1],
        role=detect_role(stem),
        files=sorted(files, key=lambda f: f.extension),
    )


def build_bundle_for_file(
    changed_abs: str,
    project_root: str,
    allowed_exts: set[str] | None = None,
    explicit_files: set[str] | None = None,
) -> SourceBundle | None:
    """Discover the bundle for a single changed file via os.walk (slow path).

    Prefer build_bundle_from_stem_map when a cached stem_map is available.
    Returns None if no matching files are found.
    """
    src_root = os.path.join(project_root, "src")
    try:
        rel_changed = os.path.relpath(changed_abs, src_root).replace("\\", "/")
    except ValueError:
        return None

    bundle_stem = component_stem(rel_changed)
    # Use pre-compiled module-level regex (OPT-1)
    matched: list[SourceFile] = []

    for dp, dirs, fnames in os.walk(src_root):
        dirs[:] = [d for d in dirs if not _EXCLUDE_RE.search(
            os.path.join(dp, d).replace("\\", "/")
        )]
        for fname in fnames:
            ext = Path(fname).suffix.lower()
            _exts = allowed_exts if allowed_exts is not None else SOURCE_EXTENSIONS
            if ext not in _exts or fname.endswith(".spec.ts"):
                continue
            abs_p = os.path.join(dp, fname)
            rel_p = os.path.relpath(abs_p, src_root).replace("\\", "/")
            if _EXCLUDE_RE.search(rel_p):
                continue
            if component_stem(rel_p) == bundle_stem:
                st = os.stat(abs_p)
                matched.append(SourceFile(
                    abs_path=abs_p,
                    rel_path=rel_p,
                    extension=ext,
                    is_spec=False,
                    size_bytes=st.st_size,
                    mtime=st.st_mtime,
                ))

    # Also check if it's an explicit file bundle
    if not matched:
        # We don't have explicit_files passed down all the way here, but we can do a direct check
        # if the change_abs perfectly equals the file, or if the changed_abs maps to bundle_stem
        try:
            rel_changed_from_root = os.path.relpath(changed_abs, project_root).replace("\\", "/")
        except ValueError:
            rel_changed_from_root = changed_abs.replace("\\", "/")

        if os.path.isfile(changed_abs) and component_stem(rel_changed_from_root) == bundle_stem:
            st = os.stat(changed_abs)
            ext = Path(changed_abs).suffix.lower()
            matched.append(SourceFile(
                abs_path=changed_abs,
                rel_path=rel_changed_from_root,
                extension=ext,
                is_spec=False,
                size_bytes=st.st_size,
                mtime=st.st_mtime,
            ))

    if not matched:
        return None

    matched.sort(key=lambda f: f.extension)
    safe = safe_name_from_stem(bundle_stem)
    return SourceBundle(
        name=safe,
        display_title=bundle_stem.split("/")[-1],
        role=detect_role(bundle_stem),
        files=matched,
    )


# ═══════════════════════════════════════════════════════════════
# CDP AUTH (shared between runner + watcher)
# ═══════════════════════════════════════════════════════════════

def find_notebooklm_page(
    probe_ports: list[int] | None = None,
) -> tuple[int | None, dict | None]:
    """Probe CDP ports; return (port, page_dict) for the first NotebookLM page found."""
    try:
        from notebooklm_mcp.auth_cli import get_chrome_pages
    except ImportError:
        return None, None

    for port in (probe_ports or CDP_PROBE_PORTS):
        try:
            for page in get_chrome_pages(port):
                if "notebooklm.google.com" in page.get("url", ""):
                    return port, page
        except Exception:
            pass
    return None, None


def reload_cookies_from_disk(force: bool = False) -> bool:
    """Pick up cookies saved to auth.json externally (disk fallback)."""
    global _auth_file_mtime
    try:
        auth_path = str(Path.home() / ".notebooklm-mcp" / "auth.json")
        if not os.path.exists(auth_path):
            return False
        current_mtime = os.path.getmtime(auth_path)
        if not force and current_mtime == _auth_file_mtime:
            return False
        from notebooklm_mcp.server import reset_client
        reset_client()
        _auth_file_mtime = current_mtime
        return True
    except Exception:
        return False


def refresh_cookies(
    probe_ports: list[int] | None = None,
    auto_launch: bool = True,
) -> bool:
    """Re-extract cookies from Chrome via CDP and update the auth cache.

    Strategy:
      1. Probe CDP ports for a NotebookLM page
      2. Auto-launch Chrome if not found (when auto_launch=True)
      3. Extract cookies + CSRF token via CDP WebSocket
      4. Save to auth cache and reset MCP client
      5. Fallback to disk-based auth.json if CDP unavailable
    """
    global _chrome_launched

    try:
        from notebooklm_mcp.auth_cli import (
            get_chrome_pages, get_page_cookies, get_page_html,
            launch_chrome, CDP_DEFAULT_PORT, extract_session_id_from_html,
        )
        from notebooklm_mcp.auth import (
            AuthTokens, extract_csrf_from_page_source,
            save_tokens_to_cache, validate_cookies,
        )

        ports = probe_ports or CDP_PROBE_PORTS
        found_port, nb_page = find_notebooklm_page(ports)

        if nb_page is None and auto_launch:
            target_port = ports[0] if ports else CDP_DEFAULT_PORT
            try:
                launch_chrome(target_port, headless=False)
                _chrome_launched = True
                time.sleep(5)
                found_port, nb_page = find_notebooklm_page([target_port])
                if nb_page is None:
                    from notebooklm_mcp.auth_cli import find_or_create_notebooklm_page
                    nb_page = find_or_create_notebooklm_page(target_port)
                    if nb_page:
                        found_port = target_port
                        time.sleep(4)
            except Exception:
                pass

        if nb_page is None:
            return reload_cookies_from_disk(force=True)

        ws_url = nb_page.get("webSocketDebuggerUrl")
        if not ws_url:
            return reload_cookies_from_disk(force=True)

        cookies = {c["name"]: c["value"] for c in get_page_cookies(ws_url)}
        if not validate_cookies(cookies):
            return reload_cookies_from_disk(force=True)

        html       = get_page_html(ws_url)
        csrf_token = extract_csrf_from_page_source(html) or ""
        session_id = extract_session_id_from_html(html)

        save_tokens_to_cache(AuthTokens(
            cookies=cookies, csrf_token=csrf_token,
            session_id=session_id, extracted_at=time.time(),
        ), silent=True)

        from notebooklm_mcp import server
        server.reset_client()
        return True

    except Exception:
        return reload_cookies_from_disk(force=True)
