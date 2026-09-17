## Context

内容创作阶段（`templates/collaborative/workbench.html`）的大纲侧边栏 `#content-outline-list` 当前由 `renderContentOutlineList()` 渲染。它调用 `flattenOutlineSections()` 计算每个章节的 `depth`，但**忽略 depth**，所有 `.content-outline-item` 以零缩进平铺渲染。内容序列化 `serializeArticleForEdit()` 对每个大纲章节一律输出 `## 标题`（`parseArticleText`、`scrollToContentSection` 也只识别 `## `）。详见 proposal.md。

## Goals / Non-Goals

**Goals:**
- 侧边栏按 markdown 标题层级缩进渲染多级目录。
- 目录随创作者输入实时同步（防抖）。
- 点击目录项滚动定位到编辑器对应标题行并高亮。
- `serializeArticleForEdit` 按大纲深度输出嵌套标题（`##`/`###`/`####`），使 AI 生成内容呈现层级。

**Non-Goals:**
- 不改动大纲阶段编辑器（`#outline-tree`，已支持多级）。
- 不改动后端 API、历史文章页面。
- 不实现目录节点的拖拽重排或就地编辑（保持只读导航）。

## Decisions

### 决策 1：侧边栏数据来源——解析内容文本而非大纲树
侧边栏改为解析 `#article-content-input` 文本中的 markdown 标题（正则 `/^(#{2,6})\s+(.*)$/m`，与现有 `renderMarkdown` 的 `headingRE` 一致），构建 `{level, title, lineIndex}` 列表，按 `level-2` 缩进渲染。

- **备选 A（按大纲树深度缩进）**：仅可视化 `sections` 树，无法反映创作者在内容中手写的 `###` 标题。与用户"解析内容 markdown（实时 TOC）"的选择冲突，弃用。
- **备选 B（解析内容文本）**：侧边栏成为真正的实时目录，与内容强一致。采用。

### 决策 2：序列化按深度输出嵌套标题
`serializeArticleForEdit` 复用 `flattenOutlineSections()`（前序遍历，含 depth），对每个章节输出 `'#'.repeat(depth+2) + ' ' + title`（depth 0→`##`，1→`###`，2→`####`），正文接于标题之后。

- **备选 A（递归重写遍历）**：与 `flattenOutlineSections` 重复，弃用。
- **备选 B（复用 flattenOutlineSections + depth）**：单一遍历来源，前序顺序与大纲一致。采用。

### 决策 3：标题与大纲章节的映射——按前序位置匹配
`parseArticleText` 用 `matchAll` 找出所有标题块（含 level 与 title），按出现顺序与 `flattenOutlineSections()` 的前序章节列表**位置匹配**（第 i 个标题块 → 第 i 个展平章节）。超出大纲章节数的额外标题不写入 contentData（仍保留于文本）。

- **备选 A（按标题文本模糊匹配）**：标题易被创作者改写，脆弱，弃用。
- **备选 B（前序位置匹配）**：与序列化顺序一致，覆盖"改标题 / 改正文 / AI 再生"等常见场景。采用（代价见 Risks）。

### 决策 4：实时同步与定位
- `onArticleInput` 在解析/自适应高度/防抖保存之外，追加调用 `renderContentOutlineList()`（复用 600ms 防抖计时器区域，短延迟刷新）。
- 目录项点击按标题行号比例估算 `scrollTop`（`ratio = lineIndex / totalLines`），替代原先仅计 `## ` 的 `scrollToContentSection`；后者保留但改为计数任意层级标题。

## Risks / Trade-offs

- **[位置映射脆弱性] → 文档化限制**：若创作者在内容中间插入一个不属于大纲章节的 `###` 标题，后续标题块与章节的位置对齐会偏移，导致回写 contentData 错位。缓解：序列化与解析位置一致，常见编辑（改标题、改正文、AI 再生章节数不变）不受影响；额外标题超出章节数部分不参与映射（spec 已明确）。列为已知限制。
- **[滚动定位是估算] → 可接受**：按行号比例估算 `scrollTop`，对已自适应高度的单一文本域足够准确；不引入字符级偏移计算。
- **[无回归自动化] → 人工验证**：项目无前端测试套件，改动后通过 `node --check` 校验 JS 语法 + 浏览器人工验证目录层级与定位。

## Migration Plan

无数据迁移。改动仅限前端渲染与序列化逻辑；项目重新加载时 `serializeArticleForEdit` 按新格式输出，旧项目的 `## ` 平铺文本仍能被新 `parseArticleText`（识别 `#{2,6}`）正确解析。

## Open Questions

无。

## Implementation Divergence

> 本节在 verify 阶段追加，记录实现与本 design.md（open 阶段）早期决策的偏差。实现以绑定权威 Superpowers Design Doc（`docs/superpowers/specs/2026-09-02-multi-level-outline-design.md`）为准。

### 决策 2 偏差：序列化模型

- **本 design.md 原始决策 2** 描述「按 depth 输出嵌套标题」：`serializeArticleForEdit` 复用 `flattenOutlineSections()`（前序遍历，含 depth），对每个章节输出 `'#'.repeat(depth+2) + ' ' + title`（depth 0→`##`，1→`###`，2→`####`）。
- **偏差原因**：该方案为 Superpowers Design Doc 决策 2 明确否决的「备选 A」。后端 `generate_content` 仅读取顶层 `sections`、不递归 `children`，嵌套标题无内容可填，且与创作者手写 `###` 冲突。
- **实际实现**（与 Superpowers Design Doc 决策 2 一致）：平顶层 `##` + 正文保留手写 `###`。`serializeArticleForEdit` 按顶层章节输出 `## 标题\n\n正文`，正文中创作者手写的 `###`/`####` 原样保留；`parseArticleText` 仅按 `## ` 切分顶层章节，子层级作为正文一部分，往返稳定。

### 决策 3 偏差：标题与大纲章节的映射

- **本 design.md 原始决策 3** 描述 `parseArticleText` 用 `matchAll` 找出所有标题块（含 level 与 title），按出现顺序与 `flattenOutlineSections()` 前序章节列表位置匹配。
- **偏差原因**：该方案依赖「内容中标题块数 = 大纲章节数」的隐含假设，创作者在中间插入不属于大纲的 `###` 时位置对齐会偏移，导致 contentData 错位；且与上述 depth 序列化耦合。
- **实际实现**（与 Superpowers Design Doc 决策 2 一致）：`##` 视为顶层章节分隔符，与大纲顶层 `sections` 按出现顺序 1:1 映射；`###`/`####` 视为章节内联子标题，保留于正文而不映射为独立大纲章节。

### 影响范围

- 偏差仅限文档层面：本 design.md 决策 2/3 的过时描述。delta spec、Superpowers Design Doc、实现三者一致。
- 无需修改代码；归档时本 design.md 将标记为 `superseded-by-main-spec`。
