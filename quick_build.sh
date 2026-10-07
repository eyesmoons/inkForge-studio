#!/bin/bash
# 快速编译脚本（仅编译 .app，不制作 DMG）

cd /Users/casey/WorkBuddy/20260325140058/wechat-publisher

echo "开始编译 .app..."
.venv/bin/pyinstaller WeChatPublisher.spec --clean --noconfirm \
    --distpath dist \
    --workpath build

echo ""
echo "编译完成！"
ls -la dist/*.app 2>/dev/null || echo "未找到 .app 文件"

echo ""
echo "查看启动日志："
echo "  open ~/Library/Logs/WeChatPublisher/startup_error.txt"
