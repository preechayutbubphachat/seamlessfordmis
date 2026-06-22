@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SeamlessForDMIS — Health Check

:: ============================================================
::  healthcheck.bat
::  ตรวจสุขภาพระบบ SeamlessForDMIS แบบละเอียด
::  แสดง: Docker, containers, HTTP endpoints, disk space
:: ============================================================

cd /d "%~dp0\.."
set "FAIL_COUNT=0"
set "WARN_COUNT=0"

echo.
echo  ============================================================
echo   SeamlessForDMIS — Health Check
echo  ============================================================
echo.

:: ── 1. Docker Engine ─────────────────────────────────────────
echo  [1/5] Docker Engine
where docker >nul 2>nul
if errorlevel 1 (
    echo        FAIL  ไม่พบ docker ใน PATH
    echo               ติดตั้ง Docker Desktop แล้วรีสตาร์ทเครื่อง
    set /a FAIL_COUNT+=1
    goto :DONE
)
docker info >nul 2>nul
if errorlevel 1 (
    echo        FAIL  Docker ยังไม่เปิดทำงาน
    echo               เปิด Docker Desktop รอจนไอคอนหยุดหมุน แล้วลองใหม่
    set /a FAIL_COUNT+=1
    goto :DONE
)
docker compose version >nul 2>nul
if errorlevel 1 (
    echo        FAIL  ไม่พบ docker compose plugin
    set /a FAIL_COUNT+=1
    goto :DONE
)
echo        OK    Docker Engine พร้อมใช้งาน

if not exist ".env" (
    echo        FAIL  ไม่พบไฟล์ .env — รัน offline\install.bat หรือ copy .env.offline.example เป็น .env
    set /a FAIL_COUNT+=1
    goto :DONE
)

:: ── 2. Container status ──────────────────────────────────────
echo.
echo  [2/5] Container Status
docker compose ps --format "table {{.Service}}\t{{.Status}}" 2>nul
echo.

set "ALL_HEALTHY=1"
for %%S in (db backend nginx) do (
    docker compose ps %%S 2>nul | findstr /I "healthy" >nul
    if errorlevel 1 (
        echo        FAIL  %%S — ไม่ healthy
        set "ALL_HEALTHY=0"
        set /a FAIL_COUNT+=1
    ) else (
        echo        OK    %%S — healthy
    )
)
if "!ALL_HEALTHY!"=="1" (
    echo.
    echo        ผลรวม: บริการหลักทุกตัว healthy
) else (
    echo.
    echo        ผลรวม: มีบริการที่ยังไม่ healthy
    echo                ดู log ด้วย: docker compose logs ^<service^>
)

:: ── 3. HTTP Endpoint ─────────────────────────────────────────
echo.
echo  [3/5] HTTP Endpoints
set "HTTP_PORT=80"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%K in (".env") do (
        if "%%K"=="HTTP_PORT" set "HTTP_PORT=%%L"
    )
)

:: Backend health (direct)
docker compose exec -T backend curl -fsS http://localhost:8010/health >nul 2>nul
if errorlevel 1 (
    echo        FAIL  Backend /health  ^(http://localhost:8010/health^)
    set /a FAIL_COUNT+=1
) else (
    echo        OK    Backend /health
)

:: nginx (via host port)
curl -fsS --max-time 5 http://localhost:!HTTP_PORT! >nul 2>nul
if errorlevel 1 (
    echo        FAIL  nginx port !HTTP_PORT! — ไม่ตอบสนอง ^(curl ไม่พบหรือ port ยังไม่พร้อม^)
    set /a FAIL_COUNT+=1
) else (
    echo        OK    nginx port !HTTP_PORT!  ^(http://localhost:!HTTP_PORT!^)
)

:: API Smoke Test
docker compose exec -T backend curl -fsS --max-time 5 "http://localhost:8010/api/system/status" >nul 2>nul
if errorlevel 1 (
    echo        FAIL  API /api/system/status — ไม่ตอบสนอง
    set /a FAIL_COUNT+=1
) else (
    echo        OK    API /api/system/status
)

:: ── 4. Volume / Disk ─────────────────────────────────────────
echo.
echo  [4/5] Docker Volumes
docker volume ls --filter name=seamlessfordmis 2>nul | findstr /V "VOLUME NAME"
echo.

echo  [5/5] Disk Space (โฟลเดอร์ data\backups)
if exist "data\backups" (
    for /f "tokens=3" %%D in ('dir /s /-c "data\backups" 2^>nul ^| findstr /R "ไฟล์.*ไบต์\|files.*bytes"') do (
        echo        ขนาดสำรองข้อมูลสะสม: %%D bytes
    )
) else (
    echo        WARN  ยังไม่มีไฟล์สำรอง
    set /a WARN_COUNT+=1
)

:DONE
echo.
echo  สรุป: FAIL=!FAIL_COUNT!  WARN=!WARN_COUNT!
echo  ============================================================
echo   Health check เสร็จสิ้น
echo  ============================================================
echo.
if "%~1"=="" pause
if !FAIL_COUNT! GTR 0 exit /b 1
if !WARN_COUNT! GTR 0 exit /b 2
exit /b 0
