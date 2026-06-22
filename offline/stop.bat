@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

:: ---- ตรวจสอบ Docker ----
where docker >nul 2>nul || (
  echo [ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Desktop ก่อน
  exit /b 1
)
docker info >nul 2>nul || (
  echo [WARN] Docker ยังไม่ทำงาน — containers อาจหยุดอยู่แล้ว
)

echo กำลังหยุดระบบ SeamlessFordMIS...
docker compose down

echo.
echo [OK] หยุดระบบเรียบร้อยแล้ว
echo      ข้อมูลทั้งหมดยังอยู่ใน Docker volumes ครบถ้วน
echo      รัน offline\start.bat เพื่อเริ่มระบบอีกครั้ง
