---
comet_change: multi-level-outline
role: technical-design
canonical_spec: openspec
archived-with: 2026-09-02-multi-level-outline
status: final
---

# 内容阶段大纲侧边栏多级目录设计

## Context

内容创作阶段（`templates/collaborative/workbench.html`）的大纲侧边栏 `#content-outline-list` 当前由 `renderContentOutlineList()` 渲染。它调用 `flattenOutlineSections()` 计算每个章节的 `depth`，但**忽略 depth**，所有 `.content-outline-item` 以零缩进平铺渲染。内容序列化 `serializeArticleForEdit()` 对每个大纲章节一律输出 `## 标题`（`parseArticleText`、`scrollToContentSection` 也只识别 `## `）。创作者无法在内容中用 `###`/`####` 表达子层级，侧边栏也无法实时反映内容层级。

后端约束（`modules/ai_writer.py`）：`generate_content` 仅读取 `outline.get("sections", [])` 顶层章节，**不递归 `children`**，子章节不会被 AI 填充。因此「AI 生成嵌套内容」不可行；内容层级的真相源是创作者在编辑器中手写的 markdown 标题。

## Goals / Non-Goals

**Goals:**
- 侧边栏按 markdown 标题层级（`##`/`###`/`####`…）缩进渲染多级目录。
- 目录随创作者输入实时同步（防抖）。
- 点击目录项滚动定位到编辑器对应标题行并高亮。
- 保存/重新加载后内容层级保持（往返一致）。

**Non-Goals:**
- 不改动大纲阶段编辑器（`#outline树`，已支持多级）。
- 不改动后端 `generate_outline` / `generate_content`。
- 不实现目录节点的拖拽重排或就地编辑（保持只读导航）。
- 不把 `###` 提升为独立大纲章节。

## Decisions

### 决策 1：侧边栏数据来源——解析内容文本
侧边栏改为解析 `#article-content-input` 文本中的 markdown 标题（正则 `/^(#{2,6})\s+(.*)$/gm`），构建 `{level, title, lineIndex}` 列表，按 `level-2` 缩进渲染。跳过围栏代码块（`` ``` ``），避免 `# 注释` 误识别为标题。

- **备选 A（按大纲树深度缩进）**：仅可视化 `sections` 树，无法反映创作者手写的 `###`。弃用。
- **备选 B（解析内容文本）**：侧边栏成为实时目录，与内容强一致。采用。

### 决策 2：序列化模型——平顶层 `##` + 正文保留手写 `###`
`serializeArticleForEdit` 按顶层章节输出 `## 标题\n\n正文`；`parseArticleText` 仅按 `## ` 切分顶层章节，正文中的 `###`/`####` 原样保留。`##` = 顶层章节分隔符（与顶层大纲章节 1:1）；`###`/`####` = 章节内联子标题。

- **备选 A（按 depth 输出嵌套标题）**：后端不递归子章节，嵌套标题无内容可填，且与手写 `###` 冲突。弃用。
- **备选 B（平顶层 + 正文保留）**：子层级作为正文一部分，往返稳定，消除位置错位。采用。

### 决策 3：实时同步与定位
- `onArticleInput` 在解析/自适应高度/防抖保存外，追加防抖调用 `renderContentOutlineList()`。
- 点击目录项按标题行号比例估算 `scrollTop`（`ratio = lineIndex / totalLines`）。

## Technical Design

### 新增 `parseContentHeadings(text)`

```
输入：编辑器文本字符串
输出：Array<{level: number, title: string, lineIndex: number}>
```

逻辑：
1. 按 `\n` 分行，维护 `inCodeBlock` 标志（遇到 `` ``` `` 切换）。
2. 对非代码块行应用 `/^(#{2,6})\s+(.*)$/`，捕获 level（# 数）与 title。
3. 记录该行 `lineIndex`（从 0 起）。
4. 仅识别 `##`–`######`：`##` 为顶层（与大纲顶层章节对齐），避免 `#` 单标题扰乱层级。

### 改写 `renderContentOutlineList()`

1. 读取 `#article-content-input` 的 `value`。
2. 调用 `parseContentHeadings`。
3. 若无标题 → 显示 `#content-outline-empty-hint`，返回。
4. 否则清空列表（保留 empty-hint 节点），为每条创建 `.content-outline-item`，`paddingLeft = (level - 2) * 16px`，存储 `lineIndex`。
5. 点击回调：滚动编辑器到该标题行并高亮该项。

### 实时同步

在 `onArticleInput(ta)` 中，`parseArticleText` + `autoResizeTextarea` 之后，使用独立短延迟计时器（~300ms）调用 `renderContentOutlineList()`，避免每次击键重渲染。

### 点击定位

```
滚动：main.scrollTop = (lineIndex / totalLines) * main.scrollHeight
高亮：当前项加 .active，其余移除
```

保留并泛化 `scrollToContentSection(id)`：改为计数任意层级标题行，兼容旧调用点（若有）。

### 往返序列化

- `serializeArticleForEdit`：遍历顶层 `currentOutline().sections`，每节输出 `## title\n\nbody`（body 取自 `contentData`，含用户手写 `###`）。
- `parseArticleText`：`text.split(/^##\s+/m)` 过滤空块，按顺序匹配顶层章节，取 title 与 body（body 内 `###` 原样保留）。

## Risks / Trade-offs

- **[滚动估算]** → 按行号比例估算，对单文本域足够准确；不引入字符级偏移。
- **[往返一致性]** → `##` 分隔符与顶层大纲 1:1，手写 `###` 留于正文，重加载后侧边栏重新解析，层级不丢。
- **[无前端自动化测试]** → `node --check` 校验语法 + 浏览器人工验证。

## Testing Strategy

- `node --check` 校验 `workbench.html` 内联 JS 语法。
- 浏览器人工验证：
  - AI 生成内容后侧边栏显示嵌套目录。
  - 手动添加 `###`/`####` 目录实时刷新；删除同步移除。
  - 点击子标题定位正确并高亮。
  - 保存后再加载层级保持。
  - 围栏代码块内 `# 注释` 不误识别为标题。

## Migration Plan

无数据迁移。改动仅限前端渲染与序列化逻辑。旧项目 `## ` 平铺文本仍被新 `parseArticleText`（识别 `## `）正确解析。

## Open Questions

无。
