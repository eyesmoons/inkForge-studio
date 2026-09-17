---
change: multi-level-outline
design-doc: docs/superpowers/specs/2026-09-02-multi-level-outline-design.md
base-ref: 
archived-with: 2026-09-02-multi-level-outline
---

# 内容阶段大纲侧边栏多级目录 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将内容阶段大纲侧边栏从平铺零缩进改为按 markdown 标题层级（`##`/`###`/`####`…）缩进渲染多级目录，支持实时同步与点击定位，并保持内容序列化的往返一致性。

**Architecture:** 侧边栏数据来源从「遍历大纲树 `flattenOutlineSections`」改为「解析 `#article-content-input` 文本中的 markdown 标题」，新增 `parseContentHeadings(text)` 提取 `{level, title, lineIndex}`；`renderContentOutlineList` 按 `level-2` 缩进渲染；`onArticleInput` 追加防抖调用 `renderContentOutlineList`；`scrollToContentSection` 泛化为计数任意层级标题行。序列化保持平顶层 `##` + 正文保留手写 `###`（与顶层大纲 1:1，子层级作为正文一部分）。

**Tech Stack:** 原生 JavaScript（`workbench.html` 内联 `<script>`，与现有代码风格一致）、正则表达式 `/^(#{2,6})\s+(.*)$/`、`node --check` 语法校验。

**Spec:** docs/superpowers/specs/2026-09-02-multi-level-outline-design.md

## Global Constraints

- 改动仅限 `templates/collaborative/workbench.html` 内联 JS，不新增文件、不引入外部库。
- 侧边栏数据来源为解析内容文本（正则 `/^(#{2,6})\s+(.*)$/gm`），**不**按大纲树深度缩进（设计文档决策 1）。
- 序列化保持平顶层 `##` + 正文保留手写 `###`（设计文档决策 2）；`##` = 顶层章节分隔符（与顶层大纲章节 1:1），`###`/`####` = 章节内联子标题。
- 实时同步使用独立短延迟计时器（~300ms），与现有 600ms 保存计时器分离。
- 围栏代码块（`` ``` ``）内的 `#` 注释不误识别为标题。
- 仅识别 `##`–`######`（2–6 个 `#`），避免单 `#` 扰乱层级。
- 范围严格以 `docs/openspec/changes/multi-level-outline/tasks.md` 为准，不扩展。
- 无前端自动化测试基础设施；语法校验使用 `node --check`，功能验证使用浏览器人工测试。

---

## File Structure

**修改文件：**
- `templates/collaborative/workbench.html` — 唯一改动文件

**改动区域映射：**

| 区域 | 行号 | 改动内容 |
|------|------|----------|
| CSS | 23–26 | 新增 `.content-outline-item` 缩进变量支持（通过 JS 动态设置 `paddingLeft`） |
| `parseContentHeadings` | 新增 | 从内容文本提取标题层级列表 |
| `renderContentOutlineList` | 1098–1127 | 改为调用 `parseContentHeadings`，按层级缩进渲染 |
| `scrollToContentSection` | 1246–1270 | 泛化为计数任意层级标题行 |
| `onArticleInput` | 1309–1317 | 追加防抖调用 `renderContentOutlineList` |

---

## Task 1: 新增 `parseContentHeadings` 函数

**Files:**
- Create: `templates/collaborative/workbench.html`（在 `flattenOutlineSections` 之前新增函数）
- Test: 浏览器人工验证（Task 4.2 覆盖）

**Interfaces:**
- Consumes: `#article-content-input` 的 `value`（字符串）
- Produces: `Array<{level: number, title: string, lineIndex: number}>` — 供 `renderContentOutlineList` 消费

- [x] **Step 1: 在 `flattenOutlineSections` 之前新增 `parseContentHeadings` 函数**

在 `templates/collaborative/workbench.html` 第 1078 行（`// 内容阶段逻辑` 注释之后、`flattenOutlineSections` 之前）插入以下代码：

