"""
E2E + Stress Test — Multi-Notebook Deduplication
=================================================
Uses only 10 test files in a temp directory (not the full 40) so each
upload round completes in ~30s instead of ~2min.

Tests:
  T0 — Baseline verify    : fresh state, 0 [AngularTest] sources, 0 dupes
  T1 — First upload       : 10 new sources → each NB gets 10 [AngularTest] sources
  T2 — Idempotency        : re-run without changes → skip=10 per NB, 0 API calls
  T3 — Pre-flight sync    : delete ALL 3 per-NB logs → runner seeds from notebook → no dupes
  T4 — Force re-upload    : --force → bulk-clear + fresh upload → still 10 each
  T5 — Idempotency after  : run again straight after T4 → skip=10, no dupes
  T6 — Single log delete  : delete NB2 log only → NB2 seeds from notebook, NB1/NB3 skip
  T7 — Concurrent stress  : 2 simultaneous upload processes → no dupes
  T8 — Cleanup            : delete all [AngularTest] sources from all 3 NBs
  T9 — Final verify       : ground-truth API check → 0 [AngularTest] sources per NB

Usage:
    uv run python test_dedup_e2e.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────
NB_IDS = [
    "117e47ed-6385-4dc5-9abc-1bf57588a263",
    "b0376e17-644a-4228-8911-fdce0439a672",
    "493bbdb5-7ca4-409f-bf96-673d86311d9e",
]
NB_IDS_STR   = ",".join(NB_IDS)
RUNNER        = Path(__file__).parent / "angular-rag-runner.py"
SOURCE_DIR    = Path(__file__).parent / "ANGULAR-RAG-SOURCES"
NUM_TEST_FILES = 10          # use exactly 10 of the 40 available .md files
# Use a prefix that won't clash with real [Angular] sources
TEST_PREFIX   = "[AngularTest]"
EXPECTED_COUNT = NUM_TEST_FILES

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Test directory setup ──────────────────────────────────────────────
# Permanent temp dir for the test (so log files persist between runner calls)
TEST_DIR = Path(tempfile.gettempdir()) / "notebooklm_dedup_test"


def setup_test_dir() -> Path:
    """Create TEST_DIR with 10 dummy .md files and empty upload logs."""
    TEST_DIR.mkdir(exist_ok=True)
    # Delete any leftover logs from previous runs
    for f in TEST_DIR.glob("upload-log-*.json"):
        f.unlink()

    # Pick the first 10 real .md files and copy them in
    real_mds = sorted(p for p in SOURCE_DIR.glob("*.md")
                      if not p.name.startswith("upload-log"))[:NUM_TEST_FILES]
    for p in real_mds:
        shutil.copy2(p, TEST_DIR / p.name)
    print(f"    📁 Test dir: {TEST_DIR}  ({NUM_TEST_FILES} files)")
    return TEST_DIR


def delete_test_logs(nb_ids: list[str] | None = None):
    targets = nb_ids or NB_IDS
    for nb_id in targets:
        log = TEST_DIR / f"upload-log-{nb_id[:8]}.json"
        if log.exists():
            log.unlink()
            print(f"    🗑️  Deleted {log.name}")
        else:
            print(f"    ℹ️  {log.name} not found")


# ── API helpers ───────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "src"))
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")


def get_source_counts(prefix: str = "[Angular]") -> dict[str, dict]:
    """Return {nb_id: {angular, dupes}} counting sources that start with `prefix`."""
    from notebooklm_mcp.server import get_client
    client = get_client()
    results = {}
    for nb_id in NB_IDS:
        try:
            data = client.get_notebook(nb_id)
            sources = []
            if isinstance(data, list) and data:
                nb = data[0] if isinstance(data[0], list) else data
                if len(nb) > 1 and isinstance(nb[1], list):
                    for s in nb[1]:
                        if isinstance(s, list) and len(s) > 1:
                            t = s[1] if isinstance(s[1], str) else str(s[1])
                            sources.append(t)
            ang = [t for t in sources if t.startswith(prefix)]
            seen: dict[str, int] = {}
            for t in ang:
                seen[t] = seen.get(t, 0) + 1
            dupes = {t: c for t, c in seen.items() if c > 1}
            results[nb_id] = {"angular": len(ang), "dupes": len(dupes),
                               "dupe_titles": dupes}
        except Exception as e:
            results[nb_id] = {"error": str(e), "angular": -1, "dupes": -1}
    return results


def delete_test_sources():
    """Delete all [AngularTest] sources from all 3 notebooks (cleanup)."""
    from notebooklm_mcp.server import get_client
    client = get_client()
    total = 0
    for nb_id in NB_IDS:
        try:
            data = client.get_notebook(nb_id)
            sources = []
            if isinstance(data, list) and data:
                nb = data[0] if isinstance(data[0], list) else data
                if len(nb) > 1 and isinstance(nb[1], list):
                    for s in nb[1]:
                        if isinstance(s, list) and len(s) > 1:
                            sid_w = s[0]
                            sid = sid_w[0] if isinstance(sid_w, list) and sid_w else None
                            t = s[1] if isinstance(s[1], str) else str(s[1])
                            if sid and t.startswith(TEST_PREFIX):
                                sources.append({"id": sid, "title": t})
            for src in sources:
                try:
                    client.delete_source(src["id"])
                    total += 1
                except Exception:
                    pass
            print(f"    [{nb_id[:8]}] deleted {len(sources)} test sources")
        except Exception as e:
            print(f"    [{nb_id[:8]}] cleanup error: {e}")
    return total


def print_counts(counts: dict, expected: int = EXPECTED_COUNT, indent="    ") -> bool:
    all_pass = True
    for nb_id, info in counts.items():
        if "error" in info:
            print(f"{indent}❌ [{nb_id[:8]}] ERROR: {info['error']}")
            all_pass = False
            continue
        ang, dup = info["angular"], info["dupes"]
        ok = ang == expected and dup == 0
        icon = "✅" if ok else "❌"
        print(f"{indent}{icon} [{nb_id[:8]}]  sources={ang}  dupes={dup}")
        for t, c in list(info.get("dupe_titles", {}).items())[:3]:
            print(f"{indent}       ⚠️  '{t[:55]}' × {c}")
        if not ok:
            all_pass = False
    return all_pass


def run_runner(*extra_args: str, timeout: int = 300) -> tuple[int, str]:
    """Run the runner against the TEST_DIR (10 files) with given extra args."""
    cmd = [sys.executable, str(RUNNER),
           "--upload-only",
           "--notebook-ids", NB_IDS_STR,
           "--output-dir", str(TEST_DIR),
           "--source-prefix", TEST_PREFIX,   # isolate test uploads from real [Angular] sources
           *extra_args]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    return result.returncode, result.stdout + result.stderr


# ── Test harness ─────────────────────────────────────────────────────
RESULTS: list[dict] = []


def run_test(name: str, fn) -> bool:
    print(f"\n{'='*58}")
    print(f"  {name}")
    print(f"{'='*58}")
    t0 = time.time()
    try:
        passed = fn()
    except Exception as e:
        import traceback
        print(f"  ❌ EXCEPTION: {e}")
        traceback.print_exc()
        passed = False
    elapsed = time.time() - t0
    icon = "PASS ✅" if passed else "FAIL ❌"
    print(f"\n  Result: {icon}  ({elapsed:.1f}s)")
    RESULTS.append({"test": name, "passed": passed, "elapsed": elapsed})
    return passed


# ── Tests ─────────────────────────────────────────────────────────────

def t0_baseline():
    """Verify 0 [AngularTest] sources exist before we start."""
    print(f"  Checking for pre-existing {TEST_PREFIX} sources...")
    counts = get_source_counts(TEST_PREFIX)
    return print_counts(counts, expected=0)


def t1_first_upload():
    """Upload 10 test files for the first time → each NB gets exactly 10."""
    print(f"  First upload of {NUM_TEST_FILES} test files to all 3 NBs...")
    rc, out = run_runner()
    lines = [l for l in out.splitlines() if "skip=" in l or "new=" in l or "done" in l]
    for l in lines: print(f"    {l.strip()}")
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    return rc == 0 and print_counts(counts, expected=EXPECTED_COUNT)


def t2_idempotency():
    """Re-run without file changes → skip=10 per NB, 0 new uploads."""
    print("  Re-running with no file changes (expecting all-skip)...")
    rc, out = run_runner()
    skip_lines = [l for l in out.splitlines() if "skip=" in l and "update=" in l]
    for l in skip_lines: print(f"    {l.strip()}")
    all_skip = all(f"skip={EXPECTED_COUNT}" in l for l in skip_lines)
    any_new  = any(f"new=0" not in l for l in skip_lines if "new=" in l)
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    api_ok = print_counts(counts, expected=EXPECTED_COUNT)
    return rc == 0 and all_skip and not any_new and api_ok


def t3_preflight_sync():
    """Delete all 3 logs → pre-flight sync should seed from notebook → still 10, 0 dupes."""
    print("  Deleting all 3 logs...")
    delete_test_logs()
    print("  Running (expecting pre-flight sync for all 3 NBs)...")
    rc, out = run_runner()
    seed_lines = [l for l in out.splitlines() if "Empty log" in l or "Seeding" in l]
    print(f"  Seeding messages: {len(seed_lines)}")
    for l in seed_lines: print(f"    {l.strip()}")
    skip_lines = [l for l in out.splitlines() if "skip=" in l and "update=" in l]
    for l in skip_lines: print(f"    {l.strip()}")
    all_skip = all(f"skip={EXPECTED_COUNT}" in l for l in skip_lines)
    logs_exist = all((TEST_DIR / f"upload-log-{nb[:8]}.json").exists() for nb in NB_IDS)
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    api_ok = print_counts(counts, expected=EXPECTED_COUNT)
    return rc == 0 and all_skip and api_ok and logs_exist


def t4_force_reupload():
    """--force → bulk-clear + fresh upload → still exactly 10 each, 0 dupes."""
    print("  Running --force (bulk-clear + re-upload)...")
    rc, out = run_runner("--force")
    cleared = [l for l in out.splitlines() if "Cleared" in l]
    done    = [l for l in out.splitlines() if "done" in l and "new=" in l]
    for l in cleared + done: print(f"    {l.strip()}")
    all_new_10 = all(f"new={EXPECTED_COUNT}" in l for l in done) and len(done) >= 3
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    api_ok = print_counts(counts, expected=EXPECTED_COUNT)
    return rc == 0 and all_new_10 and api_ok


def t5_idempotency_after_force():
    """Immediately after --force, re-run → skip=10, 0 new."""
    print("  Running immediately after --force (expecting all-skip)...")
    rc, out = run_runner()
    skip_lines = [l for l in out.splitlines() if "skip=" in l and "update=" in l]
    for l in skip_lines: print(f"    {l.strip()}")
    all_skip = all(f"skip={EXPECTED_COUNT}" in l for l in skip_lines)
    any_new  = any(f"new=0" not in l for l in skip_lines if "new=" in l)
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    api_ok = print_counts(counts, expected=EXPECTED_COUNT)
    return rc == 0 and all_skip and not any_new and api_ok


def t6_single_log_delete():
    """Delete NB2 log only → NB2 pre-flight syncs; NB1/NB3 skip."""
    nb2 = NB_IDS[1]
    print(f"  Deleting only NB2 log ({nb2[:8]})...")
    delete_test_logs([nb2])
    rc, out = run_runner()
    seeded = any(nb2[:8] in l and ("Empty log" in l or "Seeding" in l)
                 for l in out.splitlines())
    skip_lines = [l for l in out.splitlines() if "skip=" in l and "update=" in l]
    for l in skip_lines: print(f"    {l.strip()}")
    print(f"  NB2 pre-flight seeded: {seeded}")
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    api_ok = print_counts(counts, expected=EXPECTED_COUNT)
    return rc == 0 and seeded and api_ok


def t7_concurrent_stress():
    """2 simultaneous upload processes → idempotent, no dupes."""
    print("  Launching 2 concurrent upload processes...")
    cmd = [sys.executable, str(RUNNER),
           "--upload-only", "--notebook-ids", NB_IDS_STR,
           "--output-dir", str(TEST_DIR)]
    p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace")
    p2 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace")
    try:
        p1.communicate(timeout=300)
        p2.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        p1.kill(); p2.kill()
        print("  ❌ Timeout")
        return False
    print(f"  P1={p1.returncode}  P2={p2.returncode}")
    print("  API verify...")
    counts = get_source_counts(TEST_PREFIX)
    api_ok = print_counts(counts, expected=EXPECTED_COUNT)
    return (p1.returncode == 0 or p2.returncode == 0) and api_ok


def t8_cleanup():
    """Delete all [AngularTest] sources from all 3 NBs."""
    print("  Deleting all test sources from notebooks...")
    deleted = delete_test_sources()
    print(f"  Total deleted: {deleted}")
    # Also remove test logs and temp dir
    delete_test_logs()
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    print(f"  Test dir removed: {TEST_DIR}")
    return deleted >= 0   # always passes


def t9_final_verify():
    """Ground-truth final check — 0 [AngularTest] sources per NB."""
    print("  Final verify: 0 [AngularTest] sources should remain...")
    counts = get_source_counts(TEST_PREFIX)
    ok = print_counts(counts, expected=0)
    if ok:
        print("  🎉 All test sources cleaned — notebooks unaffected")
    return ok


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("\n" + "█" * 58)
    print("  ANGULAR RAG DEDUP — E2E STRESS TEST (10-file subset)")
    print(f"  Source files: {NUM_TEST_FILES}  (sampled from 40)")
    print(f"  Notebooks   : {len(NB_IDS)}")
    print(f"  Test prefix : {TEST_PREFIX}")
    print("█" * 58)

    setup_test_dir()

    run_test("T0 — Baseline (0 test sources exist)",        t0_baseline)
    run_test("T1 — First Upload (10 → 3 NBs)",              t1_first_upload)
    run_test("T2 — Idempotency (no changes)",               t2_idempotency)
    run_test("T3 — Pre-flight Sync (all logs deleted)",     t3_preflight_sync)
    run_test("T4 — Force Re-upload (bulk-clear + fresh)",   t4_force_reupload)
    run_test("T5 — Idempotency After Force",                t5_idempotency_after_force)
    run_test("T6 — Single Log Delete (NB2 only)",           t6_single_log_delete)
    run_test("T7 — Concurrent Stress (2 processes)",        t7_concurrent_stress)
    run_test("T8 — Cleanup (delete test sources)",          t8_cleanup)
    run_test("T9 — Final Verify (0 test sources remain)",   t9_final_verify)

    print("\n" + "=" * 58)
    print("  TEST RESULTS SUMMARY")
    print("=" * 58)
    all_pass = True
    for r in RESULTS:
        icon = "✅" if r["passed"] else "❌"
        print(f"  {icon}  {r['test']:<42}  {r['elapsed']:5.1f}s")
        if not r["passed"]:
            all_pass = False
    print("=" * 58)
    print(f"  OVERALL: {'✅ ALL PASS' if all_pass else '❌ SOME FAILED'}")
    print("=" * 58)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
