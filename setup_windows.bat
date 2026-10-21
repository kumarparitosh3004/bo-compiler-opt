@echo off
rem One-time setup on Windows: Python environment, packages, GCC, self-check.
setlocal
cd /d "%~dp0"
echo.
echo == PassTune setup (Windows) ==

set "PY="
py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.10 or newer is needed. Install Python 3.12 from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation, then run this again.
  pause
  exit /b 1
)
echo [1/4] Python: %PY%

set "GCC="
if exist "C:\mingw64\bin\gcc.exe" set "GCC=C:/mingw64/bin/gcc.exe"
if not defined GCC for /f "delims=" %%g in ('where gcc 2^>nul') do if not defined GCC set "GCC=%%g"
if not defined GCC (
  echo GCC was not found. Download the WinLibs GCC UCRT build from https://winlibs.com/
  echo and extract it so that C:\mingw64\bin\gcc.exe exists, then run this again.
  pause
  exit /b 1
)
echo [2/4] GCC: %GCC%
> config\local.yaml echo # Per-machine settings (written by setup_windows.bat).
>> config\local.yaml echo compiler: %GCC:\=/%

if not exist .venv\Scripts\python.exe %PY% -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 .venv\Scripts\python -m pip install flask matplotlib numpy pandas pytest python-docx pyyaml scikit-learn scipy
if errorlevel 1 (
  echo Package installation failed.
  pause
  exit /b 1
)
echo [3/4] Packages: OK

echo [4/4] Checking the compiler and benchmarks...
.venv\Scripts\python scripts\check_setup.py --fix-references
if errorlevel 1 (
  pause
  exit /b 1
)
echo.
echo Setup finished. Start the app with run_windows.bat
pause
