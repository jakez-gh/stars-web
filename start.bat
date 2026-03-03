@echo off
REM Start the Stars! web UI dev server and open it in a browser.
REM Kills any existing server on port 5000 before starting.

cd /d "%~dp0"

set PYTHONPATH=%~dp0src

echo Starting Stars! web UI...
start "" http://127.0.0.1:5000

python -m stars_web.run %*
