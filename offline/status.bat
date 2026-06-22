@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

:: ---- ตรวจสอบ Docker ----
where docker >nul 2>nul || (
  echo [ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Desktop ก่อน
  exit /b 1
)
docker info >nul 2>nul || (
  echo [WARN] Docker ยังไม่ทำงาน กรุณาเปิด Docker Desktop ก่อน
  exit /b 1
)

:: ---- อ่าน HTTP_PORT จาก .env ----
set "HTTP_PORT=80"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b "HTTP_PORT" ".env"`) do (
    if "%%A"=="HTTP_PORT" set "HTTP_PORT=%%B"
  )
)
set "URL=http://localhost"
if not "!HTTP_PORT!"=="80" set "URL=http://localhost:!HTTP_PORT!"

echo.
echo ============================================================
echo  SeamlessFordMIS — สถานะระบบ
echo ============================================================
echo.

docker compose ps

echo.
echo Health checks:
docker compose ps db      2>nul | findstr /I "healthy" >nul && echo   db:      healthy || echo   db:      ไม่ healthy
docker compose ps backend 2>nul | findstr /I "healthy" >nul && echo   backend: healthy || echo   backend: ไม่ healthy
docker compose ps nginx   2>nul | findstr /I "healthy" >nul && echo   nginx:   healthy || echo   nginx:   ไม่ healthy

echo.
echo  URL เว็บ: !URL!
echo.
echo  ถ้าระบบไม่ทำงาน: offline\start.bat  — เพื่อเริ่มระบบ
echo  ดู log:          docker compose logs ^<service^>
echo  ตรวจสอบละเอียด: offline\healthcheck.bat
