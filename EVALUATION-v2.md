# NotebookLM MCP Pipeline — Evaluation v2

## Test Run Trace (Feb 16, 2026)

| Step | Call | Wall Time | Context Cost | Notes |
|------|------|-----------|-------------|-------|
| 1 | `check_auth_status` | ~2s | 50 chars | ✅ Fast, lightweight |
| 2 | `notebook_add_local_files` (5 files, 344KB) | ~15s | 200 chars | ✅ **No context consumed** — reads from disk |
| 3 | 5× `notebook_query` (parallel) | ~45s | **25KB** | ⚠️ Serialized by mutex; full answers transit context |
| 4 | 5× `view_file` (read output.txt) | ~3s | **25KB** (again) | ❌ Redundant — answers are re-read from disk |
| 5 | 2× `write_to_file` (manual) | ~2s | **10KB** | ❌ Manually copying answer text to .md |
| 6 | 3× `save_digests.py` (script) | ~3s | 100 chars | ✅ Automated conversion |
| **Total** | | **~70s** | **~60KB** | |

## Bottleneck Analysis

### 🔴 Critical: Context Window Waste (Steps 3→4→5)

The **biggest problem** is that each 4-6KB digest answer transits through the agent
context **three times**:

1. **Step 3**: MCP tool returns answer JSON (~5KB per doc) → saved to output.txt by system
2. **Step 4**: Agent calls `view_file` to read the output.txt → 5KB loaded again
3. **Step 5**: Agent calls `write_to_file` with the answer text → 5KB written out

For 5 documents: 5 × 5KB × 3 passes = **75KB of context burned** on pass-through text
that the agent doesn't analyze — it just moves it from A to B.

For a 50-document batch, this would be **750KB of pure overhead** — likely exceeding the
context window and causing truncation.

**Root cause**: No tool exists that queries NotebookLM AND saves the result directly to
disk. The agent must act as a middleman.

### 🟡 Moderate: Mutex Serialization (Step 3)

The lazy-mcp proxy serializes all stdio calls through a per-server mutex:

```go
mutex := registry.GetClientMutex(serverName)
mutex.Lock()
defer mutex.Unlock()
```

Even though 5 queries are fired "in parallel," they execute sequentially:
- Query 1: 0-15s (executing)
- Query 2: 15-30s (waited 15s for mutex, then executing)
- Query 3: 30-45s (waited 30s for mutex, then executing)
- Query 4: 45-60s (waited 45s for mutex, timeout risk!)
- Query 5: 60-75s (waited 60s for mutex, high timeout risk!)

With the 120s global timeout, parallel queries to the same server are limited to
~8 queries before timeout (120s / 15s avg per query).

**Root cause**: Stdio is inherently single-channel. This is a transport limitation,
not a bug. But it means "parallel" calls are an illusion for same-server tools.

### 🟡 Moderate: batch query timeout (notebook_query_batch)

The `notebook_query_batch` tool — designed to fix the multi-turn problem — itself
timed out during testing. It runs all queries sequentially inside a single MCP call,
so the total time = N × per-query-time. For 5 queries × 15s = 75s minimum, which
is within 120s but was not within the original 30s.

With the 120s fix, `notebook_query_batch` should work for up to ~7 queries. But for
larger batches (10+ docs), it will need chunking or a longer timeout.

### 🟢 Minor: Script Discovery Friction (Step 6)

The `save_digests.py` script requires knowing the output.txt path from the Antigravity
brain directory — an internal system path that changes per conversation. This makes
the script impractical for automated workflows.

## Optimization Plan

### Optimization 1: `notebook_query_save` tool [HIGH IMPACT]

**New tool** that queries AND saves the result to disk in one step.
The answer never transits through the agent context.

```python
@mcp.tool()
def notebook_query_save(
    notebook_id: str,
    query: str,
    output_path: str,
    source_ids: list[str] | None = None,
) -> dict:
    """Query notebook and save answer directly to a .md file on disk."""
```

Returns only metadata: `{"status": "success", "output_path": "...", "size_bytes": 4509}`

**Impact**: Eliminates 75KB of context waste for 5 docs. Reduces 3 steps to 1.

### Optimization 2: `notebook_digest_pipeline` tool [HIGHEST IMPACT]

**Single tool** that does the ENTIRE pipeline:
1. Adds files from disk as sources
2. Queries each source for a digest
3. Saves each digest to an output directory

```python
@mcp.tool()
def notebook_digest_pipeline(
    notebook_id: str,
    file_paths: list[str],
    output_dir: str,
    query_template: str = DEFAULT_DIGEST_QUERY,
    titles: list[str] | None = None,
) -> dict:
    """Full pipeline: add files → query each → save digests to disk."""
```

Reduces the **entire workflow to 2 tool calls**: `check_auth` + `digest_pipeline`.

**Impact**: 20+ agent turns → 2 turns. ~60KB context → ~500 chars.

### Optimization 3: Per-server timeout in lazy-mcp [MEDIUM IMPACT]

Add a `toolTimeout` field to the server config that overrides the global 120s:

```json
"notebooklm": {
    "transportType": "stdio",
    "command": "...",
    "toolTimeout": 300
}
```

**Impact**: Allows `notebook_digest_pipeline` to process larger batches without
timeout. Other servers keep the safe 120s default.

## Implementation Priority

| # | Optimization | Impact | Effort | Status |
|---|-------------|--------|--------|--------|
| 1 | `notebook_query_save` | High | Low | To implement |
| 2 | `notebook_digest_pipeline` | Highest | Medium | To implement |
| 3 | Per-server `toolTimeout` in proxy | Medium | Low | To implement |
