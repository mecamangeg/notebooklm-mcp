"""Process e-SCRA cases via the notebook_digest_multi pipeline.

Usage: 
  python notebooklm-mcp-runner.py --volume Volume_001
  python notebooklm-mcp-runner.py --all  (Iterates through all Volumes numerically)

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

_last_refresh_time = 0


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
    if _last_refresh_time and (time.time() - _last_refresh_time) > REFRESH_INTERVAL_SECONDS:
        return True
    return False


# ── Processing Logic ──────────────────────────────────────────────

def process_directory(src_dir, out_dir, label):
    if not os.path.isdir(src_dir):
        print(f"ERROR: {src_dir} not found")
        return

    files = sorted([
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".md")
    ])

    if not files:
        print(f"  {label}: no .md files found")
        return

    # Check existing digests
    existing = 0
    if os.path.isdir(out_dir):
        existing = len([f for f in os.listdir(out_dir) if f.endswith("-case-digest.md")])

    print(f"\n{'='*60}")
    print(f"  Processing {label}")
    print(f"  {len(files)} files found, {existing} already completed")
    print(f"  Source: {src_dir}")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}")

    if existing >= len(files):
        print(f"  SKIP — all {len(files)} already complete")
        return

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

    # If the whole volume failed, it's likely auth expiration.
    # Attempt auto-refresh and retry once.
    if failed > 0 and summary.get("digests_saved", 0) == summary.get("skipped", 0):
        print(f"\n  ⚠️ Entire volume failed — likely auth expiration. Attempting auto-refresh...")
        if silent_refresh_cookies():
            print(f"  🔄 Retrying {label}...")
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

    return result


def get_volume_number(name):
    # Extracts number from "Volume_123" -> 123
    match = re.search(r'Volume_(\d+)', name)
    return int(match.group(1)) if match else 0


def main():
    global _last_refresh_time

    parser = argparse.ArgumentParser(description="Process e-SCRA cases via NotebookLM multi-pipeline.")
    parser.add_argument("--volume", help="Specific volume (e.g., Volume_001)")
    parser.add_argument("--all", action="store_true", help="Process all volumes in C:\\PROJECTS\\e-scra\\MARKDOWN")
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

    _last_refresh_time = time.time()  # Reset timer regardless

    if args.all:
        # Get all folders named Volume_NNN
        volumes = [d for d in os.listdir(ESCRA_ROOT) if os.path.isdir(os.path.join(ESCRA_ROOT, d)) and d.startswith("Volume_")]
        
        # Sort numerically instead of lexicographically
        volumes.sort(key=get_volume_number)
        
        print(f"Found {len(volumes)} volumes. Starting recursive processing...")
        print(f"Auto-refresh: every {refresh_interval} volumes or {REFRESH_INTERVAL_SECONDS}s\n")

        volumes_since_refresh = 0
        for vol in volumes:
            # Proactive refresh check
            if should_refresh(volumes_since_refresh):
                print(f"\n  ⏰ Proactive cookie refresh (after {volumes_since_refresh} volumes)...")
                if silent_refresh_cookies():
                    volumes_since_refresh = 0

            src = os.path.join(ESCRA_ROOT, vol)
            dst = os.path.join(OUTPUT_ROOT, vol)
            process_directory(src, dst, vol)
            volumes_since_refresh += 1
            
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
        import traceback
        traceback.print_exc()
        sys.exit(1)
