"""
launcher.py — AI 辅助协作写作平台 macOS App 启动入口

打包为 .app 后：
1. 启动 Flask 服务（localhost:5678）
2. 等待服务就绪后自动打开默认浏览器
3. 在系统托盘显示状态（可选：用 rumps）
"""

import os
import sys
import time
import threading
import subprocess
import webbrowser
from pathlib import Path

# ── 关键：将 _MEIPASS（PyInstaller 解压目录）加入 PATH ──────────────
if getattr(sys, 'frozen', False):
    # 打包后的运行目录
    BASE_DIR = Path(sys._MEIPASS)
    # 数据目录放在 ~/Library/Application Support/WeChatPublisher
    DATA_DIR = Path.home() / 'Library' / 'Application Support' / 'WeChatPublisher'
else:
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

PORT = 5678
URL  = f'http://localhost:{PORT}'


def wait_and_open_browser():
    """等待 Flask 就绪后打开浏览器"""
    import urllib.request
    for _ in range(30):  # 最多等 30 秒
        time.sleep(1)
        try:
            urllib.request.urlopen(URL, timeout=1)
            break
        except Exception:
            continue
    webbrowser.open(URL)


def run_flask():
    """在子线程中运行 Flask"""
    # 设置工作目录相关环境变量
    os.environ.setdefault('WECHAT_PUB_DATA_DIR', str(DATA_DIR))

    # 启动浏览器线程
    t = threading.Thread(target=wait_and_open_browser, daemon=True)
    t.start()

    # 导入并启动 Flask app
    from web_app import app as flask_app
    flask_app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_flask()
