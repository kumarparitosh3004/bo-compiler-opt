@echo off
rem Start PassTune on Windows and open it in the browser.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
echo PassTune is starting at http://127.0.0.1:5000  (close this window to stop it)
start "" http://127.0.0.1:5000
.venv\Scripts\python web\app.py --port 5000
