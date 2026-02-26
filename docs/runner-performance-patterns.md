# NotebookLM Runner — Performance Patterns Reference

> **Last updated:** 2026-02-26  
> **Applies to:** All `*-runner.py` scripts in `C:\PROJECTS\notebooklm-mcp\`

All runners share a common optimisation philosophy: **bypass the MCP protocol layer
entirely** by importing `src/notebooklm_mcp` directly as a Python module.
This eliminates the stdin/stdout JSON-RPC round-trip that costs 100–500 ms *per
tool call* before any real API work is done.

The eight patterns below are ordered from most impactful to most situational.

---

## Pattern 1 — Direct Module Import (bypasses ALL MCP overhead)

**Adopted by:** every runner  
**Impact:** eliminates ~100–500 ms per call of subprocess + JSON-RPC overhead

```python
# Add src/ to sys.path so we can import the package directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Then import and call the API client directly — no subprocess, no JSON-RPC
from notebooklm_mcp.server import get_client, notebook_add_text_batch
from notebooklm_mcp.api_client import NotebookLMClient
```

**Why it matters:** When an agent calls a NotebookLM MCP tool through the MCP
protocol it spawns a subprocess, sends JSON over stdin, waits for a JSON reply
over stdout, then deserialises it — all before the actual HTTP request to
Google is made. Importing the module directly skips all of that.

---

## Pattern 2 — `.fn()` Bypass (skip FastMCP wrapper layer)

**Adopted by:** `notebooklm-mcp-runner.py` (line 304), `angular-rag-runner.py` (batch path)  
**Impact:** removes FastMCP's input-validation / Pydantic serialisation overhead per call

```python
# Instead of calling the MCP tool via the protocol:
#   result = mcp.call_tool("notebook_digest_multi", {...})

# Call the underlying Python function directly via FastMCP's .fn attribute:
result = notebook_digest_multi.fn(
    notebook_ids=NOTEBOOK_IDS,
    file_paths=files,
    output_dir=out_dir,
)

# Same for the batch uploader:
result = notebook_add_text_batch.fn(
    notebook_id=notebook_id,
    sources=api_sources,
)
```

**When to use:** Any time you call a FastMCP-decorated function from a runner
script rather than through the MCP protocol. The `.fn` attribute is the raw
decorated function without the MCP validation/serialisation wrapper.

---

## Pattern 3 — Client Singleton Reuse (`get_client()`)

**Adopted by:** every runner  
**Impact:** avoids TLS handshake and auth-token reload on every API call

```python
from notebooklm_mcp.server import get_client

# get_client() is thread-safe and returns a cached httpx client.
# The connection pool is reused across all calls in the same process.
client = get_client()

# Use it for multiple operations — pool stays warm
client.add_text_source(notebook_id, text=content, title=title)
client.delete_source(old_source_id)
client.query(notebook_id, query_text="...")
```

**Implementation note:** `reset_client()` (also from `server`) forces the
singleton to be recreated with fresh credentials after a cookie refresh.

---

## Pattern 4 — Batch RPC (one call for N sources)

**Adopted by:** `angular-rag-runner.py`, `notebooklm-mcp-runner.py` (15-notebook parallel),  
`sft-accounting-runner.py`  
**Impact:** reduces N sequential round-trips to 1; typically 10× faster than sequential

```python
# BAD: N calls, N round-trips
for source in sources:
    client.add_text_source(notebook_id, text=source["text"], title=source["title"])

# GOOD: 1 call, 1 batchexecute RPC
result = notebook_add_text_batch.fn(
    notebook_id=notebook_id,
    sources=[{"text": s["text"], "title": s["title"]} for s in delta_sources],
)
```

**For digest pipelines:** `notebooklm-mcp-runner.py` uses a different form of
batching — distributing files across **15 notebooks running in parallel threads**,
giving ~15× throughput compared to sequential processing.

---

## Pattern 5 — Disk-Based Skip Logic (content-hash deduplication)

**Adopted by:** every runner  
**Impact:** zero API calls for files that haven't changed since the last run

```python
# Load the upload log once (not per-file)
_log_cache = _load_upload_log(upload_log_path)

for md_path in md_files:
    content = Path(md_path).read_text(encoding="utf-8")
    status, old_source_id = _check_upload_status_loaded(md_path, content, _log_cache)

    if status == "skip":
        continue          # content hash unchanged → no API call needed
    elif status == "update":
        client.delete_source(old_source_id)   # delete stale source
    # status == "new" → fresh upload

    client.add_text_source(notebook_id, text=content, title=title)
    _record_upload(md_path, upload_log_path, source_id, content, _log_cache)
```

**Key detail:** validation checks actual file content (size + structural markers),
not just `os.path.exists()`, to catch truncated or corrupted output files.

---

## Pattern 6 — Lazy Imports (defer heavy dependencies until needed)

**Adopted by:** `notebooklm-mcp-runner.py` (line 287–288), `angular-rag-runner.py`  
**Impact:** `--help`, `--dry-run`, and `--convert-only` pay zero import cost for
CDP/auth stack or the file-scanner machinery

```python
# BAD: loads CDP, httpx, auth stack, file scanner on every run
from angular_rag_core import discover_source_files, build_bundles, refresh_cookies
from notebooklm_mcp.server import get_client

def main():
    args = parse_args()
    if args.convert_only:
        convert_project(...)   # only this branch needed

# GOOD: import inside the function that actually uses it
_core = None

