# -*- mode: python ; coding: utf-8 -*-
"""
WeChatPublisher_mac.spec — macOS arm64 专用打包规格（Apple Silicon）

与 Windows 的 WeChatPublisher.spec 分离：Windows 的 build_exe.bat 每次运行都会
用命令行参数重新生成 WeChatPublisher.spec，不能再共用一个文件，否则 Mac 的
COLLECT/BUNDLE 配置会被覆盖，导致打不出 .app。

用法（由 build_dmg.sh 调用）：
  pyinstaller WeChatPublisher_mac.spec --clean --noconfirm --distpath dist --workpath build
"""

import glob as _glob
from pathlib import Path

# 本 spec 所在目录即项目根目录（避免写死绝对路径）
PROJECT = Path(SPECPATH)

# ── 需要一起打包的数据目录/文件 ────────────────────────────────────
added_files = [
    (str(PROJECT / 'web_static'),  'web_static'),
    (str(PROJECT / 'modules'),     'modules'),
    (str(PROJECT / 'templates'),   'templates'),
    (str(PROJECT / 'domains_config.json'), '.'),
    (str(PROJECT / 'web_app.py'),  '.'),
    (str(PROJECT / 'main.py'),     '.'),
]

# jieba 词典（分词用）—— 动态查找虚拟环境里的 jieba 包目录
_jieba_paths = _glob.glob(str(PROJECT / '.venv/lib/python*/site-packages/jieba'))
if _jieba_paths:
    added_files.append((_jieba_paths[0], 'jieba'))


# ── 隐式导入（Flask 插件 / APScheduler / 模块内函数级导入等） ─────────
hidden_imports = [
    'flask', 'flask.templating', 'jinja2', 'jinja2.ext',
    'werkzeug', 'werkzeug.serving', 'werkzeug.debug',
    'requests', 'mistune', 'premailer',
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
    'jieba', 'jieba.analyse',
    'qrcode', 'qrcode.image.pil',
    'apscheduler', 'apscheduler.schedulers.background',
    'apscheduler.triggers.cron', 'apscheduler.triggers.interval',
    'sqlite3', 'hashlib', 'threading', 'queue', 'webbrowser',
    'webview', 'bs4', 'readability',
    'modules.user_db', 'modules.ai_writer', 'modules.auto_selector',
    'modules.cover_generator', 'modules.cover_maker', 'modules.keyword_extractor',
    'modules.md_converter', 'modules.wx_publisher', 'modules.article_rewriter',
    'modules.material_library', 'modules.hotrank', 'modules.today_in_history',
    'modules.ai_assistant',
]

a = Analysis(
    [str(PROJECT / 'launcher_webview.py')],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WeChatPublisher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # macOS 上不用 UPX
    console=False,       # 不显示终端窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT / 'assets/AppIcon.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WeChatPublisher',
)

app = BUNDLE(
    coll,
    name='微信公众号发布助手.app',
    icon=str(PROJECT / 'assets/AppIcon.icns'),
    bundle_identifier='com.wechat.publisher',
    version='1.0.0',
    info_plist={
        'CFBundleName':               '微信公众号发布助手',
        'CFBundleDisplayName':        '微信公众号发布助手',
        'CFBundleIdentifier':         'com.wechat.publisher',
        'CFBundleVersion':            '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable':    True,
        'LSUIElement':                False,      # 显示在 Dock
        'NSHumanReadableCopyright':   'Copyright © 2026',
        'CFBundleDocumentTypes':      [],
        # macOS 13+ 网络权限
        'NSLocalNetworkUsageDescription': '需要本地网络权限以启动内置 Web 服务',
    },
)