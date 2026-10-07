# document-rewrite-workflow Specification

## Purpose
将文档解析后的纯文本内容通过 AI 改写模块重新生成适合公众号发布的文章，复用现有改写能力与 SSE 日志流。

## Requirements

### Requirement: AI 改写调用
系统 SHALL 将用户确认后的文本内容传递给现有 AI 改写模块（`modules/article_rewriter.py`），生成完整的公众号文章。

#### Scenario: 调用改写模块成功
- **WHEN** 用户提交非空的文档内容、风格和字数配置
- **THEN** 系统调用 `rewrite_article()` 并返回 Markdown 格式文章

#### Scenario: LLM 不可用时降级
- **WHEN** AI 模型未配置或调用失败
- **THEN** 系统返回错误信息"AI 模型未配置，请先在系统配置中添加模型"，不生成空文章

### Requirement: SSE 流式日志
系统 SHALL 在改写过程中通过 SSE 实时推送进度日志，完成后将结果填入文章编辑器。

#### Scenario: 实时进度显示
- **WHEN** 用户点击"开始改写"
- **THEN** 页面显示日志卡片，实时滚动显示改写进度消息

#### Scenario: 完成后自动填充
- **WHEN** AI 改写完成
- **THEN** 系统将生成的 Markdown 填入文章编辑器，启用预览和发布按钮

### Requirement: 文章预览与发布
改写完成后，系统 SHALL 支持预览和推送到公众号草稿箱，与现有写稿流程一致。

#### Scenario: 预览生成文章
- **WHEN** 改写完成且文章填入编辑器
- **THEN" 系统渲染 Markdown 预览，用户可查看排版效果

#### Scenario: 推送到草稿箱
- **WHEN** 用户在预览后点击"推送到草稿箱"
- **THEN" 系统调用发布接口将文章推送到公众号
