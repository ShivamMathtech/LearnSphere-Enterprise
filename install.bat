@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.12 x64 from python.org.
  exit /b 1
)
py -3.12 --version
if errorlevel 1 exit /b 1
where npm >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 24 LTS, then reopen your terminal.
  exit /b 1
)
if not exist .env copy .env.example .env >nul
if not exist .venv py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if errorlevel 1 exit /b 1
pushd frontend
call npm ci --no-fund --no-audit
if errorlevel 1 (
  popd
  exit /b 1
)
popd
pushd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
  popd
  exit /b 1
)
..\.venv\Scripts\python.exe -m app.cli seed-permissions
if errorlevel 1 (
  popd
  exit /b 1
)
popd
.venv\Scripts\python.exe scripts\seed-if-enabled.py
if errorlevel 1 exit /b 1
echo Installation complete. Run run-local.bat.
exit /b 0
