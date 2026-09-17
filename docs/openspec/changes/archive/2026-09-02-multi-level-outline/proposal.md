## Why

内容创作阶段的大纲侧边栏（"大纲章节"）当前将所有章节渲染为**平铺列表**，不体现层级。`flattenOutlineSections()` 已计算每个章节的 `depth`，但 `renderContentOutlineList()` 忽略了它。同时内容序列化（`serializeArticleForEdit`）把每个大纲章节一律输出为 `## 标题`，创作者无法在内容中用 `###`/`####` 表达子层级，AI 生成内容也无法体现大纲的嵌套结构。创作者已期望在内容中用 markdown 标题语法新增层级时，大纲侧边栏能实时展示对应的目录层级。

## What Changes

- 内容阶段大纲侧边栏改为**多级目录展示**：按标题层级（`##`/`###`/`####` …）缩进渲染，形成树状目录。
- 侧边栏数据来源改为**解析内容编辑器中的 markdown 标题**（实时 TOC），随创作者输入实时更新（防抖）。
- `serializeArticleForEdit` 按大纲章节的嵌套**深度**输出标题（一级 `##`、二级 `###`、三级 `####` …），使 AI 生成内容与手动编辑都呈现层级。
- `parseArticleText` 与 `scrollToContentSection` 适配多级标题的解析与定位。
- 点击目录项滚动到编辑器对应标题行并高亮。

## Capabilities

### New Capabilities

-（无新增能力）

### Modified Capabilities

- `collaborative-workbench`: 为内容创作阶段的大纲侧边栏新增"多级目录实时展示"要求，并扩展内容序列化/解析以支持按大纲深度输出与回读多级 markdown 标题。

## Impact

- **涉及文件**：`templates/collaborative/workbench.html`（`renderContentOutlineList`、`serializeArticleForEdit`、`parseArticleText`、`scrollToContentSection` 及内容输入事件）。
- **不涉及**：后端 API、大纲阶段编辑器（已支持多级）、历史文章页面、其他页面。
- **风险**：创作者在内容中新增的 `###` 标题若超出大纲 `sections` 数量，与大纲章节的映射按位置顺序匹配；多余标题仍渲染为目录项但不关联大纲章节操作。
