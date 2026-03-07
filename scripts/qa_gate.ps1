#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run all local quality gates, then hot-swap the development server.

.DESCRIPTION
    Executes the full local quality gate suite in order:
      1. inventory quality gate  (tools/check_inventory.py)
      2. pytest with coverage    (1191 tests, >=50% threshold)

    On success the current Flask dev server is killed and a fresh instance
    is started immediately so the latest code is always live.

    On failure the existing server is left running (stable version stays up)
    and a clear error summary is printed.

.PARAMETER GameDir
    Optional path to the Stars! game directory.  Forwarded to stars_web.run.
    Defaults to the STARS_GAME_DIR env var or the built-in fallback.

.EXAMPLE
    .\scripts\qa_gate.ps1
    .\scripts\qa_gate.ps1 -GameDir C:\Games\Stars\MyGame
#>
param(
    [string]$GameDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Locate project root (stars_web/) ─────────────────────────────────────────
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Push-Location $ProjectRoot
try {

    $Python = "py"
    $PyArgs = @("-3.11")

    # Make stars_web importable for both quality gate commands and the server.
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"

    # ── Gate 1: inventory quality gate ───────────────────────────────────────
    Write-Host ""
    Write-Host "=== GATE 1: Inventory Quality Gate ===" -ForegroundColor Cyan
    & $Python @PyArgs tools/check_inventory.py
    $gate1 = $LASTEXITCODE

    # ── Gate 2: pytest ───────────────────────────────────────────────────────
    Write-Host ""
    Write-Host "=== GATE 2: pytest (parallel, 50% coverage gate) ===" -ForegroundColor Cyan
    & $Python @PyArgs -m pytest -q --tb=short
    $gate2 = $LASTEXITCODE

    # ── Results ──────────────────────────────────────────────────────────────
    Write-Host ""
    $pass1 = $gate1 -eq 0
    $pass2 = $gate2 -eq 0

    Write-Host "Gate results:"
    Write-Host ("  [$(if ($pass1) {'PASS'} else {'FAIL'})] inventory quality gate") `
        -ForegroundColor $(if ($pass1) { "Green" } else { "Red" })
    Write-Host ("  [$(if ($pass2) {'PASS'} else {'FAIL'})] pytest") `
        -ForegroundColor $(if ($pass2) { "Green" } else { "Red" })

    if (-not ($pass1 -and $pass2)) {
        Write-Host ""
        Write-Host "QUALITY GATE FAILED — server NOT restarted (stable version remains live)." -ForegroundColor Red
        exit 1
    }

    # ── All gates green: hot-swap the server ─────────────────────────────────
    Write-Host ""
    Write-Host "All gates PASSED — restarting development server..." -ForegroundColor Green

    # run.py already kills any existing process on the assigned port at startup.
    # Launch in a new window so it stays alive after this script exits.
    # PYTHONPATH is already set above so the new window inherits it.
    $serverArgs = @("-3.11", "-m", "stars_web.run")
    if ($GameDir -ne "") { $serverArgs += $GameDir }
    Start-Process -FilePath $Python -ArgumentList $serverArgs `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Normal

    Write-Host "Server restarted. Check the new window for the URL." -ForegroundColor Green
    Write-Host ""

} finally {
    Pop-Location
}