```javascript
// 从内容文本提取 markdown 标题层级列表（跳过围栏代码块）
function parseContentHeadings(text) {
  const headings = [];
  const lines = text.split('\n');
  let inCodeBlock = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^```/.test(line.trim())) {
      inCodeBlock = !inCodeBlock;
      continue;
    }
    if (inCodeBlock) continue;
    const m = /^(#{2,6})\s+(.*)$/.exec(line);
    if (m) {
      headings.push({ level: m[1].length, title: m[2].trim(), lineIndex: i });
    }
  }
  return headings;
}
```

- [x] **Step 2: 运行 `node --check` 校验语法**

```bash
node --check templates/collaborative/workbench.html 2>&1 || echo "SYNTAX_ERROR"
```

> **注意：** `node --check` 对 HTML 文件中的内联 JS 无法直接校验（会报 HTML 标签错误）。正确做法是提取 `<script>` 内容后校验，或仅做人工审查。若项目有构建脚本则使用之；否则跳过此步，依赖 Task 4.1 的浏览器验证。

Expected: 无语法错误（或跳过，因 `node --check` 不适用于 HTML 文件）。

- [x] **Step 3: 验证函数逻辑正确性（人工审查）**

确认以下场景被正确处理：
- `## 标题` → `{level: 2, title: "标题", lineIndex: N}`
- `### 子标题` → `{level: 3, title: "子标题", lineIndex: N}`
- `#### 更深` → `{level: 4, title: "更深", lineIndex: N}`
- `# 单标题` → 被忽略（不识别单 `#`）
- ```` ``` ```` → 切换 `inCodeBlock` 状态
- 代码块内 `# 注释` → 被忽略
- 空行、普通正文 → 被忽略

---

## Task 2: 改写 `renderContentOutlineList` 按层级缩进渲染

**Files:**
- Modify: `templates/collaborative/workbench.html` — `renderContentOutlineList` 函数（当前第 1098–1127 行）
- Test: 浏览器人工验证（Task 4.2 覆盖）

**Interfaces:**
- Consumes: `parseContentHeadings(text)` 的输出（`Array<{level, title, lineIndex}>`）
- Produces: `.content-outline-item` 元素列表，每个元素设置 `paddingLeft = (level - 2) * 16px` 和 `data-line-index` 属性

- [x] **Step 1: 替换 `renderContentOutlineList` 函数体**

将 `templates/collaborative/workbench.html` 中第 1098–1127 行的 `renderContentOutlineList` 函数替换为：

```javascript
function renderContentOutlineList() {
  const container = document.getElementById('content-outline-list');
  const emptyHint = document.getElementById('content-outline-empty-hint');
  if (!container) return;
  // 保留 empty-hint 节点，仅清空之前渲染的章节行
  Array.from(container.children).forEach(child => {
    if (child.id !== 'content-outline-empty-hint') container.removeChild(child);
  });

  const ta = document.getElementById('article-content-input');
  if (!ta) return;
  const headings = parseContentHeadings(ta.value);
  if (headings.length === 0) {
    if (emptyHint) emptyHint.style.display = '';
    return;
  }
  if (emptyHint) emptyHint.style.display = 'none';

  headings.forEach(h => {
    const row = document.createElement('div');
    row.className = 'content-outline-item';
    row.setAttribute('data-line-index', h.lineIndex);
    row.style.paddingLeft = ((h.level - 2) * 16) + 'px';
    row.onclick = function() { scrollToContentSectionByLine(h.lineIndex, row); };

    const titleSpan = document.createElement('span');
    titleSpan.className = 'ci-title';
    titleSpan.textContent = h.title;

    row.appendChild(titleSpan);
    container.appendChild(row);
  });
}
```

- [x] **Step 2: 验证缩进渲染逻辑（人工审查）**

确认：
- `##` 标题 → `paddingLeft: 0px`（顶层，无缩进）
- `###` 标题 → `paddingLeft: 16px`（一级缩进）
- `####` 标题 → `paddingLeft: 32px`（二级缩进）
- 无标题时显示 `#content-outline-empty-hint`
- 每个 `.content-outline-item` 存储 `data-line-index` 供点击定位使用

---

## Task 3: 新增 `scrollToContentSectionByLine` 辅助函数

**Files:**
- Create: `templates/collaborative/workbench.html`（在 `scrollToContentSection` 之前新增）
- Test: 浏览器人工验证（Task 4.2 覆盖）

**Interfaces:**
- Consumes: `lineIndex: number`（标题行号）+ `rowElement: HTMLElement`（目录项 DOM 元素）
- Produces: 滚动编辑器到对应行 + 高亮该目录项

