# Brainstorm Summary

- Change: document-rewrite
- Date: 2026-09-30

## 确认的技术方案

### 后端
- **文档解析模块**: `modules/document_parser.py`，单一职责函数 `parse_document(file_bytes, filename) -> str`
- **解析库**: python-docx（docx）、pdfplumber（pdf）、原生 open（md/txt）
- **API 设计**: `/api/document/parse`（同步返回）+ `/api/document/rewrite`（后台线程 + SSE）
- **改写复用**: `modules/article_rewriter.py` 的 `rewrite_article()` 函数

### 前端
- **页面**: `web_static/document_rewrite.html` + `document_rewrite.js`，独立文件
- **导航**: 侧边栏新增"📄 文档改写"，复用 `switchPage()` + `data-page` 模式
- **上传**: `FormData` + `fetch`，与素材库上传一致
- **SSE**: 复用 `subscribeSSE()` from `common.js`
- **状态机**: idle → file_selected → parsing → preview → rewriting → done

### 数据流
```
用户选文件 → FormData POST /api/document/parse → 后端解析 → 返回纯文本
→ 前端填充可编辑文本框 → 用户编辑确认 → POST /api/document/rewrite
→ 后台线程调用 rewrite_article() → SSE 推送日志 → 完成时推送 md_content
→ 前端填充编辑器 → 预览 + 发布
```

## 关键取舍与风险

- **解析仅纯文本** → 不含图片/表格，降低复杂度
- **同步 parse API** → 文档 <10MB 解析通常在 1s 内完成，无需异步
- **rewrite 复用 SSE 模式** → 与现有 write 流程一致，降低维护成本
- **文件不落盘** → 解析后直接丢弃二进制，仅保留解析文本
- **风险**: 扫描版 PDF 无法提取文字 → 前端提示用户；大文档解析可能慢 → 10MB 限制

## 测试策略
- 单元：`parse_document()` 各格式单元测试
- 集成：curl 测试 `/api/document/parse` 和 `/api/document/rewrite`
- E2E：浏览器手动测试完整工作流（上传→解析→改写→预览）
- 边界：不支持格式、超大文件、损坏文件、空内容

## Spec Patch

无（现有 spec 已覆盖所有验收场景）
