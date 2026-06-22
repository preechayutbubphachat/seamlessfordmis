@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

where docker >nul 2>nul || (
    echo [!] ไม่พบ Docker — ติดตั้ง Docker Desktop ก่อน
    exit /b 1
)
docker info >nul 2>nul || (
    echo [!] Docker ยังไม่เปิดทำงาน — เปิด Docker Desktop รอจนไอคอนหยุดหมุน แล้วลองใหม่
    exit /b 1
)

echo กำลังเริ่มระบบ...
docker compose up -d
if errorlevel 1 (
    echo [!] เกิดข้อผิดพลาด ดู log: docker compose logs
    exit /b 1
)

echo.
echo รอให้บริการพร้อม...
set "READY=0"
for /L %%i in (1,1,30) do (
    docker compose ps backend 2>nul | findstr /I "healthy" >nul && (
        set "READY=1"
        goto :STARTED
    )
    timeout /t 2 >nul
)

:STARTED
set "HTTP_PORT=80"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%K in (".env") do (
        if "%%K"=="HTTP_PORT" set "HTTP_PORT=%%L"
    )
)

echo.
docker compose ps
echo.
if "!READY!"=="1" (
    if "!HTTP_PORT!"=="80" (
        echo [OK] ระบบพร้อมใช้งาน: http://localhost
    ) else (
        echo [OK] ระบบพร้อมใช้งาน: http://localhost:!HTTP_PORT!
    )
) else (
    echo [!] บริการอาจยังไม่พร้อม — ตรวจสอบด้วย: offline\healthcheck.bat
)
