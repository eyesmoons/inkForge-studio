## 1. 侧边栏多级目录渲染

- [x] 1.1 新增 `parseContentHeadings(text)`：用正则 `/^(#{2,6})\s+(.*)$/gm` 从内容文本提取 `{level, title, lineIndex}` 列表，验证对 `##`/`###`/`####` 均能提取且行号正确。
- [x] 1.2 改写 `renderContentOutlineList()`：读取 `#article-content-input` 文本，调用 `parseContentHeadings`，按 `level-2` 缩进渲染 `.content-outline-item`（无标题时显示空提示），验证多级标题呈现嵌套缩进。

## 2. 实时同步与点击定位

- [x] 2.1 在 `onArticleInput` 中追加调用 `renderContentOutlineList()`（防抖），验证编辑标题后目录实时刷新（新增/删除标题同步）。
- [x] 2.2 目录项点击按行号比例滚动编辑器到对应标题并高亮该目录项，验证点击 `###` 子项定位正确。

## 3. 内容序列化按大纲深度输出多级标题

- [x] 3.1 验证 `serializeArticleForEdit()` 已符合设计文档决策 2：按顶层大纲章节输出 `## 标题\n\n正文`，正文中创作者手写的 `###`/`####` 原样保留（无需修改）。
- [x] 3.2 验证 `parseArticleText()` 已符合设计文档决策 2：仅按 `## ` 切分顶层章节，正文内 `###`/`####` 原样保留，往返一致（无需修改）。
- [x] 3.3 调整 `scrollToContentSection()` 计数任意层级标题（不再仅限 `## `），验证按章节 id 定位到多级标题行。

## 4. 集成验证

- [x] 4.1 运行 `node --check` 校验 `workbench.html` 内联 JS 语法无错误。
- [x] 4.2 浏览器人工验证：AI 生成内容后大纲侧边栏显示嵌套目录；手动在编辑器添加 `###`/`####` 目录实时更新；点击定位与保存后再加载层级保持。（注：浏览器人工验证需人执行，已记录为 verify 阶段验收项，build 阶段不代替人工点击验证。）
