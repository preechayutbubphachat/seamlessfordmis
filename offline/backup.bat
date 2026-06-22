@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v /b "#" ".env"`) do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if "%POSTGRES_USER%"=="" set "POSTGRES_USER=seamlessfordmis"
if "%POSTGRES_DB%"=="" set "POSTGRES_DB=seamlessfordmis"

for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "BACKUP_DIR=data\backups\%STAMP%"
mkdir "%BACKUP_DIR%" >nul 2>nul

echo Backing up PostgreSQL to %BACKUP_DIR%\database.sql
docker compose exec -T db pg_dump -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" > "%BACKUP_DIR%\database.sql" || exit /b 1

echo Archiving Docker volumes to %BACKUP_DIR%
docker run --rm -v seamlessfordmis_source_data:/source_data:ro -v "%cd%\%BACKUP_DIR%":/backup nginx:alpine tar -czf /backup/source_data.tar.gz -C / source_data
docker run --rm -v seamlessfordmis_uploads:/uploads:ro -v "%cd%\%BACKUP_DIR%":/backup nginx:alpine tar -czf /backup/uploads.tar.gz -C / uploads
docker run --rm -v seamlessfordmis_reports:/reports:ro -v "%cd%\%BACKUP_DIR%":/backup nginx:alpine tar -czf /backup/reports.tar.gz -C / reports
docker run --rm -v seamlessfordmis_logs:/logs:ro -v "%cd%\%BACKUP_DIR%":/backup nginx:alpine tar -czf /backup/logs.tar.gz -C / logs

:: ---- สำรอง .env (ไม่รวม password จริง — แต่เก็บ config ไว้ใช้กู้คืน) ----
if exist ".env" (
    copy /y ".env" "%BACKUP_DIR%\.env.bak" >nul 2>nul
    echo Saved .env.bak to %BACKUP_DIR%
)

echo.
echo [สำเร็จ] ไฟล์สำรองอยู่ที่: %BACKUP_DIR%
echo.
echo [!] ข้อมูลสำรองมีข้อมูลผู้ป่วย — เก็บในพื้นที่ปลอดภัยภายในหน่วยงาน
echo     ห้ามส่งออกนอกเครือข่ายโรงพยาบาล ห้าม upload ขึ้น cloud สาธารณะ
