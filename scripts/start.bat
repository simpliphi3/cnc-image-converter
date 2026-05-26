@echo off
REM CNC Image Converter — one-click launcher.
REM Starts the local server and opens the browser.

cd /d "%~dp0\.."

REM Open browser shortly after we start the server.
start "" /b cmd /c "ping -n 4 127.0.0.1 >nul && start http://127.0.0.1:7777"

uv run python -m backend.app
