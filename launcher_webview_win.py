"""
launcher.py — AI 辅助协作写作平台 Windows App 启动入口（嵌入式 WebView 版）

功能：
1. 启动 Flask 服务（localhost:5678）
2. 使用 pywebview 创建原生窗口，嵌入本地 Web 服务
3. 无需通过外部浏览器访问
"""

import os
import sys
import time
import threading
import traceback
from pathlib import Path

# ── 关键：将 _MEIPASS（PyInstaller 解压目录）加入 PATH ──────────────
try:
    if getattr(sys, 'frozen', False):
        # 打包后的运行目录
        BASE_DIR = Path(sys._MEIPASS)
        # 数据目录放在 %APPDATA%\WeChatPublisher
        DATA_DIR = Path(os.environ.get('APPDATA', '')) / 'WeChatPublisher'
        LOG_DIR = Path(os.environ.get('APPDATA', '')) / 'WeChatPublisher' / 'logs'
    else:
        BASE_DIR = Path(__file__).parent
        DATA_DIR = BASE_DIR
        LOG_DIR = BASE_DIR / 'logs'

    # 创建必要的目录
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 设置工作目录
    os.chdir(BASE_DIR)
    sys.path.insert(0, str(BASE_DIR))

except Exception as e:
    # 早期错误处理：目录创建失败
    error_msg = f"[CRITICAL] 启动失败：目录初始化错误\n{traceback.format_exc()}"
    print(error_msg, file=sys.stderr)

    # 尝试写入日志
    try:
        log_path = Path(os.environ.get('APPDATA', '')) / 'WeChatPublisher' / 'logs'
        log_path.mkdir(parents=True, exist_ok=True)
        with open(log_path / 'startup_error.txt', 'w', encoding='utf-8') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n{error_msg}")
    except:
        pass

    sys.exit(1)

PORT = 5678
URL  = f'http://localhost:{PORT}'

# ── Flask 服务状态 ────────────────────────────────────────────────
_flask_app = None
_flask_thread = None
_flask_ready = threading.Event()


def wait_flask_ready():
    """等待 Flask 服务启动"""
    import urllib.request
    for _ in range(60):  # 最多等 60 秒
        time.sleep(1)
        try:
            urllib.request.urlopen(URL, timeout=1)
            _flask_ready.set()
            break
        except Exception:
            continue
    else:
        print("[WARNING] Flask 服务启动超时", file=sys.stderr)


def run_flask():
    """在子线程中运行 Flask"""
    global _flask_app

    # 设置工作目录相关环境变量
    os.environ.setdefault('WECHAT_PUB_DATA_DIR', str(DATA_DIR))

    # 导入并启动 Flask app
    try:
        from web_app import app as flask_app
        _flask_app = flask_app

        # 启动 Flask（不使用 debug 模式，避免重启）
        flask_app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        error_msg = f"[CRITICAL] Flask 启动失败\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)

        # 写入日志
        try:
            with open(LOG_DIR / 'startup_error.txt', 'w', encoding='utf-8') as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n{error_msg}")
        except:
            pass

        sys.exit(1)


def start_webview():
    """启动 WebView 窗口"""
    import webview

    # 等待 Flask 服务就绪
    print("[INFO] 等待服务启动...")
    _flask_ready.wait()

    print("[INFO] 启动 WebView 窗口...")

    # 创建 WebView 窗口
    webview.create_window(
        title='协作写作助手',
        url=URL,
        width=1400,
        height=900,
        min_size=(1024, 768),
        resizable=True,
        fullscreen=False,
    )

    # 启动 WebView 主循环
    webview.start(debug=False)


def main():
    """主入口"""
    print(f"[INFO] 启动协作写作助手")
    print(f"[INFO] 数据目录: {DATA_DIR}")
    print(f"[INFO] 日志目录: {LOG_DIR}")
    print(f"[INFO] 工作目录: {BASE_DIR}")
    print(f"[INFO] 服务地址: {URL}")

    # 启动 Flask 服务线程
    _flask_thread = threading.Thread(target=run_flask, daemon=True)
    _flask_thread.start()

    # 启动等待线程
    wait_thread = threading.Thread(target=wait_flask_ready, daemon=True)
    wait_thread.start()

    # 启动 WebView（主线程）
    start_webview()


if __name__ == '__main__':
    main()
