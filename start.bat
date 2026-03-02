@echo off
REM Start the Stars! web UI dev server and open it in a browser.

cd /d "%~dp0"

set PYTHONPATH=src

echo Starting Stars! web UI...
echo Star map at http://127.0.0.1:5000
start "" http://127.0.0.1:5000

python -m stars_web.run %*
