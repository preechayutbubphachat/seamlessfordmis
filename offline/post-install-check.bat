@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

echo ============================================================
echo  SeamlessFordMIS — ตรวจสอบระบบหลังติดตั้ง
echo ============================================================
echo.

set "PASS=0"
set "FAIL=0"
set "WARN=0"

:: ---- [1] Docker ติดตั้งอยู่หรือไม่ ----
echo [ตรวจสอบ 1/7] Docker ติดตั้งอยู่หรือไม่...
where docker >nul 2>nul
if errorlevel 1 (
  echo [FAIL] ไม่พบ Docker
  echo        กรุณาติดตั้ง Docker Desktop จาก https://www.docker.com/products/docker-desktop/
  set /a FAIL+=1
  goto :summary
)
echo [OK]   Docker พบที่ระบบ
set /a PASS+=1

:: ---- [2] Docker Engine กำลังทำงานหรือไม่ ----
echo.
echo [ตรวจสอบ 2/7] Docker Engine กำลังทำงานหรือไม่...
docker info >nul 2>nul
if errorlevel 1 (
  echo [FAIL] Docker Engine ยังไม่ทำงาน กรุณาเปิด Docker Desktop แล้วรอจนพร้อม
  set /a FAIL+=1
  goto :summary
)
echo [OK]   Docker Engine พร้อมทำงาน
set /a PASS+=1

:: ---- [3] ไฟล์ตั้งค่า .env ----
echo.
echo [ตรวจสอบ 3/7] ไฟล์ตั้งค่า .env...
if not exist ".env" (
  echo [FAIL] ไม่พบไฟล์ .env
  echo        ไฟล์นี้ควรถูกสร้างโดย Installer โดยอัตโนมัติ
  echo        ถ้าไม่มี ให้คัดลอก .env.offline.example มาเป็น .env และแก้รหัสผ่าน
  set /a FAIL+=1
) else (
  echo [OK]   พบไฟล์ .env
  set /a PASS+=1
)

:: ---- [4] Docker images ถูกโหลดแล้วหรือไม่ ----
echo.
echo [ตรวจสอบ 4/7] Docker images...
set "IMG_FAIL=0"

docker image inspect postgres:16 >nul 2>nul
if errorlevel 1 (
  echo [FAIL] ไม่พบ image: postgres:16
  set "IMG_FAIL=1"
) else (
  echo [OK]   postgres:16
)

docker image inspect nginx:alpine >nul 2>nul
if errorlevel 1 (
  echo [FAIL] ไม่พบ image: nginx:alpine
  set "IMG_FAIL=1"
) else (
  echo [OK]   nginx:alpine
)

docker image inspect seamlessfordmis-backend:latest >nul 2>nul
if errorlevel 1 (
  echo [FAIL] ไม่พบ image: seamlessfordmis-backend:latest
  set "IMG_FAIL=1"
) else (
  echo [OK]   seamlessfordmis-backend:latest
)

docker image inspect seamlessfordmis-frontend:latest >nul 2>nul
if errorlevel 1 (
  echo [FAIL] ไม่พบ image: seamlessfordmis-frontend:latest
  set "IMG_FAIL=1"
) else (
  echo [OK]   seamlessfordmis-frontend:latest
)

if "!IMG_FAIL!"=="1" (
  echo.
  echo        หาก images ไม่ครบ ให้รัน offline\load-images.bat เพื่อโหลด images
  set /a FAIL+=1
) else (
  set /a PASS+=1
)

:: ---- [5] Containers กำลังทำงานหรือไม่ ----
echo.
echo [ตรวจสอบ 5/7] Containers กำลังทำงานหรือไม่...
set "CONTAINERS_RUNNING=0"

docker compose ps --services --filter "status=running" 2>nul | findstr /i "db" >nul 2>nul
if errorlevel 1 (
  echo [WARN] Container db ยังไม่ทำงาน
) else (
  echo [OK]   db
  set "CONTAINERS_RUNNING=1"
)

docker compose ps --services --filter "status=running" 2>nul | findstr /i "backend" >nul 2>nul
if errorlevel 1 (
  echo [WARN] Container backend ยังไม่ทำงาน
) else (
  echo [OK]   backend
)

