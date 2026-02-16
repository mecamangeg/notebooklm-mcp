---
description: Process court case documents through NotebookLM for digest generation
---

# NotebookLM Case Digest Pipeline

Batch-process court case `.md` files into AI-generated case digests via NotebookLM.

## Prerequisites

- NotebookLM authentication cookies must be valid
- Target notebook must exist (or will be created)
- Source `.md` files must be accessible on local disk

## Workflow Steps

// turbo-all

1. **Validate Authentication**
   Call `check_auth_status` to validate cookies before starting. If cookies are expired, re-authenticate using `save_auth_tokens` with fresh cookies from Chrome DevTools.

   ```
   execute_tool("notebooklm.check_auth_status", {})
   ```

2. **Identify Source Files**
   List the target directory to identify all `.md` files to process. Filter out any existing `-case-digest.md` files.

   ```powershell
   Get-ChildItem "C:\path\to\cases\*.md" | Where-Object { $_.Name -notlike "*-case-digest*" } | Select-Object FullName, Name
   ```

3. **Add All Sources via Local File Path (Single Call)**
   Use `notebook_add_local_files` to add all files in ONE call — no need to read files into context:

   ```
   execute_tool("notebooklm.notebook_add_local_files", {
     "notebook_id": "<NOTEBOOK_ID>",
     "file_paths": ["C:\\path\\to\\case1.md", "C:\\path\\to\\case2.md", ...],
     "titles": ["Case 1 Title", "Case 2 Title", ...]
   })
   ```

   This returns `source_id` for each successfully added file.

4. **Generate All Digests (Single Call)**
   Use `notebook_query_batch` to query each source for its case digest:

   ```
   execute_tool("notebooklm.notebook_query_batch", {
     "notebook_id": "<NOTEBOOK_ID>",
     "queries": [
       {
         "query": "Provide a comprehensive case digest for this document. Include: (1) Case Title and Citation, (2) Facts, (3) Issues, (4) Ruling/Held, (5) Ratio Decidendi/Reasoning, and (6) Disposition. Be thorough and precise.",
         "source_ids": ["<SOURCE_ID_1>"],
         "label": "Case 1 Title"
       },
       ...
     ]
   })
   ```

5. **Save All Digests**
   Write each digest to a new `-case-digest.md` file in the same directory as the source:

   ```
   For each result:
     write_to_file(
       TargetFile="<original_path_without_extension>-case-digest.md",
       CodeContent=result.answer
     )
   ```

## Performance Comparison

| Approach | Agent Turns | Estimated Time |
|----------|-------------|----------------|
| **Old (sequential)** | ~20+ turns | ~150s for 10 docs |
| **New (batch tools)** | 3-4 turns | ~30-45s for 10 docs |

## Troubleshooting

- **Auth failure mid-batch**: Run `check_auth_status` first. If it fails, re-authenticate.
- **Rate limit**: Free tier allows ~50 queries/day. For large batches, split across days.
- **Large files**: Files >500KB may timeout. Consider splitting or summarizing first.
