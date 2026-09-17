#!/bin/bash
# 启动微信公众号管理界面
cd "$(dirname "$0")"

PYTHON=".venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
  PYTHON="python3"
fi

# 检查是否指定了 -d 参数（后台运行）
if [ "$1" == "-d" ]; then
  echo "🚀 后台启动服务..."
  LOG_DIR="logs"
  mkdir -p "$LOG_DIR"
  LOG_FILE="$LOG_DIR/web_app_$(date +%Y%m%d_%H%M%S).log"
  nohup $PYTHON web_app.py > "$LOG_FILE" 2>&1 &
  echo "✅ 服务已在后台启动"
  echo "📝 日志文件：$LOG_FILE"
  echo "🌐 访问地址：http://localhost:5678"
else
  echo "🚀 启动服务..."
  $PYTHON web_app.py
fi
