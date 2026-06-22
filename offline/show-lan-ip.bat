@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

:: อ่าน HTTP_PORT จาก .env
set "HTTP_PORT=80"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b "HTTP_PORT" ".env"`) do (
    if "%%A"=="HTTP_PORT" set "HTTP_PORT=%%B"
  )
)

echo.
echo ============================================================
echo  SeamlessFordMIS — IP สำหรับเครื่องอื่นใน LAN
echo ============================================================
echo.
echo  IP ของเครื่องนี้ที่เครื่องอื่น LAN ใช้เข้าระบบได้:
echo.

for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /C:"IPv4"') do (
  set "IP=%%I"
  :: ตัดช่องว่างนำหน้า
  for /f "tokens=* delims= " %%T in ("!IP!") do set "IP=%%T"
  if not "!IP!"=="127.0.0.1" (
    if "!HTTP_PORT!"=="80" (
      echo    !IP!  ^>  http://!IP!
    ) else (
      echo    !IP!  ^>  http://!IP!:!HTTP_PORT!
    )
  )
)

echo.
echo  วิธีใช้:
echo    1. บอก URL ด้านบนให้ผู้ใช้เครื่องอื่นใน LAN เดียวกัน
echo    2. ผู้ใช้เปิด browser พิมพ์ URL แล้วใช้งานได้ทันที
echo.
echo  ถ้าเข้าไม่ได้จากเครื่องอื่น ให้ตรวจสอบ Windows Firewall:
echo    เปิด port !HTTP_PORT! สำหรับ Inbound TCP
echo    หรือรัน PowerShell (Admin):
echo    New-NetFirewallRule -DisplayName "SeamlessFordMIS" -Direction Inbound -Protocol TCP -LocalPort !HTTP_PORT! -Action Allow
echo.
