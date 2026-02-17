---
description: Run SFT accounting questions against NotebookLM using parallel workers for ~4x throughput
---

# SFT Parallel Workers Workflow

## Overview

Generates a supervised fine-tuning (SFT) dataset by querying NotebookLM with 155 multi-part IFRS/IAS accounting questions. Uses 4 parallel Python processes to achieve ~4x throughput.

## Prerequisites

- **Notebook ID**: `f6418509-d4a1-4e67-bf8e-294eb7b7d937` (IFRS notebook with 150+ PDF sources)
- **Fresh cookies** must be saved via NotebookLM MCP `save_auth_tokens` tool
- **Script**: `c:\PROJECTS\notebooklm-mcp\sft-accounting-runner.py`
- **Output dir**: `C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS\`

## Key Configuration (in sft-accounting-runner.py)

| Setting | Value | Notes |
|---------|-------|-------|
| `QUERY_DELAY_SECONDS` | 15 | Default delay between queries per worker |
| `MAX_RETRIES` | 5 | Retries per question with exponential backoff |
| `BACKOFF_BASE` | 30 | Base seconds for exponential backoff (30, 60, 120, 240) |
| `COOLDOWN_AFTER_FAILURES` | 60 | Cooldown after 3+ consecutive failures |
| httpx timeout | 120s | In `api_client.py` line 341 — MUST be 120s for 150+ source notebooks |

## Step 1: Check Current Progress

// turbo
```powershell
$count = (Get-ChildItem "C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS\Q*.md" | Measure-Object).Count
$totalKB = [math]::Round((Get-ChildItem "C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS\Q*.md" | Measure-Object -Property Length -Sum).Sum / 1024, 1)
Write-Output "$count / 155 files completed, ${totalKB} KB total"

# Show which questions are missing
$existing = Get-ChildItem "C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS\Q*.md" | ForEach-Object { [int]($_.BaseName -replace 'Q','') } | Sort-Object
$all = 1..155
$missing = $all | Where-Object { $_ -notin $existing }
Write-Output "Missing: $($missing -join ', ')"
```

## Step 2: Refresh Cookies (if needed)

Ask the user to paste fresh cookies from Chrome DevTools (Network tab → any batchexecute request → Cookie header).

Then save via MCP:
```
execute_tool("notebooklm.save_auth_tokens", {"cookies": "<PASTE_COOKIE_STRING>"})
```

Test with a quick query:
```
execute_tool("notebooklm.notebook_query", {
  "notebook_id": "f6418509-d4a1-4e67-bf8e-294eb7b7d937",
  "query": "What is IAS 2?",
  "source_ids": ["ecd44473-ca67-4977-b07b-9c90da5f6010"]
})
```

If the answer is empty, cookies are expired → re-extract.

## Step 3: Launch Parallel Workers

Split the missing questions into 4 roughly equal ranges and launch each as a background process. The script auto-skips questions that already have valid answer files.

Example splitting 129 remaining questions (Q27-Q155) into 4 workers:

// turbo-all
```powershell
# Worker 1: Q27-Q59
$env:PYTHONIOENCODING="utf-8"; uv run python sft-accounting-runner.py --notebook-id f6418509-d4a1-4e67-bf8e-294eb7b7d937 --start-at 27 --end-at 59 --delay 5

# Worker 2: Q60-Q91  
$env:PYTHONIOENCODING="utf-8"; uv run python sft-accounting-runner.py --notebook-id f6418509-d4a1-4e67-bf8e-294eb7b7d937 --start-at 60 --end-at 91 --delay 5

# Worker 3: Q92-Q123
$env:PYTHONIOENCODING="utf-8"; uv run python sft-accounting-runner.py --notebook-id f6418509-d4a1-4e67-bf8e-294eb7b7d937 --start-at 92 --end-at 123 --delay 5

# Worker 4: Q124-Q155
$env:PYTHONIOENCODING="utf-8"; uv run python sft-accounting-runner.py --notebook-id f6418509-d4a1-4e67-bf8e-294eb7b7d937 --start-at 124 --end-at 155 --delay 5
```

**IMPORTANT**: Each worker must run from `c:\PROJECTS\notebooklm-mcp` directory.

**Adjust ranges** based on Step 1 results. If only specific questions are missing, you can run targeted workers like:
```powershell
# Re-run just Q47-Q50
uv run python sft-accounting-runner.py --notebook-id f6418509-d4a1-4e67-bf8e-294eb7b7d937 --start-at 47 --end-at 50 --delay 5
```

## Step 4: Monitor Progress

// turbo
```powershell
# Quick count check
(Get-ChildItem "C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS\Q*.md" | Measure-Object).Count

# Check log for errors
Get-Content "C:\Users\Michael\.notebooklm-mcp\sft-accounting.log" -Tail 20
```

## Step 5: Post-Process to SFT JSONL

Once all 155 questions have answers:

```powershell
cd c:\PROJECTS\notebooklm-mcp
$env:PYTHONIOENCODING="utf-8"; uv run python sft-accounting-runner.py --post-process-only
```

This generates: `C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\sft_accounting.jsonl`

## Troubleshooting

### Empty answers
- **Cause**: Usually expired cookies or httpx timeout too low
- **Fix**: Re-extract cookies from Chrome, confirm httpx timeout ≥ 120s in `api_client.py` line 341

### ReadTimeout errors
- **Cause**: httpx timeout < 120s (default was 30s, we changed to 120s)
- **Fix**: Verify `timeout=120.0` in `src/notebooklm_mcp/api_client.py` `_get_client()` method

### Rate limiting (consecutive empty answers)
- Script has built-in exponential backoff (30s → 60s → 120s → 240s)
- Script resets client + attempts cookie refresh on empty answers
- If persistent, reduce to 3 workers or increase `--delay` to 10-15

### Worker crashes on startup
- Can happen if KeyboardInterrupt signal leaks to newly spawned process
- Fix: Add `Start-Sleep 5` before the command, or just restart

## Performance

| Config | Throughput | ETA for 155 Qs |
|--------|-----------|----------------|
| 1 worker, 15s delay | ~1.2 Q/min | ~2.5 hours |
| 4 workers, 5s delay | ~3.5 Q/min | ~45 min |
| 4 workers, 15s delay | ~2.5 Q/min | ~60 min |

Average query time: 60-90s (varies with question complexity and source count).
