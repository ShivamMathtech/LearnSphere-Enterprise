@echo off
setlocal
cd /d "%~dp0"
echo This only resets the default LOCAL SQLite development database.
echo It never resets PostgreSQL or a production environment.
set /p "LEARNSPHERE_RESET_CONFIRM=Type RESET DEMO to continue: "
if not "%LEARNSPHERE_RESET_CONFIRM%"=="RESET DEMO" (
  echo Cancelled.
  exit /b 1
)
.venv\Scripts\python.exe scripts\reset-demo.py --confirmed
exit /b %errorlevel%
