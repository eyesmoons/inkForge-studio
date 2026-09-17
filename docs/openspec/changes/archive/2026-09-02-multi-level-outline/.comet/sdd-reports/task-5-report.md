# Task 5 Report: 在 `onArticleInput` 中追加防抖调用 `renderContentOutlineList`

## What I Implemented

在 `templates/collaborative/workbench.html` 的 `onArticleInput(ta)` 函数中追加了第二个独立的防抖计时器 `_outlineTimer`（300ms），调用 `renderContentOutlineList()`，使大纲目录在用户输入时实时刷新。

具体改动：
- 在 `_saveArticleTimer` 声明下方新增 `let _outlineTimer = null;`
- 在 `onArticleInput` 函数体内，600ms 保存计时器之后新增 300ms 目录刷新计时器
- 更新注释，从"防抖保存"改为"防抖保存 + 防抖刷新目录"
- 两个计时器相互独立，目录刷新（300ms）先于保存（600ms）触发

## Syntax Check

```
sed -n '/<script>/,/<\/script>/p' templates/collaborative/workbench.html | sed '1d;$d' > /tmp/wb_check.js && node --check /tmp/wb_check.js && echo "SYNTAX_OK"
```

输出：`SYNTAX_OK`

## Files Changed

- `templates/collaborative/workbench.html` — 仅修改内联 JS，行 1346-1362

## Timer Declaration Location

- `_saveArticleTimer`：行 1347，脚本级（模块级）`let` 声明，函数外部
- `_outlineTimer`：行 1348，脚本级（模块级）`let` 声明，函数外部

两个计时器变量均在 `onArticleInput` 函数作用域外声明，通过闭包被函数访问，符合 brief 要求。

## Self-Review Findings

- `_outlineTimer` 独立于 `_saveArticleTimer`：各自有独立的 `clearTimeout` / `setTimeout`，互不干扰
- 延迟 300ms，短于保存的 600ms，确保目录先刷新
- 每次击键重置两个计时器，避免连续输入时频繁重渲染/保存
- 未修改 `renderContentOutlineList`、`parseArticleText`、`autoResizeTextarea`
- 未新增文件、未引入外部库
- 注释使用 zh-CN，与文件内已有中文注释风格一致

## Concerns

无。改动简洁、语法验证通过、逻辑符合 brief 要求。
