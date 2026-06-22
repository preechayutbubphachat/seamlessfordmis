@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

:: อ่าน HTTP_PORT จาก .env (ค่าเริ่มต้น 80)
set "HTTP_PORT=80"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b "HTTP_PORT" ".env"`) do (
    if "%%A"=="HTTP_PORT" set "HTTP_PORT=%%B"
  )
)

set "URL=http://localhost"
if not "!HTTP_PORT!"=="80" set "URL=http://localhost:!HTTP_PORT!"

echo เปิดเว็บ SeamlessFordMIS...
echo URL: !URL!
echo.
start "" "!URL!"

exit /b 0
