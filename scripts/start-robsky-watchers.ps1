# ============================================================================
# start-robsky-watchers.ps1
# Launches 4 parallel Angular RAG watcher instances for the Robsky AI project
# covering: Frontend (src/), Backend (functions/src/), Workflows (.agent/), Configs
#
# Usage (from C:\PROJECTS\notebooklm-mcp):
#   .\scripts\start-robsky-watchers.ps1
#
# Prerequisites:
#   - uv must be installed (https://github.com/astral-sh/uv)
#   - notebooklm-mcp installed: uv tool install .
#   - Chrome open & logged into notebooklm.google.com (for cookie refresh)
#
# Notebook IDs — edit these to match your actual Robsky notebooks:
# ============================================================================

$NOTEBOOK_IDS = "117e47ed-REPLACE-ME,b0376e17-REPLACE-ME,493bbdb5-REPLACE-ME"
$PROJECT_ROOT = "C:\PROJECTS\robsky-angular"
$MCP_ROOT     = "C:\PROJECTS\notebooklm-mcp"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🔭  Robsky Angular RAG — Multi-Watcher Launcher            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if ($NOTEBOOK_IDS -match "REPLACE-ME") {
    Write-Host "⚠️  WARNING: Notebook IDs not configured!" -ForegroundColor Yellow
    Write-Host "   Edit scripts\start-robsky-watchers.ps1 and replace the REPLACE-ME values." -ForegroundColor Yellow
    Write-Host "   Running in convert-only mode (no uploads)." -ForegroundColor Yellow
    Write-Host ""
    $NOTEBOOK_IDS = ""
}

# ── Terminal 1: Frontend (src/) ─────────────────────────────────────────────
Write-Host "▶ Starting Watcher 1: Frontend (src/)..." -ForegroundColor Green
$watcher1 = @{
    Label   = "RAG-FRONTEND"
    Cmd     = "uv run python angular-rag-watcher.py " +
              "--project `"$PROJECT_ROOT`" " +
              "--output-dir ANGULAR-RAG-FRONTEND " +
              "--notebook-ids `"$NOTEBOOK_IDS`" " +
              "--verbose"
}

# ── Terminal 2: Backend (functions/src/) ────────────────────────────────────
Write-Host "▶ Starting Watcher 2: Backend (functions/src/)..." -ForegroundColor Green
$watcher2 = @{
    Label   = "RAG-BACKEND"
    Cmd     = "uv run python angular-rag-watcher.py " +
              "--project `"$PROJECT_ROOT\functions\src`" " +
              "--output-dir ANGULAR-RAG-BACKEND " +
              "--extra-exts .json " +
              "--notebook-ids `"$NOTEBOOK_IDS`" " +
              "--verbose"
}

# ── Terminal 3: DevOps Workflows (.agent/workflows/) ────────────────────────
Write-Host "▶ Starting Watcher 3: Workflows (.agent/workflows/)..." -ForegroundColor Green
$watcher3 = @{
    Label   = "RAG-WORKFLOWS"
    Cmd     = "uv run python angular-rag-watcher.py " +
              "--project `"$PROJECT_ROOT`" " +
              "--watch-dir .agent\workflows " +
              "--output-dir ANGULAR-RAG-WORKFLOWS " +
              "--extra-exts .md,.json " +
              "--notebook-ids `"$NOTEBOOK_IDS`" " +
              "--verbose"
}

# ── Terminal 4: Root Config Files ──────────────────────────────────────────
Write-Host "▶ Starting Watcher 4: Root config files..." -ForegroundColor Green
$watcher4 = @{
    Label   = "RAG-CONFIG"
    Cmd     = "uv run python angular-rag-watcher.py " +
              "--project `"$PROJECT_ROOT`" " +
              "--watch-files firebase.json,netlify.toml,angular.json,package.json,README.md,DESIGN.md " +
              "--output-dir ANGULAR-RAG-CONFIG " +
              "--extra-exts .json,.toml,.md " +
              "--notebook-ids `"$NOTEBOOK_IDS`" " +
              "--verbose"
}

# ── Launch all 4 in separate Windows Terminal tabs (or PowerShell windows) ──
$watchers = @($watcher1, $watcher2, $watcher3, $watcher4)
$jobs = @()

foreach ($w in $watchers) {
    $label = $w.Label
    $cmd   = $w.Cmd

    # Try Windows Terminal first (wt), fall back to Start-Process powershell
    try {
        Start-Process -FilePath "wt" -ArgumentList @(
            "--title", $label,
            "powershell", "-NoExit",
            "-Command", "cd '$MCP_ROOT'; $cmd"
        ) -ErrorAction Stop
    } catch {
        # Fallback: plain PowerShell window
        Start-Process powershell -ArgumentList @(
            "-NoExit",
            "-Command",
            "cd '$MCP_ROOT'; Write-Host '[$label]' -ForegroundColor Cyan; $cmd"
        )
    }

    Start-Sleep -Milliseconds 800   # stagger starts to avoid auth collision
}

Write-Host ""
Write-Host "✅ All 4 watchers launched!" -ForegroundColor Green
Write-Host ""
Write-Host "   Watcher 1 [RAG-FRONTEND]   → src/                    → ANGULAR-RAG-FRONTEND/"
Write-Host "   Watcher 2 [RAG-BACKEND]    → functions/src/           → ANGULAR-RAG-BACKEND/"
Write-Host "   Watcher 3 [RAG-WORKFLOWS]  → .agent/workflows/        → ANGULAR-RAG-WORKFLOWS/"
Write-Host "   Watcher 4 [RAG-CONFIG]     → firebase/angular/package → ANGULAR-RAG-CONFIG/"
Write-Host ""
Write-Host "Press Ctrl+C in each watcher window to stop." -ForegroundColor DarkGray
