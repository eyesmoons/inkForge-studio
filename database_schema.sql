-- ═══════════════════════════════════════════════════════════════
-- 微信公众号自动化发布系统 - 数据库表结构
-- ═══════════════════════════════════════════════════════════════
-- 数据库位置：wechat-publisher/.cache/users.db
-- 创建时间：2026-04-03
-- 更新时间：2026-04-16
-- 说明：本文档包含系统的所有数据表定义和初始数据
-- ═══════════════════════════════════════════════════════════════

-- =================================================================
-- 1. 用户表 (users)
-- =================================================================
-- 用途：存储系统用户信息
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引：用户名查询
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);


-- =================================================================
-- 2. 会话表 (sessions)
-- =================================================================
-- 用途：存储用户登录会话信息
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 索引：会话 ID 查询
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
-- 索引：过期时间查询（用于清理过期会话）
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);


-- =================================================================
-- 3. 公众号账号表 (accounts)
-- =================================================================
-- 用途：存储用户的微信公众号账号配置
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    app_id TEXT NOT NULL,
    app_secret TEXT NOT NULL,
    author TEXT NOT NULL,
    topic_prompt TEXT DEFAULT '',
    article_style TEXT DEFAULT '观点评论',
    word_count INTEGER DEFAULT 2000,
    theme TEXT DEFAULT 'green',
    writing_prompt TEXT DEFAULT '',
    domain TEXT DEFAULT '科技',
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
-- 索引：公众号 ID 查询
CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id);


-- =================================================================
-- 4. 历史文章表 (articles)
-- =================================================================
-- 用途：存储用户创建/发布的文章记录
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    wechat_media_id TEXT,
    wechat_draft_id TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (account_id) REFERENCES accounts (id)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_articles_user_id ON articles(user_id);
-- 索引：公众号查询
CREATE INDEX IF NOT EXISTS idx_articles_account_id ON articles(account_id);


-- =================================================================
-- 5. 定时任务表 (scheduled_tasks)
-- =================================================================
-- 用途：存储用户的定时发布任务配置
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    enabled INTEGER DEFAULT 0,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    draft_only INTEGER DEFAULT 1,
    execution_mode TEXT DEFAULT 'serial',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (account_id) REFERENCES accounts (id)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_user_id ON scheduled_tasks(user_id);


-- =================================================================
-- 6. 定时任务执行记录表 (scheduled_task_runs)
-- =================================================================
-- 用途：记录定时任务的执行历史和状态
CREATE TABLE IF NOT EXISTS scheduled_task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    status TEXT DEFAULT 'running',
    result TEXT,
    error_message TEXT,
    run_log TEXT,
    article_id INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES scheduled_tasks (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (account_id) REFERENCES accounts (id),
    FOREIGN KEY (article_id) REFERENCES articles (id)
);

-- 索引：任务 ID 查询
CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_task_id ON scheduled_task_runs(task_id);
-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_user_id ON scheduled_task_runs(user_id);
-- 索引：开始时间查询
CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_started_at ON scheduled_task_runs(started_at);


-- =================================================================
-- 7. 领域分类表 (domains)
-- =================================================================
-- 用途：存储文章领域分类（科技、财经、教育等）
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    is_system INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_domains_user_id ON domains(user_id);
-- 索引：领域名称查询
CREATE INDEX IF NOT EXISTS idx_domains_name ON domains(name);


-- =================================================================
-- 8. AI 大模型表 (ai_models)
-- =================================================================
-- 用途：存储用户配置的 AI 大模型
CREATE TABLE IF NOT EXISTS ai_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    api_key TEXT NOT NULL,
    api_base TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    UNIQUE(user_id, name)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_ai_models_user_id ON ai_models(user_id);


-- =================================================================
-- 9. 封面生成记录表 (cover_generations)
-- =================================================================
-- 用途：存储用户通过AI生成的封面图片记录，支持用户隔离
CREATE TABLE IF NOT EXISTS cover_generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    filename TEXT NOT NULL,
    model_name TEXT DEFAULT '',
    width INTEGER DEFAULT 1024,
    height INTEGER DEFAULT 1024,
    is_collected INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_cover_generations_user_id ON cover_generations(user_id);
-- 索引：文件名查询
CREATE INDEX IF NOT EXISTS idx_cover_generations_filename ON cover_generations(filename);


-- =================================================================
-- 10. 素材分组表 (material_groups)
-- =================================================================
-- 用途：存储用户素材库的分组信息，支持用户隔离
CREATE TABLE IF NOT EXISTS material_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users (id),
    UNIQUE(user_id, name)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_material_groups_user_id ON material_groups(user_id);


