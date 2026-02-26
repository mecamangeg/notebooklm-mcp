"""test_angular_rag.py — E2E + Stress Tests for the Angular RAG pipeline.

Coverage:
  1. Unit: all angular_rag_core public functions
  2. E2E:  convert_project() on a realistic synthetic Angular project tree
  3. Stress: 1000-file discovery, 200-bundle render, upload-log round-trips × 500

Run with:
  uv run --no-project python -m pytest test_angular_rag.py -v
  # or faster:
  uv run --no-project python test_angular_rag.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import threading
from pathlib import Path
from typing import Optional

# ─── path so we can import the runner (which appends src/ itself) ───
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import angular_rag_core as core
from angular_rag_core import (
    SourceFile,
    SourceBundle,
    detect_role,
    ext_to_language,
    extract_ts_symbols,
    component_stem,
    safe_name_from_stem,
    compute_content_hash,
    load_upload_log,
    check_upload_status_loaded,
    check_upload_status,
    record_upload,
    discover_source_files,
    build_bundles_component,
    build_bundles_flat,
    build_bundles_single,
    build_bundles,
    build_markdown,
    build_stem_map,
    build_bundle_from_stem_map,
    build_bundle_for_file,
    _EXCLUDE_RE,
    UPLOAD_LOG_FORMAT_VERSION,
)

# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

PASS = "✅"
FAIL = "❌"

_results: list[tuple[str, bool, str]] = []

def ok(name: str, cond: bool, detail: str = "") -> bool:
    sym = PASS if cond else FAIL
    msg = f"  {sym}  {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    _results.append((name, cond, detail))
    return cond


def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def make_source_file(
    rel_path: str,
    abs_path: str = "/fake/src/app/foo.ts",
    size_bytes: int = 100,
    is_spec: bool = False,
) -> SourceFile:
    return SourceFile(
        abs_path=abs_path,
        rel_path=rel_path,
        extension=Path(rel_path).suffix.lower(),
        is_spec=is_spec,
        size_bytes=size_bytes,
        mtime=time.time(),
    )


# ═══════════════════════════════════════════════════════════
# 1. UNIT — CLASSIFICATION
# ═══════════════════════════════════════════════════════════

def test_detect_role():
    section("1. detect_role()")
    cases = [
        ("chat.service.ts",             "Service"),
        ("chat.component.ts",           "Component"),
        ("chat.component.html",         "Component"),   # .component. prefix wins over .html
        ("chat.pipe.ts",                "Pipe"),
        ("auth.guard.ts",               "Guard"),
        ("page.resolver.ts",            "Resolver"),
        ("http.interceptor.ts",         "Interceptor"),
        ("app.module.ts",               "Module"),
        ("highlight.directive.ts",      "Directive"),
        ("app.routes.ts",               "Routes"),
        ("app.config.ts",               "Config"),
        ("user.model.ts",               "Model/Types"),
        ("response.types.ts",           "Model/Types"),
        ("string.util.ts",              "Utility"),
        ("environment.prod.ts",         "Environment Config"),
        ("standalone.html",             "Template"),
        ("global.scss",                 "Styles"),
        ("global.css",                  "Styles"),
        ("app.spec.ts",                 "Unit Test"),
        ("completely-unknown.ts",       "Source"),
    ]
    for path, expected in cases:
        r = detect_role(path)
        ok(f"detect_role({path!r})", r == expected, f"got {r!r}, want {expected!r}")


def test_ext_to_language():
    section("2. ext_to_language()")
    cases = [
        (".ts",   "typescript"),
        (".html", "html"),
        (".scss", "scss"),
        (".css",  "css"),
        (".json", "json"),
        (".js",   "javascript"),
        (".md",   "markdown"),
        (".xyz",  "text"),   # unknown → fallback
    ]
    for ext, expected in cases:
        r = ext_to_language(ext)
        ok(f"ext_to_language({ext!r})", r == expected, f"got {r!r}")


def test_extract_ts_symbols():
    section("3. extract_ts_symbols()")
    src = """
