## 1. 数据库与基础设施

- [x] 1.1 在 `user_db.py` 中新增 `version_snapshots` 表（字段：id, project_id, user_id, version_name, content_json, created_at, trigger_type）和 `ai_label_config` 表（字段：id, label_text, updated_at, updated_by），验证：表创建成功且可通过 SQL 查询
- [x] 1.2 在 `user_db.py` 中新增 `collaborative_projects` 表（字段：id, user_id, title, current_phase, topic_json, outline_json, content_json, created_at, updated_at）和 `article_history` 表（字段：id, user_id, title, topic_json, outline_json, content_json, ai_label, created_at, updated_at），验证：表创建成功且与 users 表外键关联正确
- [x] 1.3 新增 `modules/version_manager.py` 模块，实现 `create_snapshot()`、`list_versions()`、`get_version()`、`compare_versions()`、`rollback_to_version()` 函数，验证：单元测试覆盖各函数

## 2. AI 辅助能力拆分

- [x] 2.1 在 `modules/ai_writer.py` 中新增 `generate_topics(idea, count=5)` 函数，接收想法返回多个选题建议（每个包含标题和说明），验证：调用返回包含 3-5 个选题的列表
- [x] 2.2 在 `modules/ai_writer.py` 中新增 `generate_outline(topic, context=None)` 函数，基于选题返回结构化大纲 JSON，验证：调用返回包含章节和要点的 JSON 结构
- [x] 2.3 在 `modules/ai_writer.py` 中新增 `generate_content(outline, section=None)` 函数，基于大纲生成内容，section 为 None 时生成全部内容，验证：传入大纲返回段落内容，section 参数控制是否仅生成单段
- [x] 2.4 确保三个新函数共享现有 LLM 配置检测逻辑（`_detect_llm_backend`），验证：在无 API key 时自动降级到 Ollama 或内置模板

## 3. AI 标识模块

- [x] 3.1 新增 `modules/ai_labeler.py` 模块，实现 `get_label_text()`（从配置表读取，返回默认文案）、`attach_label(content)`（在内容末尾附加标识）、`validate_content(content)`（校验标识存在），验证：单元测试覆盖标识附加和校验逻辑
- [x] 3.2 实现管理员配置接口 `set_label_text(new_text, admin_user)`，验证：非管理员调用被拒绝，管理员调用成功更新配置

## 4. 历史文章模块

- [x] 4.1 新增 `modules/article_history.py` 模块，实现 `save_article()`、`list_articles()`、`get_article()`、`update_article()`、`delete_article()` 函数，验证：单元测试覆盖各函数
- [x] 4.2 在保存文章流程中集成 `ai_labeler.attach_label()` 自动附加 AI 标识，验证：保存的文章末尾包含 AI 标识
- [x] 4.3 在保存文章流程中集成 `ai_labeler.validate_content()` 校验，标识缺失时阻止保存，验证：标识缺失时保存被阻止并返回明确错误

## 5. 协同创作路由与页面

- [x] 5.1 在 `web_app.py` 中新增 `/collaborative` 路由蓝图，包含：`GET /`（创作列表）、`POST /create`（新建创作项目）、`GET /<project_id>`（进入创作项目），验证：路由可访问且需要登录
- [x] 5.2 新增 `templates/collaborative/list.html` 页面，展示当前用户的协同创作项目列表和历史文章列表，验证：页面正确渲染两个列表并按更新时间排序
- [x] 5.3 新增 `templates/collaborative/workbench.html` 页面，包含创作流程导航（选题/大纲/内容/保存四个阶段指示器），验证：页面展示流程导航且当前阶段高亮
- [x] 5.4 实现创作状态持久化 API：`GET /api/collaborative/<project_id>/state` 和 `POST /api/collaborative/<project_id>/state`，验证：状态保存后刷新页面可恢复

## 6. 选题生成环节前端

- [x] 6.1 在工作台页面实现"选题生成"面板：想法输入框 + "生成选题"按钮 + 选题卡片列表，验证：点击按钮后展示 AI 生成的选题卡片
- [x] 6.2 实现选题卡片展示：标题、说明、"选择此选题"按钮、"修改"按钮，验证：选题卡片正确渲染且可交互
- [x] 6.3 实现"自定义选题"功能：创作者可跳过 AI 生成直接输入选题，验证：自定义选题后进入大纲生成环节
- [x] 6.4 实现"确认选题，进入大纲生成"按钮，确认后触发版本快照，验证：确认后选题进入只读状态且版本历史出现新快照

