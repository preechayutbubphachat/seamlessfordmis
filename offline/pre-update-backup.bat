@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

echo ============================================================
echo  SeamlessFordMIS — สำรองข้อมูลก่อนอัปเดตระบบ
echo ============================================================
echo.
echo  สคริปต์นี้สำรองข้อมูลทั้งหมดก่อนทำการอัปเดตหรืออัปเกรดระบบ
echo  ควรรันทุกครั้งก่อนที่จะ:
echo    - อัปเดต Docker images เป็นเวอร์ชันใหม่
echo    - รัน database migration
echo    - เปลี่ยน configuration สำคัญ
echo    - ถอนการติดตั้งและติดตั้งใหม่
echo.

:: ---- ตรวจสอบ Docker ----
where docker >nul 2>nul || (
  echo [ERROR] ไม่พบ Docker กรุณาเปิด Docker Desktop ก่อน
  pause
  exit /b 1
)
docker info >nul 2>nul || (
  echo [ERROR] Docker ยังไม่ทำงาน กรุณาเปิด Docker Desktop แล้วรอจนพร้อม
  pause
  exit /b 1
)
echo [OK] Docker พร้อมทำงาน

:: ---- ตรวจสอบว่า containers กำลังทำงาน ----
echo.
echo [INFO] ตรวจสอบสถานะ containers...
docker compose ps --services --filter "status=running" 2>nul | findstr "db" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [WARNING] Container db ไม่ได้ทำงานอยู่
  echo           ไม่สามารถ dump ฐานข้อมูลได้หาก db ไม่ทำงาน
  echo.
  echo  ตัวเลือก:
  echo    1. เริ่มระบบก่อนด้วย offline\start.bat แล้วรันสคริปต์นี้ใหม่
  echo    2. สำรองเฉพาะ Docker volumes โดยไม่มี database dump
  echo.
  choice /C YN /M "ต้องการสำรองเฉพาะ Docker volumes โดยไม่มี database dump หรือไม่?"
  if errorlevel 2 (
    echo.
    echo   ยกเลิก กรุณาเริ่มระบบก่อนแล้วรันสคริปต์นี้ใหม่
    echo.
    pause
    exit /b 1
  )
  set "SKIP_DB_DUMP=1"
) else (
  echo [OK] Container db กำลังทำงาน
  set "SKIP_DB_DUMP=0"
)

