# NotebookLM MCP — Process Evaluation

**Date:** 2026-02-16
**Scope:** End-to-end evaluation of the NotebookLM MCP integration for batch case digest generation (10 documents)

---

## 1. Architecture Trace

```
Local Files (10 .md) 
    → view_file (read content)
    → lazy-mcp proxy (execute_tool) 
    → notebooklm-mcp.exe (Go binary, stdio)
    → NotebookLM API (reverse-engineered, cookie auth)
    → AI response
    → write_to_file (save digest)
```

**Component Stack:**
| Layer | Technology | Role |
|-------|-----------|------|
| Source files | Local filesystem (.md) | Raw case text |
| Agent orchestrator | Antigravity | Reads files, calls tools, saves output |
| Tool proxy | lazy-mcp (`mcp-proxy.exe`) | Routes `execute_tool` to backend |
| MCP server | `notebooklm-mcp.exe` (Go) | Translates tool calls → NotebookLM HTTP API |
| Backend | Google NotebookLM (web) | AI processing, source indexing |
| Auth | Cookie-based (`save_auth_tokens`) | Session persistence via captured cookies |

---

## 2. Workflow Timeline (Observed)

| Phase | Operations | Parallelism | Turn Count | Wall Time (est.) |
|-------|-----------|-------------|------------|-----------------|
| **A. Setup & discovery** | `get_tools_in_category("notebooklm")` | 1 | 1 | ~5s |
| **B. Read source files** | 10× `view_file` | Parallel (all 10) | 1 | ~3s |
| **C. Add sources** | 10× `notebook_add_text` | **Sequential (1 at a time)** | 10 | ~60-90s |
| **D. Generate digests** | 10× `notebook_query` | **Partial parallel (4+5+1)** | 3 | ~45-60s |
| **E. Save digests** | 10× `write_to_file` | Parallel (5+5) | 2 | ~3s |

**Total estimated: ~120-160s for 10 documents**

---

## 3. Bottlenecks Identified

### 🔴 B1: Sequential Source Addition (CRITICAL)

**Problem:** Each `notebook_add_text` call was made sequentially — one per agent turn. For 10 documents, this means 10 round-trips through the proxy chain.

**Root Cause:** The agent treated each source addition as dependent on the previous one. In reality, `notebook_add_text` calls are **independent** — each simply POSTs content to the notebook. They could all be fired in parallel.

**Impact:** ~60-90 seconds wasted (6-9s per call × 10).

**Fix:** Fire all 10 `notebook_add_text` calls in a single parallel batch.

---

### 🟡 B2: Full Text Re-transmission Through Proxy (MODERATE)

**Problem:** Each source document (2-15 KB of legal text) is transmitted through the full proxy chain: **Agent → lazy-mcp → notebooklm-mcp.exe → NotebookLM API**. The text is the MCP tool's `text` parameter, encoded in JSON.

**Root Cause:** The MCP protocol uses `notebook_add_text` which requires the full text as an argument. There's no "add from file path" option.

**Impact:** For 10 documents averaging ~5KB each, that's ~50KB of text shuttled through 3 hops. Not a bandwidth bottleneck at this scale, but significant for 100+ document batches. The JSON encoding also inflates payload size (escaping newlines, quotes).

**Potential Fix:**
- A `notebook_add_files` batch tool that accepts an array of `{title, text}` objects
- Or a `notebook_add_local_file` tool that reads from disk and uploads directly

---

### 🟡 B3: Digest Queries Not Fully Parallelized (MODERATE)

**Problem:** The 10 digest queries were split into batches (4 parallel, then 5 parallel, then 1 that was serialized due to large output). This was better than source addition, but still suboptimal.

**Root Cause:** 
1. Agent conservatism — not issuing all 10 in one batch
2. NotebookLM may rate-limit parallel requests (unconfirmed, but a reasonable concern for reverse-engineered APIs)
3. One response was so large it was saved to a file instead of returned inline, adding an extra `view_file` turn

**Impact:** ~15-20 seconds of unnecessary serialization.

**Fix:** Issue all 10 queries in a single parallel batch if the API can handle it.

---

### 🟢 B4: Large Response File Redirect (MINOR)

**Problem:** The Carolina Vda. de Figuracion digest response was too large for inline return, so the proxy saved it to `steps/75/output.txt`, requiring an extra `view_file` call.

**Root Cause:** The lazy-mcp proxy has an output size threshold that triggers file-based storage for large responses.

**Impact:** One extra round-trip (~2s). Minor for this batch, but could compound at scale.

**Fix:** Increase the inline response size threshold, or have the agent pre-emptively handle file-based responses.

---

## 4. Friction Points

### ⚡ F1: Cookie-Based Auth is Fragile

**Nature:** The NotebookLM MCP uses reverse-engineered cookie auth (`save_auth_tokens`). Cookies expire, Google may rotate session IDs, and there's no OAuth refresh flow.

**User Experience:** In the previous session, the user had to manually capture cookies from Chrome DevTools. This is a **one-time per session** friction, but it's high-ceremony (open DevTools → copy cookies → paste into tool).

**Mitigation:** The MCP already auto-extracts CSRF tokens, which is good. But there's no automatic cookie refresh or expiry warning.

**Ideal State:** OAuth-based auth with automatic token refresh. However, since this is a reverse-engineered API, that may not be feasible.

---

### ⚡ F2: No Batch/Bulk Tools

**Nature:** Every operation is atomic — add one source, query one digest. For batch workflows (this exact use case), the agent must loop manually.

