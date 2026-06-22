@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

:: ============================================================
:: SeamlessFordMIS — Test Runner (Windows)
:: ============================================================
:: Usage:
::   run_tests.bat          -> D2.15: SQLite smoke tests only (no .env needed)
::   run_tests.bat all      -> D2.15 + D2.16 (needs .env with DATABASE_URL)
::   run_tests.bat d2.16    -> D2.16 regression only (needs .env with DATABASE_URL)
:: ============================================================

set MODE=%~1
if "%MODE%"=="" set MODE=d2.15

:: ── Locate Python ───────────────────────────────────────────
set PYTHON=
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    echo [OK] venv found: .venv\Scripts\python.exe
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
        echo [WARN] No .venv found — using system Python. Consider creating a venv first.
    ) else (
        echo [ERROR] Python not found. Install Python 3.11+ or create .venv first.
        exit /b 1
    )
)

:: ── Verify pytest is available ──────────────────────────────
%PYTHON% -m pytest --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pytest not installed. Run: %PYTHON% -m pip install -r requirements.txt
    exit /b 1
)

:: ── Run tests ───────────────────────────────────────────────
if "%MODE%"=="d2.15" goto :run_d215
if "%MODE%"=="d2.16" goto :run_d216
if "%MODE%"=="all"   goto :run_all

echo [ERROR] Unknown mode: %MODE%
echo Usage: run_tests.bat [d2.15 ^| d2.16 ^| all]
exit /b 1


:run_d215
echo.
echo ====================================================
echo  D2.15 — SQLite Desktop Smoke Tests (13 tests)
echo  No .env or PostgreSQL required.
echo ====================================================
%PYTHON% -m pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly
set EXIT_D215=%errorlevel%
echo.
if %EXIT_D215%==0 (
    echo [PASS] D2.15 — All 13 SQLite smoke tests passed.
    echo        Phase D3 Desktop Shell gate G1 = CLEARED.
) else (
    echo [FAIL] D2.15 — One or more tests failed.
    echo        Run with --tb=long for full traceback:
    echo        %PYTHON% -m pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly --tb=long
)
exit /b %EXIT_D215%


:run_d216
echo.
echo ====================================================
echo  D2.16 — LAN/PostgreSQL Regression Tests
echo  Requires: .env with DATABASE_URL pointing to PostgreSQL
echo ====================================================
if not exist ".env" (
    echo [ERROR] No .env file found.
    echo         Create backend\.env with:
    echo         DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/hospital_group_history
    exit /b 1
)
%PYTHON% -m pytest tests/ -v --ignore=tests/test_desktop_sqlite_workflow.py
set EXIT_D216=%errorlevel%
echo.
if %EXIT_D216%==0 (
    echo [PASS] D2.16 — All LAN/PostgreSQL regression tests passed.
    echo        Phase D3 Desktop Shell gate G5 = CLEARED.
) else (
    echo [FAIL] D2.16 — One or more regression tests failed.
)
exit /b %EXIT_D216%


:run_all
echo.
echo ====================================================
echo  Running D2.15 + D2.16
echo ====================================================

call :run_d215_sub
set RESULT_215=%errorlevel%

call :run_d216_sub
set RESULT_216=%errorlevel%

echo.
echo ====================================================
echo  Gate Summary
echo ====================================================
if %RESULT_215%==0 (echo  G1 [PASS] D2.15 SQLite smoke tests) else (echo  G1 [FAIL] D2.15 SQLite smoke tests)
if %RESULT_216%==0 (echo  G5 [PASS] D2.16 PostgreSQL regression) else (echo  G5 [FAIL] D2.16 PostgreSQL regression)
echo.
if %RESULT_215%==0 if %RESULT_216%==0 (
    echo  [GO] Both gates cleared — Phase D3 Desktop Shell Prototype is UNLOCKED.
    exit /b 0
)
echo  [NO-GO] Fix failing tests before starting D3.
exit /b 1


:run_d215_sub
echo.
echo [D2.15] SQLite smoke tests...
%PYTHON% -m pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly
exit /b %errorlevel%

:run_d216_sub
echo.
echo [D2.16] PostgreSQL regression tests...
if not exist ".env" (
    echo [SKIP] D2.16 — No .env file. Create .env with DATABASE_URL to run PostgreSQL regression.
    exit /b 1
)
%PYTHON% -m pytest tests/ -v --ignore=tests/test_desktop_sqlite_workflow.py
exit /b %errorlevel%
