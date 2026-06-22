@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo [!] แนะนำ: สำรองข้อมูลปัจจุบันก่อน (offline\backup.bat) ก่อนดำเนินการกู้คืน
echo.

if "%~1"=="" (
  echo Usage: offline\restore.bat data\backups\YYYYMMDD-HHMMSS
  exit /b 1
)

set "RESTORE_DIR=%~1"
if not exist "%RESTORE_DIR%\database.sql" (
  echo Missing %RESTORE_DIR%\database.sql
  exit /b 1
)

echo This will destructively restore the database from:
echo %RESTORE_DIR%\database.sql
set /p CONFIRM=Type RESTORE to continue: 
if not "%CONFIRM%"=="RESTORE" (
  echo Restore cancelled.
  exit /b 1
)

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v /b "#" ".env"`) do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if "%POSTGRES_USER%"=="" set "POSTGRES_USER=seamlessfordmis"
if "%POSTGRES_DB%"=="" set "POSTGRES_DB=seamlessfordmis"

docker compose up -d db || exit /b 1
echo Resetting public schema...
echo DROP SCHEMA public CASCADE; CREATE SCHEMA public; | docker compose exec -T db psql -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" || exit /b 1
type "%RESTORE_DIR%\database.sql" | docker compose exec -T db psql -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" || exit /b 1

if exist "%RESTORE_DIR%\source_data.tar.gz" docker run --rm -v seamlessfordmis_source_data:/source_data -v "%cd%\%RESTORE_DIR%":/backup nginx:alpine sh -c "rm -rf /source_data/* && tar -xzf /backup/source_data.tar.gz -C /"
if exist "%RESTORE_DIR%\uploads.tar.gz" docker run --rm -v seamlessfordmis_uploads:/uploads -v "%cd%\%RESTORE_DIR%":/backup nginx:alpine sh -c "rm -rf /uploads/* && tar -xzf /backup/uploads.tar.gz -C /"
if exist "%RESTORE_DIR%\reports.tar.gz" docker run --rm -v seamlessfordmis_reports:/reports -v "%cd%\%RESTORE_DIR%":/backup nginx:alpine sh -c "rm -rf /reports/* && tar -xzf /backup/reports.tar.gz -C /"
if exist "%RESTORE_DIR%\logs.tar.gz" docker run --rm -v seamlessfordmis_logs:/logs -v "%cd%\%RESTORE_DIR%":/backup nginx:alpine sh -c "rm -rf /logs/* && tar -xzf /backup/logs.tar.gz -C /"

echo.
echo [สำเร็จ] กู้คืนข้อมูลเสร็จสิ้น
echo         รัน offline\start.bat เพื่อเริ่มระบบ