## 7. 大纲生成环节前端

- [x] 7.1 在工作台页面实现"大纲生成"面板：选题展示 + "生成大纲"按钮 + 大纲树展示区域，验证：点击按钮后展示 AI 生成的大纲结构
- [x] 7.2 实现大纲编辑功能：节点双击编辑、添加节点、删除节点、拖拽排序，验证：编辑后大纲 JSON 正确更新
- [x] 7.3 实现"锁定大纲，进入内容生成"按钮，锁定后触发版本快照，验证：锁定后大纲进入只读状态且版本历史出现新快照

## 8. 内容生成环节前端

- [x] 8.1 在工作台页面实现"内容生成"面板：大纲章节列表 + 每个章节的"生成内容"按钮 + "为全部大纲生成内容"按钮，验证：两种触发方式均可正常工作
- [x] 8.2 实现段落级内容展示：按大纲章节分组，每个段落显示正文和对应大纲节点标注，验证：段落按大纲结构分组展示
- [x] 8.3 实现内容二次修改功能：创作者可直接编辑段落文本，修改后自动保存，验证：编辑后内容更新且状态变为"已修改"
- [x] 8.4 实现内容生成进度指示器（已生成/总章节数），验证：进度随内容生成实时更新
- [x] 8.5 实现"保存到历史文章"按钮，汇总所有段落为完整文章，验证：点击后进入保存环节

## 9. 版本管理前端

- [x] 9.1 在工作台侧边栏实现"版本历史"面板：版本列表（时间、名称、变更摘要），验证：版本列表按时间倒序展示
- [x] 9.2 实现版本内容查看（只读模式），验证：点击历史版本展示该版本完整内容
- [x] 9.3 实现版本对比功能：选择两个版本查看差异，验证：差异视图正确高亮新增/删除/修改
- [x] 9.4 实现版本回溯功能：回溯到历史版本创建新版本，验证：回溯后版本历史完整保留且当前内容更新

## 10. 历史文章前端

- [x] 10.1 实现历史文章列表页面：标题、保存时间、字数、"查看"/"继续编辑"/"删除"操作，验证：列表正确渲染且操作按钮可用
- [x] 10.2 实现历史文章查看页面：完整内容展示（含 AI 标识），验证：查看页面展示正文和末尾 AI 标识
- [x] 10.3 实现"继续编辑"功能：创建新协同创作项目并预填充历史文章内容，验证：继续编辑后新项目内容预填充正确
- [x] 10.4 实现"删除"功能：删除前确认，验证：删除后文章从列表移除

## 11. 平台专属功能移除

- [x] 11.1 移除 `modules/wx_publisher.py`（草稿推送模块），验证：模块文件被移除且无其他模块引用
- [x] 11.2 移除 `modules/md_converter.py`（MD 转平台 HTML 模块），验证：模块文件被移除且无其他模块引用
- [x] 11.3 移除 `modules/cover_generator.py` 和 `modules/cover_maker.py`（封面生成模块），验证：模块文件被移除且无其他模块引用
- [x] 11.4 移除 `web_app.py` 中平台相关路由和菜单（平台发布、草稿箱、平台设置等），验证：相关路由不再可访问
- [x] 11.5 移除平台相关配置文件（`domains_config.json` 等）和前端模板，验证：配置文件被移除且无引用
- [x] 11.6 清理 `main.py` 中平台相关命令行入口和流程，验证：命令行不再展示平台相关选项

## 12. 集成测试与验收

- [x] 12.1 执行完整协同创作流程测试：输入想法 → 生成选题 → 选择选题 → 生成大纲 → 编辑大纲 → 生成内容 → 修改内容 → 保存到历史文章，验证：全流程顺畅且保存文章包含 AI 标识
- [x] 12.2 验证版本管理全流程：多次编辑产生多个版本 → 查看历史 → 对比版本 → 回溯版本，验证：版本记录完整且回溯正确
- [x] 12.3 验证 AI 标识合规性：尝试保存无标识内容被阻止，管理员修改标识文案后新保存使用新文案，验证：标识强制且可配置
- [x] 12.4 验证历史文章管理：保存多篇文章 → 查看列表 → 查看详情 → 继续编辑 → 删除，验证：历史文章管理功能完整
- [x] 12.5 验证平台功能完全移除：相关模块、路由、菜单、配置均不存在，验证：代码库中无平台专属功能残留
