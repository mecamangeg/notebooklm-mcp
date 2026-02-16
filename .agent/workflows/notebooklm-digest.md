---
description: Generate case digests using NotebookLM MCP (optimized v2 pipeline)
---

# NotebookLM Case Digest Pipeline (v2)

## Overview
Generates case digests from court decision files using NotebookLM AI.
Uses the `notebook_digest_pipeline` tool for zero-context-cost processing.

## Prerequisites
- NotebookLM cookies configured (run `check_auth_status` to verify)
- Case files in markdown/txt format on disk
- Fresh MCP proxy with `toolTimeout: 300` for notebooklm server

---

## Pipeline (2 turns)

### Turn 1: Auth + Create Notebook
```
1. Run notebooklm.check_auth_status to verify cookies are valid
2. Run notebooklm.notebook_create with a descriptive project title
   (e.g., "Feb 2013 Case Digests")
3. Note the notebook_id from the response
```

### Turn 2: Run Full Pipeline
```
Run notebooklm.notebook_digest_pipeline with:
  - notebook_id: <from step 1>
  - file_paths: list of absolute paths to case .md files
  - output_dir: directory to save digest files (e.g., "C:\output\2013")
  - query_template: (optional, defaults to comprehensive case digest prompt)
  - titles: (optional, defaults to filenames)
```

That's it. The pipeline tool handles everything:
1. Reads each file from disk (no context cost)
2. Adds as a source to the notebook
3. Queries NotebookLM for a case digest
4. Saves the digest to disk as a .md file
5. Returns only metadata (status, sizes, paths)

---

## Performance Comparison

| Metric | v1 (manual) | v1.5 (batch tools) | v2 (pipeline) |
|--------|-------------|---------------------|---------------|
| Agent turns | 20+ | 3-4 | **2** |
| Tool calls | 15+ | 7-10 | **3** |
| Context consumed | ~200KB | ~60KB | **~500 bytes** |
| Time (5 docs) | ~5 min | ~70s | **~90s** |
| Timeout risk | None | High (30s) | Low (300s) |

---

## Tool Decision Tree

Choose the right tool based on your use case:

```
Need to process batch of files into digests?
  └─ YES → notebook_digest_pipeline (1 call, zero context cost)

Need to query and save a single answer?
  └─ YES → notebook_query_save (saves to disk, zero context cost)

Need to query and see the answer in context?
  └─ YES → notebook_query (answer returns through context)

Need to add many files without generating digests?
  └─ YES → notebook_add_local_files (batch add, zero context cost)
```

---

## Timeout Configuration

The `notebooklm` server has `toolTimeout: 300` (5 minutes) configured in
`C:\Tools\lazy-mcp\config.json`. This allows processing up to ~15 documents
in a single pipeline call (at ~20s per document).

For larger batches (15+ docs), split into multiple pipeline calls.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Auth expired | Run `check_auth_status`, then `save_auth_tokens` with fresh cookies |
| Pipeline timeout | Reduce batch size or increase `toolTimeout` in lazy-mcp config |
| Partial results | Pipeline saves incrementally — check `output_dir` for completed digests |
| Empty answers | Source may be too short or NotebookLM couldn't parse it |

---

## Example Usage

```
# Turn 1
check_auth_status → ✅ valid
notebook_create("Feb 2013 Digests") → notebook_id: "abc-123"

# Turn 2  
notebook_digest_pipeline(
    notebook_id="abc-123",
    file_paths=[
        "C:/cases/CIR v. San Roque.md",
        "C:/cases/Cavite Apparel v. Marquez.md",
        "C:/cases/Diaz v. People.md"
    ],
    output_dir="C:/output/2013"
) → {status: "success", digests_saved: 3}
```
