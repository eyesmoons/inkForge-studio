#!/bin/bash
# =============================================================
# build_dmg.sh — 微信公众号发布助手 macOS .dmg 打包脚本
# 适用平台：macOS Apple Silicon (arm64)
# 运行方式：cd wechat-publisher && bash build_dmg.sh
# =============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="微信公众号发布助手"
DMG_NAME="WeChatPublisher-1.0.0-arm64"
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
VENV_PIP="$SCRIPT_DIR/.venv/bin/pip"
PYINSTALLER="$SCRIPT_DIR/.venv/bin/pyinstaller"

echo "======================================================"
echo "  微信公众号发布助手 — macOS 打包脚本"
echo "======================================================"

# ── Step 1: 检查/创建虚拟环境 ─────────────────────────────────
if [ ! -f "$VENV_PY" ]; then
    echo "[1/5] 创建虚拟环境..."
    python3 -m venv .venv
fi

# ── Step 2: 安装依赖 ──────────────────────────────────────────
echo "[2/5] 安装依赖（flask / pyinstaller 等）..."
"$VENV_PIP" install --quiet \
    flask requests mistune premailer Pillow jieba qrcode apscheduler pyinstaller pywebview beautifulsoup4 readability-lxml

# ── Step 3: 生成应用图标 ──────────────────────────────────────
echo "[3/5] 生成应用图标..."
mkdir -p assets
if [ ! -f "assets/AppIcon.icns" ]; then
    "$VENV_PY" -c "
from PIL import Image, ImageDraw
import math, os, subprocess

# 生成 1024x1024 图标
size = 1024
img = Image.new('RGBA', (size, size), (0,0,0,0))
draw = ImageDraw.Draw(img)

# 渐变背景
for y in range(size):
    ratio = y / size
    r_val = int(26 + (37-26)*ratio)
    g_val = int(58 + (99-58)*ratio)
    b_val = int(107 + (235-107)*ratio)
    draw.line([(0,y),(size,y)], fill=(r_val, g_val, b_val, 255))

# 圆角遮罩
mask = Image.new('L', (size,size), 0)
mdraw = ImageDraw.Draw(mask)
mdraw.rounded_rectangle([0,0,size-1,size-1], radius=220, fill=255)
img.putalpha(mask)

draw2 = ImageDraw.Draw(img)
cx, cy = size//2, size//2 - 40

# 气泡
bw, bh = 500, 340
bx = cx - bw//2
by = cy - bh//2
draw2.rounded_rectangle([bx, by, bx+bw, by+bh], radius=60, fill=(255,255,255,230))
tail = [(cx-60, by+bh),(cx-110, by+bh+90),(cx+30, by+bh)]
draw2.polygon(tail, fill=(255,255,255,230))

# 向上箭头
ax, ay = cx, cy - 20
draw2.rectangle([ax-24, ay+20, ax+24, ay+120], fill=(37,99,235,255))
draw2.polygon([(ax-70, ay+20),(ax+70, ay+20),(ax, ay-60)], fill=(37,99,235,255))

# 三个点
for dx in [-72, 0, 72]:
    draw2.ellipse([cx+dx-14, cy+130, cx+dx+14, cy+158], fill=(37,99,235,200))

os.makedirs('assets/icon.iconset', exist_ok=True)
img.save('assets/icon_1024.png')

# 生成各尺寸
src = Image.open('assets/icon_1024.png').convert('RGBA')
for s in [16,32,64,128,256,512,1024]:
    img_resized = src.resize((s,s), Image.LANCZOS)
    img_resized.save(f'assets/icon.iconset/icon_{s}x{s}.png')
    if s<=512:
        img2 = src.resize((s*2,s*2), Image.LANCZOS)
        img2.save(f'assets/icon.iconset/icon_{s}x{s}@2x.png')
print('  -> 图标尺寸生成完成')
"
    iconutil -c icns assets/icon.iconset -o assets/AppIcon.icns
    echo "  -> AppIcon.icns OK"
