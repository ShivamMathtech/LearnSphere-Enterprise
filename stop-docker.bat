@echo off
cd /d "%~dp0"
docker compose -f docker-compose.dev.yml down
exit /b %errorlevel%