:: ---- อ่านค่าจาก .env ----
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v /b "#" ".env"`) do (
    if not "%%A"=="" set "%%A=%%B"
  )
)
if "%POSTGRES_USER%"=="" set "POSTGRES_USER=seamlessfordmis"
if "%POSTGRES_DB%"==""   set "POSTGRES_DB=seamlessfordmis"

:: ---- สร้าง timestamp และ backup directory ----
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "BACKUP_DIR=data\backups\pre-update-%STAMP%"

echo.
echo [INFO] สร้างโฟลเดอร์สำรอง: %BACKUP_DIR%
mkdir "%BACKUP_DIR%" >nul 2>nul || (
  echo [ERROR] ไม่สามารถสร้างโฟลเดอร์ %BACKUP_DIR% ได้
  pause
  exit /b 1
)

set "BACKUP_OK=1"

:: ---- Step 1: Database dump ----
echo.
if "!SKIP_DB_DUMP!"=="1" (
  echo [SKIP] ข้ามการ dump ฐานข้อมูล (container db ไม่ได้ทำงาน)
) else (
  echo [STEP 1/5] กำลัง dump ฐานข้อมูล PostgreSQL...
  docker compose exec -T db pg_dump -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" > "%BACKUP_DIR%\database.sql" 2>nul
  if errorlevel 1 (
    echo [ERROR] Dump ฐานข้อมูลล้มเหลว
    echo         ตรวจสอบว่า container db ทำงานปกติ: docker compose ps
    set "BACKUP_OK=0"
  ) else (
    for %%F in ("%BACKUP_DIR%\database.sql") do (
      set /a DB_MB=%%~zF / 1048576
    )
    echo [OK]   dump ฐานข้อมูลสำเร็จ (!DB_MB! MB)
  )
)

:: ---- Step 2: source_data volume ----
echo.
echo [STEP 2/5] กำลังสำรอง volume source_data...
docker run --rm ^
  -v seamlessfordmis_source_data:/source_data:ro ^
  -v "%cd%\%BACKUP_DIR%":/backup ^
  nginx:alpine tar -czf /backup/source_data.tar.gz -C / source_data 2>nul
if errorlevel 1 (
  echo [WARNING] สำรอง source_data ล้มเหลว (อาจยังไม่มีข้อมูล)
) else (
  echo [OK]   source_data.tar.gz สำเร็จ
)

:: ---- Step 3: uploads volume ----
echo.
echo [STEP 3/5] กำลังสำรอง volume uploads...
docker run --rm ^
  -v seamlessfordmis_uploads:/uploads:ro ^
  -v "%cd%\%BACKUP_DIR%":/backup ^
  nginx:alpine tar -czf /backup/uploads.tar.gz -C / uploads 2>nul
if errorlevel 1 (
  echo [WARNING] สำรอง uploads ล้มเหลว (อาจยังไม่มีข้อมูล)
) else (
  echo [OK]   uploads.tar.gz สำเร็จ
)

:: ---- Step 4: reports volume ----
echo.
echo [STEP 4/5] กำลังสำรอง volume reports...
docker run --rm ^
  -v seamlessfordmis_reports:/reports:ro ^
  -v "%cd%\%BACKUP_DIR%":/backup ^
  nginx:alpine tar -czf /backup/reports.tar.gz -C / reports 2>nul
if errorlevel 1 (
  echo [WARNING] สำรอง reports ล้มเหลว (อาจยังไม่มีข้อมูล)
) else (
  echo [OK]   reports.tar.gz สำเร็จ
)

:: ---- Step 4b: logs volume ----
echo.
echo [STEP 4b] กำลังสำรอง volume logs...
docker run --rm ^
  -v seamlessfordmis_logs:/logs:ro ^
  -v "%cd%\%BACKUP_DIR%":/backup ^
  nginx:alpine tar -czf /backup/logs.tar.gz -C / logs 2>nul
if errorlevel 1 (
  echo [WARNING] สำรอง logs ล้มเหลว (อาจยังไม่มีข้อมูล)
) else (
  echo [OK]   logs.tar.gz สำเร็จ
)

:: ---- Step 5: คัดลอก .env ----
echo.
echo [STEP 5/5] สำรองไฟล์ตั้งค่า .env...
if exist ".env" (
  copy /y ".env" "%BACKUP_DIR%\.env.bak" >nul 2>nul
  echo [OK]   .env.bak สำเร็จ
) else (
  echo [WARNING] ไม่พบ .env
)

:: ---- สรุป ----
echo.
echo ============================================================
if "!BACKUP_OK!"=="1" (
  echo  สำรองข้อมูลก่อนอัปเดตเสร็จสิ้น
) else (
  echo  สำรองข้อมูลเสร็จสิ้น (มีบางส่วนล้มเหลว — ดูข้อความด้านบน)
)
echo ============================================================
echo.
echo  ที่เก็บข้อมูลสำรอง: %BACKUP_DIR%\
echo.
echo  ไฟล์ที่สำรอง:
if exist "%BACKUP_DIR%\database.sql"        echo    • database.sql         (ฐานข้อมูลผู้ป่วย)
if exist "%BACKUP_DIR%\source_data.tar.gz" echo    • source_data.tar.gz   (ข้อมูลต้นทาง)
if exist "%BACKUP_DIR%\uploads.tar.gz"     echo    • uploads.tar.gz       (ไฟล์ที่อัปโหลด)
if exist "%BACKUP_DIR%\reports.tar.gz"     echo    • reports.tar.gz       (รายงาน)
if exist "%BACKUP_DIR%\logs.tar.gz"        echo    • logs.tar.gz          (Logs)
if exist "%BACKUP_DIR%\.env.bak"           echo    • .env.bak             (ไฟล์ตั้งค่า)
echo.
echo ============================================================
echo  [!] ข้อมูลสำรองมีข้อมูลผู้ป่วย — เก็บในพื้นที่ปลอดภัยภายในหน่วยงาน
echo      ห้ามส่งออกนอกเครือข่ายโรงพยาบาล ห้าม upload ขึ้น cloud สาธารณะ
echo ============================================================
echo.
echo  ขั้นตอนต่อไป — ดำเนินการอัปเดตได้เลย:
echo    1. รัน offline\stop.bat เพื่อหยุดระบบ
echo    2. ดำเนินการอัปเดต (เปลี่ยน images หรือรัน migration)
echo    3. รัน offline\start.bat เพื่อเริ่มระบบใหม่
echo    4. หากมีปัญหา ใช้ไฟล์สำรองใน %BACKUP_DIR%\ เพื่อกู้คืน
echo.
pause
