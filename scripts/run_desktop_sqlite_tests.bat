@echo off
REM ============================================================
REM  SeamlessFordMIS - Desktop SQLite D3 Gate Test Runner (Windows)
REM  Runs G4 (compile), G1 (SQLite smoke), G5 (regression).
REM  Writes everything to: desktop-sqlite-test-results.txt
REM  Usage: double-click, or:  scripts\run_desktop_sqlite_tests.bat
REM  Then paste desktop-sqlite-test-results.txt back to the assistant.
REM ============================================================
setlocal EnableExtensions

REM --- locate repo root (this script lives in <root>\scripts) ---
set "ROOT=%~dp0.."
pushd "%ROOT%" || (echo Cannot cd to repo root & exit /b 1)
set "ROOT=%CD%"
set "LOG=%ROOT%\desktop-sqlite-test-results.txt"

echo SeamlessFordMIS Desktop SQLite D3 Gate run > "%LOG%"
echo Started: %DATE% %TIME% >> "%LOG%"
echo Repo: %ROOT% >> "%LOG%"
echo. >> "%LOG%"

cd backend || (echo backend folder missing & exit /b 1)

REM --- venv (create if missing) ---
if not exist ".venv\Scripts\python.exe" (
    echo [setup] creating venv...
    python -m venv .venv || (echo venv creation failed & goto :show)
)
call .venv\Scripts\activate.bat

echo [setup] installing backend/requirements.txt (includes pytest)...
python -m pip install --upgrade pip >> "%LOG%" 2>&1
python -m pip install -r requirements.txt >> "%LOG%" 2>&1

echo ============================================================ >> "%LOG%"
echo G4 - compileall backend/app >> "%LOG%"
echo ============================================================ >> "%LOG%"
python -m compileall -q app >> "%LOG%" 2>&1
echo G4 exit code: %ERRORLEVEL% >> "%LOG%"
echo. >> "%LOG%"

echo ============================================================ >> "%LOG%"
echo G1 - SQLite workflow smoke suite (desktop_local + sqlite) >> "%LOG%"
echo ============================================================ >> "%LOG%"
set "APP_EDITION=desktop_local"
set "DATABASE_ENGINE=sqlite"
python -m pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly --tb=short >> "%LOG%" 2>&1
echo G1 exit code: %ERRORLEVEL% >> "%LOG%"
set "APP_EDITION="
set "DATABASE_ENGINE="
echo. >> "%LOG%"

echo ============================================================ >> "%LOG%"
echo G5 - Regression (rest of suite; uses your .env / PostgreSQL) >> "%LOG%"
echo NOTE: failures here may just mean PostgreSQL is not running. >> "%LOG%"
echo ============================================================ >> "%LOG%"
python -m pytest tests/ -v --ignore=tests/test_desktop_sqlite_workflow.py --tb=short >> "%LOG%" 2>&1
echo G5 exit code: %ERRORLEVEL% >> "%LOG%"
echo. >> "%LOG%"
echo Finished: %DATE% %TIME% >> "%LOG%"

:show
echo.
echo ============================================================
echo Results written to: %LOG%
echo ============================================================
type "%LOG%"
popd
endlocal
