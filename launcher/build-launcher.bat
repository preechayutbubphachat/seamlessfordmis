@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  SeamlessFordMIS - Build GUI Launcher EXE
echo ============================================================
echo.
echo  Python + CustomTkinter + PyInstaller
echo  Output: launcher\SeamlessFordMIS-Launcher.exe
echo.

where python >nul 2>nul
if errorlevel 1 goto PYTHON_MISSING

python -c "import sys; print('Python ' + sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto PYTHON_TOO_OLD
echo.

echo [STEP 1/3] Installing dependencies...
python -m pip install --upgrade pip --quiet
if errorlevel 1 goto PIP_FAILED
python -m pip install -r requirements.txt --quiet
if errorlevel 1 goto PIP_FAILED
python -m pip install pyinstaller --quiet
if errorlevel 1 goto PIP_FAILED
echo [OK] Dependencies ready
echo.

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "SeamlessFordMIS-Launcher.exe" del /q "SeamlessFordMIS-Launcher.exe"

echo [STEP 2/3] Building EXE with PyInstaller...
python -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name "SeamlessFordMIS-Launcher" ^
  seamlessfordmis_launcher.py
if errorlevel 1 goto PYINSTALLER_FAILED

echo.
echo [STEP 3/3] Copying EXE...
if not exist "dist\SeamlessFordMIS-Launcher.exe" goto OUTPUT_MISSING
copy /y "dist\SeamlessFordMIS-Launcher.exe" "SeamlessFordMIS-Launcher.exe" >nul
if errorlevel 1 goto COPY_FAILED

for %%F in ("SeamlessFordMIS-Launcher.exe") do echo [OK] launcher\SeamlessFordMIS-Launcher.exe %%~zF bytes
echo.
echo ============================================================
echo  Build complete
echo ============================================================
echo.
echo  Output: launcher\SeamlessFordMIS-Launcher.exe
echo  Installer include path now expects this file.
echo.
echo  Note: Some antivirus products may flag PyInstaller EXEs as a false positive.
echo.
exit /b 0

:PYTHON_MISSING
echo [ERROR] Python was not found. Install Python 3.10+ first.
echo         https://www.python.org/downloads/
exit /b 1

:PYTHON_TOO_OLD
echo [ERROR] Python 3.10+ is required.
exit /b 1

:PIP_FAILED
echo [ERROR] Dependency installation failed.
exit /b 1

:PYINSTALLER_FAILED
echo [ERROR] PyInstaller build failed. Check output above.
echo         Common causes: antivirus blocking PyInstaller, or missing Windows runtime components.
exit /b 1

:OUTPUT_MISSING
echo [ERROR] dist\SeamlessFordMIS-Launcher.exe was not created.
exit /b 1

:COPY_FAILED
echo [ERROR] Could not copy launcher EXE.
exit /b 1
