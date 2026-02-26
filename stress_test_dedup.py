"""
Deduplication Stress Test Suite — T5 through T9
================================================
Continues from the T0-T4 E2E tests documented in docs/multi-notebook-dedup-fixes.md.

Tests:
  T5 — Partial update     : Mutate 2 MD files, verify only 2 get re-uploaded per NB
  T6 — New NB onboarding  : Pre-flight sync on a 4th (empty-log) notebook
  T7 — Concurrent preflight : Delete all 3 logs, run in parallel — race safety check
  T8 — batch-unknown recovery : Inject batch-unknown IDs into log, trigger update path
  T9 — Rapid re-run stress  : 5 back-to-back runs with no changes → all skip=120

Usage:
  cd C:\\PROJECTS\\notebooklm-mcp
  uv run python stress_test_dedup.py

Pre-requisites:
  - All 3 notebooks must be in a clean state: 40 [Angular] sources each, no dupes
  - Run after T4 from the prior session (notebooks already clean)
  - Cookies must be fresh (run check_auth_status first if in doubt)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

# ── Environment bootstrap (mirrors runner startup) ─────────────────────────────
sys.path.insert(0, "src")
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

# ── Constants ──────────────────────────────────────────────────────────────────
NB_IDS = [
    "117e47ed-6385-4dc5-9abc-1bf57588a263",   # NB1  robsky-angular-sourcecode
    "b0376e17-644a-4228-8911-fdce0439a672",   # NB2
    "493bbdb5-7ca4-409f-bf96-673d86311d9e",   # NB3
]

# NB4 is used only for T6 — it must already exist in your account
NB4_ID = None

# Using a temp dir and prefix to isolate stress tests
TEST_DIR    = Path(os.environ.get("TEMP", "tmp")) / "notebooklm_stress_test"
OUTPUT_DIR  = TEST_DIR
RUNNER_PY   = Path("angular-rag-runner.py")
TEST_PREFIX = "[AngularTest]"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results: list[tuple[str, str, str]] = []   # (test_id, description, result_emoji)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _log_path(nb_id: str) -> Path:
    return OUTPUT_DIR / f"upload-log-{nb_id[:8]}.json"


def _backup_log(nb_id: str) -> Path | None:
    src = _log_path(nb_id)
    if src.exists():
        bak = src.with_suffix(".json.bak")
        shutil.copy2(src, bak)
        return bak
    return None


def _restore_log(nb_id: str):
    bak = _log_path(nb_id).with_suffix(".json.bak")
    if bak.exists():
        shutil.move(str(bak), str(_log_path(nb_id)))


def _load_log(nb_id: str) -> dict:
    p = _log_path(nb_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_log(nb_id: str, data: dict):
    _log_path(nb_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get_md_files() -> list[Path]:
    return sorted(p for p in OUTPUT_DIR.glob("*.md")
                  if not p.name.startswith("upload-log"))


def get_notebook_sources_api(client, nb_id: str) -> list[dict]:
    """Live API fetch — same logic as runner's get_notebook_sources()."""
    try:
        data = client.get_notebook(nb_id)
        if not data:
            return []
        sources = []
        if isinstance(data, list) and data:
            nb = data[0] if isinstance(data[0], list) else data
            srcs = nb[1] if len(nb) > 1 else []
            if isinstance(srcs, list):
                for s in srcs:
                    if isinstance(s, list) and len(s) >= 2:
                        sid_wrap = s[0]
                        sid = sid_wrap[0] if isinstance(sid_wrap, list) and sid_wrap else None
                        title = s[1] if isinstance(s[1], str) else str(s[1])
                        if sid:
                            sources.append({"id": sid, "title": title})
        return sources
    except Exception as e:
        print(f"    ⚠️  get_notebook_sources_api({nb_id[:8]}) failed: {e}", file=sys.stderr)
        return []


