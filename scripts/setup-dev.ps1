# setup-dev.ps1 — First-time developer setup (Windows PowerShell)
# Run once after cloning:  .\scripts\setup-dev.ps1

$ErrorActionPreference = "Stop"

Write-Host "==> Activating git hooks from .githooks/ ..." -ForegroundColor Cyan
git config core.hooksPath .githooks

Write-Host "==> Installing Python dependencies ..." -ForegroundColor Cyan
# Install pre-commit into the active virtualenv (required for the hook to run)
pip install pre-commit

Write-Host ""
Write-Host "Done. Git hooks are active." -ForegroundColor Green
Write-Host "Activate your virtualenv before committing."
Write-Host "Run 'pre-commit run --all-files' to verify all checks pass."
