@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

where docker >nul 2>nul || (
  echo Docker was not found. Install Docker Desktop or Docker Engine first.
  exit /b 1
)

docker info >nul 2>nul || (
  echo Docker is not running. Start Docker Desktop, then run this script again.
  exit /b 1
)

if not exist ".env" (
  copy ".env.offline.example" ".env" >nul
  echo Created .env from .env.offline.example
  echo Edit .env and change POSTGRES_PASSWORD before real production use.
)

if not exist "data\backups" mkdir "data\backups"

:: ---- ตรวจสอบว่า images มีอยู่แล้วหรือไม่ ----
:: ถ้ามีครบทั้ง 4 ตัว (เช่น หลัง load-images.bat) ข้ามขั้นตอน build
:: กรณีนี้เกิดเมื่อใช้ Windows Installer ที่รวม image tars มาด้วย
setlocal EnableDelayedExpansion
set "IMAGES_READY=1"
for %%I in (seamlessfordmis-backend:latest seamlessfordmis-frontend:latest postgres:16 nginx:alpine) do (
    docker image inspect %%I >nul 2>nul || set "IMAGES_READY=0"
)

if "!IMAGES_READY!"=="1" (
    echo Images already present in Docker - skipping build step.
    echo ^(หาก images ไม่ถูกต้อง รัน offline\build-images.bat เพื่อ rebuild^)
) else (
    :: ---- ถ้าพบไฟล์ tar ใน images\ → โหลดจาก offline package ก่อน ----
    set "TAR_FOUND=0"
    if exist "images\seamlessfordmis-backend.tar"  set "TAR_FOUND=1"
    if exist "images\seamlessfordmis-frontend.tar" set "TAR_FOUND=1"

    if "!TAR_FOUND!"=="1" (
        echo พบไฟล์ tar ใน images\ กำลังโหลด Docker images จาก offline package...
        call offline\load-images.bat
        if errorlevel 1 (
            echo [ERROR] โหลด images ล้มเหลว กรุณาตรวจสอบไฟล์ใน images\
            exit /b 1
        )
    ) else (
        echo Building Docker images... ^(ต้องการ internet และ source code^)
        docker compose build || exit /b 1
    )
)

docker compose up -d db || exit /b 1

echo Waiting for database health...
set "DB_READY=0"
for /L %%i in (1,1,60) do (
  docker compose ps db | findstr /I "healthy" >nul && (
    set "DB_READY=1"
    goto db_ready
  )
  timeout /t 2 >nul
)

:db_ready
if not "%DB_READY%"=="1" (
  echo Database did not become healthy in time.
  docker compose ps
  exit /b 1
)

call offline\migrate.bat || exit /b 1
docker compose up -d || exit /b 1
docker compose ps
