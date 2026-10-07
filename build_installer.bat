@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ======================================================
echo   WeChat Publisher - Windows Installer Build
echo ======================================================

REM Step 1: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [1/6] ERROR: Python not found, please install Python 3.8+
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [1/6] Python version: !PY_VER!

REM Step 2: Create/activate venv
echo [2/6] Checking virtual environment...
if not exist ".venv\Scripts\python.exe" (
    echo    Creating venv...
    if exist ".venv" (
        echo    Removing existing .venv folder...
        rmdir /s /q .venv 2>nul
    )
    python -m venv .venv
)

echo    Activating venv...
call .venv\Scripts\activate.bat

REM Step 3: Install dependencies
echo [3/6] Installing dependencies...
pip install --quiet flask requests mistune premailer Pillow jieba qrcode apscheduler pyinstaller pywebview

REM Step 4: Generate icon
echo [4/6] Generating app icon...
if not exist "assets\icon_256.png" (
    python -c "from PIL import Image, ImageDraw, ImageEnhance; import os; os.makedirs('assets', exist_ok=True); size = 256; img = Image.new('RGBA', (size, size), (0,0,0,0)); draw = ImageDraw.Draw(img); [draw.line([(0,y),(size,y)], fill=(int(26+(37-26)*y/size), int(58+(99-58)*y/size), int(107+(235-107)*y/size), 255)) for y in range(size)]; mask = Image.new('L', (size,size), 0); mdraw = ImageDraw.Draw(mask); mdraw.rounded_rectangle([0,0,size-1,size-1], radius=60, fill=255); img.putalpha(mask); draw2 = ImageDraw.Draw(img); cx, cy = size//2, size//2 - 10; draw2.rounded_rectangle([cx-70, cy-60, cx+70, cy+50], radius=20, fill=(255,255,255,230)); draw2.polygon([(cx-20, cy+50),(cx-40, cy+90),(cx+30, cy+50)], fill=(255,255,255,230)); draw2.rectangle([cx-12, cy-8, cx+12, cy+40], fill=(37,99,235,255)); draw2.polygon([(cx-24, cy-8),(cx+24, cy-8),(cx, cy-32)], fill=(37,99,235,255)); [draw2.ellipse([cx+dx-6, cy+55, cx+dx+6, cy+67], fill=(37,99,235,200)) for dx in [-20, 0, 20]]; img.save('assets/icon_256.png'); print('icon_256.png OK')"
)

REM Generate ICO file
python -c "from PIL import Image; img = Image.open('assets/icon_256.png').convert('RGBA'); img.save('assets/AppIcon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('AppIcon.ico OK')"

REM Step 5: PyInstaller build
echo [5/6] PyInstaller building (2-5 minutes, please wait)...
pyinstaller --clean --noconfirm ^
    --name "WeChatPublisher" ^
    --icon "assets\AppIcon.ico" ^
    --onefile ^
    --windowed ^
    --add-data "web_static;web_static" ^
    --add-data "modules;modules" ^
    --add-data "templates;templates" ^
    --hidden-import "flask" ^
    --hidden-import "flask.templating" ^
    --hidden-import "jinja2" ^
    --hidden-import "jinja2.ext" ^
    --hidden-import "werkzeug" ^
    --hidden-import "werkzeug.serving" ^
    --hidden-import "werkzeug.debug" ^
    --hidden-import "requests" ^
    --hidden-import "mistune" ^
    --hidden-import "premailer" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "PIL.ImageDraw" ^
    --hidden-import "PIL.ImageFont" ^
    --hidden-import "jieba" ^
    --hidden-import "jieba.analyse" ^
    --hidden-import "qrcode" ^
    --hidden-import "qrcode.image.pil" ^
    --hidden-import "apscheduler" ^
    --hidden-import "apscheduler.schedulers.background" ^
    --hidden-import "apscheduler.triggers.cron" ^
    --hidden-import "apscheduler.triggers.interval" ^
    --hidden-import "sqlite3" ^
    --hidden-import "hashlib" ^
    --hidden-import "threading" ^
    --hidden-import "queue" ^
    --hidden-import "webbrowser" ^
    --hidden-import "webview" ^
    --hidden-import "modules.user_db" ^
    --hidden-import "modules.ai_writer" ^
    --hidden-import "modules.auto_selector" ^
    --hidden-import "modules.cover_generator" ^
    --hidden-import "modules.keyword_extractor" ^
    --hidden-import "modules.md_converter" ^
    --hidden-import "modules.wx_publisher" ^
    launcher_webview_win.py

if not exist "dist\WeChatPublisher.exe" (
    echo ERROR: Build failed, WeChatPublisher.exe not found
    pause
    exit /b 1
)
echo    -> WeChatPublisher.exe created

REM Step 6: Build NSIS installer
echo [6/6] Building NSIS installer...

where makensis >nul 2>&1
if errorlevel 1 (
    echo    -> NSIS not found, skipping installer
    echo    -> Download from: https://nsis.sourceforge.io/Download
    goto :DONE
)

echo    -> Running makensis installer.nsi...
makensis installer.nsi
if exist "WeChatPublisher-Setup.exe" (
    echo    -> Installer created: WeChatPublisher-Setup.exe
) else (
    echo    -> Installer failed, but WeChatPublisher.exe is available
    echo    -> Check installer.nsi for errors
)

:DONE
echo.
echo ======================================================
echo SUCCESS!
echo    EXE: dist\WeChatPublisher.exe
if exist "WeChatPublisher-Setup.exe" (
    echo    Installer: WeChatPublisher-Setup.exe
)
echo.
echo    Usage:
echo    - Run: dist\WeChatPublisher.exe
echo    - Or install: WeChatPublisher-Setup.exe (if created)
echo    - App window opens with embedded WebView
echo ======================================================
pause
