# Known Issues and Fragility

This document describes known limitations and potential failure points in the NotebookLM MCP. Since this project uses reverse-engineered internal APIs, certain breakages are expected over time.

---

## 1. Hardcoded `bl` Version String

### What it is
The `bl` (build label) parameter is a frontend version identifier required by NotebookLM's batchexecute API. It looks like:
```
boq_labs-tailwind-frontend_20251221.14_p0
```

### When it breaks
Google deploys new frontend versions periodically. When this happens, the hardcoded `bl` value may become stale. Symptoms:
- API calls return errors or unexpected responses
- Operations that previously worked start failing

### How to fix
Set the `NOTEBOOKLM_BL` environment variable to override the default:

```bash
export NOTEBOOKLM_BL="boq_labs-tailwind-frontend_YYYYMMDD.XX_p0"
```

To find the current value:
1. Open Chrome DevTools on `notebooklm.google.com`
2. Go to Network tab
3. Find any request to `/_/LabsTailwindUi/data/batchexecute`
4. Look for the `bl=` parameter in the URL

---

## 2. Cookie Expiration

### What it is
Authentication uses browser cookies extracted from an active Chrome session. These cookies have a limited lifespan.

### When it breaks
Cookies typically expire after 2-4 weeks. CSRF tokens expire much faster (minutes to hours). Symptoms:
- `ValueError: Cookies have expired. Please re-authenticate...`
- API calls redirect to Google login page
- HTTP 401/403 errors mid-run
- Authentication errors on previously working operations

### Auto-Recovery (v2 — implemented in runner + server)

The batch pipeline has **three layers of auth resilience**:

1. **Proactive refresh** (runner level): Cookies are re-extracted from Chrome CDP every 5 volumes or 10 minutes, whichever comes first. Configurable via `--refresh-every`.

2. **Per-volume retry** (runner level): If a volume has >5% failure rate, the runner automatically:
   - Refreshes cookies from Chrome
   - Retries the entire volume (only unfinished files)
   - Up to `--max-retries` attempts (default: 3)

3. **Mid-flight thread recovery** (server level): When any of the 15 notebook threads detects an auth error during `add_text_source` or `query`:
   - Thread calls `_attempt_auth_recovery()` with leader election
   - First thread to acquire the lock performs recovery via CDP callback
   - Other threads block on the lock; when they enter, they see the updated generation counter and skip
   - All threads then call `get_client()` which returns a fresh client from the new cached tokens
   - The failed operation is retried with the new client

### Manual fix (if auto-recovery fails)
Re-extract fresh cookies manually:

**Option A: notebooklm-mcp-auth CLI (recommended)**

```bash
notebooklm-mcp-auth
```

If Chrome is not running, it will be launched automatically. If you're not logged in, the CLI waits for you to complete login in the browser window. Tokens are cached to `~/.notebooklm-mcp/auth.json`.

**Option B: Chrome DevTools MCP**

If your AI assistant has Chrome DevTools MCP available:
1. Navigate to `notebooklm.google.com` in Chrome
2. Use Chrome DevTools MCP to extract cookies from any network request
3. Call `save_auth_tokens(cookies=<cookie_header>)`

**Option C: Manual extraction**
1. Open Chrome DevTools on `notebooklm.google.com`
2. Network tab → find any request → copy Cookie header
3. Set `NOTEBOOKLM_COOKIES` environment variable

---

## 3. Rate Limits

### What it is
The free tier of NotebookLM has usage limits enforced server-side.

### Current limits
- ~50 queries per day (approximate, not officially documented)
- Studio content generation may have separate limits

### Symptoms when exceeded
- API returns rate limit errors
- Operations start failing mid-session

### Mitigation
- Space out operations when possible
- Avoid tight polling loops
- Consider batching queries where the API supports it

---

## 4. API Instability (Reverse-Engineered)

### What it is
This MCP uses internal, undocumented APIs that Google can change at any time without notice.

### What can break
- RPC IDs (e.g., `wXbhsf` for list notebooks) may be renamed
- Request/response structure may change
- New required parameters may be added
- Endpoints may be deprecated or moved

### Symptoms
- Parsing errors (unexpected response shape)
- `None` results from previously working operations
- New error messages from the API

### What to do when it breaks
1. Check if the issue is widespread (Google may have deployed changes)
2. Use Chrome DevTools to capture current request/response format
3. Update the relevant RPC handling in `api_client.py`
4. Submit a PR or issue if you discover the fix

---

## 5. CSRF Token and Session ID

### What it is
The MCP auto-extracts CSRF token (`SNlM0e`) and session ID (`FdrFJe`) from the NotebookLM homepage on first use.

### When it breaks
- If the homepage structure changes, extraction may fail
- Tokens are per-session and must be refreshed if the page is not accessible

### Symptoms
- `ValueError: Could not extract CSRF token from page`
- Debug HTML saved to `~/.notebooklm-mcp/debug_page.html`

### How to fix
If auto-extraction fails:
1. Manually extract tokens from Chrome DevTools Network tab
2. Pass them via `save_auth_tokens(cookies=..., request_body=..., request_url=...)`

---

## 6. Batch Pipeline — Resolved Issues (v3)

The following issues were discovered and **resolved** in the v3 pipeline refactor on 2026-02-16:

### 6a. Split Mismatch (RESOLVED)
- **Cause**: Batching 3 cases per query required regex splitting of the combined response. NotebookLM's formatting varied, causing the regex to produce wrong splits (10-30% failure rate).
- **Fix**: Switched to 1:1 architecture (one case per query). No splitting needed. 100% success rate.

### 6b. Truncated/Corrupt Digests Saved (RESOLVED)
- **Cause**: The save logic wrote partial responses to disk. The resume check (`>100 bytes`) then skipped these files, treating them as completed.
- **Fix**: Response validation before save (≥2 structural markers + ≥300 chars). Content-validated resume checks CAPTION/FACTS/ISSUE/RULING markers instead of just file size.

### 6c. Source Leak on Error (RESOLVED)
- **Cause**: If an error occurred after adding a source but before deletion, the source remained in the notebook, slowly filling it up.
- **Fix**: LIFO cleanup moved to `finally` block — source is always deleted regardless of error.

### 6d. Output Directory Race Condition (RESOLVED)
- **Cause**: Cleaning output directory while the pipeline was still writing caused `No such file or directory` errors.
- **Fix**: `os.makedirs(output_dir, exist_ok=True)` ensures directory exists before each save attempt.

---

## 7. `uv tool install` Cache Trap

### What it is
`uv tool install --force` does **NOT** pick up code changes from a local path if the package version hasn't changed. It uses cached build artifacts.

### Symptoms
- Code changes in `server.py` are not reflected after `uv tool install --force`
- The installed version at `C:\Users\Michael\AppData\Roaming\uv\tools\notebooklm-mcp-server\Lib\site-packages\notebooklm_mcp\server.py` still shows old code

### How to fix
**Always use `--reinstall`**:
```powershell
Stop-Process -Name "notebooklm-mcp" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
uv tool install "C:\PROJECTS\notebooklm-mcp" --force --reinstall
```

The `--reinstall` flag forces uv to rebuild from source instead of using cached artifacts.

---

## Reporting Issues

When reporting issues, include:
1. The specific tool/operation that failed
2. The error message (redact any sensitive info)
3. Whether the operation worked before
4. The current date (to correlate with potential Google deployments)
