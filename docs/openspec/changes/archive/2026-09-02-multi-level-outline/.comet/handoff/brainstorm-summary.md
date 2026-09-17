# Brainstorm Summary

- Change: multi-level-outline
- Date: 2026-09-02

## 确认的技术方案

**核心：前端实时多级目录（TOC）**，无后端变更。

1. `parseContentHeadings(text)`：正则 `/^(#{2,6})\s+(.*)$/gm` 逐行解析内容编辑器文本 → `[{level, title, lineIndex}]`，跳过围栏代码块（避免 `# 注释` 误识别）。
2. 改写 `renderContentOutlineList()`：读取编辑器文本，按 `level-2` 缩进渲染 `.content-outline-item`（`##`=顶级 0px，`###`=16px，`####`=32px…），无标题时显示空提示。
3. 实时同步：`onArticleInput` 中防抖调用 `renderContentOutlineList()`。
4. 点击定位：点击目录项 → 按行号比例滚动编辑器到对应标题（`ratio = lineIndex/totalLines`）并高亮该项。
5. 往返序列化：`serializeArticleForEdit` 按顶层章节输出 `## 标题\n\n正文`（正文保留用户手写的 `###`）；`parseArticleText` 仅按 `## ` 切分顶层章节，正文中的 `###` 原样保留。

**关键修正（相较 open 阶段 design.md）**：序列化改为「平顶层 `##` + 正文保留手写 `###`」，不再按大纲 depth 输出嵌套标题。理由：(1) 后端 `generate_content` 不递归子章节，子层级本就不会被 AI 填充；(2) 用户手写在正文中的 `###` 才是内容层级的真相源，侧边栏解析它即可。

## 关键取舍与风险

- **[位置映射] 简化**：不再把 `###` 映射为独立大纲章节，而是作为章节正文的一部分，消除位置错位风险。
- **[往返一致性]**：`##` = 顶层章节分隔符（与顶层大纲章节 1:1）；`###`/`####` = 章节内联子标题，正文内原样保留。重加载后侧边栏重新解析，层级不丢。
- **[滚动估算]**：按行号比例估算 scrollTop，对单文本域足够准确。
- **[无前端自动化测试]**：`node --check` 校验语法 + 浏览器人工验证。

## 测试策略

- `node --check` 校验 workbench.html 内联 JS。
- 浏览器人工：AI 生成内容后侧边栏嵌套目录；手写 `###`/`####` 实时刷新；点击定位；保存再加载层级保持；代码块内 `#` 不误识别为标题。

## Spec Patch

需在 delta spec 中补充/修正：
- 明确「`##` 为顶层章节分隔符，`###`/`####` 为章节内联子标题，保留于正文」，以及「`parseContentHeadings` 跳过围栏代码块」。
