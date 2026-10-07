## Purpose

智能体模块允许用户输入一篇公众号文章链接并选择目标公众号账号，系统调用 Coze 工作流自动提取原文并改写为原创文章，在页面展示结果并支持一键推送到公众号草稿箱。

## ADDED Requirements

### Requirement: 侧边栏显示智能体菜单项
系统 SHALL 在侧边栏导航中显示一个名为「智能体」的菜单项，与「写稿」「一键排版」等现有模块并列。

#### Scenario: 已登录用户查看侧边栏
- **WHEN** 已登录用户打开任意页面
- **THEN** 侧边栏显示「智能体」菜单项，点击后跳转到智能体页面

#### Scenario: 智能体菜单项激活状态
- **WHEN** 用户点击「智能体」菜单项
- **THEN** 该菜单项显示为激活（高亮）状态，页面内容区切换为智能体页面

### Requirement: 智能体页面输入表单
智能体页面 SHALL 展示一个输入表单，包含文章链接输入框和公众号账号下拉选择器。

#### Scenario: 页面加载时加载账号列表
- **WHEN** 用户打开智能体页面
- **THEN** 账号下拉选择器加载当前用户配置的所有公众号账号

#### Scenario: 表单校验
- **WHEN** 用户未填写文章链接或未选择账号就点击「生成文章」
- **THEN** 系统提示用户填写必填项，不发起 Coze 调用

### Requirement: 调用 Coze 工作流改写文章
系统 SHALL 将文章链接和所选账号的 AppID/AppSecret 发送到 Coze Workflow API，并展示改写后的文章。

#### Scenario: 成功调用 Coze 工作流
- **WHEN** 用户填写了有效文章链接并选择账号后点击「生成文章」
- **THEN** 系统调用 Coze Workflow API，等待返回后将改写后的文章标题和正文展示在结果区

#### Scenario: Coze 工作流调用失败
- **WHEN** Coze Workflow API 返回错误或超时
- **THEN** 系统在页面上显示友好的错误提示（如"生成失败，请稍后重试"），不丢失用户已填写的输入

#### Scenario: 调用过程中显示加载状态
- **WHEN** 系统正在调用 Coze Workflow API
- **THEN** 页面显示加载指示器，禁用「生成文章」按钮防止重复提交

### Requirement: 展示改写结果
系统 SHALL 在结果区展示 Coze 返回的文章标题和正文内容。

#### Scenario: 展示文章标题和正文
- **WHEN** Coze 工作流返回改写结果
- **THEN** 结果区显示文章标题和正文，内容可滚动查看

### Requirement: 推送文章到草稿箱
系统 SHALL 允许用户将改写后的文章一键推送到公众号草稿箱。

#### Scenario: 成功推送到草稿箱
- **WHEN** 用户在改写结果展示后点击「推送到草稿箱」
- **THEN** 系统使用所选账号的凭证，通过现有微信发布流程将文章创建为草稿，并提示成功

#### Scenario: 推送失败
- **WHEN** 推送到草稿箱时微信 API 返回错误
- **THEN** 系统显示错误原因（如 access_token 获取失败），文章内容保留在页面中

### Requirement: Coze 凭证配置
系统 SHALL 支持配置 Coze Workflow API 所需的 Workflow ID 和 API Token。

#### Scenario: 凭证未配置时提示
- **WHEN** 用户未配置 Coze 凭证就尝试生成文章
- **THEN** 系统提示用户先在系统配置中完成 Coze 工作流配置