def assert_clean(client, label: str, expect_count: int = 40) -> bool:
    """Verify all 3 notebooks have exactly expect_count test sources, zero dupes."""
    all_ok = True
    for nb_id in NB_IDS:
        sources = get_notebook_sources_api(client, nb_id)
        angular = [s for s in sources if s["title"].startswith(TEST_PREFIX)]
        titles  = [s["title"] for s in angular]
        dupes   = [t for t in set(titles) if titles.count(t) > 1]
        ok = (len(angular) == expect_count and not dupes)
        status = PASS if ok else FAIL
        print(f"    {status} [{nb_id[:8]}] angular={len(angular)} dupes={len(dupes)}  ({label})")
        if not ok:
            all_ok = False
            if len(angular) != expect_count:
                print(f"         Expected {expect_count}, got {len(angular)}")
            for d in dupes:
                print(f"         DUPE: {d}")
    return all_ok


def run_upload(extra_args: list[str] = (), label: str = "", quiet: bool = False) -> tuple[str, int]:
    """Run angular-rag-runner.py --upload-only and capture stdout as a string."""
    import subprocess
    ids_str = ",".join(NB_IDS)
    cmd = [
        sys.executable, str(RUNNER_PY),
        "--upload-only",
        "--notebook-ids", ids_str,
        "--output-dir", str(OUTPUT_DIR),
        "--source-prefix", TEST_PREFIX,
    ] + list(extra_args)

    if label:
        print(f"    📤 {label}")
        if not quiet:
            print(f"       cmd: {' '.join(cmd[-6:])}")

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=str(Path(__file__).parent))
    elapsed = time.time() - t0

    # Echo stdout (suppressed in quiet mode)
    if not quiet:
        for line in result.stdout.splitlines():
            print(f"       | {line}")
    if result.returncode != 0:
        print(f"       !! STDERR:", file=sys.stderr)
        for line in result.stderr.splitlines()[:20]:
            print(f"          {line}", file=sys.stderr)

    return result.stdout, result.returncode


def record(test_id: str, desc: str, passed: bool):
    sym = PASS if passed else FAIL
    results.append((test_id, desc, sym))
    print(f"\n  {sym}  {test_id}: {desc}\n")


# ══════════════════════════════════════════════════════════════════════════════
# BASELINE CHECK
# ══════════════════════════════════════════════════════════════════════════════

def preflight_baseline(client) -> bool:
    print("\n" + "="*64)
    print(f"  PREFLIGHT: Verifying baseline (all 3 NBs @ 40 sources, 0 dupes)")
    print("="*64)
    ok = assert_clean(client, "pre-test baseline")
    if not ok:
        print(f"\n  !! BASELINE FAILED — notebooks are not in a clean 40-source state.")
        print(f"     Run: python runner.py --output-dir {OUTPUT_DIR} --source-prefix {TEST_PREFIX} --force")
        print("     then re-run this script.")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# T5 — PARTIAL UPDATE
# ══════════════════════════════════════════════════════════════════════════════

