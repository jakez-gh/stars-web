# start.ps1 — Start the Stars! web UI dev server.
# Kills any existing server on port 5000, then starts fresh.
# Usage: .\start.ps1 [game_dir]

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$env:PYTHONPATH = Join-Path $repoRoot "src"

Write-Host "Starting Stars! web UI (http://127.0.0.1:5000)..." -ForegroundColor Cyan

# kill_port is handled inside python -m stars_web.run, but also do it here
# so port is clear before Python even starts (avoids address-already-in-use
# race if the old process hasn't died yet).
$listeners = netstat -ano -p TCP 2>$null | Select-String ":5000 .+LISTENING"
foreach ($line in $listeners) {
    $pid_ = ($line -split "\s+")[-1]
    if ($pid_ -match "^\d+$" -and $pid_ -ne "0") {
        Write-Host "  Killing PID $pid_ on port 5000..."
        taskkill /F /PID $pid_ 2>$null | Out-Null
    }
}

Start-Process "http://127.0.0.1:5000"

Set-Location $repoRoot
python -m stars_web.run @args
