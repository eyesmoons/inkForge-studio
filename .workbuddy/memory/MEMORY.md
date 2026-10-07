# 项目长期记忆

## 项目概况
- 微信公众号自动化发布系统，Flask + vanilla JS + SQLite + DeepSeek API
- 热榜聚合数据源：豆瓣、知乎、IT之家、少数派
- AI图像生成模型：智谱CogView-4（2026-04-16从glm-image切换）

## 核心模块
- `modules/title_generator.py` - 统一的爆款标题生成模块，所有涉及标题生成的模块（链接改写、AI小助手等）都引用此模块
- `modules/cover_maker.py` - 封面制作，使用cover_generations表，支持user_id用户隔离，is_collected标记
- `modules/material_library.py` - 素材库CRUD + 分组CRUD + 上传图片 + 收藏去重，支持user_id用户隔离
- `modules/auto_selector.py` - 选题生成（搜索引擎 + 8平台热搜聚合 + AI整理），热搜通过_fetch_hotrank_sources()注入；AI选题时会注入公众号运营规范作为最高优先级准则（2026-05-05）
- `modules/article_rewriter.py` - 链接改写V2五步流水线（提取→观点→仿写→标题→排版），标题生成引用统一模块
- `modules/ai_writer.py` - 文章生成，build_article_prompt()含动态时间约束(_time_context) + skill_prompt参数（最高优先级）；生成时会注入运营规范 + 历史文章去重检查（2026-05-05）
- `modules/md_converter.py` - MD→HTML 转换，含排版模板系统（TEMPLATES 字典），支持 5 套模板 + 4 种配色
- `web_app.py` - Flask路由，含/api/rewrite_v2、/api/skills CRUD、/api/generate(含skill_id)、/api/auto(含skill_id)

## 数据库关键表
- cover_generations: 封面生成记录（user_id, prompt, filename, model_name, is_collected）
- material_groups: 素材分组（user_id, name, sort_order）
- material_library: 素材库（user_id, group_id, title, tags, source_type, filename, prompt, notes）
- operating_guidelines: 公众号运营规范（user_id, content, updated_at）（2026-05-05新增）
- writing_skills: 写作技能（user_id, name, description, prompt_content, category, is_active, sort_order）（2026-07-12新增）

## 前端架构
- 16个HTML页面（含login、skill），15个共享侧边栏导航，菜单分4组：核心流程/灵感发现/资源管理/系统
- 灵感发现分组含：每日热搜、历史上的今天
- 资源管理分组含：封面制作、素材库、写作技能、历史文章（2026-07-12新增写作技能）
- 顶部导航栏有"🔗 公众号平台"外链按钮（target="_blank" 打开 mp.weixin.qq.com）
- 封面制作页有"收藏到素材库"按钮，已收藏的显示"✅已收藏"（不可重复收藏）
- 素材库页左侧分组侧栏 + 主区网格展示，支持标签筛选、搜索、上传、移动分组、收藏/删除
- 素材文件命名：封面收藏用mat_前缀，上传用upload_前缀
- 工作台(dashboard.html)用Tab切换：数据概览/全自动流水线/最近文章
- 图表均为原生Canvas手绘，所有图表已适配Retina(devicePixelRatio)和白色文字
- 新图表函数独立为 dash_charts.js，包含：状态分布饼图、发文时段热力图、月度趋势、账号排行、关键词词云

## 用户偏好
- Casey偏好直接简洁的反馈，反对过度工程
- 前腾讯开发者，技术经验涵盖Spark/HBase、SSE、CSS主题化、网页结构解析

## 新增功能（2026-05-05）
- 公众号运营规范系统：config.html新增「公众号运营规范」手风琴菜单，可编辑保存；选题和写稿时自动注入规范作为最高优先级
- 历史文章去重：写稿前调用 `_check_history_duplicates()` 使用两步策略（bigram预筛Top10 → LLM语义判断），精准检测同一产品/型号重复写稿
- API接口：GET/POST `/api/operating_guidelines`、`GET /api/articles/dedup`
- 爆款标题提示词：强调11种爆款标题特征（强烈吸引力、激发好奇心、情感共鸣等），适合微信公众号平台
- 选题时间过滤：长安逸动蓝鲸超擎4月24日上市，无日期搜索结果直接丢弃（2026-05-05修复）
- 全自动流水线：generate_topics 现在传递 user_id，确保选题时加载运营规范
- AI写作价格约束（汽车类）：汽车文章中所有价格信息必须来自易车/懂车帝/汽车之家等权威平台，严禁编造价格；未经确认的价格标注"以官方公布为准"

## 新增功能（2026-07-12）
- 写作技能管理系统：skill.html页面（资源管理分组），支持创建/编辑/删除/启停技能，内置5个快捷模板（科技深度分析/汽车评测风格/幽默段子手/情感共鸣/硬核科普）
- 写稿页(write.html)新增写作技能下拉选择器，选择后生成文章时优先使用该技能的提示词
- API接口：GET/POST `/api/skills`、PUT/DELETE `/api/skills/<id>`、`/api/skills?active_only=1`
- 提示词优先级链：skill_prompt > custom_writing_prompt > config_prompt.json > 默认高质量提示词
- `/api/generate` 和 `/api/auto` 均支持 `skill_id` 参数，`run_auto_pipeline()` 透传 `skill_prompt`
