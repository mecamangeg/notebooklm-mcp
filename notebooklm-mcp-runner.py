"""Process e-SCRA cases via the notebook_digest_multi pipeline.

Usage:
  python notebooklm-mcp-runner.py --volume Volume_001
  python notebooklm-mcp-runner.py --all  (Iterates through all Volumes numerically)
  python notebooklm-mcp-runner.py --all --start-at Volume_050  (Skip volumes before 050)

Auth resilience (v2):
  - Thread-safe auth recovery: when any notebook thread detects expired auth,
    ONE thread refreshes cookies via Chrome CDP while others wait, then all
    resume with fresh credentials.
  - Per-volume retry: volumes with >50% failure get automatically retried
    up to --max-retries times with a cookie refresh between each attempt.
  - Proactive refresh: cookies are refreshed every N volumes (default: 5)
    or every M seconds (default: 600) to prevent expiration in the first place.
  - Chrome must be open with NotebookLM loaded for CDP cookie extraction.
"""
import json
import logging
import os
import sys
import time
import argparse
import re
import traceback
from pathlib import Path

# Add source to path so we can import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Logging Setup ─────────────────────────────────────────────────
# Console: INFO level (clean progress output)
# File: DEBUG level (full tracebacks for post-mortem analysis)
LOG_DIR = Path.home() / ".notebooklm-mcp"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "runner.log"

logger = logging.getLogger("notebooklm_runner")
logger.setLevel(logging.DEBUG)

# File handler — DEBUG level, append mode, with tracebacks
_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logger.addHandler(_fh)

# Console handler — INFO level, compact format
_ch = logging.StreamHandler(sys.stderr)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_ch)

# Also configure the server logger to use our file handler
logging.getLogger("notebooklm_mcp.server").setLevel(logging.DEBUG)
logging.getLogger("notebooklm_mcp.server").addHandler(_fh)
logging.getLogger("notebooklm_mcp.server").addHandler(_ch)

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
MAX_VOLUME_RETRIES = 3         # Retry a failed volume up to N times

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
        from notebooklm_mcp import server
        server.reset_client()

        _last_refresh_time = time.time()
        print(f"  [auto-refresh] ✅ Cookies refreshed ({len(cookies)} cookies, CSRF={'yes' if csrf_token else 'no'})")
        return True

    except Exception as e:
        logger.error("[auto-refresh] Cookie refresh failed", exc_info=True)
        print(f"  [auto-refresh] ⚠️ Failed: {e}", file=sys.stderr)
        return False


def _auth_recovery_callback():
    """Auth recovery callback registered with the server module.

    This is invoked BY pipeline threads when they detect auth expiration.
    It refreshes cookies from Chrome CDP and resets the server's client.
    Thread-safe coordination is handled by the server module — only one
    thread at a time will invoke this callback.
    """
    print("\n  🔑 [mid-flight auth recovery] Thread detected expired auth, refreshing...", file=sys.stderr)
    success = silent_refresh_cookies()
    if success:
        print("  🔑 [mid-flight auth recovery] ✅ Done — threads will resume with fresh auth", file=sys.stderr)
    else:
        print("  🔑 [mid-flight auth recovery] ❌ Could not refresh from Chrome", file=sys.stderr)
    return success


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
        logger.debug("_is_digest_valid failed for %s", filepath, exc_info=True)
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

def process_directory(src_dir, out_dir, label, max_retries=MAX_VOLUME_RETRIES):
    """Process a single volume directory with automatic retry on failure.

    Returns the result dict or None.
    """
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

    # ── Retry loop: retry the volume if there are failures ──
    best_result = None

    for attempt_num in range(1, max_retries + 1):
        # Re-check completion before each attempt (digests accumulate on disk)
        if attempt_num > 1:
            valid_existing, total = _count_valid_digests(out_dir, files)
            if valid_existing >= total:
                print(f"  ✅ All {total} digests complete after retry!")
                return {"status": "success", "summary": {"total": total, "skipped": total, "failed": 0}}
            print(f"\n  🔄 Retry {attempt_num}/{max_retries} for {label} "
                  f"({valid_existing}/{total} done, {total - valid_existing} remaining)")

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
        saved = summary.get("digests_saved", 0)

        attempt_label = f"Attempt {attempt_num}" if attempt_num > 1 else "Result"
        print(f"\n  {attempt_label}: {status}")
        print(f"  Saved: {saved}/{summary.get('total', '?')}")
        print(f"  Failed: {failed}")
        print(f"  Elapsed: {elapsed:.1f}s ({summary.get('queries_per_minute', 0):.1f} q/min)")

        # Print progress log (last 30 lines)
        logs = result.get("progress_log", [])
        if len(logs) > 30:
            print(f"    ... {len(logs)-30} logs hidden ...")
            for line in logs[-30:]:
                print(f"    {line}")
        else:
            for line in logs:
                print(f"    {line}")

        best_result = result

        # ── Decide whether to retry ──
        if failed == 0:
            break  # All files succeeded or were skipped — done!

        # Only retry if there were significant failures (>20% failure rate)
        failure_rate = failed / max(summary.get("total", 1), 1)
        if failure_rate < 0.05:
            print(f"  ℹ️ Only {failed} failures ({failure_rate:.0%}) — accepting result.")
            break

        if attempt_num < max_retries:
            # Proactive cookie refresh before retry
            print(f"\n  ⚠️ {failed} file(s) failed ({failure_rate:.0%}). Refreshing cookies before retry...")
            if silent_refresh_cookies():
                print(f"  ✅ Cookies refreshed. Retrying in 3s...")
                time.sleep(3)  # Brief cooldown before retry
            else:
                print(f"  ⚠️ Cookie refresh failed — retrying anyway (threads will attempt recovery)...")
                time.sleep(2)
        else:
            print(f"\n  ⚠️ {failed} file(s) still failed after {max_retries} attempts.")

    return best_result


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
    parser.add_argument("--max-retries", type=int, default=MAX_VOLUME_RETRIES,
                        help=f"Max retry attempts per volume (default: {MAX_VOLUME_RETRIES})")

    args = parser.parse_args()
    refresh_interval = args.refresh_every
    max_retries = args.max_retries

    # ── Register auth-recovery callback with server module ──
    # This lets pipeline threads trigger cookie refresh mid-flight
    from notebooklm_mcp.server import set_auth_recovery_callback
    set_auth_recovery_callback(_auth_recovery_callback)
    print("✅ Auth recovery callback registered (threads can self-heal)")

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
        print(f"Auto-refresh: every {refresh_interval} volumes or {REFRESH_INTERVAL_SECONDS}s")
        print(f"Max retries per volume: {max_retries}\n")

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
            result = process_directory(src, dst, vol, max_retries=max_retries)
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
        process_directory(src, dst, args.volume, max_retries=max_retries)
    else:
        parser.print_help()


if __name__ == "__main__":
    logger.info("Runner started, log file: %s", LOG_FILE)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        print("\n\nInterrupted! Progress saved to disk. Re-run to resume.")
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL ERROR", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
