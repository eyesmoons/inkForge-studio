"""
user_db.py
用户数据库管理

功能：
- 用户表（id/username/password/email/role/created_at）
- 会话表（session_id/user_id/expires_at）
- 账号隔离（accounts.json 添加 user_id 字段）
"""

import sys
import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

# ── 数据库路径 ────────────────────────────────────────────
# 打包后使用用户数据目录，开发模式使用项目根目录 .cache
if getattr(sys, 'frozen', False):
    # 打包后的运行目录（macOS/Windows 通用）
    if sys.platform == 'darwin':
        DATA_DIR = Path.home() / 'Library' / 'Application Support' / 'WeChatPublisher'
    else:  # Windows
        DATA_DIR = Path.home() / 'AppData' / 'Local' / 'WeChatPublisher'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DATA_DIR / "users.db"
else:
    # 开发模式：项目根目录 .cache
    DB_DIR = Path(__file__).parent.parent / ".cache"
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DB_DIR / "users.db"

# ── 会话有效期（小时）────────────────────────────────────
SESSION_EXPIRE_HOURS = 24


class UserDB:
    """用户数据库管理"""

    def __init__(self):
        self.conn = None
        self._init_db()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _connect(self):
        """创建数据库连接"""
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

    def _init_db(self):
        """初始化数据库表"""
        self._connect()
        cur = self.conn.cursor()

        # 用户表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 会话表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 账号表
        cur.execute("""
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
            )
        """)

        # 历史文章表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        """)

        # 领域分类表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                ref_websites TEXT DEFAULT '[]',
                is_system INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        # 兼容旧数据库：补加 ref_websites 列
        try:
            cur.execute("ALTER TABLE domains ADD COLUMN ref_websites TEXT DEFAULT '[]'")
            self.conn.commit()
        except Exception:
            pass  # 列已存在，忽略

        # AI 大模型表
        cur.execute("""
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
            )
        """)

        # 封面生成记录表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cover_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                style TEXT DEFAULT '',
                size TEXT DEFAULT '',
                custom_prompt TEXT DEFAULT '',
                filename TEXT NOT NULL,
                image_url TEXT DEFAULT '',
                prompt TEXT DEFAULT '',
                revised_prompt TEXT DEFAULT '',
                model TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 素材分组表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS material_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, name)
            )
        """)

        # 素材库表
        cur.execute("""
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
            )
        """)

        # 运营规范表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operating_guidelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                content TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 写作技能表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS writing_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                prompt_content TEXT NOT NULL,
                category TEXT DEFAULT '通用',
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 协同创作项目表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS collaborative_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                current_phase TEXT NOT NULL DEFAULT 'topic',
                topic_json TEXT,
                outline_json TEXT,
                content_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 历史文章表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS article_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                topic_json TEXT,
                outline_json TEXT,
                content_json TEXT,
                ai_label TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 版本快照表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS version_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                version_name TEXT,
                content_json TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES collaborative_projects (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # AI 标识配置表（单条记录）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_label_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label_text TEXT NOT NULL DEFAULT '本文由 AI 辅助生成，请仔细甄别文章内容。',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER REFERENCES users (id)
            )
        """)
        cur.execute("SELECT COUNT(*) FROM ai_label_config")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO ai_label_config (id, label_text) VALUES (1, ?)",
                ("本文由 AI 辅助生成，请仔细甄别文章内容。",)
            )
            self.conn.commit()

        # 数据库迁移：添加 is_image_model 字段（标识图像生成模型）
        try:
            cur.execute("SELECT is_image_model FROM ai_models LIMIT 1")
        except sqlite3.OperationalError:
            print("[db] 迁移：为 ai_models 表添加 is_image_model 字段")
            cur.execute("ALTER TABLE ai_models ADD COLUMN is_image_model INTEGER DEFAULT 0")
            self.conn.commit()

        # 数据库迁移：添加 domain 字段（如果不存在）
        try:
            cur.execute("SELECT domain FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            print("[db] 迁移：为 accounts 表添加 domain 字段")
            cur.execute("ALTER TABLE accounts ADD COLUMN domain TEXT DEFAULT '科技'")
            self.conn.commit()

        # 数据库迁移：添加 ending_text 字段到 accounts（如果不存在）
        try:
            cur.execute("SELECT ending_text FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            print("[db] 迁移：为 accounts 表添加 ending_text 字段")
            cur.execute("ALTER TABLE accounts ADD COLUMN ending_text TEXT DEFAULT '感谢阅读，我们下期见。'")
            self.conn.commit()

        # 数据库迁移：为 material_library 添加 group_id 字段
        try:
            cur.execute("SELECT group_id FROM material_library LIMIT 1")
        except sqlite3.OperationalError:
            print("[db] 迁移：为 material_library 表添加 group_id 字段")
            cur.execute("ALTER TABLE material_library ADD COLUMN group_id INTEGER")
            self.conn.commit()

        # 数据库迁移：为 cover_generations 添加 is_collected 字段
        try:
            cur.execute("SELECT is_collected FROM cover_generations LIMIT 1")
        except sqlite3.OperationalError:
            print("[db] 迁移：为 cover_generations 表添加 is_collected 字段")
            cur.execute("ALTER TABLE cover_generations ADD COLUMN is_collected INTEGER DEFAULT 0")
            self.conn.commit()

        # 数据库迁移：移除发布相关字段（wechat_media_id/wechat_draft_id）
        try:
            cur.execute("SELECT wechat_media_id FROM articles LIMIT 1")
            print("[db] 迁移：移除 articles 表的 wechat_media_id/wechat_draft_id 字段")
            cur.execute("ALTER TABLE articles DROP COLUMN wechat_media_id")
            cur.execute("ALTER TABLE articles DROP COLUMN wechat_draft_id")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # 字段不存在或已移除，忽略

        # 创建默认用户（如果不存在）
        cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cur.fetchone()[0] == 0:
            print("[db] 创建默认用户 admin / 123456")
            password_hash = self._hash_password("123456")
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", password_hash, "admin")
            )
            self.conn.commit()

        # 创建索引（放在迁移之后，确保字段已存在）
        cur.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON sessions(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON sessions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_user_id ON articles(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_account_id ON articles(account_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_domains_user_id ON domains(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_domains_name ON domains(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_models_user_id ON ai_models(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cover_generations_user_id ON cover_generations(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_material_library_user_id ON material_library(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_material_library_group_id ON material_library(group_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_material_groups_user_id ON material_groups(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_operating_guidelines_user_id ON operating_guidelines(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_writing_skills_user_id ON writing_skills(user_id)")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_collab_projects_user_id ON collaborative_projects(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_collab_projects_updated_at ON collaborative_projects(updated_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_article_history_user_id ON article_history(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_article_history_created_at ON article_history(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_version_snapshots_project_id ON version_snapshots(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_version_snapshots_created_at ON version_snapshots(created_at)")

        self.conn.commit()

    def _hash_password(self, password: str) -> str:
        """密码哈希（SHA-256 + salt）"""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256(f"{password}{salt}".encode())
        return f"{salt}${hash_obj.hexdigest()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            salt, hash_str = password_hash.split("$")
            hash_obj = hashlib.sha256(f"{password}{salt}".encode())
            return hash_obj.hexdigest() == hash_str
        except:
            return False

    # ════════════════════════════════════════════════════════════
    # 用户管理
    # ════════════════════════════════════════════════════════════

    def create_user(
        self,
        username: str,
        password: str,
        email: str = "",
        role: str = "user"
    ) -> Optional[int]:
        """
        创建新用户

        Returns:
            用户 ID，失败返回 None
        """
        self._connect()
        cur = self.conn.cursor()
        try:
            password_hash = self._hash_password(password)
            cur.execute(
                "INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
                (username, password_hash, email, role)
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """通过用户名获取用户"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """通过邮箱获取用户"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """通过 ID 获取用户"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def verify_user(self, username: str, password: str) -> Optional[Dict]:
        """
        验证用户登录（用户名）

        Returns:
            用户信息（不含密码哈希），验证失败返回 None
        """
        user = self.get_user_by_username(username)
        if user and self._verify_password(password, user["password_hash"]):
            # 移除敏感信息
            user.pop("password_hash", None)
            return user
        return None

    # ════════════════════════════════════════════════════════════
    # 会话管理
    # ════════════════════════════════════════════════════════════

    def create_session(self, user_id: int) -> str:
        """
        创建会话

        Returns:
            session_id
        """
        self._connect()
        cur = self.conn.cursor()

        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=SESSION_EXPIRE_HOURS)

        cur.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_id, user_id, expires_at.isoformat())
        )
        self.conn.commit()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM sessions WHERE session_id = ? AND expires_at > CURRENT_TIMESTAMP",
            (session_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str):
        """删除会话（登出）"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()

    def cleanup_expired_sessions(self):
        """清理过期会话"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP")
        deleted = cur.rowcount
        self.conn.commit()
        return deleted

    def delete_all_user_sessions(self, user_id: int):
        """删除用户的所有会话"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def update_password(self, user_id: int, new_password: str) -> bool:
        """更新用户密码"""
        self._connect()
        cur = self.conn.cursor()
        try:
            password_hash = self._hash_password(new_password)
            cur.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (password_hash, user_id)
            )
            self.conn.commit()
            return True
        except:
            return False

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ════════════════════════════════════════════════════════════
    # 账号与写作偏好
    # ════════════════════════════════════════════════════════════


    def get_account_by_id(self, account_db_id: int) -> Optional[Dict]:
        """通过数据库 ID 获取账号"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM accounts WHERE id = ?", (account_db_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_operating_guidelines(self, user_id: int) -> str:
        """获取用户的运营规范"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("SELECT content FROM operating_guidelines WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row["content"] if row else ""


    # ════════════════════════════════════════════════════════════
    # 写作技能管理
    # ════════════════════════════════════════════════════════════

    def get_user_skills(self, user_id: int, active_only: bool = False) -> List[Dict]:
        """获取用户的写作技能列表"""
        self._connect()
        cur = self.conn.cursor()
        sql = "SELECT * FROM writing_skills WHERE user_id = ?"
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY sort_order ASC, created_at DESC"
        cur.execute(sql, (user_id,))
        return [dict(row) for row in cur.fetchall()]

    def get_skill_by_id(self, skill_id: int, user_id: int) -> Optional[Dict]:
        """获取单个技能（检查用户权限）"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM writing_skills WHERE id = ? AND user_id = ?",
            (skill_id, user_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def create_skill(self, user_id: int, name: str, prompt_content: str,
                     description: str = "", category: str = "通用") -> Optional[int]:
        """创建写作技能"""
        self._connect()
        cur = self.conn.cursor()
        try:
            cur.execute(
                """INSERT INTO writing_skills (user_id, name, description, prompt_content, category, is_active, sort_order)
                   VALUES (?, ?, ?, ?, ?, 1, 0)""",
                (user_id, name, description, prompt_content, category)
            )
            self.conn.commit()
            return cur.lastrowid
        except Exception as e:
            print(f"[create_skill] 错误：{e}")
            return None

    def update_skill(self, skill_id: int, user_id: int, name: str = None,
                     prompt_content: str = None, description: str = None,
                     category: str = None, is_active: int = None) -> bool:
        """更新写作技能"""
        self._connect()
        cur = self.conn.cursor()
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if prompt_content is not None:
            updates.append("prompt_content = ?")
            params.append(prompt_content)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        if not updates:
            return False
        updates.append("updated_at = datetime('now', 'localtime')")
        params.extend([skill_id, user_id])
        try:
            cur.execute(
                f"UPDATE writing_skills SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params
            )
            self.conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            print(f"[update_skill] 错误：{e}")
            return False

    def delete_skill(self, skill_id: int, user_id: int) -> bool:
        """删除写作技能"""
        self._connect()
        cur = self.conn.cursor()
        try:
            cur.execute(
                "DELETE FROM writing_skills WHERE id = ? AND user_id = ?",
                (skill_id, user_id)
            )
            self.conn.commit()
            return cur.rowcount > 0
        except:
            return False

    def get_articles_for_dedup(self, user_id: int, limit: int = 200) -> List[Dict]:
        """获取用户历史文章标题列表（用于写稿前去重）"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT title, file_path, created_at FROM articles
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cur.fetchall()]

    def get_account_by_account_id(self, account_id: str) -> Optional[Dict]:
        """通过 account_id（如 bigdata、car）获取账号"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,))
        row = cur.fetchone()
        return dict(row) if row else None


    def get_user_default_account(self, user_id: int) -> Optional[Dict]:
        """获取用户的默认账号"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM accounts WHERE user_id = ? AND is_default = 1 LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


    # ════════════════════════════════════════════════════════════
    # 领域分类管理
    # ════════════════════════════════════════════════════════════

    def get_user_domains(self, user_id: int) -> List[Dict]:
        """获取用户的所有领域分类"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, user_id, name, description, ref_websites, is_system, created_at, updated_at FROM domains WHERE user_id = ? OR is_system = 1 ORDER BY is_system, id",
            (user_id,)
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # 将 ref_websites JSON 字符串解析为列表
            try:
                d["ref_websites"] = json.loads(d.get("ref_websites") or "[]")
            except Exception:
                d["ref_websites"] = []
            result.append(d)
        return result

    def get_domain_by_id(self, domain_id: int, user_id: int) -> Optional[Dict]:
        """获取指定领域的详细信息"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM domains WHERE id = ? AND (user_id = ? OR is_system = 1)",
            (domain_id, user_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def create_domain(
        self,
        user_id: int,
        name: str,
        description: str = "",
        is_system: int = 0,
        ref_websites: list = None
    ) -> Optional[int]:
        """创建新领域分类"""
        self._connect()
        cur = self.conn.cursor()
        try:
            websites_json = json.dumps(ref_websites or [], ensure_ascii=False)
            cur.execute(
                "INSERT INTO domains (user_id, name, description, ref_websites, is_system) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, description, websites_json, is_system)
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            # 名称冲突
            return None
        except:
            return None

    def update_domain(
        self,
        domain_id: int,
        user_id: int,
        name: str = None,
        description: str = None,
        ref_websites: list = None
    ) -> bool:
        """更新领域分类（系统领域不可改名）"""
        self._connect()
        cur = self.conn.cursor()
        try:
            # 先检查是否为系统领域
            cur.execute("SELECT is_system FROM domains WHERE id = ?", (domain_id,))
            row = cur.fetchone()
            if not row or (row["is_system"] and name is not None):
                return False

            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if ref_websites is not None:
                updates.append("ref_websites = ?")
                params.append(json.dumps(ref_websites, ensure_ascii=False))

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.extend([domain_id, user_id])
                cur.execute(
                    f"UPDATE domains SET {', '.join(updates)} WHERE id = ? AND (user_id = ? OR is_system = 1)",
                    params
                )
                self.conn.commit()
                return cur.rowcount > 0
            return False
        except:
            return False

    def delete_domain(self, domain_id: int, user_id: int) -> bool:
        """删除领域分类（系统领域不可删除）"""
        self._connect()
        cur = self.conn.cursor()
        try:
            cur.execute(
                "DELETE FROM domains WHERE id = ? AND user_id = ? AND is_system = 0",
                (domain_id, user_id)
            )
            self.conn.commit()
            return cur.rowcount > 0
        except:
            return False

    # ════════════════════════════════════════════════════════════
    # 历史文章管理
    # ════════════════════════════════════════════════════════════

    def create_article(
        self,
        user_id: int,
        account_db_id: int,
        title: str,
        file_path: str,
        status: str = "draft",
        published_at: str = None,
        clear_published_at: bool = False
    ) -> Optional[int]:
        """
        创建或更新历史文章记录

        如果同一 file_path 的记录已存在，则更新该记录；
        否则创建新记录。

        Args:
            user_id: 用户 ID
            account_db_id: 账号数据库 ID
            title: 文章标题
            file_path: 文件路径（只存文件名）
            status: 状态（draft/published）
            published_at: 发布时间字符串
            clear_published_at: 是否清空 published_at 字段（从已发布状态转为草稿时使用）

        Returns:
            文章 ID，失败返回 None
        """
        self._connect()
        cur = self.conn.cursor()
        try:
            # 先检查是否已存在相同 file_path + account_id 的记录(不区分 user_id)
            # 原因:同一账号下同一文件应该只有一条记录,跨用户操作时应该更新而非新建
            cur.execute(
                """
                SELECT id, user_id FROM articles
                WHERE account_id = ? AND file_path = ?
                LIMIT 1
                """,
                (account_db_id, file_path)
            )
            existing = cur.fetchone()

            if existing:
                # 已存在，更新记录
                article_id = existing[0]
                print(f"[create_article] 更新现有记录: ID={article_id}, file_path={file_path}")

                # 构建更新 SQL
                update_fields = []
                update_values = []
                params = []

                if title is not None:
                    update_fields.append("title = ?")
                    params.append(title)

                if status is not None:
                    update_fields.append("status = ?")
                    params.append(status)

                # published_at 需要特殊处理
                if clear_published_at:
                    # 清空 published_at（从已发布转为草稿时）
                    update_fields.append("published_at = NULL")
                elif published_at is not None:
                    # 设置或更新 published_at
                    update_fields.append("published_at = ?")
                    params.append(published_at)
                # else: 不更新 published_at 字段

                # 更新 user_id 为当前操作的用户
                update_fields.append("user_id = ?")
                params.append(user_id)

                params.append(article_id)

                if update_fields:
                    sql = f"UPDATE articles SET {', '.join(update_fields)} WHERE id = ?"
                    cur.execute(sql, params)
                    self.conn.commit()
                else:
                    print(f"[create_article] 没有字段需要更新")

                return article_id
            else:
                # 不存在，创建新记录
                print(f"[create_article] 创建新记录: file_path={file_path}, status={status}")
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    """
                    INSERT INTO articles (
                        user_id, account_id, title, file_path, status,
                        published_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, account_db_id, title, file_path, status,
                     published_at, created_at)
                )
                self.conn.commit()
                return cur.lastrowid
        except Exception as e:
            import traceback
            print(f"[create_article] 错误：{e}")
            print(f"[create_article] 参数：user_id={user_id}, account_db_id={account_db_id}, title={title[:30] if title else 'None'}..., file_path={file_path}, status={status}")
            traceback.print_exc()
            return None

    def get_user_articles(self, user_id: int, limit: int = 100) -> List[Dict]:
        """获取用户的历史文章

        对于同一 account_id + file_path 的记录,只保留 created_at 最新的记录(去重)
        注意:不按 user_id 隔离,同一账号下同一文件只显示一次(最新的)
        """
        self._connect()
        cur = self.conn.cursor()
        # 使用 CTE 去重:先按 account_id+file_path 分组,取每组 id 最大的记录
        # 不按 user_id 隔离,同一账号下同一文件只显示一次
        cur.execute(
            """
            WITH ranked AS (
                SELECT
                    a.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY a.account_id, a.file_path
                        ORDER BY a.created_at DESC, a.id DESC
                    ) as rn
                FROM articles a
            )
            SELECT r.*, acc.name as account_name, acc.account_id as account_str_id
            FROM ranked r
            LEFT JOIN accounts acc ON r.account_id = acc.id
            WHERE r.rn = 1
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_user_articles_paginated(self, user_id: int, page: int = 1, page_size: int = 10, account_str_id: str = None, keyword: str = None) -> Dict[str, Any]:
        """获取用户的历史文章（分页版本）

        对于同一 account_id + file_path 的记录,只保留 created_at 最新的记录(去重)
        返回分页信息和文章列表

        :param account_str_id: 可选，按账号字符串 ID（如 "car"）过滤，与 accounts.account_id 匹配
        :param keyword: 可选，按标题/文件名模糊搜索
        """
        self._connect()
        cur = self.conn.cursor()

        # 构建过滤条件
        filters = []
        params_count = [user_id]

        if account_str_id:
            filters.append("AND acc2.account_id = ?")
            params_count.append(account_str_id)

        if keyword:
            filters.append("AND (a.title LIKE ? OR a.file_path LIKE ?)")
            kw_pattern = f"%{keyword}%"
            params_count.extend([kw_pattern, kw_pattern])

        account_filter = " ".join(filters)

        # 计算总数（用于分页）
        cur.execute(
            f"""
            WITH ranked AS (
                SELECT
                    a.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY a.account_id, a.file_path
                        ORDER BY a.created_at DESC, a.id DESC
                    ) as rn
                FROM articles a
                LEFT JOIN accounts acc2 ON a.account_id = acc2.id
                WHERE a.user_id = ?
                {account_filter}
            )
            SELECT COUNT(*) as total
            FROM ranked
            WHERE rn = 1
            """,
            params_count
        )
        total_row = cur.fetchone()
        if total_row:
            try:
                total = total_row["total"]
            except (KeyError, TypeError):
                total = total_row[0] if len(total_row) > 0 else 0
        else:
            total = 0
        total_pages = (total + page_size - 1) // page_size

        # 分页查询
        offset = (page - 1) * page_size
        page_params = list(params_count) + [page_size, offset]
        cur.execute(
            f"""
            WITH ranked AS (
                SELECT
                    a.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY a.account_id, a.file_path
                        ORDER BY a.created_at DESC, a.id DESC
                    ) as rn
                FROM articles a
                LEFT JOIN accounts acc2 ON a.account_id = acc2.id
                WHERE a.user_id = ?
                {account_filter}
            )
            SELECT r.*, acc.name as account_name, acc.account_id as account_str_id
            FROM ranked r
            LEFT JOIN accounts acc ON r.account_id = acc.id
            WHERE r.rn = 1
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            page_params
        )
        articles = [dict(row) for row in cur.fetchall()]

        return {
            "articles": articles,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages
            }
        }

    def get_article_by_id(self, article_id: int, user_id: int) -> Optional[Dict]:
        """通过 ID 获取文章（检查用户权限）"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT a.*, acc.name as account_name
            FROM articles a
            LEFT JOIN accounts acc ON a.account_id = acc.id
            WHERE a.id = ? AND a.user_id = ?
            """,
            (article_id, user_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_article_by_filename_and_account(self, file_path: str, account_id: int, user_id: int = None) -> Optional[Dict]:
        """通过文件名和账号ID获取文章（用于推送时更新已有记录）

        不按 user_id 隔离，因为同一账号下同一文件应该只有一条记录（create_article 的 upsert 逻辑）
        """
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT a.*, acc.name as account_name
            FROM articles a
            LEFT JOIN accounts acc ON a.account_id = acc.id
            WHERE a.file_path = ? AND a.account_id = ?
            """,
            (file_path, account_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def update_article_status(
        self,
        article_id: int,
        status: str = None,
        published_at: str = None
    ) -> bool:
        """更新文章状态"""
        self._connect()
        cur = self.conn.cursor()
        try:
            # 构建 SET 子句，只更新提供的字段
            set_clauses = []
            params = []

            if status is not None:
                set_clauses.append("status = ?")
                params.append(status)

            if published_at is not None:
                set_clauses.append("published_at = ?")
                params.append(published_at)

            params.append(article_id)

            if set_clauses:
                query = f"UPDATE articles SET {', '.join(set_clauses)} WHERE id = ?"
                cur.execute(query, params)
                self.conn.commit()
                return cur.rowcount > 0
            return False
        except Exception as e:
            print(f"[update_article_status] 错误：{e}")
            return False

    def delete_article_by_filename(self, file_path: str, user_id: int) -> bool:
        """通过文件名删除文章（检查用户权限）"""
        self._connect()
        cur = self.conn.cursor()
        try:
            cur.execute(
                "DELETE FROM articles WHERE file_path = ? AND user_id = ?",
                (file_path, user_id)
            )
            self.conn.commit()
            return cur.rowcount > 0
        except:
            return False

    def get_user_stats(self, user_id: int) -> Dict:
        """获取用户的统计数据
        
        注意:不按 user_id 隔离,统计该用户账号下的所有文章(包括跨用户更新的)
        """
        self._connect()
        cur = self.conn.cursor()

        # 先获取用户的所有账号 ID
        cur.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,))
        account_ids = [row["id"] for row in cur.fetchall()]
        
        if not account_ids:
            # 没有账号,返回零值
            return {
                "total_articles": 0,
                "draft_articles": 0,
                "published_articles": 0,
                "today_articles": 0,
                "weekly_data": [],
                "weekly_account_data": [],
                "account_stats": [],
                "keyword_top10": [],
                "account_7d_stats": [],
                "status_funnel": [],
                "status_distribution": [],
                "hourly_data": [],
                "monthly_data": [],
                "account_rank": [],
                "keyword_cloud": [],
            }

        account_ids_str = ",".join(str(aid) for aid in account_ids)
        
        # 总文章数(统计用户所有账号下的文章,不按 user_id 隔离)
        cur.execute(f"SELECT COUNT(*) FROM articles WHERE account_id IN ({account_ids_str})")
        total_articles = cur.fetchone()[0]

        # 按 status 统计（草稿/已发布）
        cur.execute(f"""
            SELECT status, COUNT(*) as count
            FROM articles
            WHERE account_id IN ({account_ids_str})
            GROUP BY status
        """)
        status_counts = {row["status"]: row["count"] for row in cur.fetchall()}

        draft_articles = status_counts.get("draft", 0)
        published_articles = status_counts.get("published", 0)

        # 今日新增
        cur.execute(f"""
            SELECT COUNT(*)
            FROM articles
            WHERE account_id IN ({account_ids_str}) AND DATE(created_at) = DATE('now')
        """)
        today_articles = cur.fetchone()[0]

        # 最近7天每天的文章数
        cur.execute(f"""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM articles
            WHERE account_id IN ({account_ids_str}) AND created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        weekly_data = [{"date": row["date"], "count": row["count"]} for row in cur.fetchall()]

        # 最近7天每天每账号的文章数（用于堆叠柱状图）
        cur.execute(f"""
            SELECT DATE(a.created_at) as date, a.account_id,
                   COALESCE(acc.name, '未知账号') as account_name, COUNT(*) as count
            FROM articles a
            LEFT JOIN accounts acc ON a.account_id = acc.id
            WHERE a.account_id IN ({account_ids_str}) AND a.created_at >= DATE('now', '-7 days')
            GROUP BY DATE(a.created_at), a.account_id
            ORDER BY date, a.account_id
        """)
        weekly_account_data = [
            {
                "date": row["date"],
                "account_id": row["account_id"],
                "account_name": row["account_name"],
                "count": row["count"]
            }
            for row in cur.fetchall()
        ]

        # 按账号统计
        cur.execute(f"""
            SELECT a.account_id, acc.name, COUNT(*) as count
            FROM articles a
            LEFT JOIN accounts acc ON a.account_id = acc.id
            WHERE a.account_id IN ({account_ids_str})
            GROUP BY a.account_id
            ORDER BY count DESC
        """)
        account_stats = [
            {"account_id": row["account_id"], "account_name": row["name"], "count": row["count"]}
            for row in cur.fetchall()
        ]

        # ── 近7天标题关键词 Top10 ──
        # 拉取近7天所有文章标题，然后在 Python 侧做分词统计
        cur.execute(f"""
            SELECT title FROM articles
            WHERE account_id IN ({account_ids_str})
              AND created_at >= DATE('now', '-7 days')
              AND title IS NOT NULL AND title != ''
        """)
        recent_titles = [row["title"] for row in cur.fetchall()]
        keyword_top10 = self._extract_title_keywords(recent_titles, topn=10)

        # ── 各账号近7天发文量 ──
        cur.execute(f"""
            SELECT a.account_id, COALESCE(acc.name, '未知账号') as account_name, COUNT(*) as count
            FROM articles a
            LEFT JOIN accounts acc ON a.account_id = acc.id
            WHERE a.account_id IN ({account_ids_str})
              AND a.created_at >= DATE('now', '-7 days')
            GROUP BY a.account_id
            ORDER BY count DESC
        """)
        account_7d_stats = [
            {"account_id": row["account_id"], "account_name": row["account_name"], "count": row["count"]}
            for row in cur.fetchall()
        ]

        # ── 文章状态统计（用于漏斗图：总计 / 草稿 / 已发布） ──
        status_funnel = [
            {"label": "文章总数", "count": total_articles},
            {"label": "草稿箱",  "count": draft_articles},
            {"label": "已发布",  "count": published_articles},
        ]

        # ── 文章状态分布（用于饼图） ──
        status_distribution = []
        for status_val, status_label in [("published", "已发布"), ("draft", "草稿"), ("failed", "失败")]:
            cnt = status_counts.get(status_val, 0)
            if cnt > 0:
                status_distribution.append({"status": status_val, "label": status_label, "count": cnt})

        # ── 发文时段统计（24小时分布，用 published_at 优先，回退 created_at） ──
        cur.execute(f"""
            SELECT
              CASE
                WHEN published_at IS NOT NULL THEN CAST(strftime('%H', published_at) AS INTEGER)
                ELSE CAST(strftime('%H', created_at) AS INTEGER)
              END as hour,
              COUNT(*) as count
            FROM articles
            WHERE account_id IN ({account_ids_str})
            GROUP BY hour
            ORDER BY hour
        """)
        hourly_data = [{"hour": row["hour"], "count": row["count"]} for row in cur.fetchall()]

        # ── 月度发文趋势（近6个月） ──
        cur.execute(f"""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
            FROM articles
            WHERE account_id IN ({account_ids_str})
              AND created_at >= DATE('now', '-6 months')
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month
        """)
        monthly_data = [{"month": row["month"], "count": row["count"]} for row in cur.fetchall()]

        # ── 账号发文排行（累计总数，用于横条图） ──
        account_rank = sorted(account_stats, key=lambda x: x["count"], reverse=True)

        # ── 近30天标题关键词词云（比 Top10 更多词汇） ──
        cur.execute(f"""
            SELECT title FROM articles
            WHERE account_id IN ({account_ids_str})
              AND created_at >= DATE('now', '-30 days')
              AND title IS NOT NULL AND title != ''
        """)
        cloud_titles = [row["title"] for row in cur.fetchall()]
        keyword_cloud = self._extract_title_keywords(cloud_titles, topn=50)

        return {
            "total_articles": total_articles,
            "draft_articles": draft_articles,
            "published_articles": published_articles,
            "today_articles": today_articles,
            "weekly_data": weekly_data,
            "weekly_account_data": weekly_account_data,
            "account_stats": account_stats,
            "keyword_top10": keyword_top10,
            "account_7d_stats": account_7d_stats,
            "status_funnel": status_funnel,
            "status_distribution": status_distribution,
            "hourly_data": hourly_data,
            "monthly_data": monthly_data,
            "account_rank": account_rank,
            "keyword_cloud": keyword_cloud,
        }

    @staticmethod
    def _extract_title_keywords(titles: list, topn: int = 10) -> list:
        """从标题列表中提取高频关键词，返回 [{"word": str, "count": int}, ...]"""
        import re
        from collections import Counter

        # 停用词表（常见无意义词）
        stop_words = {
            "的", "了", "和", "是", "在", "有", "我", "你", "他", "她", "它",
            "这", "那", "也", "都", "与", "对", "中", "为", "被", "把", "从",
            "到", "不", "上", "下", "一", "二", "三", "四", "五", "六", "七",
            "八", "九", "十", "个", "这个", "那个", "什么", "如何", "怎么",
            "可以", "已经", "还是", "但是", "因为", "所以", "虽然", "如果",
            "关于", "通过", "正在", "就是", "之后", "之前", "一个", "以及",
            "我们", "他们", "您好", "大家", "更多", "现在", "今天", "明天",
        }

        counter = Counter()

        for title in titles:
            # 尝试用 jieba 分词
            try:
                import jieba
                words = jieba.cut(title)
            except ImportError:
                # 降级：按标点/空格切分
                words = re.split('[\\s，。！？、：；""''《》【】\\[\\]()（）\\-_—]+', title)

            for word in words:
                word = word.strip()
                # 只保留2字及以上、不是纯数字、不在停用词中的词
                if len(word) >= 2 and not word.isdigit() and word not in stop_words:
                    counter[word] += 1

        return [{"word": w, "count": c} for w, c in counter.most_common(topn)]


# ════════════════════════════════════════════════════════════
# 便捷函数
# ════════════════════════════════════════════════════════════

# 全局单例（避免每次都重新建连接）
_db_instance: Optional["UserDB"] = None


def get_db() -> "UserDB":
    """获取全局 UserDB 单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = UserDB()
    return _db_instance


def get_current_user(session_id: str) -> Optional[Dict]:
    """根据 session_id 获取当前用户"""
    if not session_id:
        return None

    with UserDB() as db:
        session = db.get_session(session_id)
        if not session:
            return None

        user = db.get_user_by_id(session["user_id"])
        if user:
            user.pop("password_hash", None)
        return user


def init_system_domains(user_id=None):
    """初始化系统默认领域分类（按用户维度，惰性调用）"""
    with UserDB() as db:
        if user_id is None:
            # 启动时兼容：为所有已有用户初始化默认领域
            users = db.conn.execute("SELECT id FROM users").fetchall()
            for (uid,) in users:
                _ensure_default_domains(db, uid)
        else:
            _ensure_default_domains(db, user_id)


def _ensure_default_domains(db, user_id: int):
    """为指定用户确保存在系统默认领域（含预置参考网站）"""
    existing = db.get_user_domains(user_id)
    if not existing:
        # 从 domains_config.json 读取预置网站
        config_path = Path(__file__).parent.parent / "domains_config.json"
        domains_json = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                domains_json = json.load(f).get("domains", {})
        except Exception:
            pass

        system_domains = [
            ("科技", "科技互联网相关内容"),
            ("财经", "金融理财、商业分析相关内容"),
            ("教育", "教育培训、知识分享相关内容"),
            ("生活", "日常生活、健康养生相关内容"),
            ("娱乐", "影视娱乐、明星八卦相关内容"),
            ("汽车", "汽车评测、新能源车相关内容"),
            ("房产", "房地产、家居装修相关内容"),
            ("旅游", "旅游攻略、酒店民宿相关内容"),
            ("美食", "美食探店、菜谱教程相关内容"),
            ("体育", "体育赛事、健身运动相关内容"),
        ]
        for name, desc in system_domains:
            # 从配置中获取预置的 ref_websites
            ref_sites = []
            if name in domains_json:
                cfg = domains_json[name]
                # 合并 ref_websites + rss_sources + html_sources
                ref_sites = cfg.get("ref_websites", [])
                for src in cfg.get("rss_sources", []):
                    if {"name": src.get("name"), "url": src.get("url")} not in ref_sites:
                        ref_sites.append({"name": src.get("name"), "url": src.get("url")})
                for src in cfg.get("html_sources", []):
                    if {"name": src.get("name"), "url": src.get("url")} not in ref_sites:
                        ref_sites.append({"name": src.get("name"), "url": src.get("url")})
            db.create_domain(user_id=user_id, name=name, description=desc, ref_websites=ref_sites, is_system=1)
        print(f"[db] 为用户 {user_id} 初始化 {len(system_domains)} 个系统默认领域分类（含预置网站）")


def init_system_ai_models():
    """初始化系统默认AI模型（如果用户没有配置任何模型）"""
    with UserDB() as db:
        # 检查是否已有AI模型配置
        all_models = db.get_user_ai_models(1)
        if not all_models:
            print(f"[db] 用户未配置AI模型，跳过初始化")
            return

        # 确保至少有一个默认模型
        default_model = db.get_user_default_ai_model(1)
        if not default_model:
            # 将第一个模型设为默认
            first_model = all_models[0]
            db.set_default_ai_model(1, first_model["id"])
            print(f"[db] 将第一个模型设为默认：{first_model['name']}")


# ════════════════════════════════════════════════════════════
# AI 模型管理方法（追加到 UserDB 类）
# ════════════════════════════════════════════════════════════

def add_ai_model_methods():
    """动态添加AI模型管理方法到UserDB类"""
    from typing import Optional, Dict, List

    # 创建AI模型
    def create_ai_model(self,
        user_id: int,
        name: str,
        provider: str,
        model_name: str,
        api_key: str,
        api_base: str = "",
        is_default: bool = False,
        is_image_model: bool = False
    ) -> Optional[int]:
        """
        创建AI大模型配置

        Args:
            user_id: 用户ID
            name: 模型名称（用户自定义）
            provider: 提供商（如：openai, anthropic, ollama）
            model_name: 模型名称（如：gpt-4, claude-3-opus）
            api_key: API密钥
            api_base: API基础URL（可选）
            is_default: 是否设为默认模型
            is_image_model: 是否为图像生成模型

        Returns:
            模型ID，失败返回None
        """
        self._connect()
        cur = self.conn.cursor()
        try:
            # 如果设置为默认模型，先取消该用户的其他默认模型
            if is_default:
                cur.execute(
                    "UPDATE ai_models SET is_default = 0 WHERE user_id = ?",
                    (user_id,)
                )

            cur.execute(
                """
                INSERT INTO ai_models (
                    user_id, name, provider, model_name, api_key, api_base, is_default, is_image_model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, name, provider, model_name, api_key, api_base,
                 1 if is_default else 0, 1 if is_image_model else 0)
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    # 获取用户所有AI模型
    def get_user_ai_models(self, user_id: int) -> List[Dict]:
        """获取用户的所有AI模型"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM ai_models WHERE user_id = ? ORDER BY is_default DESC, created_at DESC",
            (user_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    # 获取默认AI模型
    def get_user_default_ai_model(self, user_id: int) -> Optional[Dict]:
        """获取用户的默认AI模型"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM ai_models WHERE user_id = ? AND is_default = 1 LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # 获取默认图像模型
    def get_user_default_image_model(self, user_id: int) -> Optional[Dict]:
        """获取用户的默认图像生成模型"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM ai_models WHERE user_id = ? AND is_image_model = 1 ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # 获取指定AI模型
    def get_ai_model_by_id(self, model_id: int, user_id: int) -> Optional[Dict]:
        """通过ID获取AI模型（检查用户权限）"""
        self._connect()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM ai_models WHERE id = ? AND user_id = ?",
            (model_id, user_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # 更新AI模型
    def update_ai_model(self,
        model_id: int,
        user_id: int,
        name: str = None,
        provider: str = None,
        model_name: str = None,
        api_key: str = None,
        api_base: str = None,
        is_image_model: bool = None
    ) -> bool:
        """更新AI模型信息"""
        self._connect()
        cur = self.conn.cursor()

        fields = []
        values = []

        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if provider is not None:
            fields.append("provider = ?")
            values.append(provider)
        if model_name is not None:
            fields.append("model_name = ?")
            values.append(model_name)
        if api_key is not None:
            fields.append("api_key = ?")
            values.append(api_key)
        if api_base is not None:
            fields.append("api_base = ?")
            values.append(api_base)
        if is_image_model is not None:
            fields.append("is_image_model = ?")
            values.append(1 if is_image_model else 0)

        if not fields:
            return False

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([model_id, user_id])

        try:
            cur.execute(
                f"UPDATE ai_models SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                values
            )
            self.conn.commit()
            return cur.rowcount > 0
        except:
            return False

    # 设置默认AI模型
    def set_default_ai_model(self, user_id: int, model_id: int) -> bool:
        """设置默认AI模型"""
        self._connect()
        cur = self.conn.cursor()
        try:
            cur.execute("UPDATE ai_models SET is_default = 0 WHERE user_id = ?", (user_id,))
            cur.execute(
                "UPDATE ai_models SET is_default = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (model_id, user_id)
            )
            self.conn.commit()
            return cur.rowcount > 0
        except:
            return False

    # 删除AI模型
    def delete_ai_model(self, model_id: int, user_id: int) -> bool:
        """删除AI模型（检查用户权限）"""
        self._connect()
        cur = self.conn.cursor()
        try:
            cur.execute(
                "DELETE FROM ai_models WHERE id = ? AND user_id = ?",
                (model_id, user_id)
            )
            self.conn.commit()
            return cur.rowcount > 0
        except:
            return False

    # 将方法添加到UserDB类
    UserDB.create_ai_model = create_ai_model
    UserDB.get_user_ai_models = get_user_ai_models
    UserDB.get_user_default_ai_model = get_user_default_ai_model
    UserDB.get_user_default_image_model = get_user_default_image_model
    UserDB.get_ai_model_by_id = get_ai_model_by_id
    UserDB.update_ai_model = update_ai_model
    UserDB.set_default_ai_model = set_default_ai_model
    UserDB.delete_ai_model = delete_ai_model

# 执行方法注入
add_ai_model_methods()
