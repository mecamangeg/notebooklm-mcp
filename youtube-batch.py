"""Batch YouTube Context Extractor — check status and extract multiple videos.

Parses a list of YouTube URLs (with optional numbering/titles), checks which
have already been extracted to OUTPUT/, and runs the extractor for the rest.

Supported input formats (mixed lines, all work):
  1. How to build an accuracy pipeline   https://www.youtube.com/watch?v=SHe6ylu_f1Q
  2. how to evaluate agents in practice  https://youtu.be/vuBvf7ZRKTA?si=AML...
  google adk tutorial                    https://youtu.be/wgOCzHXKw4c
  https://www.youtube.com/watch?v=ABC123   (URL only)

Usage:
  # Check status only (no extraction)
  python youtube-batch.py --check "url1 url2 ..."
  python youtube-batch.py --check --file my-list.txt

  # Check then extract unprocessed
  python youtube-batch.py --file my-list.txt
  python youtube-batch.py --urls "url1" "url2" "url3"

  # Pipe from stdin
  cat list.txt | python youtube-batch.py --stdin
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ── Resolve paths relative to this script ─────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
RUNNER     = SCRIPT_DIR / "youtube-context-runner.py"
PYTHON     = sys.executable
OUTPUT_DIR = SCRIPT_DIR / "OUTPUT"

# ── Regex: extract YouTube video ID from any URL format ───────────────────────
_YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})")
# Regex: find a URL anywhere on a line
_URL_RE    = re.compile(r"https?://\S+")


# ═══════════════════════════════════════════════════════════════════════════════
# PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_video_list(text: str) -> list[dict]:
    """Parse a block of text into [{label, url, video_id}] entries.

    Handles lines like:
      "1. Title here   https://youtu.be/ABC"
      "Title   https://youtu.be/ABC"
      "https://youtu.be/ABC"
      (blank lines and comment lines starting with # are skipped)
    """
    results = []
    seen_ids = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Find a URL on this line
        url_match = _URL_RE.search(line)
        if not url_match:
            continue
        url = url_match.group(0)

        # Strip trailing punctuation that is clearly not part of the URL
        url = url.rstrip(".,;)")

        # Extract video ID
        id_match = _YT_ID_RE.search(url)
        if not id_match:
            continue
        video_id = id_match.group(1)

        if video_id in seen_ids:
            continue
        seen_ids.add(video_id)

        # Derive a human label from the text before the URL
        before_url = line[: url_match.start()].strip()
        # Strip leading numbering like "1." or "2)"
        label = re.sub(r"^\d+[.)]\s*", "", before_url).strip()
        if not label:
            label = url  # Fall back to URL if no label text

        results.append({"label": label, "url": url, "video_id": video_id})

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def find_existing_extraction(video_id: str, output_dir: Path) -> Path | None:
    """Scan output_dir for any .md file whose header block contains video_id."""
    if not output_dir.exists():
        return None
    for f in output_dir.iterdir():
        if f.suffix != ".md":
            continue
        try:
            # Only read the first 1 KB — the header always contains the video ID
            with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                head = fh.read(1024)
            if video_id in head:
                return f
        except Exception:
            pass
    return None


def check_status(entries: list[dict], output_dir: Path) -> list[dict]:
    """For each entry, determine if it has already been extracted.

    Adds keys:
      'done'        : bool
      'output_file' : Path | None  (the existing file if done)
    """
    for e in entries:
        existing = find_existing_extraction(e["video_id"], output_dir)
        e["done"] = existing is not None
        e["output_file"] = existing
    return entries


# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY
# ═══════════════════════════════════════════════════════════════════════════════

def print_status_table(entries: list[dict], output_dir: Path) -> None:
    """Print a formatted status table to stdout."""
    done_count = sum(1 for e in entries if e["done"])
    todo_count = len(entries) - done_count

    print()
    print("=" * 72)
    print(f"  📋  YouTube Batch Status  —  {len(entries)} videos")
    print(f"      ✅ Already extracted: {done_count}   ⏳ Pending: {todo_count}")
    print("=" * 72)

    for i, e in enumerate(entries, 1):
        status_icon = "✅" if e["done"] else "⏳"
        label = e["label"][:50] if e["label"] != e["url"] else ""
        vid   = e["video_id"]

        # Truncate the label for display
        display = f"{label} ({vid})" if label else vid
        if len(display) > 55:
            display = display[:52] + "..."

        print(f"  {i:>2}. {status_icon}  {display}")

        if e["done"] and e["output_file"]:
            # Show relative filename
            rel = e["output_file"].name
            print(f"          📄 {rel}")

    print("=" * 72)
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

def run_extraction(entry: dict, cdp_port: int | None, extra_args: list[str]) -> bool:
    """Run youtube-context-runner.py for a single entry.  Returns True on success."""
    cmd = [PYTHON, str(RUNNER), "--url", entry["url"]] + extra_args
    if cdp_port:
        cmd += ["--cdp-port", str(cdp_port)]

    label = entry["label"][:60] if entry["label"] != entry["url"] else entry["video_id"]
    print(f"\n{'─'*72}")
    print(f"  🎬  Extracting: {label}")
    print(f"      URL: {entry['url']}")
    print(f"{'─'*72}\n")

    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    return result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Batch YouTube Context Extractor with status check.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES
  # Paste a list directly (use triple-quotes in PowerShell)
  python youtube-batch.py --text @"
1. How to evaluate agents  https://youtu.be/vuBvf7ZRKTA
2. ADK tutorial            https://youtu.be/wgOCzHXKw4c
"@

  # Check status only (no extraction)
  python youtube-batch.py --file my-list.txt --check

  # Read from file, extract unprocessed
  python youtube-batch.py --file my-list.txt

  # Pass URLs directly
  python youtube-batch.py --urls https://youtu.be/ABC https://youtu.be/XYZ

  # Pipe from stdin
  cat list.txt | python youtube-batch.py --stdin
""",
    )

    # ── Input source (mutually exclusive) ──────────────────────────────────
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--file", metavar="PATH",
        help="Path to a text file containing a list of YouTube URLs (one URL per line).",
    )
    src.add_argument(
        "--text", metavar="TEXT",
        help="Inline text block containing YouTube URLs (use with shell here-string).",
    )
    src.add_argument(
        "--urls", nargs="+", metavar="URL",
        help="One or more YouTube URLs to process.",
    )
    src.add_argument(
        "--stdin", action="store_true",
        help="Read URL list from stdin.",
    )

    # ── Behaviour ──────────────────────────────────────────────────────────
    parser.add_argument(
        "--check", action="store_true",
        help="Only show status table — do NOT run any extraction.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-extract even videos that already have output files.",
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help=f"Output folder (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--cdp-port", type=int, default=None,
        help="Chrome DevTools Protocol port for cookie refresh (default: auto-probe 9222, 9223, 9000).",
    )
    parser.add_argument(
        "--no-cleanup", action="store_true",
        help="Keep the transcript source in the notebook after each extraction.",
    )
    parser.add_argument(
        "--no-cookie-refresh", action="store_true",
        help="Skip the initial Chrome CDP cookie refresh.",
    )

    args = parser.parse_args()

    # ── Read input ───────────────────────────────────────────────────────────
    if args.file:
        try:
            text = Path(args.file).read_text(encoding="utf-8", errors="ignore")
        except FileNotFoundError:
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
    elif args.text:
        text = args.text
    elif args.urls:
        text = "\n".join(args.urls)
    elif args.stdin:
        text = sys.stdin.read()
    else:
        parser.print_help()
        sys.exit(1)

    # ── Parse entries ────────────────────────────────────────────────────────
    entries = parse_video_list(text)
    if not entries:
        print("ERROR: No valid YouTube URLs found in input.", file=sys.stderr)
        print("Expected formats: https://youtube.com/watch?v=... or https://youtu.be/...", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)

    # ── Check status ─────────────────────────────────────────────────────────
    entries = check_status(entries, output_dir)
    print_status_table(entries, output_dir)

    if args.check:
        print("(--check mode: no extraction run)")
        sys.exit(0)

    # ── Determine what to extract ────────────────────────────────────────────
    to_extract = [e for e in entries if not e["done"] or args.force]

    if not to_extract:
        print("🎉  All videos have already been extracted. Nothing to do.")
        print("    Use --force to re-extract them anyway.")
        sys.exit(0)

    already_done = [e for e in entries if e["done"] and not args.force]
    print(f"▶️   Will extract {len(to_extract)} video(s).", end="")
    if already_done:
        print(f"  Skipping {len(already_done)} already-extracted.")
    else:
        print()
    print()

    # ── Build extra args for the runner ─────────────────────────────────────
    extra_args = ["--output-dir", str(output_dir)]
    if args.no_cleanup:
        extra_args.append("--no-cleanup")
    if args.no_cookie_refresh:
        extra_args.append("--no-cookie-refresh")
    if args.force:
        extra_args.append("--force")

    # ── Run extractions ──────────────────────────────────────────────────────
    results = {"success": [], "failed": [], "skipped": [e for e in entries if e["done"] and not args.force]}
    start_all = time.time()

    for i, entry in enumerate(to_extract, 1):
        print(f"\n[{i}/{len(to_extract)}] Starting extraction...")
        ok = run_extraction(entry, args.cdp_port, extra_args)
        if ok:
            results["success"].append(entry)
        else:
            results["failed"].append(entry)
            print(f"\n  ❌ Extraction FAILED for: {entry['label'] or entry['video_id']}")
            print( "     Continuing with next video...")

    elapsed = time.time() - start_all

    # ── Final summary ────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print(f"  🏁  BATCH COMPLETE  —  Total time: {elapsed/60:.1f} min")
    print(f"      ✅ Extracted:      {len(results['success'])}")
    print(f"      ⏭️  Already done:   {len(results['skipped'])}")
    print(f"      ❌ Failed:         {len(results['failed'])}")
    print("=" * 72)

    if results["success"]:
        print("\n  Successfully extracted:")
        for e in results["success"]:
            existing = find_existing_extraction(e["video_id"], output_dir)
            fname = existing.name if existing else "(?)"
            print(f"    ✅  {fname}")

    if results["failed"]:
        print("\n  Failed (retry individually):")
        for e in results["failed"]:
            print(f"    ❌  {e['label'] or e['video_id']}")
            print(f"        {e['url']}")

    print()
    sys.exit(1 if results["failed"] else 0)


if __name__ == "__main__":
    main()
