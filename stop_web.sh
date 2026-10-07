#!/bin/bash

# 停止微信公众号自动化发布系统 Web 服务
# 支持 macOS/Linux

echo "🛑 正在停止 Web 服务..."

# 查找 web_app.py 的进程
PID=$(ps aux | grep "[w]eb_app.py" | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "✅ Web 服务未运行"
    exit 0
fi

echo "找到进程 PID: $PID"
kill -9 $PID

# 等待进程结束
sleep 1

# 检查是否还在运行
if ps -p $PID > /dev/null; then
    echo "❌ 无法停止进程，请手动检查"
    exit 1
else
    echo "✅ Web 服务已停止"
fi
