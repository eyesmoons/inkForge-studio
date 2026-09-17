# Task 2 报告：改写 `renderContentOutlineList` 按层级缩进渲染

## 实现内容

将 `templates/collaborative/workbench.html` 中 `renderContentOutlineList` 函数体整体替换为 Task 2 brief 中指定的代码。

### 主要变更

函数从原来基于 `flattenOutlineSections(currentOutline().sections)` 渲染大纲章节列表，改为：

1. 读取 `#article-content-input` 文本框内容
2. 调用 `parseContentHeadings(ta.value)` 解析 markdown 标题
3. 每个标题渲染为 `.content-outline-item` div，设置：
   - `data-line-index` 属性（值为 `h.lineIndex`）
   - `paddingLeft = (h.level - 2) * 16px`（`##` 无缩进，`###` 缩进 16px，`####` 缩进 32px）
   - `onclick` 调用 `scrollToContentSectionByLine(h.lineIndex, row)`
4. 无标题时显示 `#content-outline-empty-hint`

### 未修改部分

- `parseContentHeadings` 函数保持不变（Task 1 产物）
- 其他函数（`flattenOutlineSections`、`scrollToContentSection`、`renderContentSections` 等）保持原位未移动

## 语法验证

```bash
sed -n '/<script>/,/<\/script>/p' templates/collaborative/workbench.html | sed '1d;$d' > /tmp/wb_check.js && node --check /tmp/wb_check.js && echo "SYNTAX_OK"
```

输出：`SYNTAX_OK`

## 文件变更

- `templates/collaborative/workbench.html` — `renderContentOutlineList` 函数体替换（第 1118-1150 行）

## 自查发现

- 函数名 `renderContentOutlineList` 保持不变
- 缩进逻辑 `(h.level - 2) * 16` 与 brief 完全一致
- `data-line-index` 属性使用 `h.lineIndex`（来自 `parseContentHeadings` 返回值）
- `onclick` 引用 `scrollToContentSectionByLine`，该函数由 Task 3 实现；当前未定义不会导致渲染报错（点击时才调用）
- 保留了 empty-hint 的显示/隐藏逻辑
- 函数体前后代码未被波及

## 关注点

- `scrollToContentSectionByLine` 当前尚未定义（Task 3 实现），点击大纲项时会报 `ReferenceError`，但渲染本身不受影响
- 原函数中 `data-section` 属性和 `scrollToContentSection(s.id)` 调用已被完全替换，若其他代码引用 `data-section` 属性查找大纲项，需同步更新（经检查，`scrollToContentSection` 函数内部使用 `data-section` 属性，但该函数仅被旧版 `renderContentOutlineList` 调用，现已无调用方，不构成问题）