**Missing Tools:**
| Missing Tool | What It Would Do |
|---|---|
| `notebook_add_text_batch` | Add N sources in one call |
| `notebook_query_batch` | Generate digests for multiple sources in one call |
| `notebook_add_local_files` | Read local files and add them directly |

**Impact:** Forces the agent into multi-turn sequential patterns that waste time.

---

### ⚡ F3: No Source ID Return from `notebook_add_text`

**Nature:** The `notebook_add_text` tool returns the source ID in its response, BUT the agent has to parse it from the JSON response string. There's no structured return schema in the hierarchy definition.

**Impact:** The agent must mentally track 10 source IDs across turns to use them in `notebook_query(source_ids=[...])`. This is error-prone at scale.

**Ideal State:** A batch add tool that returns a mapping: `{filename → source_id}`.

---

### ⚡ F4: No Progress/Status Feedback During Long Operations

**Nature:** `notebook_query` can take 5-15 seconds per call. During this time, there's no progress indicator or streaming feedback.

**Impact:** For a 10-document batch, the user sees nothing for 30-60 seconds while queries run. Poor UX.

**Ideal State:** Streaming responses or progress callbacks.

---

## 5. Optimization Opportunities

### 🚀 O1: Parallel Source Addition (QUICK WIN)

**Change:** In the agent workflow, add all sources in a single parallel batch:
```
# Instead of 10 sequential calls:
for file in files:
    notebook_add_text(...)   # serial, 10 turns

# Do this:
parallel([notebook_add_text(f) for f in files])  # 1 turn, all 10 in parallel
```

**Expected Speedup:** 10× for the addition phase (60-90s → 6-9s).

**Risk:** NotebookLM API may rate-limit concurrent requests. Test with 5, then 10.

---

### 🚀 O2: Workflow-Level Tool (MEDIUM EFFORT)

Create a composite tool `process_case_digests` in the MCP server:

```python
def process_case_digests(notebook_id, files: list[{path, title}], query):
    """
    1. Read each file from local path
    2. Add as source to notebook
    3. Wait for indexing
    4. Query each source
    5. Return array of {title, source_id, digest}
    """
```

**Expected Speedup:** Reduces the entire workflow from ~20+ agent turns to **1 turn**.

**Risk:** Server-side complexity, error handling for partial failures.

---

### 🚀 O3: Agent Workflow Template (LOW EFFORT)

Create a `.agent/workflows/process-cases.md` workflow that codifies the optimal pattern:

```markdown
---
description: Process court cases through NotebookLM for digest generation
---
1. Read all source files in parallel
// turbo
2. Add all sources to notebook in parallel (max 5 concurrent)
// turbo
3. Query all sources for digests in parallel (max 5 concurrent)
// turbo
4. Save all digests in parallel
```

**Expected Speedup:** Ensures future runs use the optimal parallel pattern.

---

### 🚀 O4: Pre-compute Source Text at File Read (LOW EFFORT)

**Current:** Agent reads file → stores in context → pastes into `notebook_add_text` text parameter.
This means the full text exists in the agent's context window AND in the tool call payload — doubled memory usage.

**Better:** Have the MCP server accept a file path and read directly:
```json
{
  "tool": "notebook_add_local_file",
  "args": {
    "notebook_id": "...",
    "file_path": "C:\\path\\to\\case.md",
    "title": "Case Name"
  }
}
```

**Expected Benefit:** Reduces agent context consumption by ~50KB for a 10-doc batch.

---

### 🚀 O5: Structured Response Schema (LOW EFFORT)

Update the hierarchy JSON for `notebook_add_text` and `notebook_query` to include output schemas:

```json
{
  "outputSchema": {
    "properties": {
      "source_id": { "type": "string" },
      "title": { "type": "string" },
      "status": { "type": "string" }
    }
  }
}
```

**Benefit:** Agent can reliably extract source IDs without string parsing.

---

## 6. Quantified Impact Summary

| Optimization | Effort | Speedup | Context Savings |
|---|---|---|---|
| O1: Parallel source add | 🟢 None (agent pattern) | **10× on phase C** | None |
| O2: Composite workflow tool | 🟡 Medium (Go code) | **20× overall** | Major |
| O3: Workflow template | 🟢 Low (markdown) | **2-3× on future runs** | None |
| O4: Local file path tool | 🟡 Medium (Go code) | 1.5× | ~50KB per 10 docs |
| O5: Structured output schema | 🟢 Low (JSON) | None directly | Reduces parsing errors |

---

## 7. Recommendations (Priority Order)

1. **Immediate (this session):** Use parallel `notebook_add_text` calls in future batches — just fire all 10 from the same turn instead of sequential.

2. **Short-term:** Create an Antigravity workflow template (`.agent/workflows/notebooklm-digest.md`) that encodes the optimal parallel batch pattern.

3. **Medium-term:** Add a `notebook_add_local_file` tool to the MCP server that reads from disk, avoiding the need to shuttle full text through the agent context.

4. **Long-term:** Build a composite `batch_process_sources` tool in the MCP server that handles the entire add-index-query loop server-side, reducing the agent's role to just "invoke and save results."

---

## 8. Session Cookie Architecture Note

The current auth model uses `save_auth_tokens` with raw browser cookies. This is inherently fragile because:
- Google cookies have variable TTLs (some expire in hours, some in weeks)
- No automatic refresh mechanism
- The agent can't detect expiry until a call fails

**Recommendation:** Add a `check_auth_status` tool that validates the current cookies against NotebookLM before starting a batch, so failures are caught early rather than mid-pipeline.
