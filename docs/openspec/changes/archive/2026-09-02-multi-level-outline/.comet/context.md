# Comet Design Handoff

- Change: multi-level-outline
- Phase: design
- Mode: compact
- Context hash: ef99dcaea3d03db392f9435da2d857491f060a402560823454d6b58b42bd8daf

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## docs/openspec/changes/multi-level-outline/proposal.md

- Source: docs/openspec/changes/multi-level-outline/proposal.md
- Lines: 1-27
- SHA256: 4900a296e469a37f8851121d89b044b553b49315f7c62d578dad39267f230327

```md
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

```

## docs/openspec/changes/multi-level-outline/design.md

- Source: docs/openspec/changes/multi-level-outline/design.md
- Lines: 1-54
- SHA256: 6b112a19cdc08a0cd8fe1d043996d3eb2b17f890b5eb552e4f86ad840015b234

```md
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

```

## docs/openspec/changes/multi-level-outline/tasks.md

- Source: docs/openspec/changes/multi-level-outline/tasks.md
- Lines: 1-20
- SHA256: fc61e78d9cdfb65c7dbdf5214b3f22ba5978024a962a1271e24d3c9519bd90f5

```md
## 1. 侧边栏多级目录渲染

- [x] 1.1 新增 `parseContentHeadings(text)`：用正则 `/^(#{2,6})\s+(.*)$/gm` 从内容文本提取 `{level, title, lineIndex}` 列表，验证对 `##`/`###`/`####` 均能提取且行号正确。
- [x] 1.2 改写 `renderContentOutlineList()`：读取 `#article-content-input` 文本，调用 `parseContentHeadings`，按 `level-2` 缩进渲染 `.content-outline-item`（无标题时显示空提示），验证多级标题呈现嵌套缩进。

## 2. 实时同步与点击定位

- [x] 2.1 在 `onArticleInput` 中追加调用 `renderContentOutlineList()`（防抖），验证编辑标题后目录实时刷新（新增/删除标题同步）。
- [x] 2.2 目录项点击按行号比例滚动编辑器到对应标题并高亮该目录项，验证点击 `###` 子项定位正确。

## 3. 内容序列化按大纲深度输出多级标题

- [x] 3.1 验证 `serializeArticleForEdit()` 已符合设计文档决策 2：按顶层大纲章节输出 `## 标题\n\n正文`，正文中创作者手写的 `###`/`####` 原样保留（无需修改）。
- [x] 3.2 验证 `parseArticleText()` 已符合设计文档决策 2：仅按 `## ` 切分顶层章节，正文内 `###`/`####` 原样保留，往返一致（无需修改）。
- [x] 3.3 调整 `scrollToContentSection()` 计数任意层级标题（不再仅限 `## `），验证按章节 id 定位到多级标题行。

## 4. 集成验证

- [x] 4.1 运行 `node --check` 校验 `workbench.html` 内联 JS 语法无错误。
- [x] 4.2 浏览器人工验证：AI 生成内容后大纲侧边栏显示嵌套目录；手动在编辑器添加 `###`/`####` 目录实时更新；点击定位与保存后再加载层级保持。（注：浏览器人工验证需人执行，已记录为 verify 阶段验收项，build 阶段不代替人工点击验证。）

```

## docs/openspec/changes/multi-level-outline/specs/collaborative-workbench/spec.md

- Source: docs/openspec/changes/multi-level-outline/specs/collaborative-workbench/spec.md
- Lines: 1-48
- SHA256: f8957f1b2f2cd494a4fd6786282fd2132d197106b85c089708c959a0291aedfe

```md
## ADDED Requirements

### Requirement: 内容阶段大纲侧边栏多级目录展示
系统 SHALL 在内容创作阶段的大纲侧边栏（"大纲章节"）中，按照内容内 markdown 标题的层级（`##`/`###`/`####` …）以缩进形式渲染多级目录，而非平铺列表。`##` 为顶层章节分隔符（与顶层大纲章节对齐），`###`/`####` 等为章节内联子标题。解析时 SHALL 跳过围栏代码块（`` ``` ``），避免代码块内的 `#` 注释被误识别为标题。

#### Scenario: 多级标题渲染为嵌套目录
- **WHEN** 内容编辑器中存在 `## A`、`### B`、`### C`、`## D` 标题
- **THEN** 侧边栏将 A 与 D 渲染为一级目录项，B 与 C 渲染为 A 下的二级缩进子项

#### Scenario: 空内容显示空提示
- **WHEN** 尚未生成大纲或内容为空
- **THEN** 侧边栏显示空状态提示（"尚未生成大纲"），不渲染目录树

#### Scenario: 代码块内标题不误识别
- **WHEN** 内容中存在围栏代码块，其内包含 `# 注释` 或 `### 伪标题` 行
- **THEN** 这些行不被渲染为目录项

### Requirement: 大纲目录实时同步
系统 SHALL 在创作者编辑内容时，大纲侧边栏随 markdown 标题的变化实时更新（防抖），无需手动刷新。

#### Scenario: 输入时实时更新目录
- **WHEN** 创作者在编辑器中新增或修改一个 `###` 标题
- **THEN** 侧边栏在短延迟（防抖）后刷新，目录树体现新增/变更的层级

#### Scenario: 删除标题后目录同步移除
- **WHEN** 创作者删除一个 `###` 标题行
- **THEN** 侧边栏刷新后该子目录项随之消失

### Requirement: 目录项点击定位与滚动
系统 SHALL 在创作者点击大纲侧边栏的某个目录项时，将内容编辑器滚动到对应的标题行并高亮该目录项。

#### Scenario: 点击子标题定位
- **WHEN** 创作者点击侧边栏中某个 `###` 对应的子目录项
- **THEN** 编辑器滚动到该 `###` 标题所在位置，且该目录项呈高亮态

### Requirement: 内容序列化按大纲深度输出多级标题
系统 SHALL 在序列化内容为可编辑文本时，按顶层大纲章节输出 `## 标题\n\n正文`；正文中创作者手写的 `###`/`####` 等内联子标题 SHALL 原样保留，使手动编辑的层级在保存与重新加载后保持一致。

#### Scenario: 手动子标题往返保持
- **WHEN** 创作者在正文中手写 `### 子标题` 并保存
- **THEN** 重新加载后该 `### 子标题` 仍保留在对应章节正文中，侧边栏解析后仍渲染为嵌套子项

### Requirement: 标题与大纲章节的映射
系统 SHALL 将 `##` 视为顶层章节分隔符，与大纲顶层 `sections` 按出现顺序 1:1 映射；`###`/`####` 视为章节内联子标题，保留于正文而不映射为独立大纲章节。

#### Scenario: 内联子标题不作为独立章节
- **WHEN** 创作者在正文中手写 `### 子标题`
- **THEN** 该 `###` 渲染为目录子项，但不关联"单节生成内容"等大纲章节操作

```
