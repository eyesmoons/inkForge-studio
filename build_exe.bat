@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ======================================================
echo   WeChat Publisher - Windows EXE Build
echo ======================================================

REM Step 1: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [1/4] ERROR: Python not found, please install Python 3.8+
    pause
    exit /b 1
)

echo [1/4] Python version:
python --version

REM Step 2: Create/activate venv
echo [2/4] Checking virtual environment...
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

REM Step 3: Install dependencies (best-effort; if no network, system Python likely already has them)
echo [3/4] Installing dependencies...
pip install --quiet --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple flask requests mistune premailer Pillow jieba qrcode apscheduler pyinstaller pywebview beautifulsoup4 readability-lxml

if errorlevel 1 (
    echo    WARNING: pip install failed ^(no network?^). Will continue with system Python's installed packages if present.
)

REM Step 4: Generate icon (skipped when assets\AppIcon.ico already exists in repo)
echo [4/4] Checking app icon...
if exist "assets\AppIcon.ico" (
    echo    Found assets\AppIcon.ico, skipping icon generation
) else (
    echo    Generating icon ^(needs Pillow^)...
    python "assets\gen_win_icon.py"
    if not exist "assets\AppIcon.ico" (
        echo ERROR: Failed to create assets\AppIcon.ico. Please install Pillow first.
        pause
        exit /b 1
    )
)

REM Step 5: PyInstaller build
echo [5/5] PyInstaller building (2-5 minutes, please wait)...
echo.

pyinstaller --clean --noconfirm ^
    --name "WeChatPublisher" ^
    --icon "assets\AppIcon.ico" ^
    --onefile ^
    --windowed ^
    --noupx ^
    --add-data "web_static;web_static" ^
    --add-data "modules;modules" ^
    --add-data "templates;templates" ^
    --add-data "domains_config.json;." ^
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
    --hidden-import "bs4" ^
    --hidden-import "readability" ^
    --hidden-import "modules.user_db" ^
    --hidden-import "modules.ai_writer" ^
    --hidden-import "modules.auto_selector" ^
    --hidden-import "modules.cover_generator" ^
    --hidden-import "modules.cover_maker" ^
    --hidden-import "modules.keyword_extractor" ^
    --hidden-import "modules.md_converter" ^
    --hidden-import "modules.wx_publisher" ^
    --hidden-import "modules.article_rewriter" ^
    --hidden-import "modules.material_library" ^
    --hidden-import "modules.hotrank" ^
    --hidden-import "modules.today_in_history" ^
    --hidden-import "modules.ai_assistant" ^
    launcher_webview_win.py

echo.
if not exist "dist\WeChatPublisher.exe" (
    echo ERROR: Build failed, WeChatPublisher.exe not found
    pause
    exit /b 1
)

for %%F in ("dist\WeChatPublisher.exe") do set SIZE=%%~zF
set /a SIZE_MB=%SIZE% / 1048576
if %SIZE% LSS 1048576 (
    echo ERROR: Build incomplete ^(exe is %SIZE_MB% MB^). Earlier step probably failed, check the log above.
    echo        A finished onefile build with these dependencies should be 40+ MB.
    pause
    exit /b 1
)

echo.
echo ======================================================
echo SUCCESS!
echo    File: dist\WeChatPublisher.exe
echo    Size: about %SIZE_MB% MB
echo.
echo    Usage:
echo    1. Double-click WeChatPublisher.exe to run
echo    2. App window will open with embedded WebView
echo    3. Copy file anywhere or share with others
echo ======================================================
pause
