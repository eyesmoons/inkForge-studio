"""生成 AppIcon.icns 所需的各尺寸 PNG"""
from PIL import Image
import os, subprocess

os.makedirs('icon.iconset', exist_ok=True)
src = Image.open('icon_1024.png').convert('RGBA')
for s in [16, 32, 64, 128, 256, 512, 1024]:
    img = src.resize((s, s), Image.LANCZOS)
    img.save(f'icon.iconset/icon_{s}x{s}.png')
    if s <= 512:
        img2 = src.resize((s*2, s*2), Image.LANCZOS)
        img2.save(f'icon.iconset/icon_{s}x{s}@2x.png')
print('PNG sizes done')
subprocess.run(['iconutil', '-c', 'icns', 'icon.iconset', '-o', 'AppIcon.icns'], check=True)
print('AppIcon.icns OK')
