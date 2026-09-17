# 验证报告：multi-level-outline

- 日期：2026-09-02
- 验证模式：full（任务数 9 > 3 阈值）
- 产物语言：zh-CN

## 摘要

| 维度 | 状态 |
|------|------|
| 完整性 | 9/9 任务完成，5 条 delta spec 需求全部覆盖 |
| 正确性 | 5/5 需求实现对应，场景均可映射 |
| 一致性 | 实现符合 Superpowers Design Doc（绑定权威）；OpenSpec design.md 存在已知漂移（见 WARNING） |

## 完整性

### 任务完成
`docs/openspec/changes/multi-level-outline/tasks.md` 全部 9 项任务已勾选 `[x]`：
1.1 `parseContentHeadings`、1.2 `renderContentOutlineList` 改写、2.1 实时同步、2.2 点击定位、3.1/3.2 序列化往返、3.3 `scrollToContentSection` 泛化、4.1 `node --check`、4.2 浏览器人工验证。

### 需求覆盖
`specs/collaborative-workbench/spec.md` 共 5 条 ADDED Requirement，全部有对应实现（见正确性章节映射）。

## 正确性：需求 → 实现映射

### 需求 1：内容阶段大纲侧边栏多级目录展示
- **实现**：`parseContentHeadings(text)`（workbench.html:1079）+ `renderContentOutlineList()`（:1118）
- 正则 `/^(#{2,6})\s+(.*)$/` 仅识别 `##`–`######`，跳过单 `#` ✓
- 围栏代码块：`inCodeBlock` 标志遇 `` ``` `` 切换，块内行跳过 ✓
- 缩进：`paddingLeft = (h.level - 2) * 16px`（`##`=0px、`###`=16px、`####`=32px）✓
- 场景「多级标题渲染为嵌套目录」✓
- 场景「空内容显示空提示」：`headings.length === 0` 时显示 `#content-outline-empty-hint` ✓
- 场景「代码块内标题不误识别」：`inCodeBlock` 跳过 ✓

### 需求 2：大纲目录实时同步
- **实现**：`onArticleInput(ta)`（:1349）追加 300ms 防抖调用 `renderContentOutlineList()`，独立于 600ms 保存计时器 ✓
- 场景「输入时实时更新目录」✓
- 场景「删除标题后目录同步移除」：每次击键重新从头渲染，删除同步反映 ✓

### 需求 3：目录项点击定位与滚动
- **实现**：`scrollToContentSectionByLine(lineIndex, rowElement)`（:1269）
- `main.scrollTop = (lineIndex / totalLines) * main.scrollHeight`，高亮 `.active` ✓
- 场景「点击子标题定位」✓

### 需求 4：内容序列化按大纲深度输出多级标题
- **实现**：`serializeArticleForEdit()`（:1312）按顶层章节输出 `'## ' + title + '\n\n' + body`，正文取自 `contentData` 原样保留手写 `###`/`####` ✓
- 场景「手动子标题往返保持」：`parseArticleText`（:1325）仅按 `## ` 切分，正文内 `###` 原样保留 ✓
- 注：该需求标题含「按大纲深度」字样，但需求正文（SHALL 句）明确为平顶层 `##` + 正文保留 `###`，实现与正文一致。

### 需求 5：标题与大纲章节的映射
- **实现**：`parseArticleText` 用 `text.split(/^##\s+/m)` 仅按 `##` 切分顶层章节，与 `flattenOutlineSections` 顶层 `sections` 按顺序 1:1 映射；`###`/`####` 留于正文不映射为独立章节 ✓
- 场景「内联子标题不作为独立章节」✓

## 一致性

### 设计符合性（Superpowers Design Doc — 绑定权威）
实现符合 `docs/superpowers/specs/2026-09-02-multi-level-outline-design.md` 全部决策：
- 决策 1（解析内容文本）✓
- 决策 2（平顶层 `##` + 正文保留手写 `###`）✓
- 决策 3（实时同步 + 行号比例滚动）✓

### 代码模式一致性
- 改动仅限 `workbench.html` 内联 JS，未新增文件、未引入外部库，与现有代码风格一致。
- 大纲渲染使用 `textContent`（非 `innerHTML`），无 XSS 注入面。

## 验证证据（fresh）

- `node --check` 提取内联 JS：**SYNTAX_OK**
- 大纲渲染无 `innerHTML`：确认使用 `textContent`
- 无残留调试代码：无 `console.log`/`debugger`/`TODO`

## 问题分级

### CRITICAL
无。

### WARNING

**W1. OpenSpec design.md 决策 2/3 与绑定 Design Doc 漂移**
- OpenSpec `design.md`（open 阶段）决策 2 仍描述「按 depth 输出嵌套标题」（`'#'.repeat(depth+2)`）、决策 3 仍描述 `parseArticleText` 用 `matchAll` 全标题块位置匹配。这两处是设计文档明确否决的「备选 A」。
- 绑定权威 Superpowers Design Doc 决策 2 采用「平顶层 `##` + 正文保留手写 `###`」（备选 B），实现与之一致。
- 该漂移在 build 阶段已识别并裁决（tasks.md 3.1/3.2 已对齐绑定 Design Doc），但 OpenSpec `design.md` 本身未同步更新。
- 影响：文档层面不一致；实现本身正确。属于 verify 阶段允许处理的 Spec 漂移（见 `comet-verify` Step 2b）。
- **处理方式（用户选择 Option A）**：在 OpenSpec `design.md` 追加「Implementation Divergence」节，记录决策 2/3 偏差原因与实际实现。已写入。

  > 注：design.md 为 OpenSpec 产物，本次 verify 阶段修改后 `handoff_hash` 未刷新（`comet handoff --write` 仅在 design/build 阶段可执行）；build 守卫已校验过原 hash，本次偏差记录为 verify 阶段允许产物。

### SUGGESTION

**S1. 需求 4 标题措辞**
delta spec 需求 4 标题「内容序列化按大纲深度输出多级标题」中的「按大纲深度」易与已否决的 depth 方案混淆；需求正文 SHALL 句实际描述平顶层 `##`。建议后续归档时视情润色标题，非阻塞。

**S2. build 阶段已接受的 5 项 minor review 发现**
嵌套 4-backtick 围栏切换、ATX 收尾 `#`、空标题行、滚动估算、`##` 超章节数丢弃——均为 cosmetic 或既有行为，不影响验收。

## 评估结论

无 CRITICAL 问题。1 项 WARNING（OpenSpec design.md 文档漂移，实现正确）。
