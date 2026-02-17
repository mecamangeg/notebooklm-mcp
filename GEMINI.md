# GEMINI.md

## Project Overview

**NotebookLM MCP Server**

This project implements a Model Context Protocol (MCP) server that provides programmatic access to [NotebookLM](https://notebooklm.google.com). It allows AI agents and developers to interact with NotebookLM notebooks, sources, and query capabilities.

Tested with personal/free tier accounts. May work with Google Workspace accounts but has not been tested. This project relies on reverse-engineered internal APIs (`batchexecute` RPCs).

## Environment & Setup

The project uses `uv` for dependency management and tool installation.

### Prerequisites
- Python 3.11+
- `uv` (Universal Python Package Manager)
- Google Chrome (for automated authentication)

### Installation

**From PyPI (Recommended):**
```bash
uv tool install notebooklm-mcp-server
# or: pip install notebooklm-mcp-server
```

**From Source (Development):**
```bash
git clone https://github.com/YOUR_USERNAME/notebooklm-mcp.git
cd notebooklm-mcp
uv tool install .
```

## Authentication (Simplified!)

**You only need to extract cookies** - the CSRF token and session ID are now auto-extracted when the MCP starts.

**Option 1: Chrome DevTools MCP (Recommended)**
If your AI assistant has Chrome DevTools MCP:
1. Navigate to `notebooklm.google.com`
2. Get cookies from any network request
3. Call `save_auth_tokens(cookies=<cookie_header>)`

**Option 2: Manual (Environment Variables)**
Extract the `Cookie` header from Chrome DevTools Network tab:
```bash
export NOTEBOOKLM_COOKIES="SID=xxx; HSID=xxx; SSID=xxx; ..."
```

> **Note:** CSRF token and session ID are no longer needed - they are auto-extracted from the page HTML when the MCP initializes.

Cookies last for weeks. When they expire, re-extract fresh cookies.

## Development Workflow

### Building and Running

**Reinstalling after changes:**
Because `uv tool install` installs into an isolated environment, you must reinstall to see changes during development.
```bash
uv cache clean
uv tool install --force .
```

**Running the Server:**
```bash
notebooklm-mcp
```

### Testing

Run the test suite using `pytest` via `uv`:
```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_api_client.py
```

## Project Structure

- `src/notebooklm_mcp/`
    - `server.py`: Main entry point. Defines the MCP server and tools.
    - `api_client.py`: The core logic. Contains the reverse-engineered API calls.
    - `auth.py`: Handles token validation, storage, and loading.
    - `auth_cli.py`: Implementation of the `notebooklm-mcp-auth` CLI.
- `CLAUDE.md`: Contains detailed documentation on the reverse-engineered RPC IDs and protocol specifics. **Refer to this file for API deep dives.**
- `pyproject.toml`: Project configuration and dependencies.

## Key Conventions

- **Reverse Engineering:** This project relies on undocumented APIs. Changes to Google's internal API will break functionality.
- **RPC Protocol:** The API uses Google's `batchexecute` protocol. Responses often contain "anti-XSSI" prefixes (`)]}'\`) that must be stripped.
- **Tools:** New features should be exposed as MCP tools in `server.py`.

## Batch / Pipeline Optimization Tools

The following tools were added to optimize high-throughput workflows (e.g., processing 10+ court cases for digest generation):

| Tool | Purpose |
|------|---------|
| `check_auth_status` | Validate cookies BEFORE starting a batch — catch expiry early |
| `notebook_add_text_batch` | Add N text sources in one call (vs N sequential calls) |
| `notebook_add_local_files` | Read files from disk and add as sources — avoids agent context consumption |
| `notebook_query_batch` | Query N sources in one call, returns all answers together |

**Before (20+ agent turns for 10 docs):**
```
for each file:
    view_file → notebook_add_text → notebook_query → write_to_file
```

**After (3-4 agent turns for 10 docs):**
```
check_auth_status → notebook_add_local_files → notebook_query_batch → save results
```

See `.agent/workflows/notebooklm-digest.md` for the full optimized workflow.

## SFT Accounting Dataset Runner

`sft-accounting-runner.py` generates a supervised fine-tuning dataset by querying NotebookLM with 155 multi-part IFRS/IAS accounting questions.

### Key Details
- **Notebook**: `f6418509-d4a1-4e67-bf8e-294eb7b7d937` (150+ IFRS/IAS PDFs)
- **Questions**: 155 scenario-based questions across 4 markdown files in `C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\`
- **Output**: Raw answers saved to `ACCOUNTING_RAW_ANSWERS\Q001.md` - `Q155.md`
- **SFT JSONL**: `--post-process-only` converts raw answers to Vertex AI SFT format

### Critical: httpx Timeout
The httpx timeout in `api_client.py` `_get_client()` **MUST be ≥ 120s** for notebooks with 150+ sources. Default 30s causes ReadTimeout errors.

### Parallel Workers (4x throughput)
Run 4 processes with non-overlapping `--start-at`/`--end-at` ranges. Each uses the same cached cookies independently. See `.agent/workflows/sft-parallel-workers.md` for the full procedure.

```bash
# Example: 4 parallel workers
uv run python sft-accounting-runner.py --notebook-id <ID> --start-at 1 --end-at 40 --delay 5 &
uv run python sft-accounting-runner.py --notebook-id <ID> --start-at 41 --end-at 80 --delay 5 &
uv run python sft-accounting-runner.py --notebook-id <ID> --start-at 81 --end-at 120 --delay 5 &
uv run python sft-accounting-runner.py --notebook-id <ID> --start-at 121 --end-at 155 --delay 5 &
```
