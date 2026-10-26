@echo off
setlocal
cd /d "%~dp0"
uv run python scripts\setup_breeze.py
if errorlevel 1 (
  echo Breeze TTS 2 setup failed. See the error above and run this script again to resume.
  exit /b 1
)
endlocal
