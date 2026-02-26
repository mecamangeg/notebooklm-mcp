"""
T9-only runner — isolated rapid re-run stress test.
Runs 5 back-to-back uploads with no changes; expects skip=120 each time.
"""
import re, subprocess, sys, time, os
from pathlib import Path

sys.path.insert(0, "src")
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

NB_IDS = [
    "117e47ed-6385-4dc5-9abc-1bf57588a263",
    "b0376e17-644a-4228-8911-fdce0439a672",
    "493bbdb5-7ca4-409f-bf96-673d86311d9e",
]
OUTPUT_DIR = "ANGULAR-RAG-SOURCES"

runs_ok = 0
times = []

print("\n  T9 — Rapid Re-run Stress (5x with no changes)")
print("  " + "="*54)

for i in range(1, 6):
    t0 = time.time()
    cmd = [
        sys.executable, "angular-rag-runner.py",
        "--upload-only",
        "--notebook-ids", ",".join(NB_IDS),
        "--output-dir", OUTPUT_DIR,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       cwd=str(Path(__file__).parent))
    elapsed = time.time() - t0
    times.append(elapsed)

    stdout = r.stdout

    # Show raw TOTAL line for transparency
    total_lines = [l for l in stdout.splitlines() if "TOTAL" in l]
    skipped_lines = [l for l in stdout.splitlines() if "skipped=" in l]
    print(f"\n  --- Run {i} ({elapsed:.1f}s) rc={r.returncode} ---")
    for tl in total_lines:
        print(f"    TOTAL line raw:   {repr(tl.strip())}")
    for sl in skipped_lines[:3]:
        print(f"    skipped= line:    {repr(sl.strip())}")

    # Parse
    total_with_skipped = [l for l in stdout.splitlines() if "TOTAL" in l and "skipped=" in l]
    skip_total = -1
    new_total  = 0
    if total_with_skipped:
        line = total_with_skipped[0]
        m = re.search(r"skipped=(\d+)", line); skip_total = int(m.group(1)) if m else -1
        m = re.search(r"new=(\d+)", line);     new_total  = int(m.group(1)) if m else 0
        m = re.search(r"updated=(\d+)", line); new_total += int(m.group(1)) if m else 0
    else:
        print(f"    [!] No TOTAL+skipped= line found! stdout chars={len(stdout)}")
        if not stdout.strip():
            print(f"    [!] stdout is EMPTY. stderr: {r.stderr[:300]}")

    ok = (skip_total == 120 and new_total == 0)
    sym = "PASS" if ok else "FAIL"
    print(f"    Result: {sym}  skip_total={skip_total}  api_uploads={new_total}")
    if ok:
        runs_ok += 1

avg = sum(times) / len(times)
print(f"\n  Timing: avg={avg:.1f}s  max={max(times):.1f}s  total={sum(times):.1f}s")
print(f"\n  OVERALL: {'ALL PASS' if runs_ok == 5 else f'{5-runs_ok}/5 FAILED'}  ({runs_ok}/5 ok)")
sys.exit(0 if runs_ok == 5 else 1)
