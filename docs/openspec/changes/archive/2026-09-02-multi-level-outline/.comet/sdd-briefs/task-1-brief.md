# Task 1: 新增 `parseContentHeadings` 函数

**Files:**
- Modify: `templates/collaborative/workbench.html`（在 `flattenOutlineSections` 之前新增函数）

## Step 1: 在 `flattenOutlineSections` 之前新增 `parseContentHeadings` 函数

在 `templates/collaborative/workbench.html` 中 `flattenOutlineSections` 函数之前插入以下代码：

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

## Step 2: 验证函数逻辑正确性（人工审查）

确认以下场景被正确处理：
- `## 标题` → `{level: 2, title: "标题", lineIndex: N}`
- `### 子标题` → `{level: 3, title: "子标题", lineIndex: N}`
- `#### 更深` → `{level: 4, title: "更深", lineIndex: N}`
- `# 单标题` → 被忽略（不识别单 `#`）
- ```` ``` ```` → 切换 `inCodeBlock` 状态
- 代码块内 `# 注释` → 被忽略
- 空行、普通正文 → 被忽略

## 接口

- Consumes: `#article-content-input` 的 `value`（字符串）
- Produces: `Array<{level: number, title: string, lineIndex: number}>` — 供 `renderContentOutlineList` 消费