-- =================================================================
-- 11. 素材库表 (material_library)
-- =================================================================
-- 用途：存储用户收藏的素材（可从封面制作收藏，也可手动上传），支持用户隔离和分组
CREATE TABLE IF NOT EXISTS material_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    group_id INTEGER,
    title TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    source_type TEXT DEFAULT 'cover',
    source_id INTEGER,
    filename TEXT NOT NULL,
    image_url TEXT DEFAULT '',
    prompt TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (group_id) REFERENCES material_groups (id)
);

-- 索引：用户查询
CREATE INDEX IF NOT EXISTS idx_material_library_user_id ON material_library(user_id);
-- 索引：分组查询
CREATE INDEX IF NOT EXISTS idx_material_library_group_id ON material_library(group_id);
-- 索引：来源类型查询
CREATE INDEX IF NOT EXISTS idx_material_library_source_type ON material_library(source_type);
-- 索引：标签查询
CREATE INDEX IF NOT EXISTS idx_material_library_tags ON material_library(tags);


-- ═══════════════════════════════════════════════════════════════
-- 初始数据
-- ═══════════════════════════════════════════════════════════════

-- -----------------------------------------------------------------
-- 1. 默认管理员用户
-- -----------------------------------------------------------------
-- 密码：admin123
-- 密码哈希算法：SHA-256 + salt（格式：salt$hash）
INSERT INTO users (username, password_hash, email, role) VALUES
('admin', 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4$b2e0c5d2f7a9e8d3c4b6a1e9f5d8c2a3b4e7f1a9c6d3e8b5f2a7c4d1e9f6b3a8', 'admin@example.com', 'admin')
ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash;


-- -----------------------------------------------------------------
-- 2. 示例公众号账号
-- -----------------------------------------------------------------
INSERT INTO accounts (user_id, account_id, name, app_id, app_secret, author, topic_prompt, article_style, word_count, theme, writing_prompt, domain, is_default) VALUES
(1, 'demo', '示例公众号', 'wx1234567890abcdef', 'your_app_secret_here', '默认作者', '', '观点评论', 2000, 'green', '', '科技', 1)
ON CONFLICT(user_id, account_id) DO UPDATE SET name = excluded.name;


-- -----------------------------------------------------------------
-- 3. 系统默认领域分类
-- -----------------------------------------------------------------
INSERT INTO domains (user_id, name, description, is_system) VALUES
(1, '科技', '科技互联网相关内容', 1),
(1, '财经', '金融理财、商业分析相关内容', 1),
(1, '教育', '教育培训、知识分享相关内容', 1),
(1, '生活', '日常生活、健康养生相关内容', 1),
(1, '娱乐', '影视娱乐、明星八卦相关内容', 1),
(1, '汽车', '汽车评测、新能源车相关内容', 1),
(1, '房产', '房地产、家居装修相关内容', 1),
(1, '旅游', '旅游攻略、酒店民宿相关内容', 1),
(1, '美食', '美食探店、菜谱教程相关内容', 1),
(1, '体育', '体育赛事、健身运动相关内容', 1)
ON CONFLICT(name) DO UPDATE SET description = excluded.description;


-- ═══════════════════════════════════════════════════════════════
-- 常用查询示例
-- ═══════════════════════════════════════════════════════════════

-- -----------------------------------------------------------------
-- 用户管理
-- -----------------------------------------------------------------

-- 查询用户信息（不含密码哈希）
-- SELECT id, username, email, role, created_at, updated_at
-- FROM users
-- WHERE username = ?;

-- 验证用户登录
-- SELECT * FROM users WHERE username = ?;

-- 获取用户所有会话
-- SELECT * FROM sessions WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP;


-- -----------------------------------------------------------------
-- 公众号账号管理
-- -----------------------------------------------------------------

-- 查询用户的所有公众号账号
-- SELECT * FROM accounts WHERE user_id = ? ORDER BY is_default DESC, created_at DESC;

-- 查询用户的默认公众号
-- SELECT * FROM accounts WHERE user_id = ? AND is_default = 1 LIMIT 1;

-- 查询指定 account_id 的账号（如 'demo'）
-- SELECT * FROM accounts WHERE account_id = ?;


-- -----------------------------------------------------------------
-- 历史文章管理
-- -----------------------------------------------------------------

-- 查询用户的历史文章（去重：同一 account_id + file_path 只保留最新的）
-- WITH ranked AS (
--     SELECT
--         a.*,
--         ROW_NUMBER() OVER (
--             PARTITION BY a.account_id, a.file_path
--             ORDER BY a.created_at DESC, a.id DESC
--         ) as rn
--     FROM articles a
--     WHERE a.user_id = ?
-- )
-- SELECT r.*, acc.name as account_name, acc.account_id as account_str_id
-- FROM ranked r
-- LEFT JOIN accounts acc ON r.account_id = acc.id
-- WHERE r.rn = 1
-- ORDER BY r.created_at DESC;

-- 查询文章详情（含公众号名称）
-- SELECT a.*, acc.name as account_name
-- FROM articles a
-- LEFT JOIN accounts acc ON a.account_id = acc.id
-- WHERE a.id = ? AND a.user_id = ?;

-- 统计用户文章数量（按状态）
-- SELECT status, COUNT(*) as count
-- FROM articles
-- WHERE account_id IN (SELECT id FROM accounts WHERE user_id = ?)
-- GROUP BY status;


-- -----------------------------------------------------------------
-- 定时任务管理
-- -----------------------------------------------------------------

-- 查询用户的所有定时任务（含公众号名称）
-- SELECT t.*, acc.name as account_name, acc.account_id as account_str_id
-- FROM scheduled_tasks t
-- LEFT JOIN accounts acc ON t.account_id = acc.id
-- WHERE t.user_id = ?
-- ORDER BY t.created_at DESC;

-- 查询定时任务的执行记录
-- SELECT r.*, t.hour, t.minute, t.draft_only,
--        acc.name as account_name, acc.account_id as account_str_id,
--        art.title as article_title
-- FROM scheduled_task_runs r
-- LEFT JOIN scheduled_tasks t ON r.task_id = t.id
-- LEFT JOIN accounts acc ON r.account_id = acc.id
-- LEFT JOIN articles art ON r.article_id = art.id
-- WHERE r.user_id = ?
-- ORDER BY r.started_at DESC;


-- -----------------------------------------------------------------
-- 领域分类管理
-- -----------------------------------------------------------------

-- 查询用户的所有领域分类（含系统分类）
-- SELECT id, user_id, name, description, is_system, created_at, updated_at
-- FROM domains
-- WHERE user_id = ? OR is_system = 1
-- ORDER BY is_system, id;


-- -----------------------------------------------------------------
-- AI 模型管理
-- -----------------------------------------------------------------

-- 查询用户的所有 AI 模型
-- SELECT * FROM ai_models WHERE user_id = ? ORDER BY is_default DESC, created_at DESC;

-- 查询用户的默认 AI 模型
-- SELECT * FROM ai_models WHERE user_id = ? AND is_default = 1 LIMIT 1;


-- ═══════════════════════════════════════════════════════════════
-- 表关系说明
-- ═══════════════════════════════════════════════════════════════
--
-- users (用户表)
--   ├── sessions (登录会话) - 1:N
--   ├── accounts (公众号账号) - 1:N
--   ├── domains (领域分类) - 1:N
--   ├── ai_models (AI 模型) - 1:N
--   ├── cover_generations (封面生成记录) - 1:N
--   ├── material_groups (素材分组) - 1:N
--   ├── material_library (素材库) - 1:N
--   ├── articles (历史文章) - 1:N (通过 accounts.id)
--   ├── scheduled_tasks (定时任务) - 1:N (通过 accounts.id)
--   └── scheduled_task_runs (任务执行记录) - 1:N
--
-- accounts (公众号账号表)
--   ├── articles (历史文章) - 1:N
--   ├── scheduled_tasks (定时任务) - 1:N
--   └── scheduled_task_runs (任务执行记录) - 1:N
--
-- scheduled_tasks (定时任务表)
--   └── scheduled_task_runs (任务执行记录) - 1:N
--
-- material_groups (素材分组表)
--   └── material_library (素材库) - 1:N
--
-- ═══════════════════════════════════════════════════════════════
-- 字段说明
-- ═══════════════════════════════════════════════════════════════
--
-- users 表:
--   - id: 用户主键
--   - username: 用户名（唯一）
--   - password_hash: 密码哈希（SHA-256 + salt，格式：salt$hash）
--   - email: 邮箱
--   - role: 角色（'user' 或 'admin'）
--   - created_at: 创建时间
--   - updated_at: 更新时间
--
-- sessions 表:
--   - id: 会话主键
--   - session_id: 会话 ID（32 位随机字符串）
--   - user_id: 关联用户 ID
--   - expires_at: 过期时间
--   - created_at: 创建时间
--
-- accounts 表:
--   - id: 账号主键
--   - user_id: 关联用户 ID
--   - account_id: 公众号唯一标识（如 'demo'，用户内唯一）
--   - name: 公众号名称
--   - app_id: 微信 AppID
--   - app_secret: 微信 AppSecret
--   - author: 默认作者
--   - topic_prompt: 选题提示词
--   - article_style: 文章风格（如 '观点评论'）
--   - word_count: 目标字数
--   - theme: 主题颜色（green/blue/warm/dark）
--   - writing_prompt: 写作提示词（AI 模板）
--   - domain: 领域分类（默认 '科技'）
--   - is_default: 是否为默认账号（0 或 1）
--   - created_at: 创建时间
--   - updated_at: 更新时间
--
-- articles 表:
--   - id: 文章主键
--   - user_id: 关联用户 ID
--   - account_id: 关联账号 ID（外键 accounts.id）
--   - title: 文章标题
--   - file_path: Markdown 文件路径
--   - status: 状态（'draft' 或 'published'）
--   - wechat_media_id: 微信发布素材 ID
--   - wechat_draft_id: 微信草稿 ID
--   - published_at: 发布时间
--   - created_at: 创建时间
--
-- scheduled_tasks 表:
--   - id: 任务主键
--   - user_id: 关联用户 ID
--   - account_id: 关联账号 ID（外键 accounts.id）
--   - enabled: 是否启用（0 或 1）
--   - hour: 执行小时（0-23）
--   - minute: 执行分钟（0-59）
--   - draft_only: 是否仅创建草稿（0 或 1）
--   - execution_mode: 执行模式（'serial' 串行 或 'parallel' 并行）
--   - created_at: 创建时间
--   - updated_at: 更新时间
--
-- scheduled_task_runs 表:
--   - id: 执行记录主键
--   - task_id: 关联定时任务 ID（外键 scheduled_tasks.id）
--   - user_id: 关联用户 ID
--   - account_id: 关联账号 ID
--   - status: 执行状态（'running'/'success'/'failed'）
--   - result: 执行结果描述
--   - error_message: 错误信息
--   - run_log: 执行日志（SSE 推送的完整日志）
--   - article_id: 关联文章 ID（外键 articles.id，可为空）
--   - started_at: 开始时间
--   - finished_at: 完成时间
--
-- domains 表:
--   - id: 领域主键
--   - user_id: 关联用户 ID
--   - name: 领域名称（唯一）
--   - description: 领域描述
--   - is_system: 是否为系统领域（0 或 1）
--   - created_at: 创建时间
--   - updated_at: 更新时间
--
-- ai_models 表:
--   - id: 模型主键
--   - user_id: 关联用户 ID
--   - name: 模型名称（用户自定义，用户内唯一）
--   - provider: 提供商（如 'openai', 'anthropic', 'ollama'）
--   - model_name: 模型名称（如 'gpt-4', 'claude-3-opus'）
--   - api_key: API 密钥
--   - api_base: API 基础 URL
--   - is_default: 是否为默认模型（0 或 1）
--   - created_at: 创建时间
--   - updated_at: 更新时间
--
-- cover_generations 表:
--   - id: 记录主键
--   - user_id: 关联用户 ID
--   - prompt: 生成提示词
--   - filename: 生成的图片文件名（cover_ 开头）
--   - model_name: 使用的模型名称（如 'cogview-4'）
--   - width: 图片宽度
--   - height: 图片高度
--   - is_collected: 是否已收藏到素材库（0 或 1）
--   - created_at: 创建时间
--
-- material_groups 表:
--   - id: 分组主键
--   - user_id: 关联用户 ID
--   - name: 分组名称（用户内唯一）
--   - sort_order: 排序权重（越小越靠前）
--   - created_at: 创建时间
--
-- material_library 表:
--   - id: 素材主键
--   - user_id: 关联用户 ID
--   - group_id: 关联分组 ID（可为空，表示未分组）
--   - title: 素材标题
--   - tags: 标签（逗号分隔）
--   - source_type: 来源类型（'cover'=封面制作, 'upload'=手动上传）
--   - source_id: 来源 ID（如 cover_generations.id）
--   - filename: 图片文件名（mat_ 或 upload_ 开头）
--   - image_url: 图片访问 URL
--   - prompt: 生成提示词（AI生成时保留）
--   - notes: 备注
--   - created_at: 创建时间
--
-- ═══════════════════════════════════════════════════════════════
