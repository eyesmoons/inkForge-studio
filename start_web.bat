@echo off
chcp 936 >nul
title WX Publisher
cd /d "%~dp0"

echo.
echo  ========================================
echo   WX Publisher  starting...
echo  ========================================
echo.

:: If deps marker exists, skip install
if exist ".venv\.installed" goto :run

:: Check system python
python --version >nul 2>&1
if errorlevel 1 goto :no_python

:: Create venv if needed
if not exist ".venv\Scripts\python.exe" (
    echo  [1/2] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :venv_fail
)

:: Check requirements.txt exists
if not exist "requirements.txt" (
    echo  [ERROR] requirements.txt not found.
    echo  Please make sure you are running this from the wechat-publisher folder.
    pause
    exit /b 1
)

:: Install deps
echo  [2/2] Installing packages (first run ~1-3 min)...
echo.
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 goto :pip_fail

:: Mark as installed
echo installed > .venv\.installed

echo.
echo  [OK] Packages installed successfully.
echo.

:run
echo  ========================================
echo   Server: http://localhost:5678
echo   Press Ctrl+C to stop
echo  ========================================
echo.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:5678"
.venv\Scripts\python.exe web_app.py
echo.
echo  Server stopped.
echo.
pause
exit /b 0

:no_python
echo.
echo  [ERROR] Python not found.
echo  Install Python 3.8+ from https://www.python.org/downloads/
echo  Check the option: Add Python to PATH
echo.
pause
exit /b 1

:venv_fail
echo.
echo  [ERROR] Failed to create virtual environment.
echo  Make sure Python 3.8+ is installed.
echo.
pause
exit /b 1

:pip_fail
echo.
echo  [ERROR] pip install failed. Check network and try again.
echo  You can also try running manually:
echo    .venv\Scripts\pip install -r requirements.txt
echo.
pause
exit /b 1