- [x] **Step 1: 在 `scrollToContentSection` 之前新增 `scrollToContentSectionByLine` 函数**

在 `templates/collaborative/workbench.html` 中 `scrollToContentSection` 函数之前插入：

```javascript
// 按行号滚动编辑器到对应标题行并高亮该目录项
function scrollToContentSectionByLine(lineIndex, rowElement) {
  const ta = document.getElementById('article-content-input');
  const main = document.querySelector('.content-split-main');
  // 高亮当前目录项
  document.querySelectorAll('#content-outline-list .content-outline-item').forEach(el => {
    el.classList.remove('active');
  });
  if (rowElement) rowElement.classList.add('active');
  if (!ta || !main) return;
  // 估算 scrollTop：按行号比例乘以编辑框总高度
  const lines = ta.value.split('\n');
  const ratio = lineIndex / lines.length;
  main.scrollTop = ratio * main.scrollHeight;
}
```

- [x] **Step 2: 验证滚动逻辑（人工审查）**

确认：
- `ratio = lineIndex / totalLines` 估算位置
- `main.scrollTop = ratio * main.scrollHeight` 滚动
- 高亮通过 `.active` 类切换（CSS 已在第 25 行定义）

---

## Task 4: 泛化 `scrollToContentSection` 兼容任意层级标题

**Files:**
- Modify: `templates/collaborative/workbench.html` — `scrollToContentSection` 函数（当前第 1246–1270 行）
- Test: 浏览器人工验证（Task 4.2 覆盖）

**Interfaces:**
- Consumes: `id: string`（大纲章节 id，保留旧接口兼容）
- Produces: 滚动编辑器到对应标题行 + 高亮该目录项

- [x] **Step 1: 替换 `scrollToContentSection` 函数体**

将 `templates/collaborative/workbench.html` 中第 1246–1270 行的 `scrollToContentSection` 函数替换为：

```javascript
function scrollToContentSection(id) {
  const ta = document.getElementById('article-content-input');
  const main = document.querySelector('.content-split-main');
  // 高亮当前章节（兼容旧调用点：按 data-section 属性匹配）
  document.querySelectorAll('#content-outline-list .content-outline-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-section') === id);
  });
  if (!ta || !main) return;
  // 找到该章节标题在编辑框文本中的行号（计数任意层级标题行）
  const flat = flattenOutlineSections(currentOutline().sections);
  const idx = flat.findIndex(s => s.id === id);
  if (idx < 0) return;
  const lines = ta.value.split('\n');
  let lineNo = 0, found = -1;
  for (let i = 0; i < lines.length; i++) {
    if (/^#{2,6}\s+/.test(lines[i])) {
      if (lineNo === idx) { found = i; break; }
      lineNo++;
    }
  }
  if (found < 0) return;
  // 估算 scrollTop：按行比例乘以编辑框总高度
  const ratio = found / lines.length;
  main.scrollTop = ratio * main.scrollHeight;
}
```

- [x] **Step 2: 验证泛化逻辑（人工审查）**

确认：
- 正则从 `/^##\s+/` 改为 `/^#{2,6}\s+/`，兼容 `##`–`######`
- 仍按展平章节顺序匹配（`lineNo === idx`）
- 旧调用点（若有 `data-section` 属性）仍可通过高亮逻辑兼容

---

## Task 5: 在 `onArticleInput` 中追加防抖调用 `renderContentOutlineList`

**Files:**
- Modify: `templates/collaborative/workbench.html` — `onArticleInput` 函数（当前第 1309–1317 行）
- Test: 浏览器人工验证（Task 4.2 覆盖）

**Interfaces:**
- Consumes: `ta`（textarea 元素）
- Produces: 防抖调用 `renderContentOutlineList()`（~300ms 延迟）

- [x] **Step 1: 在 `onArticleInput` 中追加防抖渲染调用**

将 `templates/collaborative/workbench.html` 中第 1309–1317 行的 `onArticleInput` 函数替换为：

