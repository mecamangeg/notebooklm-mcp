"""
Angular RAG Multi-Notebook Deduplication E2E Test Suite
Tests: idempotency, pre-flight sync, --force dedup, and live source count verification.
"""
import os, sys, json, time, subprocess
from pathlib import Path

NB_IDS = "117e47ed-6385-4dc5-9abc-1bf57588a263,b0376e17-644a-4228-8911-fdce0439a672,493bbdb5-7ca4-409f-bf96-673d86311d9e"
NB_LIST = NB_IDS.split(",")
OUT_DIR = Path("ANGULAR-RAG-SOURCES")
RUNNER  = "angular-rag-runner.py"

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"

results = []

def run(*args, capture=True):
    cmd = ["uv", "run", "python", RUNNER, *args]
    print(f"\n  $ {' '.join(str(a) for a in args)}")
    if capture:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = r.stdout + r.stderr
    else:
        r = subprocess.run(cmd, encoding="utf-8", errors="replace")
        output = ""
    return r.returncode, output

def source_counts():
    """Return {nb_id: (total, angular, duplicates)} by querying each notebook."""
    from notebooklm_mcp.server import get_client
    client = get_client()
    counts = {}
    for nb_id in NB_LIST:
        try:
            data = client.get_notebook(nb_id)
            sources = []
            if isinstance(data, list) and data:
                nb = data[0] if isinstance(data[0], list) else data
                if len(nb) > 1 and isinstance(nb[1], list):
                    for s in nb[1]:
                        if isinstance(s, list) and len(s) > 1:
                            title = s[1] if isinstance(s[1], str) else str(s[1])
                            sources.append(title)
            angular = [t for t in sources if t.startswith("[Angular]")]
            seen = {}
            for t in angular:
                seen[t] = seen.get(t, 0) + 1
            dupes = {t: c for t, c in seen.items() if c > 1}
            counts[nb_id[:8]] = {"total": len(sources), "angular": len(angular), "dupes": dupes}
        except Exception as e:
            counts[nb_id[:8]] = {"total": -1, "angular": -1, "dupes": {}, "error": str(e)}
    return counts

def log_entry_counts():
    return {
        nb_id[:8]: len(json.loads((OUT_DIR / f"upload-log-{nb_id[:8]}.json").read_text(encoding="utf-8")) or {})
        if (OUT_DIR / f"upload-log-{nb_id[:8]}.json").exists() else 0
        for nb_id in NB_LIST
    }

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"\n  {status} {name}" + (f"\n     {detail}" if detail else ""))
    results.append((name, condition, detail))
    return condition

print("\n" + "="*64)
print("  ANGULAR RAG DEDUPLICATION E2E TEST SUITE")
print("="*64)

# ── STEP 0: Clean baseline ──────────────────────────────────────
print("\n\n━━━ STEP 0: Clean baseline (clear-existing + fresh upload) ━━━")
for f in OUT_DIR.glob("upload-log-*.json"):
    f.unlink()
print("  Deleted all per-notebook upload logs")
rc, out = run("--upload-only", f"--notebook-ids={NB_IDS}", "--clear-existing", "--force")
check("Step 0: clean baseline exit code 0", rc == 0, f"exit code={rc}")
check("Step 0: all 3 NBs reported new=40",
      out.count("new=40") >= 3, f"new=40 found {out.count('new=40')} times")

print("\n  Verifying source counts via live notebook API...")
counts = source_counts()
for nb, info in counts.items():
    check(f"Step 0: [{nb}] has exactly 40 Angular sources (no dupes)",
          info["angular"] == 40 and not info["dupes"],
          f"angular={info['angular']} dupes={info['dupes']}")

log_counts = log_entry_counts()
for nb, n in log_counts.items():
    check(f"Step 0: [{nb}] upload-log has 40 entries", n == 40, f"log entries={n}")

# ── TEST 1: Idempotency ──────────────────────────────────────────
print("\n\n━━━ TEST 1: IDEMPOTENCY (second run, no changes) ━━━")
t0 = time.time()
rc, out = run("--upload-only", f"--notebook-ids={NB_IDS}")
elapsed = time.time() - t0
check("T1: exit code 0", rc == 0)
check("T1: all 3 NBs skip=40", out.count("skip=40") >= 3, f"skip=40 found {out.count('skip=40')} times")
check("T1: zero new sources", "new=0" in out and out.count("new=40") == 0)
check("T1: completes in under 30s (no API calls)", elapsed < 30, f"elapsed={elapsed:.1f}s")
print(f"\n  Elapsed: {elapsed:.1f}s")

