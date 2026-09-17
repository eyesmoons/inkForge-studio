# Task 4: 泛化 `scrollToContentSection` 兼容任意层级标题

**Files:**
- Modify: `templates/collaborative/workbench.html` — `scrollToContentSection` 函数

## Step 1: 替换 `scrollToContentSection` 函数体

将 `templates/collaborative/workbench.html` 中当前的 `scrollToContentSection` 函数**整体替换**为（保留函数名不变）：

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

## 定位方法

找到 `function scrollToContentSection` 的现有定义（注意：Task 3 会在它前面插入新函数，所以它的行号会后移），整体替换函数体。

## Step 2: 验证泛化逻辑（人工审查）

确认：
- 正则从 `/^##\s+/` 改为 `/^#{2,6}\s+/`，兼容 `##`–`######`
- 仍按展平章节顺序匹配（`lineNo === idx`）
- 旧调用点（若有 `data-section` 属性）仍可通过高亮逻辑兼容

## 接口

- Consumes: `id: string`（大纲章节 id，保留旧接口兼容）
- Produces: 滚动编辑器到对应标题行 + 高亮该目录项

## 依赖

依赖 `flattenOutlineSections` 和 `currentOutline()`（均已存在于文件中，无需新增）。