def test_t5_partial_update(client):
    """
    Mutate content of 2 MD files → runner should update only those 2 per NB,
    skip the other 38.  Verify: no dupes, still 40 total.
    """
    print("\n" + "═"*64)
    print("  T5 — Partial Update (mutate 2 files → update=2, skip=38 per NB)")
    print("═"*64)

    md_files = _get_md_files()
    if len(md_files) < 2:
        record("T5", "Partial update", False)
        print("    SKIP — not enough MD files")
        return

    mutated: list[tuple[Path, str]] = []
    for p in md_files[:2]:
        orig = p.read_text(encoding="utf-8")
        mutated.append((p, orig))
        p.write_text(orig + "\n<!-- stress-test mutation T5 -->\n", encoding="utf-8")

    try:
        stdout, rc = run_upload(label="T5 upload (expect update=6, skip=114 total)")

        # Per-notebook: 2 updates, 38 skips
        # Aggregated total: update=6 skip=114
        update_line = [l for l in stdout.splitlines() if "update=" in l and "TOTAL" in l]
        skip_line   = update_line  # same line

        # Parse from per-NB lines "[xxxxxxxx] skip=38 update=2 new=0"
        per_nb_ok = True
        for nb_id in NB_IDS:
            tag = nb_id[:8]
            lines_for_nb = [l for l in stdout.splitlines() if tag in l and "skip=" in l]
            if not lines_for_nb:
                print(f"    ⚠️  No status line found for [{tag}]")
                per_nb_ok = False
                continue
            line = lines_for_nb[0]
            # Expect: skip=38 update=2 new=0
            def extract(key: str, s: str) -> int:
                import re
                m = re.search(rf"{key}=(\d+)", s)
                return int(m.group(1)) if m else -1
            skip_n   = extract("skip", line)
            update_n = extract("update", line) + extract("new", line)  # force may shift
            print(f"    [{tag}] skip={skip_n} update/new={update_n}  (from: {line.strip()})")
            if skip_n != 38 or update_n < 2:
                print(f"         ⚠️  Expected skip=38 update=2")
                per_nb_ok = False

        # API verify: still 40, no dupes
        time.sleep(5)   # Give NotebookLM a moment to reflect the changes
        api_ok = assert_clean(client, "T5 post-upload API check")

        record("T5", "Partial update (2 files mutated → update=2 skip=38 per NB)", per_nb_ok and api_ok)
    finally:
        # Restore mutated files AND fix their log hashes to match original content.
        # If we only restore the file without updating the log, subsequent tests
        # will see hash-mismatch (mutated-hash in log vs original-content on disk)
        # and trigger spurious re-uploads in T7/T8/T9.
        import hashlib as _hl
        from angular_rag_core import compute_content_hash
        for p, orig in mutated:
            p.write_text(orig, encoding="utf-8")
        # Re-normalize the log entries for the restored files
        for nb_id in NB_IDS:
            log = _load_log(nb_id)
            changed = False
            for p, orig in mutated:
                key = p.name   # log key is basename
                if key in log:
                    correct_hash = compute_content_hash(orig)
                    if log[key].get("content_hash") != correct_hash:
                        log[key]["content_hash"] = correct_hash
                        changed = True
            if changed:
                _save_log(nb_id, log)
        print("    ℹ️  Restored 2 mutated MD files + re-normalized log hashes")


# ══════════════════════════════════════════════════════════════════════════════
# T6 — NEW NOTEBOOK ONBOARDING (pre-flight sync on 4th NB)
# ══════════════════════════════════════════════════════════════════════════════

def test_t6_new_notebook_onboarding(client):
    """
    Simulate adding a 4th notebook that already has 40 [Angular] sources
    but NO upload log.  Pre-flight sync should seed the log from the API,
    meaning the next normal run should produce skip=40 (0 uploads).
    Requires NB4_ID to be set and the notebook to already have 40 [Angular] sources.
    """
    print("\n" + "═"*64)
    print("  T6 — New NB Onboarding (pre-flight sync on empty 4th NB log)")
    print("═"*64)

    if NB4_ID is None:
        print("    NB4_ID is None — skipping T6 (set NB4_ID at top of this script to run)")
        results.append(("T6", "New NB onboarding (pre-flight sync)", SKIP))
        return

    log4 = OUTPUT_DIR / f"upload-log-{NB4_ID[:8]}.json"
    # Remove the 4th NB's log to simulate fresh onboarding
    if log4.exists():
        bak = log4.with_suffix(".json.bak")
        shutil.copy2(log4, bak)
        log4.unlink()
        print(f"    Removed {log4.name} (backed up to .bak)")

    # Run with all 4 notebooks
    import subprocess
    ids_str = ",".join(NB_IDS + [NB4_ID])
    cmd = [
        sys.executable, str(RUNNER_PY),
        "--upload-only",
        "--notebook-ids", ids_str,
        "--output-dir", str(OUTPUT_DIR),
    ]
    print(f"    📤 4-NB run (NB4 log missing → expect pre-flight + 0 uploads for NB4)")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=str(Path(__file__).parent))
    stdout = result.stdout
    for line in stdout.splitlines():
        print(f"       | {line}")

    # Check NB4 got pre-flight seeded
    nb4_tag = NB4_ID[:8]
    seeded = any("seeding" in l.lower() and nb4_tag in l.lower() for l in stdout.lower().splitlines())
    skipped_all = any(nb4_tag in l and "skip=" in l for l in stdout.splitlines())

    import re
    nb4_lines = [l for l in stdout.splitlines() if nb4_tag in l and "skip=" in l]
    nb4_skip = -1
    if nb4_lines:
        m = re.search(r"skip=(\d+)", nb4_lines[0])
        nb4_skip = int(m.group(1)) if m else -1

    print(f"    NB4 pre-flight seeded: {seeded}")
    print(f"    NB4 skip count: {nb4_skip}")

    # Ideal: seeded=True, skip=40
    ok = seeded and nb4_skip == 40

    # Restore log backup
    bak = log4.with_suffix(".json.bak")
    if bak.exists():
        shutil.move(str(bak), str(log4))
        print(f"    Restored {log4.name}")

    record("T6", "New NB onboarding: pre-flight seeds log → skip=40 (no uploads)", ok)


