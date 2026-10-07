@echo off
REM 停止微信公众号自动化发布系统 Web 服务
REM 支持 Windows

echo 🛑 正在停止 Web 服务...

REM 查找 web_app.py 的进程
for /f "tokens=2" %%i in ('tasklist ^| findstr /i "python.*web_app.py"') do set PID=%%i

if "%PID%"=="" (
    echo ✅ Web 服务未运行
    exit /b 0
)

echo 找到进程 PID: %PID%
taskkill /F /PID %PID%

REM 等待进程结束
timeout /t 1 /nobreak >nul

REM 检查是否还在运行
tasklist | findstr /i "python.*web_app.py" >nul
if errorlevel 1 (
    echo ✅ Web 服务已停止
) else (
    echo ❌ 无法停止进程，请手动检查
    exit /b 1
)