```javascript
// 整篇文章输入：解析回 contentData + 自动撑高 + 防抖保存 + 防抖刷新目录（9.1）
let _saveArticleTimer = null;
let _outlineTimer = null;
function onArticleInput(ta) {
  parseArticleText(ta.value);
  autoResizeTextarea(ta);
  if (_saveArticleTimer) clearTimeout(_saveArticleTimer);
  _saveArticleTimer = setTimeout(async () => {
    try { await saveContentState(); }
    catch (e) { toast('保存失败：' + e.message, 'error'); }
  }, 600);
  // 防抖刷新大纲目录（独立短计时器，避免每次击键重渲染）
  if (_outlineTimer) clearTimeout(_outlineTimer);
  _outlineTimer = setTimeout(() => {
    renderContentOutlineList();
  }, 300);
}
```

- [x] **Step 2: 验证防抖逻辑（人工审查）**

确认：
- `_outlineTimer` 独立于 `_saveArticleTimer`
- 延迟 300ms（短于保存的 600ms，确保目录先刷新）
- 每次击键重置计时器，避免连续输入时频繁重渲染

---

## Task 6: 验证序列化往返一致性（确认现有实现已符合设计文档）

**Files:**
- Modify: 无（仅验证，不修改代码）
- Test: 浏览器人工验证（Task 4.2 覆盖）

**Interfaces:**
- Consumes: 无
- Produces: 确认 `serializeArticleForEdit` 和 `parseArticleText` 已符合设计文档决策 2

- [x] **Step 1: 审查 `serializeArticleForEdit` 确认符合设计文档决策 2**

审查 `templates/collaborative/workbench.html` 第 1273–1283 行的 `serializeArticleForEdit` 函数：

```javascript
function serializeArticleForEdit() {
  const flat = flattenOutlineSections(currentOutline().sections);
  const parts = [];
  flat.forEach(s => {
    const item = contentData.find(c => c.id === s.id);
    const title = (item && item.title) || s.title || s.id;
    const body = (item && item.content) || '';
    parts.push('## ' + title + '\n\n' + body);
  });
  return parts.join('\n\n');
}
```

确认：
- 每节输出 `## 标题\n\n正文`（平顶层 `##`）
- `body` 取自 `contentData`，含用户手写 `###`（正文保留手写 `###`）
- 符合设计文档决策 2（平顶层 + 正文保留）

**结论：** 当前实现已符合设计文档，无需修改。

- [x] **Step 2: 审查 `parseArticleText` 确认符合设计文档决策 2**

审查 `templates/collaborative/workbench.html` 第 1286–1305 行的 `parseArticleText` 函数：

```javascript
function parseArticleText(text) {
  const flat = flattenOutlineSections(currentOutline().sections);
  const blocks = text.split(/^##\s+/m).filter(b => b.length > 0);
  blocks.forEach((block, i) => {
    const sec = flat[i];
    if (!sec) return;
    const firstNewline = block.indexOf('\n');
    const title = firstNewline >= 0 ? block.slice(0, firstNewline).trim() : block.trim();
    const body = firstNewline >= 0 ? block.slice(firstNewline + 1).replace(/^\n+/, '').trim() : '';
    let item = contentData.find(c => c.id === sec.id);
    if (!item) {
      item = { id: sec.id, title: title || sec.title || sec.id, content: body, status: 'initial' };
      contentData.push(item);
    } else {
      item.title = title || item.title;
      item.content = body;
    }
    if (body && item.status === 'initial') item.status = 'edited';
  });
}
```

确认：
- 按 `## ` 切分顶层章节（`text.split(/^##\s+/m)`）
- `body` 内 `###` 原样保留（`firstNewline` 之后的内容不处理）
- 符合设计文档决策 2（平顶层 + 正文保留）

**结论：** 当前实现已符合设计文档，无需修改。

> **⚠️ 与 tasks.md 的差异说明：** tasks.md 第 3.1、3.2 条要求「按 depth 输出嵌套标题」和「识别 `#{2,6}` 标题块」，但设计文档决策 2 明确否决了按 depth 输出嵌套标题的方案（备选 A），采用「平顶层 `##` + 正文保留手写 `###`」（备选 B）。当前代码已实现备选 B，与设计文档一致。本计划以设计文档为权威规范，不执行 tasks.md 中与设计文档矛盾的步骤。

---

## Task 7: 集成验证

**Files:**
- Test: 浏览器人工验证

- [x] **Step 1: 运行 `node --check` 校验 `workbench.html` 内联 JS 语法**

由于 `node --check` 无法直接校验 HTML 文件，使用以下方法提取并校验内联 JS：

