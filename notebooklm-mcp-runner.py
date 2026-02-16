"""Process an e-SCRA volume via the notebook_digest_multi pipeline.

Usage: notebooklm-mcp-runner.py Volume_001
  or:  notebooklm-mcp-runner.py Volume_001 Volume_002 Volume_003

Reads all .md files from the volume directory, passes them to
notebook_digest_multi, and outputs to CASE-DIGESTS/Volume_NNN/.

Automatically handles resume — re-run safely to pick up where it left off.
"""
import json
import os
import sys
import time

# Add source to path so we can import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Force auth from cached tokens
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

NOTEBOOK_IDS = [
    "9daa06dc-b783-455a-b525-3c9cd3c36b9e",
    "d30bc801-da43-4e32-b044-bb1c0b6a20b4",
    "942b25a4-8528-4d50-bbf9-3915af267402",
    "42b27b34-ea16-4612-870b-84f9e40e296a",
    "599684ce-78f3-4bd2-a8c9-45c294160dfe",
    "a12b80e7-218f-438f-b7ec-411336ef40b7",
    "1b9ba80e-2d16-400d-a842-c465da2cfc10",
    "dd098ff4-c18c-412c-8cde-6cb685f78ec9",
    "a3b742e7-db9a-4f71-8efe-06c3fb88bfe9",
    "aa931c7c-a6b6-46b4-99db-843337440d3c",
    "7647a1bf-31fa-4d15-84a7-6e5ddf38094f",
    "cd58152e-163d-41e0-994d-e7d90ddeba75",
    "c35cd867-ce15-4893-8edf-94a1a3df9cd8",
    "363cba7e-15e3-4c69-ba4b-b4e78aa1e16d",
    "8b2a1455-3a0e-4b16-a574-2e0568ddea36",
]

SOURCE_ROOT = r"C:\PROJECTS\e-scra\MARKDOWN"
OUTPUT_ROOT = r"C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS"


def process_volume(volume_name):
    src_dir = os.path.join(SOURCE_ROOT, volume_name)
    out_dir = os.path.join(OUTPUT_ROOT, volume_name)

    if not os.path.isdir(src_dir):
        print(f"ERROR: {src_dir} not found")
        return

    files = sorted([
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".md")
    ])

    if not files:
        print(f"  {volume_name}: no .md files found")
        return

    # Check existing digests
    existing = 0
    if os.path.isdir(out_dir):
        existing = len([f for f in os.listdir(out_dir) if f.endswith("-case-digest.md")])

    print(f"\n{'='*60}")
    print(f"  {volume_name}: {len(files)} files, {existing} already done")
    print(f"  Source: {src_dir}")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}")

    if existing >= len(files):
        print(f"  SKIP — all {len(files)} already complete")
        return

    # Import here to avoid loading everything at startup
    from notebooklm_mcp.server import notebook_digest_multi

    start = time.time()
    result = notebook_digest_multi(
        notebook_ids=NOTEBOOK_IDS,
        file_paths=files,
        output_dir=out_dir,
    )
    elapsed = time.time() - start

    summary = result.get("summary", {})
    print(f"\n  Result: {result.get('status')}")
    print(f"  Saved: {summary.get('digests_saved', '?')}/{summary.get('total', '?')}")
    print(f"  Failed: {summary.get('failed', '?')}")
    print(f"  Elapsed: {elapsed:.1f}s ({summary.get('queries_per_minute', 0):.1f} q/min)")

    # Print progress log
    for line in result.get("progress_log", []):
        print(f"    {line}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py notebooklm-mcp-runner.py Volume_001 [Volume_002 ...]")
        print("       py notebooklm-mcp-runner.py Volume_001-Volume_010  (range)")
        sys.exit(1)

    volumes = []
    for arg in sys.argv[1:]:
        if "-" in arg and arg.count("-") == 1 and "Volume_" in arg:
            # Range: Volume_001-Volume_010
            start_vol, end_vol = arg.split("-")
            start_num = int(start_vol.replace("Volume_", ""))
            end_num = int(end_vol.replace("Volume_", ""))
            for i in range(start_num, end_num + 1):
                volumes.append(f"Volume_{i:03d}")
        else:
            volumes.append(arg)

    print(f"Processing {len(volumes)} volume(s)...")
    for vol in volumes:
        try:
            process_volume(vol)
        except KeyboardInterrupt:
            print("\n\nInterrupted! Progress saved to disk. Re-run to resume.")
            sys.exit(1)
        except Exception as e:
            print(f"\n  ERROR in {vol}: {e}")
            import traceback
            traceback.print_exc()
