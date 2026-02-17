# NotebookLM MCP Runner Guide

This guide explains how to use the `notebooklm-mcp-runner.py` script to process large volumes of e-SCRA legal cases into structured case digests using NotebookLM.

## 🚀 Overview
The runner is a robust automation layer on top of the NotebookLM MCP server. It handles:
- **Batch Processing**: Iterates through 1,000+ volumes of SCRA cases.
- **Auth Resilience**: Automatically refreshes expired cookies from an open Chrome session via DevTools Protocol (CDP).
- **Self-Healing**: Retries volumes with high failure rates automatically.
- **Smart Resumption**: Validates existing digests on disk to skip already-completed files, even if the script was interrupted.

---

## 📋 Prerequisites

1. **Virtual Environment**: Ensure you are using the project's `.venv`.
2. **Chrome Setup**:
   - Chrome must be open.
   - You must be logged into [NotebookLM](https://notebooklm.google.com).
   - Chrome must have been launched with remote debugging enabled (usually handled by `notebooklm-mcp-auth`).
3. **Paths**: The script expects sources in `C:\PROJECTS\e-scra\MARKDOWN` and outputs to `C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS`.

---

## 🛠️ Usage Commands

### 1. Process All Volumes (Standard)
Processes every volume numerically starting from Volume_001.
```powershell
.venv\Scripts\python.exe notebooklm-mcp-runner.py --all
```

### 2. Resume From a Specific Volume
Use this if you hit a daily limit or stopped the script. It will jump to that volume and continue to the end.
```powershell
.venv\Scripts\python.exe notebooklm-mcp-runner.py --all --start-at Volume_029
```

### 3. Process a Single Volume
Useful for testing or fixing a specific volume.
```powershell
.venv\Scripts\python.exe notebooklm-mcp-runner.py --volume Volume_050
```

---

## ⚙️ Arguments Reference

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--all` | Process every volume in the source directory. | N/A |
| `--volume [Name]` | Process only the specified volume (e.g., `Volume_001`). | N/A |
| `--start-at [Name]` | When used with `--all`, skips volumes prior to this one. | N/A |
| `--refresh-every [N]` | Proactively refresh cookies every N volumes. | 5 |
| `--max-retries [N]` | Maximum number of retry attempts per volume. | 3 |

---

## 📊 Monitoring Progress

The runner provides real-time feedback in the terminal:
- **Volume Header**: Shows how many files were found and how many valid digests already exist.
- **Progress Log**: Streams the last 30 actions from the pipeline threads.
- **Overall Stats**: Shows total saved, skipped, and failed files across the entire batch.
- **ETA**: Calculates remaining time based on current processing speed.

---

## 🛠️ Troubleshooting

### "No NotebookLM page found in Chrome"
- **Cause**: Chrome is closed or NotebookLM is not open in any tab.
- **Fix**: Open Chrome, go to `notebooklm.google.com`, and ensure your account is logged in.

### "Daily Limit Reached" (No answer returned)
- **Cause**: You have processed ~5,000 files in 24 hours.
- **Fix**: Stop the script (Ctrl+C). Wait for the quota to reset (approx. 24 hours), then resume using `--start-at` for the current volume.

### "Python was not found"
- **Cause**: Using `python` instead of the full path to the project's virtual environment.
- **Fix**: Always use `.venv\Scripts\python.exe`.

---

## 📝 Logs
Full debug logs (including stack traces and detailed retrieval logs) are saved to:
`%USERPROFILE%\.notebooklm-mcp\runner.log`
