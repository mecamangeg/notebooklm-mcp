# install.ps1  —  Reliable install for notebooklm-mcp-server
# Usage: .\install.ps1
# Handles the uv cache-busting issue by doing uninstall + force-reinstall.

$ErrorActionPreference = "Continue"

Write-Host "[1/4] Stopping running notebooklm-mcp processes..." -ForegroundColor Cyan
Stop-Process -Name "notebooklm-mcp" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "[2/4] Uninstalling old version..." -ForegroundColor Cyan
uv tool uninstall notebooklm-mcp-server 2>$null

Write-Host "[3/4] Installing fresh (force + reinstall to bust cache)..." -ForegroundColor Cyan
uv tool install --force --reinstall .
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Warning: exit code $LASTEXITCODE (likely exe locked, but packages installed)" -ForegroundColor Yellow
}

Write-Host "[4/4] Verifying install..." -ForegroundColor Cyan
$serverPy = Join-Path $env:APPDATA "uv\tools\notebooklm-mcp-server\Lib\site-packages\notebooklm_mcp\server.py"
if (Test-Path $serverPy) {
    $info = Get-Item $serverPy
    Write-Host "  server.py: $($info.Length) bytes, updated $($info.LastWriteTime)" -ForegroundColor Green
    # Quick check for new tools
    $hasQuerySave = Select-String -Path $serverPy -Pattern "def notebook_query_save" -Quiet
    $hasPipeline = Select-String -Path $serverPy -Pattern "def notebook_digest_pipeline" -Quiet
    $hasWN = Select-String -Path $serverPy -Pattern "W/N" -Quiet
    Write-Host "  notebook_query_save: $(if($hasQuerySave){'YES'}else{'NO'})" -ForegroundColor $(if($hasQuerySave){'Green'}else{'Red'})
    Write-Host "  notebook_digest_pipeline: $(if($hasPipeline){'YES'}else{'NO'})" -ForegroundColor $(if($hasPipeline){'Green'}else{'Red'})
    Write-Host "  Madera format (W/N): $(if($hasWN){'YES'}else{'NO'})" -ForegroundColor $(if($hasWN){'Green'}else{'Red'})
} else {
    Write-Host "  ERROR: server.py not found at $serverPy" -ForegroundColor Red
}

Write-Host ""
Write-Host "Done! Restart MCP server to pick up changes." -ForegroundColor Green