docker compose ps --services --filter "status=running" 2>nul | findstr /i "frontend" >nul 2>nul
if errorlevel 1 (
  echo [WARN] Container frontend ยังไม่ทำงาน
) else (
  echo [OK]   frontend
)

docker compose ps --services --filter "status=running" 2>nul | findstr /i "nginx" >nul 2>nul
if errorlevel 1 (
  echo [WARN] Container nginx ยังไม่ทำงาน
) else (
  echo [OK]   nginx
)

if "!CONTAINERS_RUNNING!"=="0" (
  echo.
  echo        Containers ยังไม่ทำงาน นี่เป็นเรื่องปกติในการติดตั้งครั้งแรก
  echo        กรุณารัน offline\install.bat เพื่อเริ่มระบบ
  echo        การตรวจสอบขั้นต่อไป (ฐานข้อมูล+เว็บ) จะถูกข้ามไป
  set /a WARN+=1
  goto :summary
) else (
  set /a PASS+=1
)

:: ---- [6] ฐานข้อมูล ----
echo.
echo [ตรวจสอบ 6/7] ฐานข้อมูล PostgreSQL...

set "POSTGRES_USER=seamlessfordmis"
set "POSTGRES_DB=seamlessfordmis"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v /b "#" ".env"`) do (
    if "%%A"=="POSTGRES_USER" set "POSTGRES_USER=%%B"
    if "%%A"=="POSTGRES_DB"   set "POSTGRES_DB=%%B"
  )
)

docker compose exec -T db pg_isready -U "!POSTGRES_USER!" -d "!POSTGRES_DB!" >nul 2>nul
if errorlevel 1 (
  echo [FAIL] ฐานข้อมูลยังไม่พร้อม
  echo        รอสักครู่แล้วลองใหม่ หรือดู log ด้วย: docker compose logs db
  set /a FAIL+=1
) else (
  echo [OK]   ฐานข้อมูลพร้อมทำงาน
  set /a PASS+=1
)

:: ---- [7] Web endpoint ----
echo.
echo [ตรวจสอบ 7/7] Web endpoint...

set "HTTP_PORT=80"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b "HTTP_PORT" ".env"`) do (
    if "%%A"=="HTTP_PORT" set "HTTP_PORT=%%B"
  )
)
set "URL=http://localhost"
if not "!HTTP_PORT!"=="80" set "URL=http://localhost:!HTTP_PORT!"

powershell -NoProfile -Command ^
  "try { $r=(Invoke-WebRequest -Uri '!URL!/healthz' -TimeoutSec 5 -UseBasicParsing).StatusCode; exit ($r -eq 200 ? 0 : 1) } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -Command ^
    "try { $r=(Invoke-WebRequest -Uri '!URL!' -TimeoutSec 5 -UseBasicParsing).StatusCode; exit ($r -ge 200 -and $r -lt 400 ? 0 : 1) } catch { exit 1 }" >nul 2>nul
  if errorlevel 1 (
    echo [FAIL] ไม่สามารถเชื่อมต่อเว็บได้ที่ !URL!
    echo        รอให้ containers พร้อมทำงานแล้วลองใหม่ (ใช้เวลาประมาณ 1-2 นาที)
    set /a FAIL+=1
  ) else (
    echo [OK]   เว็บพร้อมใช้งานที่ !URL!
    set /a PASS+=1
  )
) else (
  echo [OK]   เว็บพร้อมใช้งานที่ !URL!
  set /a PASS+=1
)

:summary
echo.
echo ============================================================
echo  สรุปผลการตรวจสอบ
echo ============================================================
echo.
echo  ผ่าน (PASS)  : !PASS!
echo  คำเตือน (WARN) : !WARN!
echo  ล้มเหลว (FAIL) : !FAIL!
echo.

if "!FAIL!"=="0" (
  if "!WARN!"=="0" (
    echo  [OK] ระบบพร้อมใช้งานสมบูรณ์
  ) else (
    echo  [WARN] ระบบยังไม่ได้เริ่มทำงาน — รัน offline\install.bat เพื่อเริ่มระบบ
  )
) else (
  echo  [FAIL] พบปัญหาที่ต้องแก้ไข — ดูรายละเอียดด้านบน
)

echo.
echo ============================================================
echo.
pause

if "!FAIL!"=="0" (
  if "!WARN!"=="0" (
    exit /b 0
  ) else (
    exit /b 2
  )
) else (
  exit /b 1
)
