# Task 5: 在 `onArticleInput` 中追加防抖调用 `renderContentOutlineList`

**Files:**
- Modify: `templates/collaborative/workbench.html` — `onArticleInput` 函数

## Step 1: 替换 `onArticleInput` 函数体（含两个防抖计时器）

将 `templates/collaborative/workbench.html` 中当前的 `onArticleInput` 函数及其前面的保存计时器变量**整体替换**为：

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

## 定位方法

找到现有的 `onArticleInput` 函数定义。它前面可能紧邻一个 `let _saveArticleTimer = null;`（或 `var`）声明。将**计时器变量声明 + 函数**整体替换为上面的代码。如果 `_saveArticleTimer` 声明在远处，只替换函数体并在函数前添加 `_outlineTimer` 声明（保留原有的 `_saveArticleTimer` 声明不动）。关键：两个计时器变量都必须在函数外部（模块/脚本作用域）可访问。

## Step 2: 验证防抖逻辑（人工审查）

确认：
- `_outlineTimer` 独立于 `_saveArticleTimer`
- 延迟 300ms（短于保存的 600ms，确保目录先刷新）
- 每次击键重置计时器，避免连续输入时频繁重渲染
- 两个计时器变量都在函数作用域外声明

## 接口

- Consumes: `ta`（textarea 元素）
- Produces: 防抖调用 `renderContentOutlineList()`（~300ms 延迟）

## 依赖

依赖 Task 2 的 `renderContentOutlineList`。