```bash
cd /Users/casey/workspace/inkForge-studio && sed -n '/<script>/,/<\/script>/p' templates/collaborative/workbench.html | sed '1d;$d' > /tmp/workbench_check.js && node --check /tmp/workbench_check.js && echo "SYNTAX_OK"
```

Expected: 输出 `SYNTAX_OK`，无语法错误。

- [x] **Step 2: 浏览器人工验证 — 多级目录渲染**（需人执行，已记录为 verify 阶段验收项）

1. 打开内容创作阶段工作台
2. 使用 AI 生成内容（或手动输入含 `###`/`####` 的内容）
3. 验证侧边栏显示嵌套缩进目录：
   - `##` 标题无缩进
   - `###` 标题缩进 16px
   - `####` 标题缩进 32px

- [x] **Step 3: 浏览器人工验证 — 实时同步**（需人执行，已记录为 verify 阶段验收项）

1. 在编辑器中手动添加 `### 新子标题`
2. 等待 ~300ms 后验证侧边栏出现新目录项
3. 删除该子标题，验证侧边栏同步移除

- [x] **Step 4: 浏览器人工验证 — 点击定位与高亮**（需人执行，已记录为 verify 阶段验收项）

1. 点击侧边栏中 `###` 子标题项
2. 验证编辑器滚动到对应标题行
3. 验证该目录项高亮（`.active` 类）

- [x] **Step 5: 浏览器人工验证 — 围栏代码块不误识别**（需人执行，已记录为 verify 阶段验收项）

在编辑器中输入：

````markdown
## 正常标题

```
# 这不是标题
## 这也不是标题
```

### 子标题
````

验证侧边栏仅显示「正常标题」和「子标题」，代码块内的 `#` 注释不出现。

- [x] **Step 6: 浏览器人工验证 — 保存后再加载层级保持**（需人执行，已记录为 verify 阶段验收项）

1. 在编辑器中创建含 `###`/`####` 的多级内容
2. 保存项目
3. 重新加载项目
4. 验证侧边栏仍显示完整的多级目录（层级不丢）

- [x] **Step 7: 浏览器人工验证 — 空内容显示空提示**（需人执行，已记录为 verify 阶段验收项）

1. 清空编辑器内容
2. 验证侧边栏显示 `#content-outline-empty-hint` 空提示

---

## Task 8: 清理与收尾

**Files:**
- Modify: `templates/collaborative/workbench.html`（如有调试代码则移除）

- [x] **Step 1: 确认无残留调试代码**（已确认：无 console.log/debugger/TODO）

搜索 `console.log`、`console.debug`、`debugger` 等调试语句，确认本次改动未引入新的调试代码：

```bash
cd /Users/casey/workspace/inkForge-studio && grep -n "console\.log\|console\.debug\|debugger" templates/collaborative/workbench.html | grep -v "//.*console"
```

Expected: 无本次新增的调试语句。

- [x] **Step 2: 确认 CSS 无需改动**（已确认：inline paddingLeft 覆盖 CSS 简写左内边距，符合预期）

验证 `.content-outline-item` 的现有 CSS（第 23–26 行）已支持动态 `paddingLeft`：

```css
.content-outline-item { padding: 8px 10px; ... }
```

由于 `paddingLeft` 通过 JS `row.style.paddingLeft` 内联设置，会覆盖 CSS 中的 `padding` 简写对左内边距的定义。确认这是预期行为（内联样式优先级高于 CSS 类）。

Expected: 无需修改 CSS，内联 `paddingLeft` 正常工作。

---

## 附录：改动汇总

| 改动 | 位置 | 类型 |
|------|------|------|
| 新增 `parseContentHeadings` | `flattenOutlineSections` 之前 | 新增函数 |
| 替换 `renderContentOutlineList` | 原第 1098–1127 行 | 函数体重写 |
| 新增 `scrollToContentSectionByLine` | `scrollToContentSection` 之前 | 新增函数 |
| 替换 `scrollToContentSection` | 原第 1246–1270 行 | 函数体重写 |
| 替换 `onArticleInput` | 原第 1309–1317 行 | 追加防抖调用 |
| 审查 `serializeArticleForEdit` | 第 1273–1283 行 | 验证（无需修改） |
| 审查 `parseArticleText` | 第 1286–1305 行 | 验证（无需修改） |
