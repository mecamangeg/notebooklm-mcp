"""Process e-SCRA cases via the notebook_digest_multi pipeline.

Usage: 
  python notebooklm-mcp-runner.py --volume Volume_001
  python notebooklm-mcp-runner.py --all  (Iterates through all Volumes numerically)
  python notebooklm-mcp-runner.py --all --start-at Volume_050  (Skip volumes before 050)

Auto-refresh: Cookies are silently re-extracted from Chrome every
REFRESH_INTERVAL_VOLUMES volumes (default: 5) to prevent auth expiration
during long batch runs. Chrome must be open with NotebookLM loaded.
"""
import json
import os
import sys
import time
import argparse
import re
import traceback

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

# Paths
ESCRA_ROOT = r"C:\PROJECTS\e-scra\MARKDOWN"
OUTPUT_ROOT = r"C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS"

# Auto-refresh settings
REFRESH_INTERVAL_VOLUMES = 5   # Re-extract cookies every N volumes
REFRESH_INTERVAL_SECONDS = 600 # Or every 10 minutes, whichever comes first

# ── Cookie Auto-Refresh via Chrome DevTools Protocol ──────────────

_last_refresh_time = None  # None until first refresh/timer start


def silent_refresh_cookies():
    """Re-extract cookies from Chrome via CDP and update the auth cache.

    This is a zero-interaction operation — Chrome must already be open
    with NotebookLM loaded (which it is, since notebooklm-mcp-auth
    launched it). We just reach into Chrome and grab fresh cookies.

    Returns True if refresh succeeded, False otherwise.
    """
    global _last_refresh_time

    try:
        from notebooklm_mcp.auth_cli import (
            get_chrome_pages,
            get_page_cookies,
            get_page_html,
            CDP_DEFAULT_PORT,
        )
        from notebooklm_mcp.auth import (
            AuthTokens,
            extract_csrf_from_page_source,
            save_tokens_to_cache,
            validate_cookies,
        )

        # Find NotebookLM page in Chrome
        pages = get_chrome_pages(CDP_DEFAULT_PORT)
        nb_page = None
        for page in pages:
            if "notebooklm.google.com" in page.get("url", ""):
                nb_page = page
                break

        if not nb_page:
            print("  [auto-refresh] No NotebookLM page found in Chrome", file=sys.stderr)
            return False

        ws_url = nb_page.get("webSocketDebuggerUrl")
        if not ws_url:
            print("  [auto-refresh] No WebSocket URL for page", file=sys.stderr)
            return False

        # Extract cookies
        cookies_list = get_page_cookies(ws_url)
        cookies = {c["name"]: c["value"] for c in cookies_list}

        if not validate_cookies(cookies):
            print("  [auto-refresh] Missing required cookies", file=sys.stderr)
            return False

        # Extract CSRF token
        html = get_page_html(ws_url)
        csrf_token = extract_csrf_from_page_source(html) or ""

        # Extract session ID
        from notebooklm_mcp.auth_cli import extract_session_id_from_html
        session_id = extract_session_id_from_html(html)

        # Save fresh tokens
        tokens = AuthTokens(
            cookies=cookies,
            csrf_token=csrf_token,
            session_id=session_id,
            extracted_at=time.time(),
        )
        save_tokens_to_cache(tokens, silent=True)

        # Force the server module to reload its client with fresh cookies
        _reload_client()

        _last_refresh_time = time.time()
        print(f"  [auto-refresh] ✅ Cookies refreshed ({len(cookies)} cookies, CSRF={'yes' if csrf_token else 'no'})")
        return True

    except Exception as e:
        print(f"  [auto-refresh] ⚠️ Failed: {e}", file=sys.stderr)
        return False


def _reload_client():
    """Force the server module to create a new client with fresh cookies."""
    try:
        from notebooklm_mcp import server
        # Reset the cached client so next call creates a fresh one
        server._client = None
    except Exception:
        pass


def should_refresh(volumes_since_refresh):
    """Check if it's time for a proactive cookie refresh."""
    if volumes_since_refresh >= REFRESH_INTERVAL_VOLUMES:
        return True
    if _last_refresh_time is not None and (time.time() - _last_refresh_time) > REFRESH_INTERVAL_SECONDS:
        return True
    return False


# ── Digest Validation (mirrors server's _is_digest_valid) ─────────

