@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1', 7862); Start-Process 'http://127.0.0.1:7862/'; exit 0 } catch { exit 1 } finally { $client.Dispose() }"
if not errorlevel 1 exit /b 0
if not exist "frontend\dist\index.html" (
  echo Building interface for the first run...
  call npm --prefix frontend install
  if errorlevel 1 exit /b 1
  call npm --prefix frontend run build
  if errorlevel 1 exit /b 1
)
echo Starting Audio Sprout Studio at http://127.0.0.1:7862 ...
uv run python run.py
endlocal