else
    echo "  → AppIcon.icns 已存在，跳过"
fi

# ── Step 3.5: 生成 DMG 背景图 ────────────────────────────────
if [ ! -f "assets/dmg_bg.png" ]; then
    echo "[3/5] 生成 DMG 背景图..."
    "$VENV_PY" -c "
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 600, 400
img = Image.new('RGB', (W, H), (245, 247, 252))
draw = ImageDraw.Draw(img)

# 渐变背景
for y in range(H):
    ratio = y / H
    r = int(240 + (235-240)*ratio)
    g = int(243 + (240-243)*ratio)
    b = int(252 + (248-252)*ratio)
    draw.line([(0,y),(W,y)], fill=(r,g,b))

# 装饰线
draw.line([(0, H//2-1),(W, H//2-1)], fill=(220,225,240), width=1)

# 左侧图标区域底座
draw.ellipse([60,120,200,260], fill=(230,235,250))

# 右侧 Applications 箭头区域
draw.ellipse([400,120,540,260], fill=(230,235,250))

# 中间箭头
ax, ay = W//2, H//2
for i in range(3):
    x = ax - 18 + i*18
    alpha_color = (180-i*20, 185-i*20, 210-i*20)
    draw.polygon([(x,ay-12),(x+14,ay),(x,ay+12)], fill=alpha_color)

# 底部说明文字区域
draw.rounded_rectangle([60, 310, 540, 370], radius=12, fill=(220,225,242))

# 写文字
try:
    font_sm = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 18)
    font_xs = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 13)
except:
    font_sm = ImageFont.load_default()
    font_xs = font_sm

draw.text((W//2, 335), '将应用拖入右侧 Applications 文件夹完成安装', font=font_xs, fill=(100,110,140), anchor='mm')

img.save('assets/dmg_bg.png')
print('  -> dmg_bg.png OK')
"
fi

# ── Step 4: PyInstaller 打包 ─────────────────────────────────
echo "[4/5] PyInstaller 打包（约 2~5 分钟，请耐心等待）..."
"$PYINSTALLER" WeChatPublisher_mac.spec --clean --noconfirm \
    --distpath "$SCRIPT_DIR/dist" \
    --workpath "$SCRIPT_DIR/build"

APP_PATH="$SCRIPT_DIR/dist/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 打包失败，未找到 ${APP_NAME}.app"
    exit 1
fi
echo "  → .app 生成成功：$APP_PATH"

# ── Step 5: 制作 .dmg ─────────────────────────────────────────
echo "[5/5] 制作 .dmg 安装镜像..."

if ! command -v create-dmg &>/dev/null; then
    echo "  → 安装 create-dmg..."
    brew install create-dmg
fi

DMG_OUTPUT="$SCRIPT_DIR/dist/${DMG_NAME}.dmg"
rm -f "$DMG_OUTPUT"

# 创建临时文件夹
TEMP_DIR="$SCRIPT_DIR/dist/dmg_temp"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# 复制 App 到临时文件夹
cp -R "dist/${APP_NAME}.app" "$TEMP_DIR/"

# 创建 Applications 符号链接
ln -s /Applications "$TEMP_DIR/Applications"

# 使用 hdiutil 创建 DMG
echo "  → 使用 hdiutil 创建 DMG..."
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "$TEMP_DIR" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_OUTPUT"

# 清理临时文件夹
rm -rf "$TEMP_DIR"

echo ""
echo "======================================================"
echo "✅ 打包完成！"
echo "   DMG 路径：$DMG_OUTPUT"
echo ""
echo "   安装方式："
echo "   1. 双击 ${DMG_NAME}.dmg"
echo "   2. 将「${APP_NAME}」拖入 Applications 文件夹"
echo "   3. 首次打开：右键 → 打开（绕过 Gatekeeper 安全提示）"
echo "======================================================"