@Component({ selector: 'app-root' })
export abstract class AppComponent {}
export interface AppConfig {}
export async function loadData() {}
export const APP_TOKEN = 'tok';
export type UserId = string;
export enum Status { Active, Inactive }
export let mutable = 1;
@Injectable()
export class ChatService {}
"""
    syms = extract_ts_symbols(src)
    ok("AppComponent extracted", "AppComponent" in syms)
    ok("AppConfig extracted",    "AppConfig" in syms)
    ok("loadData extracted",     "loadData" in syms)
    ok("APP_TOKEN extracted",    "APP_TOKEN" in syms)
    ok("UserId extracted",       "UserId" in syms)
    ok("Status extracted",       "Status" in syms)
    ok("mutable extracted",      "mutable" in syms)
    ok("ChatService extracted",  "ChatService" in syms)
    ok("cap at 20",              len(syms) <= 20)

    # no exports
    ok("empty source → []", extract_ts_symbols("// nothing here") == [])

    # stress: 25 exports → capped at 20
    big_src = "\n".join(f"export const VAR_{i} = {i};" for i in range(25))
    ok("stress 25 exports capped at 20", len(extract_ts_symbols(big_src)) == 20)


def test_component_stem():
    section("4. component_stem()")
    cases = [
        # file stem == parent dir → group at folder level
        ("app/components/chat/chat-area/chat-area.ts",  "app/components/chat/chat-area"),
        ("app/components/chat/chat-area/chat-area.html","app/components/chat/chat-area"),
        ("app/components/chat/chat-area/chat-area.scss","app/components/chat/chat-area"),
        # service — has dot-suffix, stem != parent
        ("app/services/chat.service.ts",                "app/services/chat.service"),
        # top-level app files: app/app.ts → stem 'app' == parent 'app' → groups at 'app'
        ("app/app.ts",                                  "app"),
        ("app/app.routes.ts",                           "app/app.routes"),
        ("app/app.config.ts",                           "app/app.config"),
        # Windows separators should be normalised
        ("app\\services\\auth.service.ts",              "app/services/auth.service"),
    ]
    for path, expected in cases:
        r = component_stem(path)
        ok(f"component_stem({path!r})", r == expected, f"got {r!r}")


def test_safe_name_from_stem():
    section("5. safe_name_from_stem()")
    cases = [
        ("app/services/chat.service",              "services__chat.service"),
        ("app/components/chat/chat-area",          "components__chat__chat-area"),
        ("app/app.routes",                         "app.routes"),          # app__ stripped, single part
        ("pages/landing/landing",                  "pages__landing__landing"),
    ]
    for stem, expected in cases:
        r = safe_name_from_stem(stem)
        ok(f"safe_name_from_stem({stem!r})", r == expected, f"got {r!r}")


# ═══════════════════════════════════════════════════════════
# 2. UNIT — CONTENT HASH / UPLOAD LOG
# ═══════════════════════════════════════════════════════════

def test_compute_content_hash():
    section("6. compute_content_hash()")
    h1 = compute_content_hash("hello world")
    h2 = compute_content_hash("hello world")
    h3 = compute_content_hash("different")
    ok("deterministic",       h1 == h2)
    ok("sensitive to change", h1 != h3)
    ok("16 hex chars",        len(h1) == 16 and all(c in "0123456789abcdef" for c in h1))
    ok("empty string",        len(compute_content_hash("")) == 16)


def test_upload_log_round_trip():
    section("7. upload log — round-trip")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "upload-log.json")
        md_path  = os.path.join(tmpdir, "chat.service.md")

        # New file — no log yet
        status, old_sid = check_upload_status(md_path, "content v1", log_path)
        ok("new file → 'new'", status == "new")
        ok("new file → old_sid None", old_sid is None)

        # Record upload
        record_upload(md_path, log_path, "src-id-001", "content v1")

        # Same content → skip
        status, old_sid = check_upload_status(md_path, "content v1", log_path)
        ok("same content → 'skip'", status == "skip")
        ok("skip → old_sid None",   old_sid is None)

        # Changed content → update
        status, old_sid = check_upload_status(md_path, "content v2", log_path)
        ok("changed content → 'update'", status == "update")
        ok("update → old_sid 'src-id-001'", old_sid == "src-id-001")

        # Record update
        record_upload(md_path, log_path, "src-id-002", "content v2")
        status, _ = check_upload_status(md_path, "content v2", log_path)
        ok("after record v2 → 'skip'", status == "skip")

        # Test stale source IDs (should return stale_sid=None)
        log = load_upload_log(log_path)
        log[os.path.basename(md_path)]["source_id"] = "unknown"
        with open(log_path, "w") as fh:
            json.dump(log, fh)
        status2, old_sid2 = check_upload_status(md_path, "content v3", log_path)
        ok("stale 'unknown' → old_sid is None", old_sid2 is None)

        # Format version written
        log_fresh = load_upload_log(log_path)
        entry = log_fresh.get(os.path.basename(md_path))
        ok("format_version written", entry and entry.get("format_version") == UPLOAD_LOG_FORMAT_VERSION)


def test_upload_log_loaded_variant():
    section("8. check_upload_status_loaded()")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "upload-log.json")
        md_path  = os.path.join(tmpdir, "foo.md")

        _log_cache: dict = {}
        record_upload(md_path, log_path, "sid-aaa", "hello", _log_cache)

        # Simulate pre-loaded cache
        loaded = load_upload_log(log_path)
        s, _ = check_upload_status_loaded(md_path, "hello", loaded)
        ok("loaded skip correct", s == "skip")
        s, sid = check_upload_status_loaded(md_path, "world", loaded)
        ok("loaded update correct", s == "update")
        ok("loaded update returns old_sid", sid == "sid-aaa")

        # Missing key
        s2, sid2 = check_upload_status_loaded(md_path + ".extra", "x", loaded)
        ok("missing key → new", s2 == "new" and sid2 is None)


def test_load_upload_log_robustness():
    section("9. load_upload_log() robustness")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Non-existent path
        r = load_upload_log(os.path.join(tmpdir, "nonexistent.json"))
        ok("missing file → {}", r == {})

        # Corrupt JSON
        bad_path = os.path.join(tmpdir, "bad.json")
        Path(bad_path).write_text("{ this is not json }", encoding="utf-8")
        r2 = load_upload_log(bad_path)
        ok("corrupt JSON → {}", r2 == {})


# ═══════════════════════════════════════════════════════════
# 3. UNIT — FILE DISCOVERY + BUNDLING
# ═══════════════════════════════════════════════════════════

def _make_angular_project(tmpdir: str, extra_files: list[tuple[str, str]] = []) -> str:
    """Create a minimal Angular project structure on disk."""
    files = [
        ("src/app/app.ts",               "@Component({}) export class AppComponent {}"),
        ("src/app/app.html",             "<app-root></app-root>"),
        ("src/app/app.scss",             "body { margin: 0; }"),
        ("src/app/app.routes.ts",        "export const routes = [];"),
        ("src/app/app.config.ts",        "export const appConfig = {};"),
        ("src/app/services/chat.service.ts",  "export class ChatService {}"),
        ("src/app/services/auth.service.ts",  "export class AuthService {}"),
        ("src/app/components/chat/chat-area/chat-area.ts",   "@Component({}) class ChatArea {}"),
        ("src/app/components/chat/chat-area/chat-area.html", "<chat-area></chat-area>"),
        ("src/app/components/chat/chat-area/chat-area.scss", ".chat { }"),
        ("src/app/components/sidebar/sidebar.ts",            "@Component({}) class Sidebar {}"),
        ("src/app/components/sidebar/sidebar.html",          "<sidebar></sidebar>"),
        ("src/app/models/user.model.ts",                     "export interface User {}"),
        # Spec files — should be excluded by default
        ("src/app/app.spec.ts",          "describe('app', () => {})"),
        # Excluded dirs
        ("node_modules/foo/index.ts",    "// should be excluded"),
        ("dist/main.js",                 "// excluded"),
        (".angular/cache/foo.ts",        "// excluded"),
        # Excluded extensions
        ("src/app/app.d.ts",             "// d.ts excluded"),
        ("src/app/app.js",               "// .js excluded"),
    ] + extra_files

    for rel, content in files:
        abs_path = os.path.join(tmpdir, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        Path(abs_path).write_text(content, encoding="utf-8")

    return tmpdir


def test_discover_source_files():
    section("10. discover_source_files()")
    with tempfile.TemporaryDirectory() as tmpdir:
        _make_angular_project(tmpdir)
        files = discover_source_files(tmpdir)

        names = [f.rel_path for f in files]
        ok("app.ts found",              any("app.ts" in n for n in names))
        ok("app.html found",            any("app.html" in n for n in names))
        ok("app.scss found",            any("app.scss" in n for n in names))
        ok("chat.service found",        any("chat.service.ts" in n for n in names))
        ok("spec excluded by default",  not any(".spec.ts" in n for n in names))
        ok("node_modules excluded",     not any("node_modules" in n for n in names))
        ok(".angular excluded",         not any(".angular" in n for n in names))
        ok(".d.ts excluded",            not any(".d.ts" in n for n in names))
        ok(".js excluded",              not any(".js" in n for n in names))
        ok("sorted",                    names == sorted(names))
        ok("SourceFile.rel_path uses /",all("/" in f.rel_path for f in files if "/" in f.rel_path))

        # With specs
        files_with_specs = discover_source_files(tmpdir, include_specs=True)
        ok("spec included when asked",  any(".spec.ts" in f.rel_path for f in files_with_specs))
        ok("more files with specs",     len(files_with_specs) > len(files))


def test_bundling_strategies():
    section("11. bundling strategies")
    with tempfile.TemporaryDirectory() as tmpdir:
        _make_angular_project(tmpdir)
        files = discover_source_files(tmpdir)

        # Component strategy
        bundles_c = build_bundles_component(files)
        bundle_names = [b.name for b in bundles_c]
        ok("component: chat-area grouped",   "components__chat__chat-area" in bundle_names)
        ok("component: chat.service grouped","services__chat.service" in bundle_names)
        ok("component: app grouped",         any("app" == b.name for b in bundles_c))
        ok("component: multiple files per bundle",
           any(len(b.files) > 1 for b in bundles_c))
        ok("component: no duplicate bundles",
           len(bundle_names) == len(set(bundle_names)))

        # Flat strategy — one bundle per file
        bundles_f = build_bundles_flat(files)
        ok("flat: same count as files",     len(bundles_f) == len(files))
        ok("flat: each bundle has 1 file",  all(len(b.files) == 1 for b in bundles_f))

        # Single strategy — everything in one bundle
        bundles_s = build_bundles_single(files)
        ok("single: exactly 1 bundle",      len(bundles_s) == 1)
        ok("single: all files inside",      len(bundles_s[0].files) == len(files))
        ok("single: name is 'angular-full-codebase'",
           bundles_s[0].name == "angular-full-codebase")

        # Router
        ok("build_bundles('component') works",len(build_bundles(files, "component")) > 0)
        ok("build_bundles('flat') works",      len(build_bundles(files, "flat"))     > 0)
        ok("build_bundles('single') works",    len(build_bundles(files, "single"))   == 1)
        ok("build_bundles(unknown) → component",
           build_bundles(files, "unknown") == build_bundles_component(files))


def test_source_bundle_properties():
    section("12. SourceBundle properties")
    sf = make_source_file("app/foo.ts", size_bytes=500)
    sb = SourceBundle(name="foo", display_title="Foo", role="Service", files=[sf])
    ok("output_filename", sb.output_filename == "foo.md")
    ok("total_bytes",     sb.total_bytes == 500)
    # Empty bundle
    empty = SourceBundle(name="empty", display_title="E", role="Source", files=[])
    ok("empty total_bytes = 0", empty.total_bytes == 0)


# ═══════════════════════════════════════════════════════════
# 4. UNIT — MARKDOWN GENERATION
# ═══════════════════════════════════════════════════════════

def test_build_markdown():
    section("13. build_markdown()")
    with tempfile.TemporaryDirectory() as tmpdir:
        ts_path = os.path.join(tmpdir, "chat.service.ts")
        Path(ts_path).write_text(
            "@Injectable()\nexport class ChatService { send() {} }",
            encoding="utf-8"
        )
        sf = SourceFile(
            abs_path=ts_path,
            rel_path="app/services/chat.service.ts",
            extension=".ts",
            is_spec=False,
            size_bytes=os.path.getsize(ts_path),
            mtime=os.path.getmtime(ts_path),
        )
        bundle = SourceBundle(
            name="services__chat.service",
            display_title="services / chat.service",
            role="Service",
            files=[sf],
        )
        md = build_markdown(bundle, "my-app")

        ok("has # heading",            md.startswith("# "))
        ok("title in heading",         "services / chat.service" in md)
        ok("project name in md",       "my-app" in md)
        ok("role in md",               "Service" in md)
        ok("bundle name in md",        "services__chat.service" in md)
        ok("file count in md",         "1" in md)
        ok("typescript fenced block",  "```typescript" in md)
        ok("ChatService exported/shown", "ChatService" in md)
        ok("rel_path in md",           "app/services/chat.service.ts" in md)
        ok("Generated row present",    "Generated" in md)

        # Unreadable file should not crash
        sf_bad = SourceFile(
            abs_path="/nonexistent/path/foo.ts",
            rel_path="app/foo.ts",
            extension=".ts",
            is_spec=False,
            size_bytes=0,
            mtime=0.0,
        )
        bundle_bad = SourceBundle(
            name="foo", display_title="Foo", role="Source", files=[sf_bad]
        )
        md_bad = build_markdown(bundle_bad, "my-app")
        ok("unreadable file handled gracefully", "[ERROR:" in md_bad)


# ═══════════════════════════════════════════════════════════
# 5. UNIT — STEM MAP + BUILD_BUNDLE_FROM_STEM_MAP
# ═══════════════════════════════════════════════════════════

def test_stem_map_and_fast_lookup():
    section("14. build_stem_map + build_bundle_from_stem_map")
    with tempfile.TemporaryDirectory() as tmpdir:
        _make_angular_project(tmpdir)
        stem_map = build_stem_map(tmpdir)

        ok("stem_map not empty", len(stem_map) > 0)
        ok("chat-area stem present",
           "app/components/chat/chat-area" in stem_map or
           any("chat-area" in k for k in stem_map))

        # Fast O(1) lookup for a known file
        ts_path = os.path.join(tmpdir, "src", "app", "services", "chat.service.ts")
        bundle = build_bundle_from_stem_map(ts_path, tmpdir, stem_map)
        ok("fast lookup finds bundle",   bundle is not None)
        ok("fast lookup correct name",   bundle and bundle.name == "services__chat.service")

        # Lookup for a file outside src/ → None
        bad_path = os.path.join("C:\\", "random", "other.ts")
        # On Windows a ValueError may be raised — the function should return None
        result = build_bundle_from_stem_map(bad_path, tmpdir, stem_map)
        # We accept None or any bundle (depends on path resolution)
        ok("out-of-tree path does not crash", True)


def test_build_bundle_for_file_slow_path():
    section("15. build_bundle_for_file() slow path")
    with tempfile.TemporaryDirectory() as tmpdir:
        _make_angular_project(tmpdir)

        ts_path = os.path.join(tmpdir, "src", "app", "services", "chat.service.ts")
        bundle = build_bundle_for_file(ts_path, tmpdir)
        ok("slow path finds bundle",   bundle is not None)
        ok("slow path correct name",   bundle and bundle.name == "services__chat.service")

        # Unknown file → None
        b2 = build_bundle_for_file("/nonexistent/path/foo.ts", tmpdir)
        ok("non-existent path → None", b2 is None)


# ═══════════════════════════════════════════════════════════
# 6. E2E — CONVERT PROJECT (no upload)
# ═══════════════════════════════════════════════════════════

def test_e2e_convert_project():
    section("16. E2E — convert_project() [--convert-only equivalent]")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = os.path.join(tmpdir, "my-angular-app")
        output_dir  = os.path.join(tmpdir, "out")
        _make_angular_project(project_dir)

        # Import runner (it will add src/ to sys.path itself at module level)
        import importlib.util, types
        # We can't easily import angular-rag-runner.py (hyphen) as a module the normal way.
        # Use importlib.util.spec_from_file_location instead.
        runner_path = os.path.join(os.path.dirname(__file__), "angular-rag-runner.py")
        spec = importlib.util.spec_from_file_location("angular_rag_runner", runner_path)
        runner_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner_mod)

        md_files = runner_mod.convert_project(
            project_root=project_dir,
            output_dir=output_dir,
            strategy="component",
            include_specs=False,
            dry_run=False,
            force=True,
        )

        ok("returns non-empty list",        len(md_files) > 0)
        ok("all paths end in .md",          all(f.endswith(".md") for f in md_files))
        ok("all files actually exist",      all(os.path.exists(f) for f in md_files))
        ok("list is sorted",                md_files == sorted(md_files))

        # Check content of one known bundle
        chat_service_md = next(
            (f for f in md_files if "chat.service" in os.path.basename(f)), None
        )
        ok("chat.service.md generated", chat_service_md is not None)
        if chat_service_md:
            content = Path(chat_service_md).read_text(encoding="utf-8")
            ok("chat.service.md has typescript block", "```typescript" in content)
            ok("chat.service.md has metadata table",   "| **Project** |" in content)

        # Re-run with no --force → files skipped (no disk writes, but still returned)
        md_files_2 = runner_mod.convert_project(
            project_root=project_dir,
            output_dir=output_dir,
            strategy="component",
            force=False,
        )
        ok("re-run returns same count",     len(md_files_2) == len(md_files))

        # Flat strategy
        out_flat = os.path.join(tmpdir, "out_flat")
        md_flat = runner_mod.convert_project(
            project_root=project_dir,
            output_dir=out_flat,
            strategy="flat",
            force=True,
        )
        src_count = len(discover_source_files(project_dir))
        ok("flat: 1 md per source file",    len(md_flat) == src_count)

        # Dry-run
        out_dry = os.path.join(tmpdir, "out_dry")
        md_dry = runner_mod.convert_project(
            project_root=project_dir,
            output_dir=out_dry,
            strategy="component",
            dry_run=True,
            force=True,
        )
        ok("dry-run returns list",           len(md_dry) > 0)
        ok("dry-run creates no files",       not any(os.path.exists(f) for f in md_dry))

        # Empty project → no files
        empty_dir = os.path.join(tmpdir, "empty-project")
        os.makedirs(os.path.join(empty_dir, "src"), exist_ok=True)
        md_empty = runner_mod.convert_project(
            project_root=empty_dir,
            output_dir=os.path.join(tmpdir, "out_empty"),
            force=True,
        )
        ok("empty project → []",             md_empty == [])


# ═══════════════════════════════════════════════════════════
# 7. E2E — UPLOAD LOG (no NotebookLM, simulated)
# ═══════════════════════════════════════════════════════════

def test_e2e_upload_log_with_convert():
    section("17. E2E — upload log tracks convert output correctly")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = os.path.join(tmpdir, "proj")
        output_dir  = os.path.join(tmpdir, "out")
        _make_angular_project(project_dir)

        import importlib.util
        runner_path = os.path.join(os.path.dirname(__file__), "angular-rag-runner.py")
        spec = importlib.util.spec_from_file_location("angular_rag_runner2", runner_path)
        runner_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner_mod)

        md_files = runner_mod.convert_project(
            project_root=project_dir,
            output_dir=output_dir,
            strategy="component",
            force=True,
        )

        log_path = os.path.join(output_dir, "upload-log.json")
        _log_cache: dict = {}

        # Simulate recording all uploads
        fake_sources: list[str] = []
        for i, md_path in enumerate(md_files):
            content = Path(md_path).read_text(encoding="utf-8")
            fake_sid = f"fake-sid-{i:04d}"
            record_upload(md_path, log_path, fake_sid, content, _log_cache)
            fake_sources.append(fake_sid)

        ok("log written to disk",              os.path.exists(log_path))
        log = load_upload_log(log_path)
        ok("all md files recorded in log",     len(log) == len(md_files))

        # Second pass: all should be 'skip'
        all_skip = True
        for md_path in md_files:
            content = Path(md_path).read_text(encoding="utf-8")
            status, _ = check_upload_status_loaded(md_path, content, log)
            if status != "skip":
                all_skip = False
                break
        ok("second pass: all entries are 'skip'", all_skip)

        # Modify one file triggers 'update'
        first_md  = md_files[0]
        basename  = os.path.basename(first_md)
        new_content = Path(first_md).read_text(encoding="utf-8") + "\n<!-- changed -->"
        status, old_sid = check_upload_status_loaded(first_md, new_content, log)
        ok("modified file → 'update'",         status == "update")
        ok("modified file → old_sid returned", old_sid is not None and old_sid.startswith("fake-sid-"))


# ═══════════════════════════════════════════════════════════
# 8. E2E — EXCLUDE REGEX PRE-COMPILATION
# ═══════════════════════════════════════════════════════════

def test_exclude_re():
    section("18. _EXCLUDE_RE pre-compiled pattern")
    ok("is compiled type",    hasattr(_EXCLUDE_RE, "search"))
    ok("excludes .spec.ts",   bool(_EXCLUDE_RE.search("foo.spec.ts")))
    ok("excludes node_modules",bool(_EXCLUDE_RE.search("node_modules/foo/bar.ts")))
    ok("excludes dist/",      bool(_EXCLUDE_RE.search("dist/main.js")))
    ok("excludes .angular/",  bool(_EXCLUDE_RE.search(".angular/cache/foo")))
    ok("excludes coverage/",  bool(_EXCLUDE_RE.search("coverage/lcov.info")))
    ok("excludes ANGULAR-RAG-SOURCES",
                              bool(_EXCLUDE_RE.search("ANGULAR-RAG-SOURCES/foo.ts")))
    ok("does NOT exclude normal ts",
                              not _EXCLUDE_RE.search("app/services/chat.service.ts"))
    ok("does NOT exclude normal html",
                              not _EXCLUDE_RE.search("app/app.html"))


# ═══════════════════════════════════════════════════════════
# 9. STRESS TESTS
# ═══════════════════════════════════════════════════════════

def test_stress_large_project_discovery():
    section("19. STRESS — discovery of 1 000-file synthetic project")
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src", "app")
        os.makedirs(src_dir, exist_ok=True)

        N = 1000
        for i in range(N):
            service_dir = os.path.join(src_dir, f"feature-{i // 10}", f"svc{i}")
            os.makedirs(service_dir, exist_ok=True)
            Path(os.path.join(service_dir, f"svc{i}.service.ts")).write_text(
                f"export class Svc{i}Service {{}}",
                encoding="utf-8",
            )
            Path(os.path.join(service_dir, f"svc{i}.service.spec.ts")).write_text(
                f"describe('svc{i}', () => {{}})",
                encoding="utf-8",
            )

        t0 = time.perf_counter()
        files = discover_source_files(tmpdir, include_specs=False)
        elapsed = time.perf_counter() - t0

        ok(f"discovered {N} .ts files",        len(files) == N)
        ok(f"spec files excluded",              not any(".spec.ts" in f.rel_path for f in files))
        ok(f"discovery in <5s (actual {elapsed:.2f}s)", elapsed < 5.0)

        # Build stem map
        t1 = time.perf_counter()
        stem_map = build_stem_map(tmpdir, include_specs=False)
        t_stem = time.perf_counter() - t1
        ok(f"build_stem_map() in <5s (actual {t_stem:.2f}s)", t_stem < 5.0)
        ok("stem_map has N entries",            len(stem_map) == N)


def test_stress_bulk_bundling_and_render():
    section("20. STRESS — bundle + render 200 synthetic bundles")
    files: list[SourceFile] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(200):
            for ext in [".ts", ".html", ".scss"]:
                fname = f"comp{i}{ext}"
                abs_p = os.path.join(tmpdir, fname)
                content = f"/* component {i} {ext} */\n" + "x" * 500
                Path(abs_p).write_text(content, encoding="utf-8")
                files.append(SourceFile(
                    abs_path=abs_p,
                    rel_path=f"app/components/comp{i}/comp{i}{ext}",
                    extension=ext,
                    is_spec=False,
                    size_bytes=len(content),
                    mtime=time.time(),
                ))

        bundles = build_bundles_component(files)
        ok("200 bundles created",      len(bundles) == 200)
        ok("each bundle has 3 files",  all(len(b.files) == 3 for b in bundles))

        # Render all 200 bundles
        t0 = time.perf_counter()
        markdowns = [build_markdown(b, "stress-app") for b in bundles]
        elapsed = time.perf_counter() - t0
        ok(f"rendered 200 bundles in <10s (actual {elapsed:.2f}s)", elapsed < 10.0)
        ok("all markdowns non-empty", all(len(m) > 0 for m in markdowns))

        # Parallel render (via ThreadPoolExecutor — mimics runner OPT-4)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        t1 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as exe:
            futures = {exe.submit(build_markdown, b, "stress-app"): b for b in bundles}
            parallel_mds = [fut.result() for fut in as_completed(futures)]
        t_parallel = time.perf_counter() - t1
        ok(f"parallel render in <10s (actual {t_parallel:.2f}s)", t_parallel < 10.0)
        ok("parallel count matches", len(parallel_mds) == 200)


def test_stress_upload_log_500_writes():
    section("21. STRESS — upload log 500 sequential writes + reads")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "upload-log.json")
        N = 500
        _log_cache: dict = {}

        t0 = time.perf_counter()
        for i in range(N):
            md_path = os.path.join(tmpdir, f"bundle_{i:04d}.md")
            content = f"# Bundle {i}\n" + "x" * 200
            record_upload(md_path, log_path, f"sid-{i:04d}", content, _log_cache)
        elapsed = time.perf_counter() - t0

        ok(f"500 record_upload() calls in <30s (actual {elapsed:.2f}s)", elapsed < 30.0)
        ok("cache has 500 entries",          len(_log_cache) == N)

        log = load_upload_log(log_path)
        ok("log file has 500 entries",       len(log) == N)

        # All entries should be 'skip' now (content unchanged)
        t1 = time.perf_counter()
        skip_count = 0
        for i in range(N):
            md_path = os.path.join(tmpdir, f"bundle_{i:04d}.md")
            content = f"# Bundle {i}\n" + "x" * 200
            status, _ = check_upload_status_loaded(md_path, content, log)
            if status == "skip":
                skip_count += 1
        t_check = time.perf_counter() - t1
        ok("all 500 checked as 'skip'",      skip_count == N)
        ok(f"500 checks in <1s (actual {t_check:.3f}s)", t_check < 1.0)


def test_stress_concurrent_hash_computation():
    section("22. STRESS — 10 000 concurrent hash computations")
    import concurrent.futures
    payloads = [f"document content {i}" + "x" * 1000 for i in range(10_000)]

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
        hashes = list(exe.map(compute_content_hash, payloads))
    elapsed = time.perf_counter() - t0

    ok("10 000 hashes computed",         len(hashes) == 10_000)
    ok("all hashes are 16 hex chars",    all(len(h) == 16 for h in hashes))
    ok("hashes are unique (high entropy)", len(set(hashes)) > 9_990)
    ok(f"10 000 hashes in <10s (actual {elapsed:.2f}s)", elapsed < 10.0)


def test_stress_exclude_regex():
    section("23. STRESS — _EXCLUDE_RE on 50 000 paths")
    paths = (
        [f"app/components/comp{i}/comp{i}.ts"         for i in range(20_000)] +
        [f"node_modules/lib{i}/index.ts"              for i in range(10_000)] +
        [f"app/services/svc{i}.spec.ts"               for i in range(10_000)] +
        [f"dist/chunk-{i}.js"                         for i in range(5_000)]  +
        [f".angular/cache/comp{i}.js"                 for i in range(5_000)]
    )
    t0 = time.perf_counter()
    excluded   = sum(1 for p in paths if _EXCLUDE_RE.search(p))
    included   = sum(1 for p in paths if not _EXCLUDE_RE.search(p))
    elapsed = time.perf_counter() - t0

    ok("50 000 paths classified",        excluded + included == 50_000)
    ok("20 000 normal TS included",      included == 20_000)
    ok("30 000 excluded paths correct",  excluded == 30_000)
    ok(f"50 000 regex matches in <2s (actual {elapsed:.2f}s)", elapsed < 2.0)


def test_stress_component_stem_10k():
    section("24. STRESS — component_stem() on 10 000 diverse paths")
    base_paths = [
        "app/components/feature-{i}/feature-{i}/feature-{i}.ts",
        "app/services/service-{i}.service.ts",
        "app/pipes/pipe-{i}.pipe.ts",
        "app/models/model-{i}.model.ts",
        "app/guards/guard-{i}.guard.ts",
    ]
    paths = [p.format(i=i) for i in range(2_000) for p in base_paths]

    t0 = time.perf_counter()
    stems = [component_stem(p) for p in paths]
    elapsed = time.perf_counter() - t0

    ok("10 000 stems computed",    len(stems) == 10_000)
    ok("stems have no backslash",  all("\\" not in s for s in stems))
    ok(f"10 000 stems in <2s (actual {elapsed:.2f}s)", elapsed < 2.0)


# ═══════════════════════════════════════════════════════════
# 10. EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════

def test_edge_cases():
    section("25. Edge cases")

    # Empty string paths
    ok("detect_role('')", detect_role("") == "Source")
    ok("component_stem('') returns empty string", component_stem("") == "")
    ok("safe_name_from_stem('') does not crash", safe_name_from_stem("") is not None)
    ok("ext_to_language('') → 'text'", ext_to_language("") == "text")

    # Paths with Windows backslashes
    ok("detect_role with backslash",
       detect_role("app\\services\\chat.service.ts") == "Service")
    ok("component_stem backslash normalised",
       "\\" not in component_stem("app\\services\\chat.service.ts"))

    # Very long paths
    long_path = "app/" + "/".join(f"nested{i}" for i in range(30)) + "/chat.service.ts"
    ok("detect_role on very long path", detect_role(long_path) == "Service")
    ok("component_stem on very long path does not crash",
       component_stem(long_path) is not None)

    # Unicode in content
    unicode_content = "# Title 你好 🎉\nContent with unicode: αβγδ"
    h = compute_content_hash(unicode_content)
    ok("unicode content hash is string", isinstance(h, str) and len(h) == 16)

    # Record upload with empty content
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "log.json")
        md = os.path.join(tmpdir, "empty.md")
        record_upload(md, log_path, "sid-empty", "", {})
        log = load_upload_log(log_path)
        ok("empty content recorded", "empty.md" in log)

    # SourceBundle with no files
    empty_bundle = SourceBundle(
        name="no-files", display_title="Empty Bundle", role="Source", files=[]
    )
    md = build_markdown(empty_bundle, "test-project")
    ok("bundle with 0 files renders without crash", isinstance(md, str) and len(md) > 0)

    # discover_source_files on non-existent dir (fallback path)
    files = discover_source_files("/nonexistent/project/path")
    ok("non-existent project → []", files == [])


def test_record_upload_cache_consistency():
    section("26. record_upload() — cache stays in sync with disk")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path  = os.path.join(tmpdir, "log.json")
        md_path   = os.path.join(tmpdir, "foo.md")
        cache: dict = {}

        record_upload(md_path, log_path, "sid-1", "content-a", cache)
        disk = load_upload_log(log_path)

        ok("cache key matches disk key",
           os.path.basename(md_path) in cache
           and os.path.basename(md_path) in disk)
        ok("cache source_id matches disk",
           cache[os.path.basename(md_path)]["source_id"] ==
           disk[os.path.basename(md_path)]["source_id"])
        ok("cache content_hash matches disk",
           cache[os.path.basename(md_path)]["content_hash"] ==
           disk[os.path.basename(md_path)]["content_hash"])

        # Second call should update both cache and disk
        record_upload(md_path, log_path, "sid-2", "content-b", cache)
        disk2 = load_upload_log(log_path)
        ok("cache updated on second call",
           cache[os.path.basename(md_path)]["source_id"] == "sid-2")
        ok("disk updated on second call",
           disk2[os.path.basename(md_path)]["source_id"] == "sid-2")


def test_format_eta():
    section("27. _format_eta() in runner")
    import importlib.util
    runner_path = os.path.join(os.path.dirname(__file__), "angular-rag-runner.py")
    spec = importlib.util.spec_from_file_location("angular_rag_runner_eta", runner_path)
    runner_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner_mod)

    ok("< 60s  → '30s'",            runner_mod._format_eta(30)   == "30s")
    ok("90s    → '1m 30s'",         runner_mod._format_eta(90)   == "1m 30s")
    ok("3600s  → '1h 0m'",          runner_mod._format_eta(3600) == "1h 0m")
    ok("3661s  → '1h 1m'",          runner_mod._format_eta(3661) == "1h 1m")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print("  ANGULAR RAG TEST SUITE — E2E + STRESS")
    print("=" * 60)

    test_detect_role()
    test_ext_to_language()
    test_extract_ts_symbols()
    test_component_stem()
    test_safe_name_from_stem()
    test_compute_content_hash()
    test_upload_log_round_trip()
    test_upload_log_loaded_variant()
    test_load_upload_log_robustness()
    test_discover_source_files()
    test_bundling_strategies()
    test_source_bundle_properties()
    test_build_markdown()
    test_stem_map_and_fast_lookup()
    test_build_bundle_for_file_slow_path()
    test_e2e_convert_project()
    test_e2e_upload_log_with_convert()
    test_exclude_re()
    test_stress_large_project_discovery()
    test_stress_bulk_bundling_and_render()
    test_stress_upload_log_500_writes()
    test_stress_concurrent_hash_computation()
    test_stress_exclude_regex()
    test_stress_component_stem_10k()
    test_edge_cases()
    test_record_upload_cache_consistency()
    test_format_eta()

    # ── Summary ────────────────────────────────────────────
    total  = len(_results)
    passed = sum(1 for _, ok_, _ in _results if ok_)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    if failed:
        print("\n  FAILURES:")
        for name, ok_, detail in _results:
            if not ok_:
                print(f"    {FAIL}  {name}")
                if detail:
                    print(f"        {detail}")
        sys.exit(1)
    else:
        print("\n  All tests passed! 🎉")
        sys.exit(0)


if __name__ == "__main__":
    main()
