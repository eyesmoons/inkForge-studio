# Task 3: 新增 `scrollToContentSectionByLine` 辅助函数

## 实现内容

在 `templates/collaborative/workbench.html` 中，将 `scrollToContentSectionByLine(lineIndex, rowElement)` 函数插入到现有 `scrollToContentSection(id)` 函数之前。

新函数逻辑：
1. 获取编辑框 (`#article-content-input`) 和滚动容器 (`.content-split-main`) 引用。
2. 清除所有目录项的 `.active` 高亮类，然后为传入的 `rowElement` 添加 `.active`。
3. 按 `lineIndex / lines.length` 计算行号比例，乘以 `main.scrollHeight` 估算 `scrollTop` 并滚动。

## 语法验证

```bash
sed -n '/<script>/,/<\/script>/p' templates/collaborative/workbench.html | sed '1d;$d' > /tmp/wb_check.js && node --check /tmp/wb_check.js && echo "SYNTAX_OK"
```

输出：`SYNTAX_OK`

## 修改文件

- `templates/collaborative/workbench.html` — 在 `scrollToContentSection` 之前新增 `scrollToContentSectionByLine` 函数（约 1268–1282 行）

## 自查结果

- 新函数完整插入在 `scrollToContentSection` 之前，原函数未被修改。
- 新函数与高亮的交互逻辑（`.active` 类切换）与现有代码风格一致。
- 滚动估算逻辑（`ratio * scrollHeight`）与 `scrollToContentSection` 内的实现方式一致。
- 注释使用 zh-CN，与文件内既有注释风格匹配。
- `node --check` 通过，内联 JS 语法无误。

## 无顾虑

无遗留问题。Task 4 将修改 `scrollToContentSection` 本身，与本次改动无冲突。