# ══════════════════════════════════════════════════════════════════════════════
# T7 — CONCURRENT PRE-FLIGHT SYNC RACE
# ══════════════════════════════════════════════════════════════════════════════

def test_t7_concurrent_preflight_race(client):
    """
    Delete ALL 3 upload logs simultaneously, then run the normal upload.
    All 3 notebook threads will fire pre-flight sync at the same time.
    Verify: no dupes, still exactly 40 each.
    """
    print("\n" + "═"*64)
    print("  T7 — Concurrent Pre-flight Race (delete all 3 logs, re-run)")
    print("═"*64)

    # Back up and delete all logs
    backups: list[tuple[str, Path]] = []
    for nb_id in NB_IDS:
        bak = _backup_log(nb_id)
        if bak:
            _log_path(nb_id).unlink()
            backups.append((nb_id, bak))
            print(f"    Deleted {_log_path(nb_id).name} (backed up)")

    try:
        stdout, rc = run_upload(label="T7 upload (all 3 logs missing → 3-way pre-flight race)")

        # Check all 3 get seeded and skip=40
        import re
        all_seeded_and_skipped = True
        for nb_id in NB_IDS:
            tag = nb_id[:8]
            seeded = any("seeding" in l.lower() and tag in l for l in stdout.lower().splitlines())
            nb_lines = [l for l in stdout.splitlines() if tag in l and "skip=" in l]
            skip_n = -1
            if nb_lines:
                m = re.search(r"skip=(\d+)", nb_lines[0])
                skip_n = int(m.group(1)) if m else -1
            print(f"    [{tag}] seeded={seeded} skip={skip_n}")
            if not seeded or skip_n != 40:
                all_seeded_and_skipped = False

        time.sleep(3)
        api_ok = assert_clean(client, "T7 post-concurrent-preflight API check")
        record("T7", "Concurrent pre-flight race (3-thread simultaneous seed, 0 dupes)", all_seeded_and_skipped and api_ok)
    finally:
        for nb_id, bak in backups:
            shutil.move(str(bak), str(_log_path(nb_id)))
            print(f"    Restored {_log_path(nb_id).name}")


# ══════════════════════════════════════════════════════════════════════════════
# T8 — batch-unknown ID RECOVERY
# ══════════════════════════════════════════════════════════════════════════════

