# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher_webview_win.py'],
    pathex=[],
    binaries=[],
    datas=[('web_static', 'web_static'), ('modules', 'modules'), ('templates', 'templates')],
    hiddenimports=['flask', 'flask.templating', 'jinja2', 'jinja2.ext', 'werkzeug', 'werkzeug.serving', 'werkzeug.debug', 'requests', 'mistune', 'premailer', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'jieba', 'jieba.analyse', 'qrcode', 'qrcode.image.pil', 'apscheduler', 'apscheduler.schedulers.background', 'apscheduler.triggers.cron', 'apscheduler.triggers.interval', 'sqlite3', 'hashlib', 'threading', 'queue', 'webbrowser', 'webview', 'modules.user_db', 'modules.ai_writer', 'modules.auto_selector', 'modules.cover_generator', 'modules.keyword_extractor', 'modules.md_converter', 'modules.wx_publisher'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WeChatPublisher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\AppIcon.ico'],
)
