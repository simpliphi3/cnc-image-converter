@echo off
REM Pull the latest version and rebuild the frontend.

cd /d "%~dp0\.."
git pull --ff-only
uv sync
pushd frontend
call npm install
call npm run build
popd
echo.
echo Update complete. Launch with scripts\start.bat
pause
