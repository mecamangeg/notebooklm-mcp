---
description: Convert Angular source code to Markdown for NotebookLM RAG ingestion
---

# Angular RAG Runner — Workflow

Converts all essential Angular source files (`src/`) to rich Markdown documents
suitable for NotebookLM source ingestion, enabling codebase-grounded RAG queries.

## Prerequisites

- NotebookLM MCP server installed (`uv tool install . --force`)
- Chrome open with NotebookLM loaded (for auth cookie refresh)
- One or more NotebookLM notebook UUIDs reserved for code RAG

## Phase 1: Convert Only (no API calls needed)

```bash
# Default: component-bundling strategy targeting C:\PROJECTS\robsky-angular
uv run python angular-rag-runner.py --convert-only

# Preview what would be converted without writing files
uv run python angular-rag-runner.py --dry-run

# Force rebuild of all .md files (skip cache)
uv run python angular-rag-runner.py --convert-only --force

# Different Angular project
uv run python angular-rag-runner.py --convert-only --project C:\MyApp

# Include unit test files (excluded by default)
uv run python angular-rag-runner.py --convert-only --include-specs

# One .md per file (max granularity, ~41 sources)
uv run python angular-rag-runner.py --convert-only --bundle-strategy flat

# Single giant .md (max context, 1 source, ~344 KB)
uv run python angular-rag-runner.py --convert-only --bundle-strategy single
```

Output: `ANGULAR-RAG-SOURCES/*.md` (40 files by default with component strategy)

## Phase 2: Convert + Upload to NotebookLM

```bash
# Full pipeline: convert then upload
uv run python angular-rag-runner.py --notebook-id <UUID>

# Clear old [Angular] sources first, then re-upload
uv run python angular-rag-runner.py --notebook-id <UUID> --clear-existing --force

# Upload only (use previously generated .md files)
uv run python angular-rag-runner.py --upload-only --notebook-id <UUID>

# Dry-run of full pipeline
uv run python angular-rag-runner.py --notebook-id <UUID> --dry-run
```

## Bundle Strategies

| Strategy | Files | NotebookLM Sources | Best for |
|---|---|---|---|
| `component` | 41 | 40 | General RAG — groups component + template |
| `flat` | 41 | 41 | Fine-grained retrieval per file |
| `single` | 41 | 1 | Small projects, maximum context |

## Output Format (each .md file)

```markdown
# services / chat.service

## Metadata
| Field | Value |
| Project | robsky-angular |
| Role | Service |
| Files | 1 |
| Total size | 15,840 bytes |
...

## Files in this Bundle
- `app/services/chat.service.ts` ...

---
## `app/services/chat.service.ts`
| Role | Service |
| Exports | ChatService, StreamingPhase, StreamMeta |
...

```typescript
// Full source code here
```
```

## Recommended Notebook for robsky-angular

Create a dedicated notebook for the Angular codebase:
1. Go to notebooklm.google.com → New notebook
2. Note the UUID from the URL
3. Run: `uv run python angular-rag-runner.py --notebook-id <UUID>`

## Auth Resilience

The runner uses the same CDP-based cookie refresh as the other runners:
- Probes ports 9222, 9223, 9000 for NotebookLM Chrome tab
- Auto-launches Chrome if no tab found
- Refreshes every 15 uploads or 10 minutes proactively
- Mid-flight auth recovery callback registered with MCP server

## Upload Log

`ANGULAR-RAG-SOURCES/upload-log.json` tracks which files have been uploaded
and their NotebookLM source IDs. Re-runs skip already-uploaded files unless
`--force` is passed.

---

## 🔭 AUTO-WATCH MODE (angular-rag-watcher.py)

The watcher monitors `robsky-angular/src` in real-time. Whenever a source
file is saved, it automatically converts the affected bundle to `.md` and
uploads it to NotebookLM — keeping the notebook always up-to-date.

### Starting the Watcher

```bash
# Full mode: convert + upload on every save
uv run angular-rag-watcher.py --notebook-id 117e47ed-6385-4dc5-9abc-1bf57588a263

# Convert-only (no upload)
uv run angular-rag-watcher.py --convert-only

# Custom debounce (ms to wait after last save before processing)
uv run angular-rag-watcher.py --notebook-id <UUID> --debounce 1200

# Disable Windows toasts
uv run angular-rag-watcher.py --notebook-id <UUID> --no-toast

# Skip startup reconciliation (faster launch, may miss stale files)
uv run angular-rag-watcher.py --notebook-id <UUID> --no-startup-sync
```

### Own venv (PEP 723)

`uv run angular-rag-watcher.py` creates its **own isolated virtual environment**
automatically via PEP 723 inline script metadata at the top of the file:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["watchdog>=6.0.0", "winotify>=1.1.0"]
# ///
```

No manual `pip install` needed — `uv run` handles everything.

### Architecture

| Feature | Detail |
|---|---|
| File watcher | `watchdog` — recursive, OS-native events |
| Debounce | 800 ms (waits for save to settle) |
| Queue | Sequential, de-duplicating — no race conditions |
| Dedup | SHA-256 content hash — skips re-upload if unchanged |
| Circuit breaker | Opens after 5 failures, recovers after 30 s |
| Cookie refresh | Every 15 uploads or 10 min (same CDP pattern as runner) |
| Toast | `winotify` — batched over 2 s window, no notification spam |
| Startup sync | Queues any .md missing or older than source on launch |
| Heartbeat | Status logged every 15 min |
| Graceful shutdown | Ctrl+C drains queue, prints stats, saves hash cache |

### Toast Notification Events

| Event | Triggered when |
|---|---|
| **Watcher Started** | On launch |
| **Angular RAG Updated** | After converting/uploading (batched 2 s) |
| **Watcher Stopped** | On Ctrl+C shutdown |

### Log file

`~/.notebooklm-mcp/angular-rag-watcher.log` — full debug log with timestamps.
Hash cache saved at `~/.notebooklm-mcp/angular-watcher-hashes.json`.

