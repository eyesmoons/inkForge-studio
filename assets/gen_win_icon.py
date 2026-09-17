"""生成 Windows 打包用的 assets/AppIcon.ico（含多尺寸）与 icon_256.png。

优先基于仓库里已有的 assets/icon_1024.png 生成，避免打包机上缺少 Pillow 或断网时
图标缺失导致 PyInstaller 在 EXE 阶段失败、产出残缺 exe。
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'icon_1024.png'
ICO = ROOT / 'AppIcon.ico'
PNG_256 = ROOT / 'icon_256.png'

if not SRC.exists():
    raise SystemExit(f'缺少源图 {SRC}，无法生成图标')

src = Image.open(SRC).convert('RGBA')

if not PNG_256.exists():
    src.resize((256, 256), Image.LANCZOS).save(PNG_256)

src.save(ICO, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('AppIcon.ico OK')