def test_t8_batch_unknown_recovery(client):
    """
    Inject 'batch-unknown' as source_id for 2 files in each NB's log,
    then mutate those files → triggers 'update' path with batch-unknown IDs.
    The runner should do a live title-match delete before re-uploading.
    Verify: still 40 each, 0 dupes.
    """
    print("\n" + "═"*64)
    print("  T8 — batch-unknown ID Recovery (live title-match delete)")
    print("═"*64)

    md_files = _get_md_files()
    if len(md_files) < 2:
        record("T8", "batch-unknown recovery", False)
        print("    SKIP — not enough MD files")
        return

    target_files = md_files[:2]

    # Back up all logs
    backups: list[tuple[str, Path]] = []
    for nb_id in NB_IDS:
        bak = _backup_log(nb_id)
        if bak:
            backups.append((nb_id, bak))

    # Mutate the 2 target files
    mutated: list[tuple[Path, str]] = []
    for p in target_files:
        orig = p.read_text(encoding="utf-8")
        mutated.append((p, orig))
        p.write_text(orig + "\n<!-- stress-test mutation T8 -->\n", encoding="utf-8")

    try:
        # Inject batch-unknown into logs for these 2 files
        for nb_id in NB_IDS:
            log = _load_log(nb_id)
            for p, orig in mutated:
                path_key = str(p)
                if path_key in log:
                    # Keep the real hash but corrupt the source_id to simulate batch-unknown
                    log[path_key]["source_id"] = "batch-unknown"
                else:
                    # File not in log → add it with batch-unknown
                    import hashlib
                    log[path_key] = {
                        "source_id": "batch-unknown",
                        "sha256": hashlib.sha256(orig.encode()).hexdigest(),
                        "uploaded_at": "2026-01-01T00:00:00+00:00",
                    }
            _save_log(nb_id, log)

        print(f"    Injected batch-unknown for {len(target_files)} files in all 3 NB logs")
        print(f"    Mutated same {len(target_files)} files → should trigger 'update' path")

        stdout, rc = run_upload(label="T8 upload (batch-unknown → title-match delete + re-upload)")

        # Expect: each NB does update=2, skip=38 (or update+new=2 total)
        import re
        per_nb_ok = True
        for nb_id in NB_IDS:
            tag = nb_id[:8]
            lines = [l for l in stdout.splitlines() if tag in l and "skip=" in l]
            if not lines:
                print(f"    ⚠️  No status line for [{tag}]")
                per_nb_ok = False
                continue
            line = lines[0]
            skip_n   = int(m.group(1)) if (m := re.search(r"skip=(\d+)", line)) else -1
            update_n = (int(m.group(1)) if (m := re.search(r"update=(\d+)", line)) else 0) + \
                       (int(m.group(1)) if (m := re.search(r"new=(\d+)", line)) else 0)
            print(f"    [{tag}] skip={skip_n} update/new={update_n}")
            if update_n < 2 or skip_n < 36:  # allow some flexibility
                per_nb_ok = False
                print(f"         ⚠️  Expected update/new≥2, skip≥36")

        time.sleep(5)
        api_ok = assert_clean(client, "T8 API check (expect 40, 0 dupes)")
        record("T8", "batch-unknown recovery: live title-match delete → no dupes", per_nb_ok and api_ok)
    finally:
        for p, orig in mutated:
            p.write_text(orig, encoding="utf-8")
        for nb_id, bak in backups:
            shutil.move(str(bak), str(_log_path(nb_id)))
        print("    ℹ️  Restored mutated files and upload logs")


# ══════════════════════════════════════════════════════════════════════════════
# T9 — RAPID RE-RUN STRESS (5x idempotency)
# ══════════════════════════════════════════════════════════════════════════════

