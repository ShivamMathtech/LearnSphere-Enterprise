@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 (
  echo Install and start Docker Desktop first.
  exit /b 1
)
docker compose -f docker-compose.dev.yml up --build -d --wait
if errorlevel 1 exit /b 1
echo Stack started. For demo accounts, run:
echo docker compose -f docker-compose.dev.yml exec backend python -m app.cli seed-demo
start "" http://localhost:8080
exit /b 0
