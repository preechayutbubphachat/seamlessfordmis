@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

echo ============================================================
echo  SeamlessFordMIS — โหลด Docker Images จาก Offline Package
echo ============================================================
echo.

:: ---- ตรวจสอบ Docker ----
where docker >nul 2>nul || (
  echo [ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Desktop ก่อน
  echo         ดาวน์โหลดได้ที่: https://www.docker.com/products/docker-desktop
  exit /b 1
)
docker info >nul 2>nul || (
  echo [ERROR] Docker ยังไม่ทำงาน กรุณาเปิด Docker Desktop แล้วรอจนพร้อม
  echo         จากนั้นรันสคริปต์นี้ใหม่อีกครั้ง
  exit /b 1
)
echo [OK] Docker พร้อมทำงาน

:: ---- ตรวจสอบว่ามีโฟลเดอร์ images/ ----
if not exist "images" (
  echo.
  echo [ERROR] ไม่พบโฟลเดอร์ images\
  echo.
  echo  ตรวจสอบว่าติดตั้งระบบถูกต้อง:
  echo    - ถ้าใช้ Windows Installer ควรมี images\ อยู่ใน C:\SeamlessFordMIS\app\images\
  echo    - ถ้าโหลดจาก .zip ให้แตกไฟล์ทั้งหมดก่อนรันสคริปต์นี้
  echo.
  echo  หรือรัน offline\save-images.bat บนเครื่องที่มี internet เพื่อสร้างไฟล์ tar
  exit /b 1
)

:: ---- ตรวจสอบว่ามีไฟล์ tar ครบ ----
echo [INFO] ตรวจสอบไฟล์ tar...
set "MISSING=0"
for %%F in (
  images\postgres-16.tar
  images\nginx-alpine.tar
  images\seamlessfordmis-backend.tar
  images\seamlessfordmis-frontend.tar
) do (
  if not exist "%%F" (
    echo [ERROR] ไม่พบไฟล์: %%F
    set "MISSING=1"
  ) else (
    for %%S in ("%%F") do (
      set /a SIZE_MB=%%~zS / 1048576
      echo [OK]   %%F (!SIZE_MB! MB)
    )
  )
)

if "!MISSING!"=="1" (
  echo.
  echo [ERROR] ไฟล์ tar บางไฟล์ขาดหาย
  echo         - ถ้าใช้ Windows Installer ให้ติดตั้งใหม่
  echo         - ถ้าโหลดจาก .zip ให้ตรวจสอบว่าแตกไฟล์ครบ
  echo         - ถ้าต้องการสร้างไฟล์ใหม่ รัน: offline\save-images.bat
  exit /b 1
)

:: ---- โหลด images ----
echo.
echo [LOAD] กำลังโหลด Docker images... (อาจใช้เวลา 3-10 นาที)
echo.

echo       โหลด postgres:16...
docker load -i "images\postgres-16.tar" || (
  echo [ERROR] โหลด postgres image ล้มเหลว
  exit /b 1
)

echo       โหลด nginx:alpine...
docker load -i "images\nginx-alpine.tar" || (
  echo [ERROR] โหลด nginx image ล้มเหลว
  exit /b 1
)

echo       โหลด seamlessfordmis-backend...
docker load -i "images\seamlessfordmis-backend.tar" || (
  echo [ERROR] โหลด backend image ล้มเหลว
  exit /b 1
)

echo       โหลด seamlessfordmis-frontend...
docker load -i "images\seamlessfordmis-frontend.tar" || (
  echo [ERROR] โหลด frontend image ล้มเหลว
  exit /b 1
)

:: ---- ยืนยัน ----
echo.
echo ============================================================
echo  โหลด Docker images สำเร็จทั้งหมด!
echo ============================================================
echo.
echo  Images ที่พร้อมใช้งาน:
docker images --filter "reference=postgres:16" --filter "reference=nginx:alpine" --filter "reference=seamlessfordmis*" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"

echo.
echo  ขั้นตอนต่อไป:
echo    - ถ้าติดตั้งครั้งแรก: รัน offline\install.bat
echo    - ถ้าระบบเคยทำงานแล้ว: รัน offline\start.bat
echo    - หรือเปิด control-panel.bat แล้วเลือก 1 (ติดตั้ง) หรือ 2 (เริ่มระบบ)
echo.
pause
