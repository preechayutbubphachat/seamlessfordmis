@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SeamlessForDMIS — แผงควบคุม

:: ============================================================
::  control-panel.bat
::  แผงควบคุมหลัก SeamlessForDMIS (ระบบ Offline / LAN)
::  รองรับ Windows 10 / 11  —  ต้องการ Docker Desktop
:: ============================================================

:: เปลี่ยน working directory ไปที่ root ของโปรเจค
cd /d "%~dp0\.."

:MENU
cls
echo.
echo  ============================================================
echo   SeamlessForDMIS  ^|  ระบบตรวจคัดกรองโรค  ^|  แผงควบคุม
echo  ============================================================
echo.

:: ตรวจสอบสถานะ Docker ก่อนแสดงเมนู
call :CHECK_DOCKER_QUIET
if errorlevel 1 (
    echo   [!] Docker ไม่พร้อมใช้งาน — บางตัวเลือกอาจทำงานไม่ได้
    echo       กรุณาเปิด Docker Desktop ก่อน แล้วกลับมาที่เมนูนี้
    echo.
)

:: แสดงสถานะย่อ
call :SHOW_QUICK_STATUS

echo.
echo  ============================================================
echo   เลือกรายการ:
echo  ============================================================
echo.
echo    1.  ติดตั้งระบบครั้งแรก    ^(build + migrate + start^)
echo    2.  เริ่มระบบ
echo    3.  หยุดระบบ
echo    4.  รีสตาร์ทระบบ
echo    5.  เปิดหน้าเว็บในเบราว์เซอร์
echo    6.  ตรวจสถานะระบบ
echo    7.  ดู log ล่าสุด  ^(กด Ctrl+C เพื่อหยุด^)
echo    8.  สำรองข้อมูล
echo    9.  กู้คืนข้อมูล
echo   10.  รัน migration  ^(alembic upgrade head^)
echo   11.  แสดง IP สำหรับเครื่องอื่นใน LAN
echo   12.  โหลด Docker images จาก offline package
echo   13.  เปิดคู่มือติดตั้ง
echo   14.  ออกจากโปรแกรม
echo.
set /p CHOICE="  กรุณาเลือก [1-14]: "

if "%CHOICE%"=="1"  goto OPT_INSTALL
if "%CHOICE%"=="2"  goto OPT_START
if "%CHOICE%"=="3"  goto OPT_STOP
if "%CHOICE%"=="4"  goto OPT_RESTART
if "%CHOICE%"=="5"  goto OPT_BROWSER
if "%CHOICE%"=="6"  goto OPT_STATUS
if "%CHOICE%"=="7"  goto OPT_LOGS
if "%CHOICE%"=="8"  goto OPT_BACKUP
if "%CHOICE%"=="9"  goto OPT_RESTORE
if "%CHOICE%"=="10" goto OPT_MIGRATE
if "%CHOICE%"=="11" goto OPT_IP
if "%CHOICE%"=="12" goto OPT_LOAD_IMAGES
if "%CHOICE%"=="13" goto OPT_GUIDE
if "%CHOICE%"=="14" goto OPT_EXIT

echo.
echo   [!] ตัวเลือกไม่ถูกต้อง กรุณาเลือก 1-14
timeout /t 2 >nul
goto MENU

:: ============================================================
::  1. ติดตั้งระบบครั้งแรก
:: ============================================================
:OPT_INSTALL
cls
echo.
echo  ============================================================
echo   [1] ติดตั้งระบบครั้งแรก
echo  ============================================================
echo.
echo   ขั้นตอนนี้จะ: build Docker images, สร้างฐานข้อมูล,
echo   รัน migration และเริ่มบริการทั้งหมด
echo.
echo   หมายเหตุ: หากยังไม่ได้ตั้งรหัสผ่านใน .env
echo   ระบบจะใช้ค่า default — กรุณาเปลี่ยนก่อนใช้งานจริง
echo.
set /p CONFIRM_INSTALL="  ยืนยันติดตั้ง? [Y/N]: "
if /i not "%CONFIRM_INSTALL%"=="Y" goto MENU

call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

echo.
call offline\install.bat
echo.
echo  [เสร็จสิ้น] กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  2. เริ่มระบบ
:: ============================================================
:OPT_START
cls
echo.
echo  ============================================================
echo   [2] เริ่มระบบ
echo  ============================================================
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

docker compose up -d
if errorlevel 1 (
    echo.
    echo  [!] เกิดข้อผิดพลาดขณะเริ่มระบบ ดู log เพื่อตรวจสอบเพิ่มเติม
) else (
    call :SHOW_APP_URL
)
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  3. หยุดระบบ
:: ============================================================
:OPT_STOP
cls
echo.
echo  ============================================================
echo   [3] หยุดระบบ
echo  ============================================================
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

docker compose down
echo.
echo  [เสร็จสิ้น] ระบบหยุดทำงานแล้ว
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  4. รีสตาร์ทระบบ
:: ============================================================
:OPT_RESTART
cls
echo.
echo  ============================================================
echo   [4] รีสตาร์ทระบบ
echo  ============================================================
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

