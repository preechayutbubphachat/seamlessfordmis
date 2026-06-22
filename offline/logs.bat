@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
docker compose logs --tail=200 -f db backend frontend nginx
