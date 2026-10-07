#!/bin/bash
# 重启Web服务器

echo "正在停止旧的服务器进程..."
pkill -f "python.*web_app.py" 2>/dev/null || echo "没有找到运行中的服务器"

# 等待进程完全停止
sleep 2

echo "正在启动Web服务器..."
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "⚠️ 虚拟环境不存在，使用系统Python"
fi

# 启动服务器
python3 web_app.py