docker compose restart
echo.
call :SHOW_APP_URL
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  5. เปิดหน้าเว็บในเบราว์เซอร์
:: ============================================================
:OPT_BROWSER
cls
echo.
echo  ============================================================
echo   [5] เปิดหน้าเว็บในเบราว์เซอร์
echo  ============================================================
echo.
call :GET_HTTP_PORT
set APP_URL=http://localhost:!HTTP_PORT!
echo   กำลังเปิด: !APP_URL!
start "" "!APP_URL!"
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  6. ตรวจสถานะระบบ
:: ============================================================
:OPT_STATUS
cls
echo.
echo  ============================================================
echo   [6] ตรวจสถานะระบบ
echo  ============================================================
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

call offline\status.bat
echo.
call :SHOW_APP_URL
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  7. ดู log ล่าสุด
:: ============================================================
:OPT_LOGS
cls
echo.
echo  ============================================================
echo   [7] ดู log ล่าสุด  (กด Ctrl+C เพื่อหยุด)
echo  ============================================================
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

docker compose logs --tail=100 -f db backend frontend nginx
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  8. สำรองข้อมูล
:: ============================================================
:OPT_BACKUP
cls
echo.
echo  ============================================================
echo   [8] สำรองข้อมูล
echo  ============================================================
echo.
echo   ระบบจะสำรอง:
echo     - ฐานข้อมูลทั้งหมด (pg_dump)
echo     - ไฟล์ต้นฉบับและไฟล์อัปโหลด
echo.
echo   ข้อมูลสำรองจะถูกบันทึกไว้ที่: data\backups\
echo.
echo   [!] ข้อมูลสำรองมีข้อมูลผู้ป่วย — เก็บในพื้นที่ปลอดภัย
echo       ห้ามส่งออกนอกเครือข่ายโรงพยาบาล
echo.
set /p CONFIRM_BACKUP="  ยืนยันสำรองข้อมูล? [Y/N]: "
if /i not "%CONFIRM_BACKUP%"=="Y" goto MENU

call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

call offline\backup.bat
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  9. กู้คืนข้อมูล
:: ============================================================
:OPT_RESTORE
cls
echo.
echo  ============================================================
echo   [9] กู้คืนข้อมูล
echo  ============================================================
echo.
echo   คำเตือน: การกู้คืนจะเขียนทับข้อมูลปัจจุบันทั้งหมด
echo.
echo   แนะนำ: สำรองข้อมูลปัจจุบันก่อน (ตัวเลือก 8)
echo   ก่อนดำเนินการกู้คืน
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

call offline\restore.bat
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  10. รัน migration
:: ============================================================
:OPT_MIGRATE
cls
echo.
echo  ============================================================
echo   [10] รัน migration (alembic upgrade head)
echo  ============================================================
echo.
echo   ขั้นตอนนี้จะอัปเดต schema ฐานข้อมูลให้เป็นเวอร์ชันล่าสุด
echo   ใช้หลังจาก pull โค้ดใหม่หรืออัปเดตระบบ
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

call offline\migrate.bat
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  11. แสดง IP สำหรับเครื่องอื่นใน LAN
:: ============================================================
:OPT_IP
cls
echo.
echo  ============================================================
echo   [11] IP ของเครื่องนี้สำหรับเครื่องอื่นใน LAN
echo  ============================================================
echo.
call :GET_HTTP_PORT

echo   เครื่องอื่นในวงเครือข่ายเดียวกันสามารถเข้าใช้ที่:
echo.

:: แสดง IPv4 ที่ไม่ใช่ loopback
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R "IPv4"') do (
    set "RAW_IP=%%A"
    set "IP=!RAW_IP: =!"
    if not "!IP!"=="127.0.0.1" (
        if "!HTTP_PORT!"=="80" (
            echo     http://!IP!
        ) else (
            echo     http://!IP!:!HTTP_PORT!
        )
    )
)

echo.
echo   เครื่องนี้เองเข้าได้ที่:
if "!HTTP_PORT!"=="80" (
    echo     http://localhost
) else (
    echo     http://localhost:!HTTP_PORT!
)
echo.
echo   หมายเหตุ: เครื่องอื่นต้องอยู่ใน LAN เดียวกัน
echo   และ firewall ต้องอนุญาต port !HTTP_PORT!
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU


:: ============================================================
::  12. โหลด Docker images จาก offline package
:: ============================================================
:OPT_LOAD_IMAGES
cls
echo.
echo  ============================================================
echo   [12] โหลด Docker Images จาก Offline Package
echo  ============================================================
echo.
echo   สคริปต์นี้จะโหลด Docker images จากไฟล์ tar ใน images\
echo   ใช้สำหรับเครื่องที่ไม่มี internet หรือหลังติดตั้งระบบใหม่
echo.
call :CHECK_DOCKER_REQUIRED
if errorlevel 1 goto MENU

