@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

:: ---- ตรวจสอบ Docker ----
where docker >nul 2>nul || (
    echo [!] ไม่พบ Docker — ติดตั้ง Docker Desktop ก่อน
    exit /b 1
)
docker info >nul 2>nul || (
    echo [!] Docker ยังไม่เปิดทำงาน — เปิด Docker Desktop รอจนไอคอนหยุดหมุน แล้วลองใหม่
    exit /b 1
)

echo กำลังรีสตาร์ทระบบ...
docker compose restart
if errorlevel 1 (
    echo [!] เกิดข้อผิดพลาด ดู log: docker compose logs
    exit /b 1
)

:: แสดง URL หลังรีสตาร์ท
set "HTTP_PORT=80"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%K in (".env") do (
        if "%%K"=="HTTP_PORT" set "HTTP_PORT=%%L"
    )
)
echo.
if "!HTTP_PORT!"=="80" (
    echo [OK] รีสตาร์ทเสร็จสิ้น: http://localhost
) else (
    echo [OK] รีสตาร์ทเสร็จสิ้น: http://localhost:!HTTP_PORT!
)
