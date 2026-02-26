"""
Isolated T9 debug: Run 2 uploads and print the raw TOTAL line.
Purpose: verify the 'TOTAL new=... updated=... skipped=...' format so T9 parser can be fixed.
"""
import subprocess, sys, re, time
from pathlib import Path

NB_IDS = [
    "117e47ed-6385-4dc5-9abc-1bf57588a263",
    "b0376e17-644a-4228-8911-fdce0439a672",
    "493bbdb5-7ca4-409f-bf96-673d86311d9e",
]
OUTPUT_DIR = "ANGULAR-RAG-SOURCES"

for run in range(1, 3):
    cmd = [
        sys.executable, "angular-rag-runner.py",
        "--upload-only",
        "--notebook-ids", ",".join(NB_IDS),
        "--output-dir", OUTPUT_DIR,
    ]
    print(f"\n{'='*60}\n  RUN {run}\n{'='*60}")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(Path(__file__).parent))
    elapsed = time.time() - t0
    
    print(f"  returncode={r.returncode}  elapsed={elapsed:.1f}s")
    
    # Show just the summary lines (TOTAL, per-NB status lines)
    print("\n  Key output lines:")
    for line in r.stdout.splitlines():
        stripped = line.strip()
        if "TOTAL" in stripped or "skip=" in stripped or "BATCH UPLOAD" in stripped:
            print(f"    > {stripped}")
    
    # Try to parse
    total_line = [l for l in r.stdout.splitlines() if "TOTAL" in l and "skipped=" in l]
    print(f"\n  TOTAL line found: {total_line}")
    if total_line:
        line = total_line[0]
        skip = re.search(r"skipped=(\d+)", line)
        new  = re.search(r"new=(\d+)", line)
        upd  = re.search(r"updated=(\d+)", line)
        print(f"  Parsed: skipped={skip.group(1) if skip else 'N/A'} "
              f"new={new.group(1) if new else 'N/A'} "
              f"updated={upd.group(1) if upd else 'N/A'}")