call offline\load-images.bat
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  13. เปิดคู่มือติดตั้ง
:: ============================================================
:OPT_GUIDE
cls
echo.
echo  ============================================================
echo   [13] เปิดคู่มือติดตั้งและการใช้งาน
echo  ============================================================
echo.
set "GUIDE_PATH=%~dp0..\OFFLINE_INSTALL.md"
if exist "!GUIDE_PATH!" (
    echo   กำลังเปิด OFFLINE_INSTALL.md...
    start "" "!GUIDE_PATH!"
) else (
    echo   [!] ไม่พบไฟล์คู่มือ: !GUIDE_PATH!
    echo   ลองเปิดไฟล์ OFFLINE_INSTALL.md ด้วยตนเองจาก Windows Explorer
)
echo.
echo  กด Enter เพื่อกลับเมนูหลัก...
pause >nul
goto MENU

:: ============================================================
::  14. ออกจากโปรแกรม
:: ============================================================
:OPT_EXIT
cls
echo.
echo   ออกจากแผงควบคุม SeamlessForDMIS
echo   ระบบยังคงทำงานอยู่ในเบื้องหลัง
echo   (ใช้ตัวเลือก 3 เพื่อหยุดระบบ)
echo.
exit /b 0

:: ============================================================
::  Subroutine: CHECK_DOCKER_QUIET
::  ตรวจ Docker โดยไม่แสดงข้อความ — คืน errorlevel 1 ถ้าไม่พร้อม
:: ============================================================
:CHECK_DOCKER_QUIET
where docker >nul 2>nul
if errorlevel 1 exit /b 1
docker info >nul 2>nul
if errorlevel 1 exit /b 1
exit /b 0

:: ============================================================
::  Subroutine: CHECK_DOCKER_REQUIRED
::  ตรวจ Docker พร้อมแสดงข้อความวิธีแก้ — คืน errorlevel 1 ถ้าไม่พร้อม
:: ============================================================
:CHECK_DOCKER_REQUIRED
where docker >nul 2>nul
if errorlevel 1 (
    echo.
    echo  [!] ไม่พบ Docker บนเครื่องนี้
    echo.
    echo   วิธีแก้: ติดตั้ง Docker Desktop จาก https://www.docker.com/products/docker-desktop
    echo   แล้วรีสตาร์ทเครื่อง จากนั้นกลับมาที่แผงควบคุมนี้
    echo.
    echo  กด Enter เพื่อกลับเมนูหลัก...
    pause >nul
    exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
    echo.
    echo  [!] Docker ยังไม่ได้เปิดทำงาน
    echo.
    echo   วิธีแก้:
    echo     1. เปิด Docker Desktop จาก Start Menu
    echo     2. รอจนไอคอน Docker ที่ Taskbar หยุดหมุน
    echo     3. กลับมาที่แผงควบคุมนี้แล้วลองใหม่
    echo.
    echo  กด Enter เพื่อกลับเมนูหลัก...
    pause >nul
    exit /b 1
)
exit /b 0

:: ============================================================
::  Subroutine: GET_HTTP_PORT
::  อ่าน HTTP_PORT จาก .env (default 80) → ตั้ง !HTTP_PORT!
:: ============================================================
:GET_HTTP_PORT
set "HTTP_PORT=80"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%K in (".env") do (
        if "%%K"=="HTTP_PORT" set "HTTP_PORT=%%L"
    )
)
exit /b 0

:: ============================================================
::  Subroutine: SHOW_APP_URL
::  แสดง URL ของ application
:: ============================================================
:SHOW_APP_URL
call :GET_HTTP_PORT
if "!HTTP_PORT!"=="80" (
    echo   เข้าใช้งานได้ที่: http://localhost
) else (
    echo   เข้าใช้งานได้ที่: http://localhost:!HTTP_PORT!
)
exit /b 0

:: ============================================================
::  Subroutine: SHOW_QUICK_STATUS
::  แสดงสถานะย่อ (running/stopped) ของบริการหลัก
:: ============================================================
:SHOW_QUICK_STATUS
where docker >nul 2>nul
if errorlevel 1 (
    echo   สถานะ: ไม่พบ Docker
    exit /b 0
)
docker info >nul 2>nul
if errorlevel 1 (
    echo   สถานะ: Docker ยังไม่เปิด
    exit /b 0
)

set "RUNNING_COUNT=0"
for /f %%C in ('docker compose ps --services --filter status^=running 2^>nul ^| find /c /v ""') do set "RUNNING_COUNT=%%C"

if "!RUNNING_COUNT!"=="0" (
    echo   สถานะ: [หยุดทำงาน]  ไม่มีบริการที่กำลังรัน
) else if "!RUNNING_COUNT!"=="4" (
    call :GET_HTTP_PORT
    if "!HTTP_PORT!"=="80" (
        echo   สถานะ: [ทำงานอยู่]  !RUNNING_COUNT!/4 บริการ  ^|  http://localhost
    ) else (
        echo   สถานะ: [ทำงานอยู่]  !RUNNING_COUNT!/4 บริการ  ^|  http://localhost:!HTTP_PORT!
    )
) else (
    echo   สถานะ: [บางส่วน]   !RUNNING_COUNT!/4 บริการกำลังรัน
)
exit /b 0