counts = source_counts()
for nb, info in counts.items():
    check(f"T1: [{nb}] still exactly 40 sources (no dupes added)",
          info["angular"] == 40 and not info["dupes"],
          f"angular={info['angular']} dupes={info['dupes']}")

# ── TEST 2: Pre-flight sync (delete NB1 log, run without force) ──
print("\n\n━━━ TEST 2: PRE-FLIGHT SYNC (delete NB1 log, expect sync + skip) ━━━")
nb1_log = OUT_DIR / f"upload-log-117e47ed.json"
nb1_log.unlink(missing_ok=True)
print(f"  Deleted {nb1_log.name}")

rc, out = run("--upload-only", f"--notebook-ids={NB_IDS}")
check("T2: exit code 0", rc == 0)
check("T2: pre-flight sync triggered for NB1",
      "Seeding log" in out or "Empty log" in out,
      f"seeding message present: {'Seeding log' in out or 'Empty log' in out}")
check("T2: NB1 ends with skip=40 (seeded then all skipped)",
      "117e47ed] skip=40" in out or out.count("skip=40") >= 3,
      f"NB1 skip report found: {'117e47ed' in out}")
check("T2: no new sources uploaded", out.count("new=40") == 0)

# Verify log was recreated
n = log_entry_counts().get("117e47ed", 0)
check("T2: NB1 upload-log recreated with 40 entries", n == 40, f"entries={n}")

counts = source_counts()
for nb, info in counts.items():
    check(f"T2: [{nb}] still exactly 40 sources (pre-flight prevented duplicates)",
          info["angular"] == 40 and not info["dupes"],
          f"angular={info['angular']} dupes={info['dupes']}")

# ── TEST 3: Force re-upload (no duplicates!) ─────────────────────
print("\n\n━━━ TEST 3: --force RE-UPLOAD (must delete-before-reupload, no dupes) ━━━")
rc, out = run("--upload-only", f"--notebook-ids={NB_IDS}", "--force")
check("T3: exit code 0", rc == 0)
# With --force: either 'new' or 'updated' depending on whether prior source_ids
# are real (targeted delete) or batch-unknown (fresh upload). Either way, the
# real correctness gate is the no-dupes API check below.
import re as _re
new_total = sum(int(m) for m in _re.findall(r"new=(\d+)", out))
upd_total = sum(int(m) for m in _re.findall(r"updated=(\d+)", out))
check("T3: --force processed all 120 sources (new + updated = 120)",
      new_total + upd_total >= 120,
      f"new_total={new_total} updated_total={upd_total} combined={new_total+upd_total}")

time.sleep(3)  # brief settle
counts = source_counts()
for nb, info in counts.items():
    check(f"T3: [{nb}] still exactly 40 sources after --force (no dupes!)",
          info["angular"] == 40 and not info["dupes"],
          f"angular={info['angular']} dupes={info['dupes']}")

# ── TEST 4: Idempotency after force ──────────────────────────────
print("\n\n━━━ TEST 4: IDEMPOTENCY AFTER --force ━━━")
rc, out = run("--upload-only", f"--notebook-ids={NB_IDS}")
check("T4: exit code 0", rc == 0)
check("T4: all 3 NBs skip=40 after force", out.count("skip=40") >= 3,
      f"skip=40 count={out.count('skip=40')}")

# ── FINAL REPORT ─────────────────────────────────────────────────
print("\n\n" + "="*64)
print("  FINAL RESULTS")
print("="*64)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
for name, ok, detail in results:
    status = "✅" if ok else "❌"
    print(f"  {status} {name}")
    if not ok and detail:
        print(f"     {detail}")
print(f"\n  {passed}/{passed+failed} tests passed")
if failed:
    print("\n  FAILED TESTS:")
    for name, ok, detail in results:
        if not ok:
            print(f"    ❌ {name}: {detail}")
    sys.exit(1)
else:
    print("\n  All deduplication tests passed! 🎉")