def _is_digest_valid(filepath):
    """Check if a digest file is complete and well-formed.

    Mirrors the validation logic in notebook_digest_multi so that the
    runner's skip logic matches what the server would do internally.
    """
    try:
        if not os.path.exists(filepath):
            return False
        size = os.path.getsize(filepath)
        if size < 500:  # Minimum viable digest is ~500 bytes
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Must contain at least 2 of these structural markers
        markers = 0
        for marker in ["CAPTION", "FACTS", "ISSUE", "RULING"]:
            if marker in content.upper():
                markers += 1
        return markers >= 2
    except Exception:
        return False


def _count_valid_digests(out_dir, files):
    """Count how many source files already have valid digests in out_dir.

    Returns (valid_count, total_checked) so we can report accurate progress.
    """
    if not os.path.isdir(out_dir):
        return 0, len(files)

    valid = 0
    for f in files:
        title = os.path.splitext(os.path.basename(f))[0]
        safe_title = "".join(
            c if c.isalnum() or c in " .-_()," else "_"
            for c in title
        ).strip()
        digest_path = os.path.join(out_dir, f"{safe_title}-case-digest.md")
        if _is_digest_valid(digest_path):
            valid += 1

    return valid, len(files)


# ── Processing Logic ──────────────────────────────────────────────

def process_directory(src_dir, out_dir, label):
    """Process a single volume directory. Returns the result dict or None."""
    if not os.path.isdir(src_dir):
        print(f"ERROR: {src_dir} not found")
        return None

    files = sorted([
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".md")
    ])

    if not files:
        print(f"  {label}: no .md files found")
        return None

    # Content-validated skip check (matches server's _is_digest_valid)
    valid_existing, total = _count_valid_digests(out_dir, files)

    print(f"\n{'='*60}")
    print(f"  Processing {label}")
    print(f"  {total} files found, {valid_existing} valid digests already exist")
    print(f"  Source: {src_dir}")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}")

    if valid_existing >= total:
        print(f"  SKIP — all {total} already complete (content-validated)")
        return {"status": "skipped", "summary": {"total": total, "skipped": total, "failed": 0}}

    # Import here to avoid loading everything at startup
    from notebooklm_mcp.server import notebook_digest_multi

    start = time.time()
    result = notebook_digest_multi.fn(
        notebook_ids=NOTEBOOK_IDS,
        file_paths=files,
        output_dir=out_dir,
    )
    elapsed = time.time() - start

    summary = result.get("summary", {})
    status = result.get("status")
    failed = summary.get("failed", 0)

    print(f"\n  Result: {status}")
    print(f"  Saved: {summary.get('digests_saved', '?')}/{summary.get('total', '?')}")
    print(f"  Failed: {failed}")
    print(f"  Elapsed: {elapsed:.1f}s ({summary.get('queries_per_minute', 0):.1f} q/min)")

    # Print progress log
    logs = result.get("progress_log", [])
    if len(logs) > 30:
        print(f"    ... {len(logs)-30} logs hidden ...")
        for line in logs[-30:]:
            print(f"    {line}")
    else:
        for line in logs:
            print(f"    {line}")

    # If ANY files failed, attempt auto-refresh and retry once.
    # (Previously only triggered on total volume failure — now catches partial failures too)
    if failed > 0:
        new_successes = summary.get("digests_saved", 0) - summary.get("skipped", 0)
        print(f"\n  ⚠️ {failed} file(s) failed (new successes: {new_successes}). Attempting auto-refresh + retry...")
        if silent_refresh_cookies():
            print(f"  🔄 Retrying {label} (only unfinished files will be re-attempted)...")
            start2 = time.time()
            result = notebook_digest_multi.fn(
                notebook_ids=NOTEBOOK_IDS,
                file_paths=files,
                output_dir=out_dir,
            )
            elapsed2 = time.time() - start2
            summary2 = result.get("summary", {})
            print(f"\n  Retry result: {result.get('status')}")
            print(f"  Saved: {summary2.get('digests_saved', '?')}/{summary2.get('total', '?')}")
            print(f"  Failed: {summary2.get('failed', '?')}")
            print(f"  Elapsed: {elapsed2:.1f}s")
        else:
            print(f"  Could not refresh cookies — retry skipped. Failures will persist.")

    return result


def get_volume_number(name):
    # Extracts number from "Volume_123" -> 123
    match = re.search(r'Volume_(\d+)', name)
    return int(match.group(1)) if match else 0


def _format_eta(seconds):
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {int(s)}s"
    else:
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{int(h)}h {int(m)}m"


