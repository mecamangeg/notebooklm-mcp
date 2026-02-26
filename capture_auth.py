"""
NotebookLM auth capture using a PERSISTENT Chrome profile.

First run: browser opens and you log in → profile saved permanently.
Future runs: browser auto-logs in silently → cookies refreshed in ~10s.
No manual login ever needed again unless Google explicitly signs you out.

Usage:
  python capture_auth.py              # headless after first login
  python capture_auth.py --headed     # show browser (for debugging)
  python capture_auth.py --force-login # force headed mode to re-login
"""
import asyncio
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, "src")

from patchright.async_api import async_playwright
from notebooklm_mcp.auth import (
    AuthTokens, extract_csrf_from_page_source,
    save_tokens_to_cache, validate_cookies,
)
from notebooklm_mcp.auth_cli import extract_session_id_from_html

# ── Config ─────────────────────────────────────────────────────────────────
# Dedicated persistent profile — survives across runs, keeps Google login
PROFILE_DIR = Path.home() / ".notebooklm-mcp" / "chrome-profile"
NB_HOME     = "https://notebooklm.google.com"
TARGET_NB   = "https://notebooklm.google.com/notebook/117e47ed-6385-4dc5-9abc-1bf57588a263"
POLL_SECS   = 2
LOGIN_TIMEOUT = 300   # 5 min for initial login
SILENT_TIMEOUT = 30   # 30s for silent refresh (already logged in)


async def main(headed: bool, force_login: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    profile_exists = any(PROFILE_DIR.iterdir()) if PROFILE_DIR.exists() else False

    # If profile exists and not forcing, try a fast silent refresh first
    silent_mode = profile_exists and not force_login

    pw = await async_playwright().start()

    print(f"\n{'='*60}")
    print("NotebookLM Auth Capture (persistent profile)")
    print(f"Profile: {PROFILE_DIR}")
    print(f"Mode: {'silent refresh' if silent_mode else 'initial login (headed)'}")
    print(f"{'='*60}\n")

    # Always use the persistent context — this is what keeps you logged in
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=(silent_mode and not headed),
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--remote-allow-origins=*",
        ],
    )

    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    timeout = SILENT_TIMEOUT if silent_mode else LOGIN_TIMEOUT

    if not silent_mode:
        print("➡  Browser opened. Please LOG IN to your Google account.")
        print(f"   The browser will remember your login for all future runs.")
        print(f"   (timeout: {timeout}s)\n")

    await page.goto(NB_HOME, wait_until="domcontentloaded", timeout=60000)

    # Poll until logged in (NotebookLM loads, not accounts.google.com)
    deadline = time.time() + timeout
    logged_in = False

    while time.time() < deadline:
        url = page.url
        cookies_list = await ctx.cookies()
        cookies = {c["name"]: c["value"] for c in cookies_list}

        has_auth = any(k in cookies for k in ("SID", "__Secure-1PSID", "SSID"))
        on_nb = "notebooklm.google.com" in url
        not_login_page = "accounts.google.com" not in url

        if has_auth and on_nb and not_login_page:
            logged_in = True
            print(f"✅ Authenticated! ({len(cookies)} cookies captured)")
            break

        if silent_mode:
            remaining = int(deadline - time.time())
            print(f"\r  Silent refresh... {remaining}s | {url[:55]!r}", end="", flush=True)
        else:
            remaining = int(deadline - time.time())
            print(f"\r  Waiting for login... {remaining}s | {url[:50]!r}", end="", flush=True)

        await asyncio.sleep(POLL_SECS)

    if not logged_in:
        if silent_mode:
            print("\n⚠️  Silent refresh timed out — switching to headed mode for login...")
            await ctx.close()
            await pw.stop()
            # Retry in headed mode
            await main(headed=True, force_login=True)
            return
        else:
            print("\n❌ Login timed out. Please try again.")
            await ctx.close()
            await pw.stop()
            sys.exit(1)

    # Navigate to the target notebook to get CSRF token from page source
    print(f"\nFetching CSRF from target notebook...")
    await page.goto(TARGET_NB, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(2)

    # Capture final cookies + extract CSRF/session
    cookies_list = await ctx.cookies()
    cookies = {c["name"]: c["value"] for c in cookies_list}

    html = await page.content()
    csrf_token  = extract_csrf_from_page_source(html) or ""
    session_id  = extract_session_id_from_html(html) or ""

    print(f"  Total cookies: {len(cookies)}")
    print(f"  CSRF found: {bool(csrf_token)}")
    print(f"  Session ID: {session_id[:40]!r}...")

    if not validate_cookies(cookies):
        print("⚠️  Warning: some expected cookies missing — saving anyway.")

    tokens = AuthTokens(
        cookies=cookies,
        csrf_token=csrf_token,
        session_id=session_id,
        extracted_at=time.time(),
    )
    save_tokens_to_cache(tokens, silent=False)

    print("\n✅ AUTH SAVED — NotebookLM MCP authenticated!")
    print("   Run this script any time cookies expire (usually hours→days).")
    print("   No login needed on future runs — Google remembers this profile.")

    if not silent_mode or headed:
        await asyncio.sleep(4)

    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NotebookLM persistent auth capture")
    parser.add_argument("--headed",      action="store_true", help="Always show browser")
    parser.add_argument("--force-login", action="store_true", help="Force re-login even if profile exists")
    args = parser.parse_args()
    asyncio.run(main(headed=args.headed, force_login=args.force_login))
