# Task 2: 改写 `renderContentOutlineList` 按层级缩进渲染

**Files:**
- Modify: `templates/collaborative/workbench.html` — `renderContentOutlineList` 函数

## Step 1: 替换 `renderContentOutlineList` 函数体

将 `templates/collaborative/workbench.html` 中当前的 `renderContentOutlineList` 函数**整体替换**为以下代码（保留函数名不变，替换函数体）：

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

## 定位方法

在文件中找到 `function renderContentOutlineList()` 的现有定义，将其从函数开头到对应的闭合 `}` 整体替换。不要移动其他函数。

## Step 2: 验证缩进渲染逻辑（人工审查）

确认：
- `##` 标题 → `paddingLeft: 0px`（顶层，无缩进）
- `###` 标题 → `paddingLeft: 16px`（一级缩进）
- `####` 标题 → `paddingLeft: 32px`（二级缩进）
- 无标题时显示 `#content-outline-empty-hint`
- 每个 `.content-outline-item` 存储 `data-line-index` 供点击定位使用

## 接口

- Consumes: `parseContentHeadings(text)` 的输出（`Array<{level, title, lineIndex}>`）
- Produces: `.content-outline-item` 元素列表，每个元素设置 `paddingLeft = (level - 2) * 16px` 和 `data-line-index` 属性

## 依赖

此任务依赖 Task 1 的 `parseContentHeadings` 函数和 Task 3 的 `scrollToContentSectionByLine` 函数。Task 2 只负责渲染；即使 `scrollToContentSectionByLine` 尚未定义，渲染代码引用它也不会报错（点击时才调用）。