def main():
    global _last_refresh_time

    parser = argparse.ArgumentParser(description="Process e-SCRA cases via NotebookLM multi-pipeline.")
    parser.add_argument("--volume", help="Specific volume (e.g., Volume_001)")
    parser.add_argument("--all", action="store_true", help="Process all volumes in C:\\PROJECTS\\e-scra\\MARKDOWN")
    parser.add_argument("--start-at", metavar="VOLUME",
                        help="Skip volumes before this one (e.g., --start-at Volume_050)")
    parser.add_argument("--refresh-every", type=int, default=REFRESH_INTERVAL_VOLUMES,
                        help=f"Auto-refresh cookies every N volumes (default: {REFRESH_INTERVAL_VOLUMES})")
    
    args = parser.parse_args()
    refresh_interval = args.refresh_every

    # Do an initial refresh to start with the freshest cookies
    print("Performing initial cookie refresh...")
    if silent_refresh_cookies():
        print("Starting with fresh cookies.\n")
    else:
        print("Could not refresh from Chrome — using cached cookies.\n")

    _last_refresh_time = time.time()  # Start the timer

    if args.all:
        # Get all folders named Volume_NNN
        volumes = [d for d in os.listdir(ESCRA_ROOT) if os.path.isdir(os.path.join(ESCRA_ROOT, d)) and d.startswith("Volume_")]
        
        # Sort numerically instead of lexicographically
        volumes.sort(key=get_volume_number)

        # --start-at: skip volumes before the specified one
        if args.start_at:
            start_num = get_volume_number(args.start_at)
            original_count = len(volumes)
            volumes = [v for v in volumes if get_volume_number(v) >= start_num]
            skipped_count = original_count - len(volumes)
            if skipped_count > 0:
                print(f"⏩ --start-at {args.start_at}: skipping {skipped_count} volumes (jumping to {volumes[0] if volumes else 'none'})")

        total_volumes = len(volumes)
        print(f"Found {total_volumes} volumes to process.")
        print(f"Auto-refresh: every {refresh_interval} volumes or {REFRESH_INTERVAL_SECONDS}s\n")

        # ── Cross-volume progress tracking ──
        volumes_since_refresh = 0
        batch_start_time = time.time()
        vol_times = []  # Track time per volume for ETA calculation
        total_files_processed = 0
        total_files_failed = 0
        total_files_skipped = 0

        for vol_idx, vol in enumerate(volumes):
            vol_start = time.time()

            # Proactive refresh check
            if should_refresh(volumes_since_refresh):
                print(f"\n  ⏰ Proactive cookie refresh (after {volumes_since_refresh} volumes)...")
                if silent_refresh_cookies():
                    volumes_since_refresh = 0

            src = os.path.join(ESCRA_ROOT, vol)
            dst = os.path.join(OUTPUT_ROOT, vol)
            result = process_directory(src, dst, vol)
            volumes_since_refresh += 1

            # Accumulate stats
            vol_elapsed = time.time() - vol_start
            vol_times.append(vol_elapsed)

            if result and "summary" in result:
                s = result["summary"]
                total_files_processed += s.get("digests_saved", 0) - s.get("skipped", 0)
                total_files_failed += s.get("failed", 0)
                total_files_skipped += s.get("skipped", 0)

            # ── Cross-volume progress report with ETA ──
            completed = vol_idx + 1
            remaining = total_volumes - completed
            overall_elapsed = time.time() - batch_start_time
            avg_time = sum(vol_times) / len(vol_times)
            eta_seconds = avg_time * remaining
            eta_str = _format_eta(eta_seconds) if remaining > 0 else "done"

            print(f"\n  📊 Overall: {completed}/{total_volumes} volumes "
                  f"({total_files_processed} saved, {total_files_skipped} skipped, {total_files_failed} failed) "
                  f"| Elapsed: {_format_eta(overall_elapsed)} | ETA: {eta_str}")

        # Final summary
        total_elapsed = time.time() - batch_start_time
        print(f"\n{'='*60}")
        print(f"  🏁 BATCH COMPLETE")
        print(f"  Volumes processed: {total_volumes}")
        print(f"  New digests saved: {total_files_processed}")
        print(f"  Skipped (already done): {total_files_skipped}")
        print(f"  Failed: {total_files_failed}")
        print(f"  Total time: {_format_eta(total_elapsed)}")
        if vol_times:
            print(f"  Avg time/volume: {_format_eta(sum(vol_times)/len(vol_times))}")
        print(f"{'='*60}")

    elif args.volume:
        src = os.path.join(ESCRA_ROOT, args.volume)
        dst = os.path.join(OUTPUT_ROOT, args.volume)
        process_directory(src, dst, args.volume)
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress saved to disk. Re-run to resume.")
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
