# Task 3: 新增 `scrollToContentSectionByLine` 辅助函数

**Files:**
- Modify: `templates/collaborative/workbench.html`（在 `scrollToContentSection` 之前新增）

## Step 1: 在 `scrollToContentSection` 之前新增 `scrollToContentSectionByLine` 函数

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

## 定位方法

找到 `function scrollToContentSection` 的现有定义，将新函数整体插入在其前面。

## Step 2: 验证滚动逻辑（人工审查）

确认：
- `ratio = lineIndex / totalLines` 估算位置
- `main.scrollTop = ratio * main.scrollHeight` 滚动
- 高亮通过 `.active` 类切换

## 接口

- Consumes: `lineIndex: number`（标题行号）+ `rowElement: HTMLElement`（目录项 DOM 元素）
- Produces: 滚动编辑器到对应行 + 高亮该目录项
