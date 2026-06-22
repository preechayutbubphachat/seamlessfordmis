@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

echo ============================================================
echo  SeamlessFordMIS — บันทึก Docker Images สำหรับใช้งาน Offline
echo ============================================================
echo.

:: ---- ตรวจสอบ Docker ----
where docker >nul 2>nul || (
  echo [ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Desktop ก่อน
  exit /b 1
)
docker info >nul 2>nul || (
  echo [ERROR] Docker ยังไม่ทำงาน กรุณาเปิด Docker Desktop แล้วรอจนพร้อม
  exit /b 1
)
echo [OK] Docker พร้อมทำงาน

:: ---- ตรวจสอบ internet (pull images จาก Docker Hub) ----
echo.
echo [INFO] ต้องการ internet เพื่อ pull base images และ build
echo        กระบวนการนี้อาจใช้เวลา 10-30 นาที ขึ้นอยู่กับความเร็วอินเทอร์เน็ต
echo.

:: ---- สร้าง images/ directory ----
if not exist "images" (
  mkdir "images"
  echo [OK] สร้างโฟลเดอร์ images\
)

:: ---- Pull base images ----
echo [PULL] กำลัง pull postgres:16...
docker pull postgres:16 || (
  echo [ERROR] Pull postgres:16 ล้มเหลว ตรวจสอบการเชื่อมต่อ internet
  exit /b 1
)

echo [PULL] กำลัง pull nginx:alpine...
docker pull nginx:alpine || (
  echo [ERROR] Pull nginx:alpine ล้มเหลว
  exit /b 1
)

:: ---- Build application images ----
echo.
echo [BUILD] กำลัง build application images...
docker compose build || (
  echo [ERROR] Build ล้มเหลว ตรวจสอบ docker-compose.yml และ Dockerfile
  exit /b 1
)

:: ---- Save images เป็น tar files ----
echo.
echo [SAVE] กำลังบันทึก images เป็นไฟล์ tar...

echo       บันทึก seamlessfordmis-backend.tar...
docker save -o "images\seamlessfordmis-backend.tar" seamlessfordmis-backend:latest || (
  echo [ERROR] บันทึก backend image ล้มเหลว
  exit /b 1
)

echo       บันทึก seamlessfordmis-frontend.tar...
docker save -o "images\seamlessfordmis-frontend.tar" seamlessfordmis-frontend:latest || (
  echo [ERROR] บันทึก frontend image ล้มเหลว
  exit /b 1
)

echo       บันทึก postgres-16.tar...
docker save -o "images\postgres-16.tar" postgres:16 || (
  echo [ERROR] บันทึก postgres image ล้มเหลว
  exit /b 1
)

echo       บันทึก nginx-alpine.tar...
docker save -o "images\nginx-alpine.tar" nginx:alpine || (
  echo [ERROR] บันทึก nginx image ล้มเหลว
  exit /b 1
)

:: ---- แสดงสรุปและขนาดไฟล์ ----
echo.
echo ============================================================
echo  บันทึก Docker images สำเร็จ!
echo ============================================================
echo.
echo  ไฟล์ที่สร้างในโฟลเดอร์ images\:
echo.

set "TOTAL=0"
for %%F in (
  "images\seamlessfordmis-backend.tar"
  "images\seamlessfordmis-frontend.tar"
  "images\postgres-16.tar"
  "images\nginx-alpine.tar"
) do (
  if exist %%F (
    for %%S in (%%F) do (
      set /a SIZE_MB=%%~zS / 1048576
      echo    %%~nxF — !SIZE_MB! MB
      set /a TOTAL+=%%~zS
    )
  )
)
set /a TOTAL_MB=TOTAL / 1048576
echo.
echo  รวมทั้งหมด: %TOTAL_MB% MB

echo.
echo  ขั้นตอนต่อไป:
echo    1. รัน installer\build-installer.bat offline-full เพื่อ build Windows installer
echo    2. หรือ zip โฟลเดอร์ทั้งหมดรวม images\ เพื่อแจกจ่าย offline
echo    3. บนเครื่องปลายทาง รัน offline\load-images.bat ก่อนใช้งาน
echo.