def test_t9_rapid_rerun_stress(client):
    """
    Run the uploader 5 times in rapid succession with NO file changes.
    Each run should produce skip=120 and make 0 API calls (from log alone).
    Total time across all 5 runs should be very short.

    Result is written to /tmp/t9_results.json to bypass terminal interleaving.
    """
    import json as _json
    T9_RESULT_FILE = Path(os.environ.get("TEMP", "/tmp")) / "t9_dedup_results.json"
    T9_RESULT_FILE.unlink(missing_ok=True)

    print("\n" + "═"*64)
    print("  T9 — Rapid Re-run Stress (5x with no changes)")
    print("═"*64)
    sys.stdout.flush()

    re_mod = __import__("re")
    run_results: list[dict] = []
    times: list[float] = []

    for i in range(1, 6):
        t0 = time.time()
        stdout, rc = run_upload(label=f"T9 run {i}/5", quiet=True)
        elapsed = time.time() - t0
        times.append(elapsed)

        # Parse TOTAL line (uses 'skipped=' in aggregate summary)
        total_line = [l for l in stdout.splitlines() if "TOTAL" in l and "skipped=" in l]
        skip_total = -1
        new_total  = 0
        if total_line:
            line = total_line[0]
            m = re_mod.search(r"skipped=(\d+)", line); skip_total = int(m.group(1)) if m else -1
            m = re_mod.search(r"new=(\d+)",     line); new_total  = int(m.group(1)) if m else 0
            m = re_mod.search(r"updated=(\d+)", line); new_total += int(m.group(1)) if m else 0
        else:
            # Fallback: sum per-NB skipped= values
            per_nb = re_mod.findall(r"skipped=(\d+)", stdout)
            if per_nb:
                skip_total = sum(int(x) for x in per_nb)

        ok_run = (skip_total == 120 and new_total == 0)
        run_results.append({"run": i, "skip": skip_total, "api": new_total,
                            "ok": ok_run, "elapsed": round(elapsed, 2)})

        sym = "PASS" if ok_run else "FAIL"
        print(f"    [{sym}] Run {i}/5: skip={skip_total} api_uploads={new_total}  ({elapsed:.1f}s)")
        sys.stdout.flush()

    avg_time = sum(times) / len(times)
    max_time = max(times)
    runs_ok  = sum(1 for r in run_results if r["ok"])

    # Write results to temp file — readable even if terminal output is garbled
    summary = {"runs": run_results, "runs_ok": runs_ok,
               "avg_s": round(avg_time, 2), "max_s": round(max_time, 2),
               "all_pass": (runs_ok == 5)}
    T9_RESULT_FILE.write_text(_json.dumps(summary, indent=2), encoding="utf-8")
    print(f"    T9 results written to: {T9_RESULT_FILE}")
    print(f"    Timing: avg={avg_time:.1f}s  max={max_time:.1f}s  total={sum(times):.1f}s")
    sys.stdout.flush()

    # Final API sanity check
    api_ok = assert_clean(client, "T9 post-stress API check")

    # Read result from file to make pass/fail decision (immune to garbled terminal)
    fresh = _json.loads(T9_RESULT_FILE.read_text(encoding="utf-8"))
    all_ok = fresh["all_pass"] and api_ok
    record("T9", f"Rapid re-run stress: 5x skip=120 (0 API calls), avg={avg_time:.1f}s", all_ok)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "+" + "-"*62 + "+")
    print("|  NOTEBOOKLM DEDUP STRESS TEST SUITE  (T5 – T9)             |")
    print("|  Continuing from T0-T4 (docs/multi-notebook-dedup-fixes.md)|")
    print("+" + "-"*62 + "+")

    # Boot the client
    from notebooklm_mcp.server import get_client
    client = get_client()
    print("\n  ✅ API client ready")

    # Gate: verify baseline before destructive tests
    if not preflight_baseline(client):
        print("\n  ❌ Aborting: baseline check failed. Fix notebooks first.")
        sys.exit(1)

    # Run tests
    test_t5_partial_update(client)
    test_t6_new_notebook_onboarding(client)
    test_t7_concurrent_preflight_race(client)
    test_t8_batch_unknown_recovery(client)
    test_t9_rapid_rerun_stress(client)

    # ── Final summary ──────────────────────────────────────────────
    print("\n" + "╔" + "═"*62 + "╗")
    print("║  STRESS TEST SUMMARY                                        ║")
    print("╚" + "═"*62 + "╝")
    print(f"  {'Test':<8}  {'Result':<10}  Description")
    print(f"  {'─'*8}  {'─'*10}  {'─'*40}")

    passed = failed = skipped = 0
    for tid, desc, sym in results:
        print(f"  {tid:<8}  {sym:<12}  {desc}")
        if "PASS" in sym:   passed  += 1
        elif "FAIL" in sym: failed  += 1
        else:               skipped += 1

    print(f"\n  {'─'*62}")
    overall = "ALL PASS ✅" if failed == 0 else f"{failed} FAILED ❌"
    print(f"  OVERALL: {overall}   ({passed} pass, {failed} fail, {skipped} skip)")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
