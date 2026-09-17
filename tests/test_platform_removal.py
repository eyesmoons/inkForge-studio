import os, sys, glob
ROOT = os.path.abspath(os.path.join(__file__, "..", ".."))

def test_platform_modules_gone():
    for name in ["wx_publisher.py","md_converter.py","cover_generator.py","cover_maker.py"]:
        assert not os.path.exists(os.path.join(ROOT, "modules", name)), f"{name} 应被删除"

def test_no_platform_imports():
    offenders = []
    for path in glob.glob(os.path.join(ROOT, "modules", "*.py")):
        if "__pycache__" in path:
            continue
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for frag in ["wx_publisher","md_converter","cover_generator","cover_maker"]:
            if frag in src and path.endswith(frag + ".py") is False:
                # 仅标记引用了已删模块的文件（自身文件名除外）
                if os.path.basename(path) != frag + ".py":
                    offenders.append((path, frag))
    assert not offenders, f"仍引用已删模块: {offenders}"

def test_domains_config_preserved():
    # domains_config.json 是通用选题研究配置（各领域 RSS 源 / 参考网站 / 搜索关键词），
    # 与特定平台无关，属于通用 AI 辅助写作基础设施，应保留。
    assert os.path.exists(os.path.join(ROOT, "domains_config.json")), \
        "domains_config.json 是通用选题配置，不应删除"
