"""Extract cookies from Chrome CDP and save to auth cache."""
import sys, os, time
sys.path.insert(0, "src")
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

from notebooklm_mcp.auth_cli import (
    get_chrome_pages, get_page_cookies, get_page_html,
    CDP_DEFAULT_PORT, extract_session_id_from_html
)
from notebooklm_mcp.auth import (
    AuthTokens, extract_csrf_from_page_source,
    save_tokens_to_cache, validate_cookies
)

pages = get_chrome_pages(CDP_DEFAULT_PORT)
nb_page = next((p for p in pages if "notebooklm.google.com" in p.get("url", "")), None)

if not nb_page:
    print("ERROR: No NotebookLM page found in Chrome CDP pages:")
    for p in pages[:10]:
        print(f"  {p.get('title', '?')[:60]} | {p.get('url', '?')[:80]}")
    sys.exit(1)

print(f"Found: {nb_page.get('title', '?')[:60]}")
ws_url = nb_page.get("webSocketDebuggerUrl")
cookies_list = get_page_cookies(ws_url)
cookies = {c["name"]: c["value"] for c in cookies_list}
print(f"Extracted {len(cookies)} cookies")

if not validate_cookies(cookies):
    print("ERROR: Missing required cookies")
    sys.exit(1)

html = get_page_html(ws_url)
csrf_token = extract_csrf_from_page_source(html) or ""
session_id = extract_session_id_from_html(html)
print(f"CSRF: {bool(csrf_token)}, Session: {bool(session_id)}")

tokens = AuthTokens(
    cookies=cookies, csrf_token=csrf_token,
    session_id=session_id, extracted_at=time.time()
)
save_tokens_to_cache(tokens, silent=False)
print("AUTH SAVED OK")
