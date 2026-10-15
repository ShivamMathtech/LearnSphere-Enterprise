@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  exit /b 1
)
if not exist .env (
  echo Copy .env.example to .env and run install.bat.
  exit /b 1
)
pushd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
  popd
  exit /b 1
)
popd
start "LearnSphere API" cmd /k call "%~dp0scripts\start-backend.bat"
start "LearnSphere Web" cmd /k call "%~dp0scripts\start-frontend.bat"
start "LearnSphere Worker" cmd /k call "%~dp0scripts\start-worker.bat"
.venv\Scripts\python.exe scripts\wait-and-open.py
exit /b %errorlevel%