def _load_core():
    global _core
    if _core is None:
        import angular_rag_core as _m
        _core = _m
    return _core

def upload_markdown_files(...):
    from notebooklm_mcp.server import get_client   # only loaded on upload
    ...
```

**Rule of thumb:** any import that touches CDP, httpx, or the file system at
module level should be moved inside the function that first needs it.

---

## Pattern 7 — Auth Recovery Callback (mid-flight cookie refresh without restart)

**Adopted by:** every runner  
**Impact:** process continues after cookie expiry instead of crashing mid-batch

```python
def _auth_recovery_callback() -> bool:
    """Invoked by server.py pipeline threads when they detect expired auth.

    Thread-safe leader election in server.py ensures only ONE thread fires
    this callback even when many threads detect expiry simultaneously.
    """
    success = silent_refresh_cookies()    # reach into Chrome CDP for fresh cookies
    if success:
        from notebooklm_mcp import server
        server.reset_client()             # force singleton to reload with new cookies
    return success

# Register ONCE at startup — before any API calls
from notebooklm_mcp.server import set_auth_recovery_callback
set_auth_recovery_callback(_auth_recovery_callback)
```

**How `server.py` protects against the thundering herd:**
It uses a lock + generation counter so when 15 parallel threads all detect auth
failure at the same instant, only the *first* thread runs the callback; the
others wait, then resume automatically with the refreshed credentials.

---

## Pattern 8 — Proactive Cookie Refresh (prevent expiry before it happens)

**Adopted by:** `notebooklm-mcp-runner.py`, `angular-rag-runner.py`, `sft-accounting-runner.py`,  
`syllabi-runner.py`  
**Impact:** avoids the cost of a failed API call + exponential backoff + retry

```python
REFRESH_INTERVAL_UPLOADS = 15   # refresh every N uploads
REFRESH_INTERVAL_SECONDS = 600  # or every 10 minutes, whichever comes first

_last_refresh_time: float = 0.0

def should_refresh(uploads_since_refresh: int) -> bool:
    if uploads_since_refresh >= REFRESH_INTERVAL_UPLOADS:
        return True
    if _last_refresh_time > 0 and (time.time() - _last_refresh_time) > REFRESH_INTERVAL_SECONDS:
        return True
    return False

# In the upload loop:
for i, md_path in enumerate(md_files):
    if should_refresh(uploads_since_refresh):
        silent_refresh_cookies()
        uploads_since_refresh = 0
    # ... do work ...
    uploads_since_refresh += 1
```

**Why proactive beats reactive:** a reactive approach (refresh after a 401)
means you've already wasted one failed HTTP round-trip + backoff time before
recovery begins. Proactive refresh takes ~0.5 s and happens during idle time
between uploads.

---

## Pattern Adoption Matrix

| Pattern | `mcp-runner` | `angular-rag` | `youtube-context` | `sft-accounting` | `syllabi` |
|---|:---:|:---:|:---:|:---:|:---:|
| 1. Direct module import | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2. `.fn()` bypass | ✅ | ✅ | ❌ | ❌ | ❌ |
| 3. Client singleton reuse | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4. Batch RPC / parallelism | ✅ | ✅ | ❌ | ❌ | ❌ |
| 5. Disk skip / content-hash | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6. Lazy imports | ✅ | ✅ | ❌ | ❌ | ❌ |
| 7. Auth recovery callback | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8. Proactive cookie refresh | ✅ | ✅ | ❌ | ✅ | ✅ |

> `notebooklm-mcp-runner.py` is the reference implementation — it applies every
> pattern and is the most battle-tested for long-running batch workflows.

---

## Quick-Start Checklist for a New Runner

When writing a new runner from scratch, apply these in order:

- [ ] `sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))` at top
- [ ] All heavy imports (`angular_rag_core`, `notebooklm_mcp`) inside functions, not at module level
- [ ] `from notebooklm_mcp.server import get_client` inside the function that uploads/queries
- [ ] Use `notebook_add_text_batch.fn(...)` for multiple sources, never loop `add_text_source`
- [ ] Load `upload_log_path` once with `_load_upload_log()`, pass cache dict to per-file checks
- [ ] Register `set_auth_recovery_callback(_auth_recovery_callback)` at startup
- [ ] In `_auth_recovery_callback`, call `server.reset_client()` after `silent_refresh_cookies()`
- [ ] Implement `should_refresh(n)` and check it in the main loop

---

## Related Files

| File | Role |
|------|------|
| `src/notebooklm_mcp/server.py` | FastMCP tool definitions, `get_client()`, `reset_client()`, auth recovery leader election |
| `src/notebooklm_mcp/api_client.py` | Raw `batchexecute` RPC implementation, httpx client |
| `src/notebooklm_mcp/auth.py` | `AuthTokens`, `save_tokens_to_cache`, `validate_cookies` |
| `src/notebooklm_mcp/auth_cli.py` | CDP helpers: `get_chrome_pages`, `get_page_cookies`, `launch_chrome` |
| `angular_rag_core.py` | Shared file-scanner, bundler, markdown generator, content-hash log |
| `angular-rag-runner.py` | Convert + batch upload + query, all 8 patterns applied |
| `notebooklm-mcp-runner.py` | Reference implementation: 15-notebook parallel digest pipeline |
| `youtube-context-runner.py` | Sequential multi-query extraction (conversation context threading) |
| `sft-accounting-runner.py` | Sequential Q&A with intent classification and backoff |
| `syllabi-runner.py` | 15-notebook parallel syllabi generation for Philippine SC cases |
