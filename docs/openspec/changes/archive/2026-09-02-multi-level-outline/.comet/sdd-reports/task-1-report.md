# Task 1 Report: 新增 `parseContentHeadings` 函数

## 实现内容

在 `templates/collaborative/workbench.html` 中，`flattenOutlineSections` 函数之前插入了 `parseContentHeadings(text)` 函数。

函数逻辑：
- 按行拆分输入文本
- 用 `inCodeBlock` 布尔状态跟踪围栏代码块（```` ``` ````），块内内容跳过
- 用正则 `/^(#{2,6})\s+(.*)$/` 匹配 2–6 个 `#` 开头的标题行（跳过单 `#`）
- 返回 `[{level, title, lineIndex}]` 数组

插入位置：原 `flattenOutlineSections` 函数之前（现文件第 1078–1096 行），与周围代码缩进风格一致（2 空格缩进，中文注释）。

## 语法检查

命令：
```
sed -n '/<script>/,/<\/script>/p' templates/collaborative/workbench.html | sed '1d;$d' > /tmp/wb_check.js && node --check /tmp/wb_check.js && echo "SYNTAX_OK"
```

输出：`SYNTAX_OK`

## 改动文件

- `templates/collaborative/workbench.html` — 新增 `parseContentHeadings` 函数（19 行）

## 自审发现

- 函数插入位置正确，紧接在 `flattenOutlineSections` 之前
- 缩进与周围代码一致（2 空格）
- 注释语言与文件现有风格一致（中文）
- 正则 `#{2,6}` 确保不识别单 `#` 标题
- 围栏代码块切换逻辑正确（`inCodeBlock = !inCodeBlock`）
- `title` 使用 `.trim()` 去除尾部空白
- 无新增文件、无外部依赖

## 无顾虑

任务按 brief 要求完成，语法检查通过。
