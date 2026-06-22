@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

where docker >nul 2>nul || (
  echo [ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Desktop ก่อน
  exit /b 1
)
docker info >nul 2>nul || (
  echo [ERROR] Docker ยังไม่ทำงาน กรุณาเปิด Docker Desktop แล้วรอจนพร้อม
  exit /b 1
)

echo กำลังรัน database migration...
docker compose run --rm backend alembic upgrade head
if errorlevel 1 (
  echo [ERROR] Migration ล้มเหลว ดู log ด้านบนสำหรับรายละเอียด
  exit /b 1
)
echo [OK] Migration เสร็จสิ้น
