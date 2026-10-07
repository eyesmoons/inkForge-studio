"""
web_app.py
微信公众号自动化发布系统 — Web 可视化管理界面（Flask 后端）

启动方式：
  python web_app.py
  # 然后在浏览器打开 http://localhost:5678
"""

import os
import sys
import re
import json
import queue
import threading
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import requests

from flask import (
    Flask, request, jsonify, Response,
    send_from_directory, send_file, session, redirect,
)

# ── 项目根目录 ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, static_folder=str(BASE_DIR / "web_static"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# ── 导入用户数据库模块 ─────────────────────────────────────────
from modules.user_db import UserDB, get_current_user, get_db
from modules.coze_client import (
    CozeAPIError,
    CozeWorkflowClient,
    load_coze_config,
    save_coze_config,
)
from modules.wx_publisher import WeChatPublisher


# ── 全局日志队列（SSE 用） ────────────────────────────────────
_log_queues: Dict[str, queue.Queue] = {}

# ── 定时任务调度器 ────────────────────────────────────────────
_SCHEDULE_FILE = BASE_DIR / "schedule_config.json"
_scheduler = None          # APScheduler BackgroundScheduler 实例
_schedule_log: List[dict] = []   # 内存运行日志（最多 50 条）
_schedule_lock = threading.Lock()
_task_run_lock = threading.Lock()  # 任务执行互斥锁：防止多个任务并发修改全局 sys.stdout


def load_schedule_config() -> dict:
    """加载定时任务配置"""
    if _SCHEDULE_FILE.exists():
        try:
            with open(_SCHEDULE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": False,
        "hour": 8,
        "minute": 0,
        "draft_only": True,   # True=仅推草稿，False=直接发布
    }


def save_schedule_config(cfg: dict):
    with open(_SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _add_schedule_log(status: str, msg: str, detail: str = "", account_id: int = None, account_name: str = None):
    """向内存日志追加一条记录（最多保留 50 条）"""
    with _schedule_lock:
        log_entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,   # "running" / "success" / "error"
            "msg": msg,
            "detail": detail,
            "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 兼容前端字段名
        }
        if account_id is not None:
            log_entry["account_id"] = account_id
        if account_name is not None:
            log_entry["account_name"] = account_name
        _schedule_log.insert(0, log_entry)
        if len(_schedule_log) > 50:
            _schedule_log.pop()


def _run_scheduled_task():
    """定时任务实际执行逻辑：选题 → 写稿 → 推草稿箱"""
    _add_schedule_log("running", "⏰ 定时任务开始执行")
    print(f"\n[Scheduler] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 定时任务触发")
    try:
        import main as m
        cfg = m.load_config()

        scfg = load_schedule_config()
        draft_only = scfg.get("draft_only", True)
        account_id = scfg.get("account_id", "")  # 获取定时任务选择的账号

        # 根据账号获取配置
        acc_cfg = get_account_config(account_id)

        # 使用账号配置构建 prompt_cfg（search_queries 已废弃）
        prompt_cfg = {
            "topic_prompt": acc_cfg.get("topic_prompt", ""),
            "search_queries": [],  # 固定传空数组，使用 AI 生成
            "article_style": acc_cfg.get("article_style", "观点评论"),
            "word_count": acc_cfg.get("word_count", 2000),
            "theme": acc_cfg.get("theme", "blue"),
            "writing_prompt": acc_cfg.get("writing_prompt", ""),
        }

        # 获取 admin 用户 ID（定时任务以 admin 身份运行）
        admin_user_id = 1
        try:
            with UserDB() as db_admin:
                cur_admin = db_admin.conn.cursor()
                cur_admin.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
                admin_row = cur_admin.fetchone()
                if admin_row:
                    admin_user_id = admin_row[0]
        except Exception:
            pass

        result = m.run_auto_pipeline(
            config=cfg,
            prompt_cfg=prompt_cfg,
            draft_only=draft_only,
            topic_index=None,
            style_override=prompt_cfg.get("article_style", ""),
            words_override=prompt_cfg.get("word_count", 0),
            theme_override=prompt_cfg.get("theme") or "blue",
            cache_hours=0,
            custom_writing_prompt=prompt_cfg.get("writing_prompt", ""),
            account_db_id=acc_cfg.get("id", 0),  # 传入数据库整数 ID，确保状态能更新
            user_id=admin_user_id,
        )

        title = result.get("title") or result.get("topic", {}).get("title", "未知标题")
        account_name = acc_cfg.get("name", "未知账号")
        msg = f"✅ 定时任务完成：《{title}》已推送到草稿箱（账号：{account_name}）"
        _add_schedule_log("success", msg, json.dumps(result, ensure_ascii=False)[:500])
        print(f"[Scheduler] {msg}")
    except Exception as e:
        err = traceback.format_exc()
        _add_schedule_log("error", f"❌ 定时任务失败：{e}", err)
        print(f"[Scheduler] ❌ 出错：{err}")


def _apply_user_schedule(user_id: int, task: dict):
    """根据用户任务配置启用/停用调度器"""
    global _scheduler
    if _scheduler is None:
        return

    # 使用任务 ID 作为 job_id，确保每个任务有独立的调度
    task_id = task.get("id")
    job_id = f"user_{user_id}_task_{task_id}"

    # 移除旧 job
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass

    if task.get("enabled"):
        hour = task["hour"]
        minute = task["minute"]
        draft_only = task["draft_only"]
        account_id = task.get("account_str_id")  # 字符串 ID，如 "car"
        account_db_id = task.get("account_id")  # 整数 ID，关联 accounts.id
        task_db_id = task.get("id")  # 任务数据库ID
        execution_mode = task.get("execution_mode", "serial")  # 执行模式：serial（串行）或 parallel（并行）

        print(f"[Scheduler] 添加定时任务：用户 {user_id}, 时间 {hour:02d}:{minute:02d}, 账号 {account_id} (ID: {account_db_id}), 草稿={draft_only}, 模式={execution_mode}")

        def run_user_task():
            """执行用户的定时任务"""
            from datetime import datetime
            from io import StringIO
            import sys

            # 创建执行记录
            run_id = None
            try:
                with UserDB() as db:
                    run_id = db.create_task_run(
                        task_id=task_db_id,
                        user_id=user_id,
                        account_id=account_db_id,  # 使用整数 ID，关联 accounts.id
                        status="running"
                    )
            except Exception as e:
                print(f"[Scheduler] 创建执行记录失败：{e}")
                run_id = None

            # 获取账号名称
            account_name = None
            with UserDB() as db:
                account = db.get_account_by_id(account_db_id)  # 使用整数 ID
                if account:
                    account_name = account["name"]

            _add_schedule_log("running", f"定时任务开始执行", account_id=account_id, account_name=account_name)
            print(f"\n[Scheduler User {user_id}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 定时任务触发")

            # 捕获完整执行日志
            log_buffer = StringIO()
            original_stdout = sys.stdout

            article_id = None

            # 定义执行逻辑的函数（串行和并行共用）
            def execute_pipeline():
                """执行自动化流程的核心逻辑"""
                sys.stdout = log_buffer
                sys.stderr = log_buffer

                # 在缓冲区中输出关键信息（这些会被保存到数据库）
                print(f"[Scheduler User {user_id}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始执行自动化流程")
                print(f"[Scheduler User {user_id}] 账号 ID: {account_id}, 仅草稿: {draft_only}, 执行模式: {execution_mode}")

                import main as m
                cfg = m.load_config()

                # 根据账号获取配置
                acc_cfg = get_account_config(account_id)

                # 使用账号配置构建 prompt_cfg
                prompt_cfg = {
                    "topic_prompt": acc_cfg.get("topic_prompt", ""),
                    "search_queries": [],
                    "article_style": acc_cfg.get("article_style", "观点评论"),
                    "word_count": acc_cfg.get("word_count", 2000),
                    "theme": acc_cfg.get("theme", "blue"),
                    "writing_prompt": acc_cfg.get("writing_prompt", ""),
                }

                print(f"[Scheduler User {user_id}] 开始调用 run_auto_pipeline (draft_only={draft_only})...", file=original_stdout, flush=True)

                result = m.run_auto_pipeline(
                    config=cfg,
                    prompt_cfg=prompt_cfg,
                    account_db_id=acc_cfg.get("id", 0),  # 使用数据库整数 ID，而非字符串 account_id
                    user_id=user_id,
                    draft_only=draft_only,
                    theme_override=acc_cfg.get("theme", "blue"),
                    cache_hours=0,
                )

                print(f"[Scheduler User {user_id}] run_auto_pipeline 返回结果: success={result.get('success')}", file=original_stdout, flush=True)

                # 获取文章ID（如果保存到了数据库）
                article_id = result.get("article_id")

                # 恢复 stdout
                sys.stdout = original_stdout
                sys.stderr = original_stdout  # 恢复 stderr

                return result

            # 根据执行模式决定是否使用锁
            # serial（串行）：使用锁，多个任务依次执行
            # parallel（并行）：不使用锁，多个任务可同时执行（可能有日志混乱风险）
            use_lock = (execution_mode == "serial")

            if use_lock:
                print(f"[Scheduler User {user_id}] 等待执行锁（串行模式）...")
                with _task_run_lock:
                    print(f"[Scheduler User {user_id}] 已获得执行锁，开始执行")
                    try:
                        result = execute_pipeline()

                        print(f"[Scheduler User {user_id}] ✅ 执行完成，文章 ID: {article_id}")
                        _add_schedule_log("success", f"定时任务完成", account_id=account_id, account_name=account_name)

                        # 更新执行记录为成功
                        if run_id:
                            try:
                                with UserDB() as db:
                                    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    db.update_task_run(
                                        run_id=run_id,
                                        status="success",
                                        result=json.dumps(result, ensure_ascii=False),
                                        article_id=article_id,
                                        finished_at=finished_at,
                                        run_log=log_buffer.getvalue()[:10000]
                                    )
                            except Exception as e:
                                print(f"[Scheduler] 更新执行记录失败：{e}")

                    except Exception as e:
                        # 恢复 stdout（防止异常时未恢复）
                        sys.stdout = original_stdout
                        sys.stderr = original_stdout

                        err = traceback.format_exc()
                        _add_schedule_log("error", f"定时任务失败", detail=str(e), account_id=account_id, account_name=account_name)
                        print(f"[Scheduler User {user_id}] ❌ 执行失败：{err}")

                        # 打印已捕获的日志（如果有）
                        captured_log = log_buffer.getvalue()
                        if captured_log:
                            print(f"[Scheduler User {user_id}] 已捕获的日志：\n{captured_log[:500]}")

                        # 更新执行记录为失败
                        if run_id:
                            try:
                                with UserDB() as db:
                                    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    db.update_task_run(
                                        run_id=run_id,
                                        status="error",
                                        error_message=str(e)[:1000],
                                        finished_at=finished_at,
                                        run_log=log_buffer.getvalue()[:10000]
                                    )
                            except Exception as e2:
                                print(f"[Scheduler] 更新执行记录失败：{e2}")
            else:
                # 并行模式：直接执行，不使用锁
                print(f"[Scheduler User {user_id}] 开始执行（并行模式）")
                try:
                    result = execute_pipeline()

                    print(f"[Scheduler User {user_id}] ✅ 执行完成，文章 ID: {article_id}")
                    _add_schedule_log("success", f"定时任务完成", account_id=account_id, account_name=account_name)

                    # 更新执行记录为成功
                    if run_id:
                        try:
                            with UserDB() as db:
                                finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                db.update_task_run(
                                    run_id=run_id,
                                    status="success",
                                    result=json.dumps(result, ensure_ascii=False),
                                    article_id=article_id,
                                    finished_at=finished_at,
                                    run_log=log_buffer.getvalue()[:10000]
                                )
                        except Exception as e:
                            print(f"[Scheduler] 更新执行记录失败：{e}")

                except Exception as e:
                    # 恢复 stdout（防止异常时未恢复）
                    sys.stdout = original_stdout
                    sys.stderr = original_stdout

                    err = traceback.format_exc()
                    _add_schedule_log("error", f"定时任务失败", detail=str(e), account_id=account_id, account_name=account_name)
                    print(f"[Scheduler User {user_id}] ❌ 执行失败：{err}")

                    # 打印已捕获的日志（如果有）
                    captured_log = log_buffer.getvalue()
                    if captured_log:
                        print(f"[Scheduler User {user_id}] 已捕获的日志：\n{captured_log[:500]}")

                    # 更新执行记录为失败
                    if run_id:
                        try:
                            with UserDB() as db:
                                finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                db.update_task_run(
                                    run_id=run_id,
                                    status="error",
                                    error_message=str(e)[:1000],
                                    finished_at=finished_at,
                                    run_log=log_buffer.getvalue()[:10000]
                                )
                        except Exception as e2:
                            print(f"[Scheduler] 更新执行记录失败：{e2}")

                    # 更新执行记录为失败
                    if run_id:
                        try:
                            with UserDB() as db:
                                # 使用与 started_at 相同的时间格式（SQLite TIMESTAMP）
                                finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                db.update_task_run(
                                    run_id=run_id,
                                    status="error",
                                    error_message=str(e)[:1000],  # 限制错误信息长度
                                    finished_at=finished_at,
                                    run_log=log_buffer.getvalue()[:10000]  # 保存已执行的日志
                                )
                        except Exception as e2:
                            print(f"[Scheduler] 更新执行记录失败：{e2}")


        _scheduler.add_job(
            run_user_task,
            trigger="cron",
            hour=hour,
            minute=minute,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=600,
        )
        
        # 获取刚添加的 job 信息
        try:
            job = _scheduler.get_job(job_id)
            print(f"[Scheduler] 用户 {user_id} ✅ 定时任务已启用，每天 {hour:02d}:{minute:02d} 执行")
            print(f"[Scheduler]   Job ID: {job_id}, 下次执行: {job.next_run_time}")
        except Exception as e:
            print(f"[Scheduler] 用户 {user_id} ⚠️  定时任务已启用，但获取 job 信息失败：{e}")
    else:
        print(f"[Scheduler] 用户 {user_id} 定时任务已停用（enabled={task.get('enabled')}）")


def _apply_all_user_schedules():
    """重新加载所有用户的定时任务"""
    global _scheduler
    if _scheduler is None:
        return

    # 清理所有现有 job
    existing_jobs = _scheduler.get_jobs()
    for job in existing_jobs:
        try:
            _scheduler.remove_job(job.id)
            print(f"[Scheduler] 清理 job: {job.id}")
        except Exception as e:
            print(f"[Scheduler] 清理 job {job.id} 失败：{e}")

    # 从数据库重新加载所有启用任务
    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute("""
            SELECT t.*, acc.account_id as account_str_id
            FROM scheduled_tasks t
            LEFT JOIN accounts acc ON t.account_id = acc.id
            WHERE t.enabled = 1
        """)
        tasks = [dict(row) for row in cur.fetchall()]

        for task in tasks:
            _apply_user_schedule(task["user_id"], task)

    print(f"[Scheduler] 已重新加载 {len(tasks)} 个定时任务")


def _init_scheduler():
    """初始化并启动调度器，并加载所有用户的定时任务"""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        print(f"[Scheduler] 开始初始化 APScheduler...")
        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _scheduler.start()
        print(f"[Scheduler] APScheduler 已启动，timezone=Asia/Shanghai")

        # 先清理所有旧 job（避免重启后残留旧版任务重复执行）
        existing_jobs = _scheduler.get_jobs()
        for job in existing_jobs:
            try:
                _scheduler.remove_job(job.id)
                print(f"[Scheduler] 清理旧 job: {job.id}")
            except Exception as e:
                print(f"[Scheduler] 清理 job {job.id} 失败：{e}")

        # 从数据库加载所有用户的定时任务
        print(f"[Scheduler] 开始从数据库加载定时任务...")
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute("""
                SELECT t.*, acc.account_id as account_str_id
                FROM scheduled_tasks t
                LEFT JOIN accounts acc ON t.account_id = acc.id
                WHERE t.enabled = 1
            """)
            tasks = [dict(row) for row in cur.fetchall()]

            print(f"[Scheduler] 查询到 {len(tasks)} 个启用状态的定时任务")
            for task in tasks:
                print(f"[Scheduler]   - 用户 {task['user_id']}, 任务 ID {task['id']}, 时间 {task['hour']:02d}:{task['minute']:02d}")
                _apply_user_schedule(task["user_id"], task)

        print(f"[Scheduler] APScheduler 启动成功，已加载 {len(tasks)} 个定时任务")
        
        # 打印当前调度器中的所有 job
        jobs = _scheduler.get_jobs()
        print(f"[Scheduler] 当前调度器中的任务列表：")
        for job in jobs:
            print(f"[Scheduler]   - Job ID: {job.id}, 下次执行: {job.next_run_time}")
            
    except Exception as e:
        import traceback
        print(f"[Scheduler] ❌ 启动失败：{e}")
        print(f"[Scheduler] 错误详情：\n{traceback.format_exc()}")


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def load_config() -> dict:
    """加载 AI 配置（config.json）"""
    p = BASE_DIR / "config.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    """保存 config.json（仅用于 AI 配置，废弃后删除）"""
    p = BASE_DIR / "config.json"
    # 保留注释字段
    old = {}
    if p.exists():
        with open(p, encoding="utf-8") as f:
            old = json.load(f)
    old.update(data)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=2)


# ========== 公众号账号管理（新） ==========
_ACCOUNTS_FILE = BASE_DIR / "accounts.json"


def get_account_config(account_id: str = None, user_id: Optional[int] = None, allow_fallback: bool = True) -> dict:
    """
    获取指定账号的完整配置（含身份 + 写作偏好）

    Args:
        account_id: 账号 ID（字符串），如 "bigdata", "tech_blog"
        user_id: 用户 ID，None 表示使用当前登录用户或 admin
        allow_fallback: 是否允许在子线程中使用 admin 用户作为兜底（子线程没有 request context）

    Returns:
        账号配置字典，含 name/app_id/app_secret/author/topic_prompt/article_style/word_count/theme/writing_prompt
        如果账号不存在，返回空字典
    """
    import os
    from modules.user_db import UserDB

    # 优先从环境变量读取
    app_id = os.environ.get("WX_APP_ID", "")
    app_secret = os.environ.get("WX_APP_SECRET", "")

    # 如果没有指定 user_id，从 session 获取（仅在主线程中）
    if user_id is None and allow_fallback:
        try:
            session_id = _get_session_id()
            current_user = get_current_user(session_id)
            user_id = current_user["id"] if current_user else None
        except RuntimeError:
            # 子线程中没有 request context，使用 admin 作为兜底
            user_id = None

    with UserDB() as db:
        # 如果指定了 account_id，通过它查找账号
        if account_id:
            account = db.get_account_by_account_id(account_id)
        # 否则获取用户的默认账号
        elif user_id:
            account = db.get_user_default_account(user_id)
        elif allow_fallback:
            # 兜底：查找 admin 的默认账号
            cur = db.conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
            admin = cur.fetchone()
            if admin:
                account = db.get_user_default_account(admin[0])
            else:
                account = None
        else:
            account = None

        # 找到账号配置
        if account:
            account_dict = dict(account)
            # 环境变量优先
            if app_id and app_secret:
                account_dict["app_id"] = app_id
                account_dict["app_secret"] = app_secret
            return account_dict

    # 没有找到账号配置，返回环境变量（如果有）
    if app_id and app_secret:
        return {
            "app_id": app_id,
            "app_secret": app_secret,
            "author": "",
        }

    return {}


def push_log(task_id: str, msg: str, level: str = "info"):
    """往 SSE 队列里推一条日志"""
    if task_id in _log_queues:
        _log_queues[task_id].put({"msg": msg, "level": level})


class QueueLogger:
    """重定向 print 到 SSE 队列"""
    def __init__(self, task_id: str, orig_stdout):
        self.task_id = task_id
        self.orig = orig_stdout

    def write(self, text: str):
        # Windows 控制台 GBK 编码不支持 emoji，安全回退
        try:
            self.orig.write(text)
            self.orig.flush()
        except (UnicodeEncodeError, UnicodeDecodeError):
            self.orig.write(text.encode('gbk', errors='replace').decode('gbk'))
            self.orig.flush()
        text = text.strip()
        if text:
            push_log(self.task_id, text)

    def flush(self):
        self.orig.flush()


# ════════════════════════════════════════════════════════════
# API：用户认证
# ════════════════════════════════════════════════════════════

def _get_session_id():
    """从请求中获取 session_id"""
    # 优先从 Header 读取（跨域支持）
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        # 从 Cookie 读取
        session_id = request.cookies.get("session_id")
    return session_id


@app.route("/api/user/current", methods=["GET"])
def api_get_current_user():
    """获取当前登录用户信息"""
    session_id = _get_session_id()
    user = get_current_user(session_id)

    if not user:
        return jsonify({"error": "未登录"}), 401

    # 移除敏感信息
    user.pop("password_hash", None)
    return jsonify({"success": True, "user": user})


@app.route("/api/user/change_password", methods=["POST"])
def api_change_password():
    """修改密码"""
    session_id = _get_session_id()
    user = get_current_user(session_id)

    if not user:
        return jsonify({"error": "未登录"}), 401

    data = request.get_json()
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if not old_password or not new_password:
        return jsonify({"error": "请填写完整密码信息"}), 400

    if len(new_password) < 6:
        return jsonify({"error": "新密码至少需要 6 位"}), 400

    with UserDB() as db:
        # 验证旧密码
        if not db.verify_user(user["username"], old_password):
            return jsonify({"error": "当前密码不正确"}), 400

        # 更新密码
        success = db.update_password(user["id"], new_password)
        if not success:
            return jsonify({"error": "密码修改失败"}), 500

        # 删除所有会话，强制重新登录
        db.delete_all_user_sessions(user["id"])

    return jsonify({"success": True})


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    """用户注册"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()

    # 参数校验
    if not username or len(username) < 3:
        return jsonify({"error": "用户名至少 3 个字符"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "密码至少 6 个字符"}), 400

    with UserDB() as db:
        user_id = db.create_user(username, password, email)
        if not user_id:
            return jsonify({"error": "用户名已存在"}), 400

        # 自动登录（创建会话）
        session_id = db.create_session(user_id)

        # 返回用户信息（不含密码哈希）
        user = db.get_user_by_id(user_id)
        user.pop("password_hash", None)

        response = jsonify({
            "success": True,
            "user": user,
            "session_id": session_id,
        })

        # 设置 Cookie
        response.set_cookie(
            "session_id",
            session_id,
            max_age=24 * 3600,  # 24 小时
            httponly=True,
            samesite="Lax"
        )
        return response


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """用户登录（用户名密码）"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    with UserDB() as db:
        user = db.verify_user(username, password)
        if not user:
            return jsonify({"error": "用户名或密码错误"}), 401

        # 创建会话
        session_id = db.create_session(user["id"])

        response = jsonify({
            "success": True,
            "user": user,
            "session_id": session_id,
        })

        # 设置 Cookie
        response.set_cookie(
            "session_id",
            session_id,
            max_age=24 * 3600,
            httponly=True,
            samesite="Lax"
        )
        return response


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """用户登出"""
    session_id = _get_session_id()
    if session_id:
        with UserDB() as db:
            db.delete_session(session_id)

    response = jsonify({"success": True, "redirect": "/login.html"})
    response.delete_cookie("session_id")
    return response


# ════════════════════════════════════════════════════════════
# 静态首页
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """首页，重定向到工作台"""
    return redirect("/dashboard.html")


@app.route("/login.html")
def login_page():
    """登录页面"""
    return send_from_directory(str(BASE_DIR / "web_static"), "login.html")


# ════════════════════════════════════════════════════════════
# 前端路由：独立页面
# ════════════════════════════════════════════════════════════

@app.route("/common.css")
def common_css():
    """提供 common.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "common.css")

@app.route("/common.js")
def common_js():
    """提供 common.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "common.js")

@app.route("/dashboard.html")
def dashboard():
    """工作台页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "dashboard.html")

@app.route("/topics.html")
def topics():
    """自动选题页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "topics.html")

@app.route("/write.html")
def write():
    """写稿&预览页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "write.html")

@app.route("/import.html")
def import_page():
    """一键排版页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "import.html")

@app.route("/rewrite.html")
def rewrite_page():
    """链接改写页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "rewrite.html")

@app.route("/history.html")
def history():
    """历史文章页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "history.html")

@app.route("/schedule.html")
def schedule():
    """定时任务页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "schedule.html")

@app.route("/config.html")
def config():
    """系统配置页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "config.html")

@app.route("/skill.html")
def skill_page():
    """写作技能管理页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "skill.html")

@app.route("/profile.html")
def profile():
    """个人中心页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "profile.html")

@app.route("/agent.html")
def agent_page():
    """智能体页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "agent.html")


@app.route("/agent.css")
def agent_css():
    """提供 agent.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "agent.css")


@app.route("/agent.js")
def agent_js():
    """提供 agent.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "agent.js")



@app.route("/hotrank.html")
def hotrank_page():
    """每日热搜榜页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "hotrank.html")

@app.route("/viral.html")
def viral_page():
    """爆款分析页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "viral.html")

@app.route("/hotrank.js")
def hotrank_js():
    """提供 hotrank.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "hotrank.js")

@app.route("/hotrank.css")
def hotrank_css():
    """提供 hotrank.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "hotrank.css")


# ════════════════════════════════════════════════════════════
# 历史上的今天页面路由
# ════════════════════════════════════════════════════════════

@app.route("/today_in_history.html")
def today_in_history_page():
    """历史上的今天页面"""
    session_id = _get_session_id()
    if not session_id or not get_current_user(session_id):
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "today_in_history.html")


@app.route("/today_in_history.js")
def today_in_history_js():
    """提供 today_in_history.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "today_in_history.js")


@app.route("/today_in_history.css")
def today_in_history_css():
    """提供 today_in_history.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "today_in_history.css")


# ════════════════════════════════════════════════════════════
# 封面制作页面路由
# ════════════════════════════════════════════════════════════

@app.route("/cover_maker.html")
def cover_maker_page():
    """封面制作页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "cover_maker.html")


@app.route("/cover_maker.js")
def cover_maker_js():
    """提供 cover_maker.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "cover_maker.js")


@app.route("/cover_maker.css")
def cover_maker_css():
    """提供 cover_maker.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "cover_maker.css")


# ════════════════════════════════════════════════════════════
# 素材库页面路由
# ════════════════════════════════════════════════════════════

@app.route("/material_library.html")
def material_library_page():
    """素材库页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "material_library.html")


@app.route("/material_library.js")
def material_library_js():
    """提供 material_library.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "material_library.js")


@app.route("/material_library.css")
def material_library_css():
    """提供 material_library.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "material_library.css")

@app.route("/document_rewrite.html")
def document_rewrite_page():
    """文档改写页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "document_rewrite.html")


@app.route("/document_rewrite.js")
def document_rewrite_js():
    """提供 document_rewrite.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "document_rewrite.js")


# ════════════════════════════════════════════════════════════
# AI 助手 API 路由（抽屉式面板，无独立页面）
# ════════════════════════════════════════════════════════════

@app.route("/web_static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(BASE_DIR / "web_static"), filename)


# ════════════════════════════════════════════════════════════
# API：配置管理
# ════════════════════════════════════════════════════════════

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取 AI 配置"""
    cfg = load_config()

    # 脱敏：只返回 key 末尾 8 位
    key = cfg.get("ai_api_key", "")
    masked_key = ("*" * (len(key) - 8) + key[-8:]) if len(key) > 8 else ("*" * len(key))

    return jsonify({
        "ai_api_key":  masked_key,
        "ai_api_base": cfg.get("ai_api_base", "https://api.deepseek.com"),
        "ai_model":    cfg.get("ai_model", "deepseek-chat"),
    })


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """保存 AI 配置"""
    data = request.json or {}

    main_fields = ["ai_api_base", "ai_model"]
    main_update = {k: data[k] for k in main_fields if k in data}

    # 只有新 key 非空且不是掩码才更新
    if data.get("ai_api_key") and not data["ai_api_key"].startswith("*"):
        main_update["ai_api_key"] = data["ai_api_key"]

    if main_update:
        save_config(main_update)

    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
# API：Coze 工作流配置
# ════════════════════════════════════════════════════════════

@app.route("/api/coze_config", methods=["GET"])
def api_get_coze_config():
    """获取 Coze 配置（不返回明文 api_token）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    cfg = load_coze_config()
    return jsonify({
        "workflow_id": cfg.get("workflow_id", ""),
        "api_token_set": bool(cfg.get("api_token")),
    })


@app.route("/api/coze_config", methods=["PUT"])
def api_save_coze_config():
    """保存 Coze 配置"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    workflow_id = (data.get("workflow_id") or "").strip()
    api_token = (data.get("api_token") or "").strip()

    if not workflow_id:
        return jsonify({"error": "Workflow ID 不能为空"}), 400

    save_coze_config({"workflow_id": workflow_id, "api_token": api_token})
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
# API：公众号运营规范
# ════════════════════════════════════════════════════════════

@app.route("/api/operating_guidelines", methods=["GET"])
def api_get_operating_guidelines():
    """获取当前用户的公众号运营规范"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        content = db.get_operating_guidelines(user["id"])

    return jsonify({"content": content})


@app.route("/api/operating_guidelines", methods=["POST"])
def api_save_operating_guidelines():
    """保存当前用户的公众号运营规范"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    content = data.get("content", "")

    with UserDB() as db:
        db.save_operating_guidelines(user["id"], content)

    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
# 写作技能管理 API
# ════════════════════════════════════════════════════════════

@app.route("/api/skills", methods=["GET"])
def api_get_skills():
    """获取当前用户的写作技能列表"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    active_only = request.args.get("active_only") == "1"
    with UserDB() as db:
        skills = db.get_user_skills(user["id"], active_only=active_only)

    return jsonify({"ok": True, "skills": skills})


@app.route("/api/skills", methods=["POST"])
def api_create_skill():
    """创建写作技能"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = (data.get("name") or "").strip()
    prompt_content = data.get("prompt_content", "").strip()
    description = (data.get("description") or "").strip()
    category = (data.get("category") or "通用").strip()

    if not name:
        return jsonify({"ok": False, "error": "技能名称不能为空"}), 400
    if not prompt_content:
        return jsonify({"ok": False, "error": "技能提示词不能为空"}), 400

    with UserDB() as db:
        new_id = db.create_skill(user["id"], name, prompt_content, description, category)

    if new_id:
        return jsonify({"ok": True, "id": new_id})
    else:
        return jsonify({"ok": False, "error": "创建失败"}), 500


@app.route("/api/skills/<int:skill_id>", methods=["PUT"])
def api_update_skill(skill_id: int):
    """更新写作技能"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    with UserDB() as db:
        result = db.update_skill(
            skill_id, user["id"],
            name=data.get("name"),
            prompt_content=data.get("prompt_content"),
            description=data.get("description"),
            category=data.get("category"),
            is_active=data.get("is_active"),
        )

    if result:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "更新失败"}), 400


@app.route("/api/skills/<int:skill_id>", methods=["DELETE"])
def api_delete_skill(skill_id: int):
    """删除写作技能"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        result = db.delete_skill(skill_id, user["id"])

    if result:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "删除失败"}), 400


@app.route("/api/articles/dedup", methods=["GET"])
def api_get_articles_for_dedup():
    """获取历史文章标题列表（用于写稿前去重）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        articles = db.get_articles_for_dedup(user["id"], limit=500)

    return jsonify({"articles": articles})


# ════════════════════════════════════════════════════════════
# API：公众号账号管理（新）
# ════════════════════════════════════════════════════════════

@app.route("/api/accounts", methods=["GET"])
def api_get_accounts():
    """获取所有账号列表（含脱敏敏感信息）"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        accounts = db.get_user_accounts(user["id"])
        default = db.get_user_default_account(user["id"])

        # 脱敏：app_secret 只返回长度掩码
        masked_accounts = []
        for acc in accounts:
            masked_accounts.append({
                "id": acc["id"],
                "account_id": acc["account_id"],
                "name": acc["name"],
                "app_id": acc["app_id"],
                "app_secret": "*" * len(acc.get("app_secret", "")),
                "author": acc["author"],
                "topic_prompt": acc["topic_prompt"],
                "article_style": acc["article_style"],
                "word_count": acc["word_count"],
                "theme": acc["theme"],
                "writing_prompt": acc["writing_prompt"],
                "ending_text": acc.get("ending_text", "感谢阅读，我们下期见。"),
                "domain": acc.get("domain", "科技"),
                "is_default": acc["is_default"],
            })

        return jsonify({
            "default_account_id": default["account_id"] if default else "",
            "default_account_db_id": default["id"] if default else None,
            "accounts": masked_accounts,
        })


@app.route("/api/accounts/<int:account_db_id>/set_default", methods=["POST"])
def api_set_default_account(account_db_id: int):
    """将指定账号设为默认账号"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    with UserDB() as db:
        # 检查账号是否存在且属于当前用户
        account = db.get_account_by_id(account_db_id)
        if not account or account["user_id"] != user["id"]:
            return jsonify({"ok": False, "error": "账号不存在或无权操作"}), 404

        if db.set_default_account(user["id"], account_db_id):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "设置失败"}), 500


@app.route("/api/accounts/check_ip", methods=["POST"])
def api_check_account_ip():
    """通过调用微信API检测IP是否在白名单中，并返回检测信息"""
    print(f"[IP检测] 开始检测IP")

    # 检查登录状态
    session_id = _get_session_id()
    print(f"[IP检测] session_id: {session_id}")
    user = get_current_user(session_id)
    if not user:
        print(f"[IP检测] 用户未登录")
        return jsonify({"success": False, "error": "请先登录"}), 401

    try:
        data = request.get_json()
        account_id = data.get("account_id")
        print(f"[IP检测] account_id: {account_id}")

        if not account_id:
            return jsonify({"success": False, "error": "请指定账号"}), 400

        # 获取账号配置
        account = None
        with UserDB() as db:
            account = db.get_account_by_account_id(account_id)
            # 验证账号属于当前用户
            if account and account["user_id"] != user["id"]:
                account = None

        if not account:
            return jsonify({"success": False, "error": "账号不存在"}), 404

        app_id = account.get("app_id")
        app_secret = account.get("app_secret")

        if not app_id or not app_secret:
            return jsonify({
                "success": False,
                "error": "账号未配置 AppID/AppSecret"
            }), 400

        # 尝试获取 access_token，检测IP是否在白名单
        url = f"https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        }

        try:
            print(f"[IP检测] 请求URL: {url}")
            print(f"[IP检测] 请求参数: {params}")
            resp = requests.get(url, params=params, timeout=10)
            print(f"[IP检测] 响应状态码: {resp.status_code}")
            result = resp.json()
            print(f"[IP检测] 响应内容: {result}")

            if "access_token" in result:
                # 成功获取token，IP在白名单中
                return jsonify({
                    "success": True,
                    "status": "ok",
                    "message": "IP地址已在白名单中，可以正常访问微信API",
                    "token_obtained": True,
                })
            else:
                # 获取失败，检查是否是IP白名单问题
                errcode = result.get("errcode")
                errmsg = result.get("errmsg", "")

                # 常见的IP白名单错误码
                # 40125: invalid appsecret
                # 40164: invalid ip, not in whitelist
                # 40013: invalid appid
                # 40163: app已被封禁 - 可能涉及IP
                # 其他错误码参考：https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html
                if errcode in [40164, 40163, 40013, 40125]:
                    return jsonify({
                        "success": True,
                        "status": "not_allowed",
                        "message": f"IP地址未在白名单中（错误码：{errcode}）",
                        "errcode": errcode,
                        "errmsg": errmsg,
                        "token_obtained": False,
                    })
                else:
                    # 其他错误
                    return jsonify({
                        "success": False,
                        "status": "error",
                        "message": f"检测失败（错误码：{errcode}）",
                        "errcode": errcode,
                        "errmsg": errmsg,
                    }), 500

        except requests.exceptions.Timeout as e:
            print(f"[IP检测] 请求超时: {e}")
            return jsonify({
                "success": False,
                "status": "timeout",
                "message": "请求超时，请检查网络连接",
                "errmsg": str(e)
            }), 500
        except Exception as e:
            print(f"[IP检测] 微信API调用异常: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "success": False,
                "status": "exception",
                "message": f"检测异常：{str(e)}",
                "errmsg": str(e)
            }), 500

    except Exception as e:
        print(f"[IP检测] 错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"检测失败: {str(e)}",
            "errmsg": str(e)
        }), 500


@app.route("/api/accounts/<int:account_db_id>", methods=["GET"])
def api_get_account_detail(account_db_id: int):
    """获取单个账号的完整信息（含明文 app_secret）"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        account = db.get_account_by_id(account_db_id)
        if not account or account["user_id"] != user["id"]:
            return jsonify({"error": "账号不存在或无权访问"}), 404

        return jsonify({
            "id": account["id"],
            "account_id": account["account_id"],
            "name": account["name"],
            "app_id": account["app_id"],
            "app_secret": account["app_secret"],
            "author": account["author"],
            "topic_prompt": account["topic_prompt"],
            "article_style": account["article_style"],
            "word_count": account["word_count"],
            "theme": account["theme"],
            "writing_prompt": account["writing_prompt"],
            "ending_text": account.get("ending_text", "感谢阅读，我们下期见。"),
            "domain": account.get("domain", "科技"),
            "is_default": account["is_default"],
        })


@app.route("/api/accounts", methods=["POST"])
def api_save_account():
    """新增或编辑账号"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    account_id = data.get("account_id")  # 这是 account_id 字符串（如 "bigdata"）
    db_id = data.get("id")  # 这是数据库 ID（编辑时需要）

    if not account_id:
        return jsonify({"ok": False, "error": "account_id is required"}), 400

    with UserDB() as db:
        if db_id:
            # 编辑模式
            account = db.get_account_by_id(db_id)
            if not account or account["user_id"] != user["id"]:
                return jsonify({"ok": False, "error": "账号不存在或无权操作"}), 404

            # app_secret 留空则保留原值
            app_secret = data.get("app_secret")
            if app_secret == "":
                app_secret = None

            # 更新账号
            updated = db.update_account(
                db_id,
                name=data.get("name"),
                app_id=data.get("app_id"),
                app_secret=app_secret,
                author=data.get("author"),
                topic_prompt=data.get("topic_prompt"),
                article_style=data.get("article_style"),
                word_count=data.get("word_count"),
                theme=data.get("theme"),
                writing_prompt=data.get("writing_prompt"),
                ending_text=data.get("ending_text", "感谢阅读，我们下期见。"),
                domain=data.get("domain", "科技"),
            )

            if updated:
                # 如果 account_id 变了，需要更新（这里简化处理，暂不支持修改 account_id）
                return jsonify({"ok": True})
            else:
                return jsonify({"ok": False, "error": "更新失败"}), 500
        else:
            # 新增模式
            # 检查 account_id 是否已存在
            existing = db.get_account_by_account_id(account_id)
            if existing:
                return jsonify({"ok": False, "error": "account_id 已存在"}), 400

            # 检查是否是第一个账号，自动设为默认
            accounts = db.get_user_accounts(user["id"])
            is_default = len(accounts) == 0

            new_id = db.create_account(
                user_id=user["id"],
                account_id=account_id,
                name=data.get("name", ""),
                app_id=data.get("app_id", ""),
                app_secret=data.get("app_secret", ""),
                author=data.get("author", ""),
                topic_prompt=data.get("topic_prompt", ""),
                article_style=data.get("article_style", "观点评论"),
                word_count=data.get("word_count", 2000),
                theme=data.get("theme", "blue"),
                writing_prompt=data.get("writing_prompt", ""),
                ending_text=data.get("ending_text", "感谢阅读，我们下期见。"),
                domain=data.get("domain", "科技"),
                is_default=is_default,
            )

            if new_id:
                return jsonify({"ok": True, "id": new_id})
            else:
                return jsonify({"ok": False, "error": "创建失败"}), 500


@app.route("/api/accounts/<int:account_db_id>", methods=["DELETE"])
def api_delete_account(account_db_id: int):
    """删除账号"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        # 检查账号是否存在且属于当前用户
        account = db.get_account_by_id(account_db_id)
        if not account or account["user_id"] != user["id"]:
            return jsonify({"error": "账号不存在或无权操作"}), 404

        if db.delete_account(account_db_id, user["id"]):
            # 如果删除的是默认账号，自动设置第一个账号为默认
            if account["is_default"]:
                accounts = db.get_user_accounts(user["id"])
                if accounts:
                    db.set_default_account(user["id"], accounts[0]["id"])

            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "删除失败"}), 500


# ════════════════════════════════════════════════════════════
# API：爆款分析（文章数据统计）
# ════════════════════════════════════════════════════════════

@app.route("/api/article_stats", methods=["GET"])
def api_get_article_stats():
    """获取当前账号的文章阅读/点赞/转发等统计数据"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    # 获取账号参数
    account_str_id = request.args.get("account_id", "").strip()
    days = request.args.get("days", "7").strip()

    try:
        days = int(days)
        days = max(1, min(days, 30))  # 限制 1-30 天
    except ValueError:
        days = 7

    # 查找账号
    with UserDB() as db:
        if account_str_id:
            account = db.get_account_by_account_id(account_str_id)
        else:
            account = db.get_user_default_account(user["id"])

        if not account or account["user_id"] != user["id"]:
            return jsonify({
                "success": False,
                "error": "未找到公众号账号，请先在系统配置中添加账号",
                "articles": [],
                "total": 0,
            })

    # 调用微信 API 获取数据
    try:
        from modules.wx_publisher import WeChatPublisher, WeChatAPIError

        publisher = WeChatPublisher(
            app_id=account["app_id"],
            app_secret=account["app_secret"],
        )
        result = publisher.fetch_viral_data(days=days)

        # 追加账号信息
        result["account_name"] = account.get("name", "")
        result["account_id"] = account.get("account_id", "")

        return jsonify(result)

    except WeChatAPIError as e:
        return jsonify({
            "success": False,
            "error": f"微信API调用失败: {str(e)}",
            "articles": [],
            "total": 0,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"获取数据异常: {str(e)}",
            "articles": [],
            "total": 0,
        })


# ════════════════════════════════════════════════════════════
# API：领域分类管理
# ════════════════════════════════════════════════════════════

@app.route("/api/domains", methods=["GET"])
def api_get_domains():
    """获取用户的所有领域分类（含系统默认）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    from modules.user_db import init_system_domains
    init_system_domains(user["id"])

    with UserDB() as db:
        domains = db.get_user_domains(user["id"])
        return jsonify({"ok": True, "domains": domains})


@app.route("/api/domains", methods=["POST"])
def api_create_domain():
    """创建新领域分类"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    ref_websites = data.get("ref_websites", [])
    if not isinstance(ref_websites, list):
        ref_websites = []

    if not name:
        return jsonify({"ok": False, "error": "领域名称不能为空"}), 400

    with UserDB() as db:
        new_id = db.create_domain(user["id"], name, description, is_system=0, ref_websites=ref_websites)
        if new_id:
            return jsonify({"ok": True, "id": new_id})
        else:
            return jsonify({"ok": False, "error": "领域名称已存在或创建失败"}), 500


@app.route("/api/domains/<int:domain_id>", methods=["PUT"])
def api_update_domain(domain_id: int):
    """更新领域分类"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name")
    description = data.get("description")
    ref_websites = data.get("ref_websites")  # None 表示不更新
    if ref_websites is not None and not isinstance(ref_websites, list):
        ref_websites = []

    if name is None and description is None and ref_websites is None:
        return jsonify({"ok": False, "error": "没有提供更新内容"}), 400

    with UserDB() as db:
        if db.update_domain(domain_id, user["id"], name, description, ref_websites):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "更新失败（系统领域不可改名）"}), 400


@app.route("/api/domains/<int:domain_id>", methods=["DELETE"])
def api_delete_domain(domain_id: int):
    """删除领域分类（系统领域不可删除）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        if db.delete_domain(domain_id, user["id"]):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "删除失败（系统领域不可删除）"}), 400


# ════════════════════════════════════════════════════════════
# API：AI 模型管理
# ════════════════════════════════════════════════════════════

@app.route("/api/ai_models", methods=["GET"])
def api_get_ai_models():
    """获取用户的所有AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        models = db.get_user_ai_models(user["id"])
        # 不返回敏感信息（api_key）
        for model in models:
            model.pop("api_key", None)
        return jsonify({"ok": True, "models": models})


@app.route("/api/ai_models/<int:model_id>/set_default", methods=["POST"])
def api_set_default_ai_model(model_id: int):
    """设置默认AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        if db.set_default_ai_model(user["id"], model_id):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "设置失败"}), 500


@app.route("/api/ai_models/<int:model_id>", methods=["GET"])
def api_get_ai_model(model_id: int):
    """获取指定AI模型详情"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        model = db.get_ai_model_by_id(model_id, user["id"])
        if model:
            # 不返回敏感信息（api_key）
            model.pop("api_key", None)
            return jsonify({"ok": True, "model": model})
        else:
            return jsonify({"ok": False, "error": "模型不存在"}), 404


@app.route("/api/ai_models", methods=["POST"])
def api_create_ai_model():
    """创建AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name", "").strip()
    provider = data.get("provider", "").strip()
    model_name = data.get("model_name", "").strip()
    api_key = data.get("api_key", "").strip()
    api_base = data.get("api_base", "").strip()
    is_default = data.get("is_default", False)
    is_image_model = data.get("is_image_model", False)

    # 验证必填字段
    if not name:
        return jsonify({"ok": False, "error": "模型名称不能为空"}), 400
    if not provider:
        return jsonify({"ok": False, "error": "提供商不能为空"}), 400
    if not model_name:
        return jsonify({"ok": False, "error": "模型名称不能为空"}), 400
    if not api_key:
        return jsonify({"ok": False, "error": "API密钥不能为空"}), 400

    with UserDB() as db:
        new_id = db.create_ai_model(
            user["id"], name, provider, model_name, api_key, api_base, is_default, is_image_model
        )
        if new_id:
            return jsonify({"ok": True, "id": new_id})
        else:
            return jsonify({"ok": False, "error": "模型名称已存在或创建失败"}), 500


@app.route("/api/ai_models/<int:model_id>", methods=["PUT"])
def api_update_ai_model(model_id: int):
    """更新AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name")
    provider = data.get("provider")
    model_name = data.get("model_name")
    api_key = data.get("api_key")
    api_base = data.get("api_base")
    is_image_model = data.get("is_image_model")

    if all(v is None for v in [name, provider, model_name, api_key, api_base, is_image_model]):
        return jsonify({"ok": False, "error": "没有提供更新内容"}), 400

    with UserDB() as db:
        if db.update_ai_model(model_id, user["id"], name, provider, model_name, api_key, api_base, is_image_model):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "更新失败"}), 500


@app.route("/api/ai_models/<int:model_id>", methods=["DELETE"])
def api_delete_ai_model(model_id: int):
    """删除AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        if db.delete_ai_model(model_id, user["id"]):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "删除失败"}), 500


# ════════════════════════════════════════════════════════════
# API：SSE 实时日志
# ════════════════════════════════════════════════════════════

@app.route("/api/logs/<task_id>")
def api_logs(task_id: str):
    """Server-Sent Events 日志流"""
    q: queue.Queue = _log_queues.get(task_id)
    if q is None:
        return Response("data: {\"msg\":\"task not found\",\"level\":\"error\"}\n\n",
                        mimetype="text/event-stream")

    def generate():
        while True:
            try:
                item = q.get(timeout=30)
                if item is None:   # 哨兵值：任务结束
                    yield f"data: {json.dumps({'msg':'__DONE__','level':'done'})}\n\n"
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield "data: {\"msg\":\"ping\",\"level\":\"ping\"}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ════════════════════════════════════════════════════════════
# API：自动选题
# ════════════════════════════════════════════════════════════

@app.route("/api/topics", methods=["POST"])
def api_get_topics():
    data = request.json or {}
    task_id = data.get("task_id", "topics")
    no_cache = data.get("no_cache", False)

    account_id = data.get("account_id", "")
    acc_cfg = get_account_config(account_id)
    prompt = data.get("topic_prompt") or acc_cfg.get("topic_prompt", "")
    # domain 仅作为 AI 背景提示，不决定爬哪些网站；留空则由 AI 从 prompt 自行判断

    # 在主线程里预先获取 user_id（子线程无法访问 Flask g）
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            # 打印当前使用的公众号
            if acc_cfg:
                print(f"📱 当前使用公众号：{acc_cfg.get('name')} (ID: {acc_cfg.get('account_id')})")
            else:
                print("⚠️ 未找到公众号配置")

            from modules.auto_selector import generate_topics
            topics = generate_topics(
                prompt=prompt,
                domain=acc_cfg.get("domain", ""),  # 传入账号领域，降级时按领域爬取
                search_queries=[],  # 固定传空数组，使用 AI 生成
                max_topics=10,
                cache_hours=0,  # 始终不使用缓存，强制重新搜索
                user_id=current_user_id,
            )
            push_log(task_id, json.dumps({"topics": topics}, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)  # 结束哨兵
            _log_queues.pop(task_id, None)  # 清理内存

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════

@app.route("/api/agent/generate", methods=["POST"])
def api_agent_generate():
    """调用 Coze 工作流改写文章，返回标题和正文"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    url = (data.get("url") or "").strip()
    account_id = (data.get("account_id") or "").strip()
    prompt = (data.get("prompt") or "不要抄袭,去除AI味").strip()

    if not url:
        return jsonify({"error": "请输入文章链接"}), 400
    if not account_id:
        return jsonify({"error": "请选择账号"}), 400

    # 加载 Coze 配置
    coze_cfg = load_coze_config()
    if not coze_cfg.get("workflow_id") or not coze_cfg.get("api_token"):
        return jsonify({"error": "请先配置 Coze 工作流（系统配置 → Coze 工作流配置）"}), 400

    # 读取账号凭证
    acc_cfg = get_account_config(account_id)
    if not acc_cfg or not acc_cfg.get("app_id") or not acc_cfg.get("app_secret"):
        return jsonify({"error": "账号未配置 AppID/AppSecret"}), 400

    try:
        client = CozeWorkflowClient(
            workflow_id=coze_cfg["workflow_id"],
            api_token=coze_cfg["api_token"],
        )
        result = client.rewrite_article(
            url=url,
            app_id=acc_cfg["app_id"],
            app_secret=acc_cfg["app_secret"],
            prompt=prompt,
        )
        return jsonify(result)
    except CozeAPIError as e:
        return jsonify({"error": f"生成失败：{e}"}), 502
    except Exception as e:
        return jsonify({"error": f"生成失败：{e}"}), 502


@app.route("/api/agent/push_draft", methods=["POST"])
def api_agent_push_draft():
    """将改写结果推送到公众号草稿箱"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    account_id = (data.get("account_id") or "").strip()

    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    if not content:
        return jsonify({"error": "正文不能为空"}), 400
    if not account_id:
        return jsonify({"error": "请选择账号"}), 400

    acc_cfg = get_account_config(account_id)
    if not acc_cfg or not acc_cfg.get("app_id") or not acc_cfg.get("app_secret"):
        return jsonify({"error": "账号未配置 AppID/AppSecret"}), 400

    try:
        from modules.md_converter import markdown_to_wechat_html

        # Coze 输出为 Markdown，转为微信草稿所需的 HTML
        content_html = markdown_to_wechat_html(
            content, title=title, author=acc_cfg.get("author", "")
        )

        publisher = WeChatPublisher(
            app_id=acc_cfg["app_id"], app_secret=acc_cfg["app_secret"]
        )
        result = publisher.create_draft_only(
            title=title,
            content_html=content_html,
            author=acc_cfg.get("author", ""),
        )
        return jsonify({"media_id": result["media_id"]})
    except Exception as e:
        return jsonify({"error": f"推送失败：{e}"}), 500


# ════════════════════════════════════════════════════════════


# API：AI 生成文章
# ════════════════════════════════════════════════════════════

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.json or {}
    task_id = data.get("task_id", "generate")

    topic = data.get("topic", {})
    account_id = data.get("account_id", "")
    acc_cfg = get_account_config(account_id)

    style = data.get("style") or acc_cfg.get("article_style", "观点评论")
    words = int(data.get("word_count") or acc_cfg.get("word_count", 2000))
    custom_writing_prompt = acc_cfg.get("writing_prompt", "")
    ending_text = acc_cfg.get("ending_text", "感谢阅读，我们下期见。")

    extra = data.get("extra_instructions", "")
    skill_id = data.get("skill_id")  # 写作技能 ID（可选）

    # 在主线程里预先获取 user_id（子线程无法访问 Flask g）
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            # 打印当前使用的公众号
            if acc_cfg:
                print(f"📱 当前使用公众号：{acc_cfg.get('name')} (ID: {acc_cfg.get('account_id')})")
            else:
                print("⚠️ 未找到公众号配置")

            from modules.ai_writer import generate_article, _check_history_duplicates

            # 历史文章去重检查（三重检测：标题bigram + 产品型号名 + 内容bigram）
            topic_title = topic.get("title", "")
            topic_content = topic.get("summary", "") + topic.get("detail", "")
            dupes = _check_history_duplicates(current_user_id, topic_title, topic_content)
            dup_warning = ""
            if dupes:
                dup_titles = "、".join([f"「{d['title']}」({d['reason']})" for d in dupes[:3]])
                dup_warning = f"\n\n⚠️ **历史文章去重提醒**：系统检测到以下相似历史文章：{dup_titles}。请务必写出与以上文章**完全不同**的角度、观点和内容，避免重复写稿。"
                print(f"   ⚠️  检测到 {len(dupes)} 篇相似历史文章：{', '.join([d['title']+'（'+d['reason']+'）' for d in dupes[:3]])}")

            # 如果选择了写作技能，加载技能提示词
            skill_prompt = ""
            if skill_id:
                try:
                    from modules.user_db import UserDB as _UDB
                    with _UDB() as _sdb:
                        _skill = _sdb.get_skill_by_id(int(skill_id), current_user_id)
                    if _skill:
                        skill_prompt = _skill["prompt_content"]
                        print(f"🎯 使用写作技能：{_skill['name']}")
                    else:
                        print(f"⚠️  未找到技能 ID={skill_id}，忽略技能")
                except Exception as _se:
                    print(f"⚠️  加载写作技能失败（{_se}），忽略技能")

            md_content, saved_path = generate_article(
                topic=topic,
                style=style,
                word_count=words,
                extra_instructions=extra + dup_warning,
                save_to_file=True,
                custom_writing_prompt=custom_writing_prompt,
                ending_text=ending_text,
                user_id=current_user_id,
                skill_prompt=skill_prompt,
            )

            # 爆款标题替换
            try:
                from modules.article_rewriter import generate_title as gen_viral_title
                import re as _re
                body_text = _re.sub(r'^#\s+.+\n*', '', md_content, count=1)
                viral_title = gen_viral_title(body_text, user_id=current_user_id)
                if viral_title and viral_title.strip():
                    md_content = _re.sub(r'^#\s+.+\n*', f'# {viral_title.strip()}\n\n', md_content, count=1)
                    if saved_path:
                        with open(saved_path, "w", encoding="utf-8") as _f:
                            _f.write(md_content)
                    print(f"   🔥 爆款标题：{viral_title.strip()}")
                else:
                    print(f"   ⚠️  爆款标题生成失败，保留原标题")
            except Exception as _e:
                print(f"   ⚠️  爆款标题生成异常（{_e}），保留原标题")

            # AI 排版优化
            try:
                from modules.ai_writer import ai_format_article
                formatted_md = ai_format_article(md_content, user_id=current_user_id)
                if formatted_md != md_content:
                    md_content = formatted_md
                    if saved_path:
                        with open(saved_path, "w", encoding="utf-8") as _f:
                            _f.write(md_content)
            except Exception as _e:
                print(f"   ⚠️  AI 排版异常（{_e}），保留原文")

            # 保存文章到数据库
            account_db_id = acc_cfg.get("id", 0)
            print(f"🔍 调试：account_db_id={account_db_id}, saved_path='{saved_path}'")
            if account_db_id > 0 and saved_path:
                try:
                    from modules.user_db import UserDB
                    db = UserDB()

                    # 从 Markdown 内容提取标题
                    import re
                    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else topic.get("title", "未命名")

                    # 从完整路径提取文件名（只存文件名到数据库）
                    file_name_only = Path(saved_path).name

                    article_id = db.create_article(
                        user_id=current_user_id,
                        account_db_id=account_db_id,
                        title=title,
                        file_path=file_name_only,  # 只存文件名
                        status="draft",
                    )

                    if article_id:
                        push_log(task_id, f"💾 文章已保存到数据库（ID: {article_id}）", "info")
                    else:
                        push_log(task_id, "⚠️  保存文章到数据库失败", "warning")
                except Exception as e:
                    push_log(task_id, f"⚠️  保存文章到数据库时出错：{e}", "warning")
            else:
                if account_db_id <= 0:
                    push_log(task_id, f"⚠️  跳过保存到数据库：无效的 account_db_id={account_db_id}", "warning")
                if not saved_path:
                    push_log(task_id, f"⚠️  跳过保存到数据库：saved_path 为空", "warning")

            push_log(task_id, json.dumps({
                "md_content": md_content,
                "saved_path": saved_path,
            }, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：链接改写（抓取 URL → AI 改写为原创文章）
# ════════════════════════════════════════════════════════════

@app.route("/api/fetch_url", methods=["POST"])
def api_fetch_url():
    """抓取 URL 内容，返回标题和正文"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"ok": False, "error": "请输入文章链接"}), 400

    try:
        from modules.article_rewriter import fetch_url_content
        title, content = fetch_url_content(url)
        return jsonify({"ok": True, "title": title, "content": content})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"抓取失败：{e}"}), 500


@app.route("/api/rewrite", methods=["POST"])
def api_rewrite():
    """AI 改写文章（SSE 实时日志）"""
    data = request.json or {}
    task_id = data.get("task_id", "rewrite")

    original_title = data.get("original_title", "")
    original_content = data.get("original_content", "")
    account_id = data.get("account_id", "")
    word_count = int(data.get("word_count", 2000))
    extra_instructions = data.get("extra_instructions", "")

    acc_cfg = get_account_config(account_id)
    style = data.get("style") or acc_cfg.get("article_style", "观点评论")
    custom_writing_prompt = acc_cfg.get("writing_prompt", "")

    if not original_content:
        return jsonify({"ok": False, "error": "没有原文内容"}), 400

    # 预先获取 user_id
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            if acc_cfg:
                print(f"   当前使用公众号：{acc_cfg.get('name')} (ID: {acc_cfg.get('account_id')})")

            print(f"   [1/2] 开始 AI 改写...")

            from modules.article_rewriter import rewrite_article
            md_content = rewrite_article(
                original_title=original_title,
                original_content=original_content,
                user_id=current_user_id,
                word_count=word_count,
                style=style,
                custom_writing_prompt=custom_writing_prompt,
                extra_instructions=extra_instructions,
            )

            print(f"   [2/2] 改写完成！")

            # 保存 Markdown 文件
            from datetime import datetime
            from modules.ai_writer import OUTPUT_DIR
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', original_title or "rewrite")[:30]
            filename = f"{timestamp}_{safe_title}.md"
            saved_path = str(OUTPUT_DIR / filename)
            with open(saved_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"   文章已保存：{saved_path}")

            # 保存到数据库
            account_db_id = acc_cfg.get("id", 0)
            if account_db_id > 0 and saved_path:
                try:
                    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else "改写文章"
                    file_name_only = Path(saved_path).name

                    db = UserDB()
                    article_id = db.create_article(
                        user_id=current_user_id,
                        account_db_id=account_db_id,
                        title=title,
                        file_path=file_name_only,
                        status="draft",
                    )
                    if article_id:
                        push_log(task_id, f"   文章已保存到数据库（ID: {article_id}）", "info")
                except Exception as e:
                    push_log(task_id, f"   保存文章到数据库时出错：{e}", "warning")

            push_log(task_id, json.dumps({
                "md_content": md_content,
                "saved_path": saved_path,
            }, ensure_ascii=False), "result")

        except Exception as e:
            push_log(task_id, f"   改写失败：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：全自动流水线（选题 → 写作 → 生成草稿）
# ════════════════════════════════════════════════════════════

@app.route("/api/auto", methods=["POST"])
def api_auto():
    data = request.json or {}
    task_id = data.get("task_id", "auto")
    no_cache = data.get("no_cache", False)
    account_id = data.get("account_id", "")
    skill_id = data.get("skill_id")  # 写作技能 ID（可选）

    # 在主线程里预先获取 user_id 和账号配置（子线程无法访问 Flask g）
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1
    acc_cfg = get_account_config(account_id)

    # 如果选择了写作技能，预先加载技能提示词
    skill_prompt = ""
    if skill_id:
        try:
            from modules.user_db import UserDB as _UDB
            with _UDB() as _sdb:
                _skill = _sdb.get_skill_by_id(int(skill_id), current_user_id)
            if _skill:
                skill_prompt = _skill["prompt_content"]
        except Exception:
            pass

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            import main as m
            cfg = m.load_config()
            # acc_cfg 已在主线程获取，直接使用（子线程无法访问 Flask g）

            # 构建用于 run_auto_pipeline 的 prompt_cfg（search_queries 已废弃）
            prompt_cfg = {
                "topic_prompt": acc_cfg.get("topic_prompt", ""),
                "search_queries": [],  # 固定传空数组，使用 AI 生成
                "article_style": acc_cfg.get("article_style", "观点评论"),
                "word_count": acc_cfg.get("word_count", 2000),
                "theme": acc_cfg.get("theme", "blue"),
                "writing_prompt": acc_cfg.get("writing_prompt", ""),
            }

            # 允许前端覆盖参数（优先级高于账号配置）
            if data.get("style"):
                prompt_cfg["article_style"] = data["style"]
            if data.get("word_count"):
                prompt_cfg["word_count"] = int(data["word_count"])
            if data.get("topic_index"):
                topic_index = int(data["topic_index"])
            else:
                topic_index = None

            theme = data.get("theme") or prompt_cfg.get("theme", acc_cfg.get("default_theme", "blue"))

            # 调试：输出账号配置
            account_db_id = acc_cfg.get("id", 0)
            if acc_cfg:
                print(f"📱 当前使用公众号：{acc_cfg.get('name')} (ID: {acc_cfg.get('account_id')})")
            else:
                print("⚠️ 未找到公众号配置")

            result = m.run_auto_pipeline(
                config=cfg,
                prompt_cfg=prompt_cfg,
                draft_only=True,
                topic_index=topic_index,
                style_override=prompt_cfg.get("article_style", ""),
                words_override=prompt_cfg.get("word_count", 0),
                theme_override=theme,
                cache_hours=0,  # 始终不使用缓存，强制重新搜索
                custom_writing_prompt=prompt_cfg.get("writing_prompt", ""),
                account_db_id=acc_cfg.get("id", 0),
                user_id=current_user_id,
                domain_override=acc_cfg.get("domain", ""),
                skill_prompt=skill_prompt,
            )

            push_log(task_id, json.dumps(result, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：获取可用排版模板列表
# ════════════════════════════════════════════════════════════

@app.route("/api/templates", methods=["GET"])
def api_get_templates():
    """返回可用的排版模板列表"""
    from modules.md_converter import TEMPLATES
    templates = []
    for key, tmpl in TEMPLATES.items():
        templates.append({
            "id": key,
            "label": tmpl["label"],
        })
    return jsonify({"ok": True, "templates": templates})


# ════════════════════════════════════════════════════════════
# API：Markdown → HTML 预览
# ════════════════════════════════════════════════════════════

@app.route("/api/preview", methods=["POST"])
def api_preview():
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "未登录"}), 401

    data        = request.json or {}
    md_text     = data.get("md_text", "")
    author      = data.get("author", load_config().get("author", ""))
    theme       = data.get("theme", "blue")
    template    = data.get("template", "")
    ending_text = data.get("ending_text", "")  # 从请求中获取自定义结尾词

    try:
        from modules.md_converter import markdown_to_wechat_html
        html = markdown_to_wechat_html(md_text, author=author, add_footer=True, theme=theme, template=template, ending_text=ending_text)
        return jsonify({"ok": True, "html": html})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ════════════════════════════════════════════════════════════
# API：统计数据
# ════════════════════════════════════════════════════════════

@app.route("/api/stats", methods=["GET"])
def api_stats():
    """获取用户统计数据（从数据库）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)

    if not user:
        return jsonify({
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
        })

    with UserDB() as db:
        stats = db.get_user_stats(user["id"])

    return jsonify({
        "total_articles": stats["total_articles"],
        "draft_articles": stats["draft_articles"],
        "published_articles": stats["published_articles"],
        "today_articles": stats["today_articles"],
        "weekly_data": stats["weekly_data"],
        "weekly_account_data": stats.get("weekly_account_data", []),
        "account_stats": stats["account_stats"],
        "keyword_top10": stats.get("keyword_top10", []),
        "account_7d_stats": stats.get("account_7d_stats", []),
        "status_funnel": stats.get("status_funnel", []),
        "status_distribution": stats.get("status_distribution", []),
        "hourly_data": stats.get("hourly_data", []),
        "monthly_data": stats.get("monthly_data", []),
        "account_rank": stats.get("account_rank", []),
        "keyword_cloud": stats.get("keyword_cloud", []),
    })


# ════════════════════════════════════════════════════════════
# API：历史文章列表
# ════════════════════════════════════════════════════════════

@app.route("/api/articles", methods=["GET"])
def api_list_articles():
    """获取历史文章列表（从数据库，支持分页）

    查询参数：
    - page: 页码，默认 1
    - page_size: 每页数量，默认 10
    - account_id: 可选，公众号 ID（字符串类型），如果提供则只返回该公众号的文章
    """
    try:
        session_id = _get_session_id()
        user = get_current_user(session_id)
        if not user:
            return jsonify({"articles": [], "pagination": {}})  # 未登录返回空列表

        # 获取查询参数
        page = request.args.get("page", type=int, default=1)
        page_size = request.args.get("page_size", type=int, default=10)
        account_id = request.args.get("account_id")
        keyword = request.args.get("keyword", "").strip()
    except Exception as e:
        import traceback
        print(f"[API ERROR] 获取参数失败: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "articles": [], "pagination": {}}), 500

    try:
        with UserDB() as db:
            # 获取分页数据（account_id 在数据库层过滤，total 才准确）
            result = db.get_user_articles_paginated(user["id"], page, page_size, account_str_id=account_id, keyword=keyword or None)
            articles = result["articles"]
            pagination = result["pagination"]
            print(f"[API] 加载文章列表: 用户 {user['id']}, 公众号 {account_id or '全部'}, 文章数 {len(articles)}, 总数 {pagination.get('total')}")
    except Exception as e:
        import traceback
        print(f"[API ERROR] 数据库查询失败: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "articles": [], "pagination": {}}), 500

    items = []
    for art in articles:
        # 读取文件大小
        file_path = BASE_DIR / "output" / "articles" / art["file_path"]
        try:
            size = file_path.stat().st_size if file_path.exists() else 0
        except Exception as e:
            print(f"[Warning] 无法读取文件 {file_path}: {e}")
            size = 0

        # 调试：打印每篇文章的状态
        print(f"[API] 文章状态 - ID:{art.get('id')}, status:{art.get('status')}")

        # 处理发布时间
        published_at = art.get("published_at")
        if published_at:
            try:
                # 检查是否是字符串，如果是则直接使用
                if isinstance(published_at, str):
                    # 尝试解析字符串时间
                    try:
                        dt = datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S")
                        # 如果时间是 UTC 时间（与当前时间相差 8 小时左右），则转换为本地时间
                        now = datetime.now()
                        time_diff = abs((now - dt).total_seconds())
                        # 如果时间差大于 7 小时（考虑误差），认为是 UTC 时间，需要转换
                        if time_diff > 7 * 3600:
                            # UTC 时间，加 8 小时转换为本地时间
                            dt_local = dt + timedelta(hours=8)
                            mtime = dt_local.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            # 已经是本地时间，直接使用
                            mtime = published_at
                    except:
                        mtime = published_at
                else:
                    mtime = published_at.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"[Warning] 无法格式化发布时间: {e}")
                mtime = ""
        else:
            mtime = ""

        # 处理创建时间
        created_at = art.get("created_at")
        created_at_str = ""
        if created_at:
            try:
                # 检查是否是字符串，如果是则直接使用
                if isinstance(created_at, str):
                    # 尝试解析字符串时间
                    try:
                        dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                        # 如果时间是 UTC 时间（与当前时间相差 8 小时左右），则转换为本地时间
                        now = datetime.now()
                        time_diff = abs((now - dt).total_seconds())
                        # 如果时间差大于 7 小时（考虑误差），认为是 UTC 时间，需要转换
                        if time_diff > 7 * 3600:
                            # UTC 时间，加 8 小时转换为本地时间
                            dt_local = dt + timedelta(hours=8)
                            created_at_str = dt_local.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            # 已经是本地时间，直接使用
                            created_at_str = created_at
                    except:
                        created_at_str = created_at
                else:
                    created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"[Warning] 无法格式化创建时间: {e}")
                created_at_str = ""
        else:
            # 如果没有创建时间，记录到日志
            print(f"[Warning] 文章 {art['file_path']} 缺少 created_at 字段")

        items.append({
            "filename": art["file_path"],
            "title": art["title"][:60] if art.get("title") else art["file_path"],
            "size": size,
            "mtime": mtime,
            "created_at": created_at_str,
            "account_id": art.get("account_str_id"),  # 公众号 ID 字符串，匹配顶部下拉框
            "account_name": art.get("account_name") or "未分类",
            "status": art.get("status", "draft"),  # 文章状态：draft/draft_box/published
        })

    # 按创建时间倒序排序（最新的在前）
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return jsonify({"articles": items, "pagination": pagination})


@app.route("/api/articles/<filename>", methods=["GET"])
def api_get_article(filename: str):
    """读取单篇文章内容（Markdown），同时返回服务器绝对路径供前端推送时复用"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    # 处理 URL 编码的文件名
    from urllib.parse import unquote
    filename = unquote(filename)

    # 如果传入的是完整路径，提取纯文件名
    if "/" in filename or "\\" in filename:
        filename = Path(filename).name

    p = BASE_DIR / "output" / "articles" / filename
    if not p.exists() or not p.suffix == ".md":
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "md_text":     p.read_text(encoding="utf-8"),
        "server_path": str(p),   # 前端推送时带上，后端直接读文件不再新建
    })


@app.route("/api/articles/<filename>", methods=["PUT"])
def api_save_article(filename: str):
    """保存编辑后的文章内容"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    p = BASE_DIR / "output" / "articles" / filename
    if not p.exists():
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    p.write_text(data.get("md_text", ""), encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/articles/<filename>", methods=["DELETE"])
def api_delete_article(filename: str):
    """删除单篇历史文章（.md 文件）并同步删除对应 HTML 草稿"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    # 只允许删 output/articles/ 下的 .md 文件，防止路径穿越
    if ".." in filename or "/" in filename or not filename.endswith(".md"):
        return jsonify({"error": "invalid filename"}), 400
    p = BASE_DIR / "output" / "articles" / filename
    if not p.exists():
        return jsonify({"error": "not found"}), 404

    stem = Path(filename).stem  # 去掉 .md 后缀的文件名
    p.unlink()

    # 同步删除 output/drafts/ 下同名的 HTML 草稿
    # 用 startswith 而不是 glob，避免文件名含中文/特殊字符时 glob 匹配失败
    drafts_dir = BASE_DIR / "output" / "drafts"
    deleted_html = []
    if drafts_dir.exists():
        for html_file in drafts_dir.iterdir():
            if html_file.suffix == ".html" and html_file.stem.startswith(stem):
                html_file.unlink()
                deleted_html.append(html_file.name)

    # 同步删除数据库记录
    with UserDB() as db:
        db.delete_article_by_filename(filename, user["id"])

    print(f"[DELETE] 已删除 {filename}，同步删除 HTML：{deleted_html}")
    return jsonify({"ok": True, "deleted_html": deleted_html})


# ════════════════════════════════════════════════════════════
# API：封面列表
# ════════════════════════════════════════════════════════════

@app.route("/api/covers/<filename>")
def api_get_cover(filename: str):
    covers_dir = BASE_DIR / "output" / "covers"
    return send_from_directory(str(covers_dir), filename)


# ════════════════════════════════════════════════════════════
# API：HTML 预览文件
# ════════════════════════════════════════════════════════════

@app.route("/api/drafts/<filename>")
def api_get_draft(filename: str):
    drafts_dir = BASE_DIR / "output" / "drafts"
    return send_from_directory(str(drafts_dir), filename)


# ════════════════════════════════════════════════════════════
# API：AI 排版（优化 Markdown 格式）
# ════════════════════════════════════════════════════════════

@app.route("/api/format", methods=["POST"])
def api_format():
    """使用 AI 优化 Markdown 文章的排版和语言风格"""
    data = request.json or {}
    task_id = data.get("task_id", "format")
    md_text = data.get("md_text", "")
    ending_text = data.get("ending_text", "").strip() if data.get("ending_text") else ""
    no_ending = data.get("no_ending", False)

    if not md_text:
        return jsonify({"ok": False, "error": "请提供 md_text"}), 400

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.ai_writer import _detect_llm_backend, _call_openai, _call_ollama

            push_log(task_id, "🔍 检测 AI 服务...", "info")

            backend, config = _detect_llm_backend()

            if backend == "template":
                push_log(task_id, "❌ 未检测到 AI 服务，无法使用 AI 排版功能", "error")
                push_log(task_id, "", "end")
                return

            push_log(task_id, f"✅ 使用 AI 服务: {backend}", "info")
            push_log(task_id, "📝 正在优化排版...", "info")

            # 构建结尾词指令
            ending_instruction = ''
            if no_ending:
                ending_instruction = '\n8. 文章不要添加任何结尾词或结束语，内容自然结束即可'
            elif ending_text:
                ending_instruction = f'\n8. 文章结尾必须使用以下文字：{ending_text}'

            # AI 排版提示词
            prompt = f"""请优化以下 Markdown 文章的排版和语言风格。

要求：
1. 保持原有的核心内容和观点不变
2. 优化语言表达，使其更自然流畅，去除AI味儿
3. 改善段落结构，使逻辑更清晰
4. **必须保留原有的所有 ## 小标题，不能删除任何一个；如果原文没有 ## 小标题，必须添加 2～4 个 ## 小标题来划分段落层次**
5. 保持 Markdown 格式正确（全文标题用 # ，段落小标题用 ## ，更细分用 ### ）
6. 不要改变原文的主旨和重要信息
7. 不要添加任何额外的客套话或总结语{ending_instruction}

待优化的文章：

{md_text}

请直接返回优化后的 Markdown 内容，不要有任何解释或说明。"""

            if backend == "openai":
                result = _call_openai(prompt, config)
            elif backend == "ollama":
                result = _call_ollama(prompt, config)
            else:
                push_log(task_id, "❌ 不支持的 AI 后端", "error")
                push_log(task_id, "", "end")
                return

            push_log(task_id, "✅ 排版优化完成", "info")
            push_log(task_id, json.dumps({"formatted_md": result}, ensure_ascii=False), "result")

        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：推送草稿到微信
# ════════════════════════════════════════════════════════════

@app.route("/api/publish", methods=["POST"])
def api_publish():
    data    = request.json or {}
    task_id = data.get("task_id", "publish")
    md_path = data.get("md_path", "")
    md_text = data.get("md_text", "")
    theme   = data.get("theme", "blue")
    template = data.get("template", "")
    account_id = data.get("account_id", "")

    # 获取当前用户 ID
    current_user = session.get("user")
    current_user_id = current_user["id"] if current_user else 1
    print(f"[API] /api/publish - 当前用户: {current_user_id}, 账号选择: {account_id}")

    # 如果 md_path 存在且文件确实存在，优先用文件；否则降级到 md_text
    if md_path and not Path(md_path).exists():
        print(f"[警告] md_path 不存在，降级使用 md_text：{md_path}")
        md_path = ""  # 清空，走下面的 md_text 分支

    # 如果没有文件路径但有文本内容，先把内容保存为临时文件
    if not md_path and md_text:
        import tempfile, re, time
        # 从第一行提取标题作为文件名
        first_line = md_text.strip().split('\n')[0].lstrip('#').strip()
        safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', first_line)[:30] or "draft"
        timestamp  = time.strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / "output" / "articles"
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = str(output_dir / f"{timestamp}_{safe_title}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)

    if not md_path:
        return jsonify({"ok": False, "error": "请提供文章内容或文件路径"}), 400

    # 在主线程中先获取账号配置（避免子线程中 fallback 到 admin）
    acc_cfg = get_account_config(account_id, user_id=current_user_id, allow_fallback=False)
    if not acc_cfg or not acc_cfg.get("app_id") or not acc_cfg.get("app_secret"):
        return jsonify({"ok": False, "error": f"账号未找到或未配置 AppID/AppSecret（账号: {account_id}）"}), 400

    # 打印当前使用的公众号（方便用户确认）
    print(f"[API] 使用公众号：{acc_cfg.get('name', '未知')} (ID: {acc_cfg.get('account_id', '未知')}, DB ID: {acc_cfg.get('id', 0)})")

    # 获取账号的数据库 ID，传给 run_publish_pipeline 确保使用正确的账号
    account_db_id = acc_cfg.get("id", 0)

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            import main as m

            # 打印当前使用的公众号（方便用户确认）
            print(f"📱 当前使用公众号：{acc_cfg.get('name', '未知')} (ID: {acc_cfg.get('account_id', '未知')})")

            # 检查文章是否已经发布过
            file_name_only = Path(md_path).name if md_path else None
            if file_name_only:
                from modules.user_db import UserDB
                db = UserDB()
                existing = db.get_article_by_filename_and_account(file_name_only, account_db_id)
                if existing and existing.get("status") == "published":
                    warning_msg = f"⚠️ 该文章已于 {existing.get('published_at', '未知时间')} 发布过，正在重新推送..."
                    push_log(task_id, warning_msg, "warning")
                    print(f"[推送草稿] {warning_msg}")

            result = m.run_publish_pipeline(
                md_path=md_path,
                config=m.load_config(),  # AI 配置
                draft_only=True,
                preview_only=False,  # 明确传参：推送到微信，不是仅预览
                theme=theme,
                template=template,
                account_db_id=account_db_id,  # 使用选择的公众号
                user_id=current_user_id,  # 明确传递用户 ID
            )
            push_log(task_id, json.dumps(result, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：定时任务管理
# ════════════════════════════════════════════════════════════

@app.route("/api/schedule", methods=["GET"])
def api_get_schedule():
    """获取所有定时任务配置 + 状态"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        tasks = db.get_user_scheduled_tasks(user["id"])

        # 获取所有启用任务的下次执行时间
        tasks_with_next_run = []
        for task in tasks:
            task_dict = {
                "id": task["id"],
                "enabled": bool(task["enabled"]),
                "hour": task["hour"],
                "minute": task["minute"],
                "draft_only": bool(task["draft_only"]),
                "account_id": task["account_id"],
                "account_name": task.get("account_name"),
                "account_str_id": task.get("account_str_id"),
                "created_at": task.get("created_at"),
                "execution_mode": task.get("execution_mode", "serial"),  # 执行模式
            }
            # 如果任务已启用，计算下次执行时间
            if task["enabled"]:
                task_dict["next_run"] = _calculate_next_run(task["hour"], task["minute"])
            tasks_with_next_run.append(task_dict)

        return jsonify({
            "tasks": tasks_with_next_run,
            "scheduler_running": _scheduler is not None and _scheduler.running,
        })


def _calculate_next_run(hour: int, minute: int) -> str:
    """计算下次执行时间"""
    now = datetime.now()
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        # 如果今天的时间已过，设置为明天
        from datetime import timedelta
        next_run += timedelta(days=1)
    return next_run.strftime("%Y-%m-%d %H:%M:%S")


@app.route("/api/schedule", methods=["POST"])
def api_save_schedule():
    """保存定时任务配置（新增或更新）"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    task_id = data.get("id")  # 任务 ID，为空表示新增
    account_db_id = data.get("account_id")
    hour = int(data.get("hour", 8))
    minute = int(data.get("minute", 0))
    draft_only = bool(data.get("draft_only", True))
    enabled = bool(data.get("enabled", False))
    execution_mode = data.get("execution_mode", "serial")  # 执行模式：serial 或 parallel

    if not account_db_id:
        return jsonify({"error": "请选择公众号账号"}), 400

    # 验证 execution_mode 值
    if execution_mode not in ("serial", "parallel"):
        return jsonify({"error": "执行模式必须是 serial（串行）或 parallel（并行）"}), 400

    with UserDB() as db:
        # 验证账号是否存在且属于当前用户
        account = db.get_account_by_id(account_db_id)
        if not account or account["user_id"] != user["id"]:
            return jsonify({"error": "账号不存在或无权操作"}), 404

        if task_id:
            # 更新现有任务
            success = db.update_scheduled_task(
                task_id=task_id,
                user_id=user["id"],
                account_db_id=account_db_id,
                hour=hour,
                minute=minute,
                draft_only=draft_only,
                enabled=enabled,
                execution_mode=execution_mode,
            )
            if not success:
                return jsonify({"error": "更新失败"}), 500
        else:
            # 新增任务
            task_id = db.create_scheduled_task(
                user_id=user["id"],
                account_db_id=account_db_id,
                hour=hour,
                minute=minute,
                draft_only=draft_only,
                enabled=enabled,
                execution_mode=execution_mode,
            )
            if not task_id:
                return jsonify({"error": "创建失败"}), 500

        # 立即重新加载调度器，使配置生效（无需重启服务）
        if _scheduler:
            print(f"[Scheduler] 配置已更新，重新加载调度器...")
            # 重新加载所有用户的调度任务（确保单个任务更新也能正确应用）
            _apply_all_user_schedules()
            print(f"[Scheduler] 调度器已重新加载")

        return jsonify({"ok": True, "id": task_id})


@app.route("/api/schedule/<int:task_id>", methods=["DELETE"])
def api_delete_schedule(task_id: int):
    """删除定时任务"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        success = db.delete_scheduled_task(task_id, user["id"])
        if success:
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "删除失败"}), 404


@app.route("/api/schedule/run", methods=["POST"])
def api_schedule_run_now():
    """立即触发一次定时任务（测试用）"""
    task_id = "schedule_now"
    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            _run_scheduled_task()
            push_log(task_id, json.dumps({"done": True}, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


@app.route("/api/schedule/logs", methods=["GET"])
def api_schedule_logs():
    """获取定时任务历史运行日志（内存中的简单日志）"""
    with _schedule_lock:
        return jsonify({"logs": list(_schedule_log)})


@app.route("/api/schedule/runs", methods=["GET"])
def api_schedule_runs():
    """获取定时任务执行记录（数据库中的详细记录）"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    task_id = request.args.get("task_id", type=int)  # 可选：指定任务的执行记录
    page = request.args.get("page", type=int, default=1)  # 页码，从 1 开始
    page_size = request.args.get("page_size", type=int, default=10)  # 每页记录数

    # 计算偏移量
    offset = (page - 1) * page_size

    with UserDB() as db:
        if task_id:
            # 指定任务的执行记录（不分页）
            runs = db.get_task_runs_by_task_id(task_id, user["id"], limit=50)
            total = len(runs)
        else:
            # 用户所有执行记录（分页）
            runs = db.get_user_task_runs(user["id"], limit=page_size, offset=offset)
            # 获取总记录数
            total = db.get_user_task_runs_count(user["id"])

        # 统一时间格式：将所有时间转换为带时区后缀的 ISO 8601 格式
        # 注意：数据库中 started_at 和 finished_at 都是本地时间（北京时间），只是格式不同
        # started_at: SQLite TIMESTAMP 格式 "2026-04-05 14:24:00"
        # finished_at: Python isoformat 格式 "2026-04-05T22:25:34.955125"
        # 两者都代表北京时间，统一添加 +08:00 时区后缀
        for run in runs:
            if run.get("started_at"):
                # started_at: "2026-04-05 14:24:00" -> "2026-04-05T14:24:00+08:00"
                if " " in run["started_at"]:
                    run["started_at"] = run["started_at"].replace(" ", "T") + "+08:00"
            if run.get("finished_at"):
                # finished_at: "2026-04-05T22:25:34.955125" -> "2026-04-05T22:25:34.955125+08:00"
                if not run["finished_at"].endswith("Z") and "+" not in run["finished_at"]:
                    run["finished_at"] = run["finished_at"] + "+08:00"

        print(f"[API] 加载定时任务运行记录: 用户 {user['id']}, 记录数 {len(runs)}, 总数 {total}")

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        return jsonify({
            "runs": runs,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages
            }
        })


@app.route("/api/schedule/run/<int:run_id>", methods=["GET"])
def api_schedule_run_detail(run_id: int):
    """获取单条定时任务执行记录的详细信息（含完整日志）"""
    # 检查登录状态
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT r.*, t.hour, t.minute, t.draft_only,
                   acc.name as account_name, acc.account_id as account_str_id,
                   art.title as article_title
            FROM scheduled_task_runs r
            LEFT JOIN scheduled_tasks t ON r.task_id = t.id
            LEFT JOIN accounts acc ON r.account_id = acc.id
            LEFT JOIN articles art ON r.article_id = art.id
            WHERE r.id = ? AND r.user_id = ?
            """,
            (run_id, user["id"])
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "执行记录不存在"}), 404

        run_data = dict(row)

        # 统一时间格式：将所有时间转换为带时区后缀的 ISO 8601 格式
        # 注意：数据库中 started_at 和 finished_at 都是本地时间（北京时间），只是格式不同
        # started_at: SQLite TIMESTAMP 格式 "2026-04-05 14:24:00"
        # finished_at: Python isoformat 格式 "2026-04-05T22:25:34.955125"
        # 两者都代表北京时间，统一添加 +08:00 时区后缀
        if run_data.get("started_at"):
            # started_at: "2026-04-05 14:24:00" -> "2026-04-05T14:24:00+08:00"
            if " " in run_data["started_at"]:
                run_data["started_at"] = run_data["started_at"].replace(" ", "T") + "+08:00"

        if run_data.get("finished_at"):
            # finished_at: "2026-04-05T22:25:34.955125" -> "2026-04-05T22:25:34.955125+08:00"
            if not run_data["finished_at"].endswith("Z") and "+" not in run_data["finished_at"]:
                run_data["finished_at"] = run_data["finished_at"] + "+08:00"

        return jsonify(run_data)



# ════════════════════════════════════════════════════════════
# API：每日热搜榜
# ════════════════════════════════════════════════════════════

@app.route("/api/hotrank/<platform_id>", methods=["GET"])
def api_hotrank(platform_id: str):
    """获取指定平台热搜榜"""
    from modules.hotrank import get_hotrank, PLATFORMS
    data = get_hotrank(platform_id)
    return jsonify(data)


@app.route("/api/hotrank", methods=["GET"])
def api_hotrank_platforms():
    """获取所有平台列表"""
    from modules.hotrank import PLATFORMS
    return jsonify({
        "ok": True,
        "platforms": [{"id": p["id"], "name": p["name"], "icon": p["icon"]} for p in PLATFORMS],
    })


# ════════════════════════════════════════════════════════════
# API：历史上的今天
# ════════════════════════════════════════════════════════════

@app.route("/api/today_in_history", methods=["GET"])
def api_today_in_history():
    """获取历史上的今天数据"""
    from modules.today_in_history import get_today_in_history
    try:
        data = get_today_in_history()
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ════════════════════════════════════════════════════════════
# API：AI 助手
# ════════════════════════════════════════════════════════════

@app.route("/api/ai_assistant/chat", methods=["POST"])
def api_ai_assistant_chat():
    """AI 助手对话接口"""
    from modules.ai_assistant import quick_chat, add_to_history
    
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401
    
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    mode = data.get("mode", "chat")
    
    if not message:
        return jsonify({"ok": False, "error": "消息不能为空"}), 400
    
    try:
        # 传递 user_id 以读取数据库中的 AI 配置
        result = quick_chat(message, mode=mode, user_id=user["id"])
        
        if result.get("ok"):
            # 保存到历史
            add_to_history(session_id, "user", message)
            add_to_history(session_id, "assistant", result.get("content", ""))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai_assistant/clear", methods=["POST"])
def api_ai_assistant_clear():
    """清空对话历史"""
    from modules.ai_assistant import clear_history
    
    session_id = _get_session_id() or "anonymous"
    clear_history(session_id)
    
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
# API：封面制作
# ════════════════════════════════════════════════════════════

@app.route("/api/cover_maker/generate", methods=["POST"])
def api_cover_maker_generate():
    """生成封面"""
    from modules.cover_maker import generate_cover, STYLE_PRESETS

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    style = data.get("style", "minimal")
    size = data.get("size", "wide")
    custom_prompt = data.get("custom_prompt", "").strip()

    if not title and not custom_prompt:
        return jsonify({"ok": False, "error": "请输入文章标题或自定义描述"}), 400

    try:
        result = generate_cover(
            title=title,
            content=content,
            style=style,
            size=size,
            custom_prompt=custom_prompt,
            user_id=user["id"],
        )
        # 附加风格中文名
        if result.get("ok") and style in STYLE_PRESETS:
            result["style_name"] = STYLE_PRESETS[style]["name"]
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cover_maker/history", methods=["GET"])
def api_cover_maker_history():
    """获取封面生成历史"""
    from modules.cover_maker import get_cover_history, STYLE_PRESETS

    session_id = _get_session_id()
    user = get_current_user(session_id)
    user_id = user["id"] if user else None

    try:
        history = get_cover_history(user_id=user_id, limit=20)
        # 附加风格中文名
        for item in history:
            style = item.get("style", "")
            if style in STYLE_PRESETS:
                item["style_name"] = STYLE_PRESETS[style]["name"]
        return jsonify({"ok": True, "data": history})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cover_maker/delete", methods=["POST"])
def api_cover_maker_delete():
    """删除封面"""
    from modules.cover_maker import delete_cover

    session_id = _get_session_id()
    user = get_current_user(session_id)
    user_id = user["id"] if user else None

    data = request.get_json() or {}
    filename = data.get("filename", "").strip()

    if not filename:
        return jsonify({"ok": False, "error": "缺少文件名"}), 400

    # 安全检查：只允许删除 cover_ 开头的文件
    if not filename.startswith("cover_") or ".." in filename:
        return jsonify({"ok": False, "error": "非法文件名"}), 400

    try:
        success = delete_cover(filename, user_id=user_id)
        return jsonify({"ok": success})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cover_maker/image/<filename>")
def api_cover_maker_image(filename):
    """提供生成的封面图片"""
    from modules.cover_maker import OUTPUT_DIR

    # 安全检查
    if not filename.startswith("cover_") or ".." in filename:
        return "Forbidden", 403

    return send_from_directory(str(OUTPUT_DIR), filename)


# ════════════════════════════════════════════════════════════
# API：素材库
# ════════════════════════════════════════════════════════════

@app.route("/api/material_library", methods=["GET"])
def api_get_materials():
    """获取素材库列表"""
    from modules.material_library import get_materials

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    tag = request.args.get("tag")
    source_type = request.args.get("source_type")
    keyword = request.args.get("keyword")
    group_id = request.args.get("group_id")
    page = request.args.get("page", type=int, default=1)
    page_size = request.args.get("page_size", type=int, default=20)

    offset = (page - 1) * page_size

    result = get_materials(
        user_id=user["id"],
        tag=tag,
        source_type=source_type,
        keyword=keyword,
        group_id=group_id,
        limit=page_size,
        offset=offset,
    )
    return jsonify(result)


@app.route("/api/material_library", methods=["POST"])
def api_add_material():
    """收藏到素材库"""
    from modules.material_library import add_to_library

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    title = data.get("title", "").strip()
    tags = data.get("tags", "").strip()
    source_type = data.get("source_type", "cover")
    source_id = data.get("source_id")
    filename = data.get("filename", "").strip()
    image_url = data.get("image_url", "").strip()
    prompt = data.get("prompt", "").strip()
    notes = data.get("notes", "").strip()
    group_id = data.get("group_id")

    if not filename:
        return jsonify({"ok": False, "error": "文件名不能为空"}), 400

    result = add_to_library(
        user_id=user["id"],
        title=title,
        tags=tags,
        source_type=source_type,
        source_id=source_id,
        filename=filename,
        image_url=image_url,
        prompt=prompt,
        notes=notes,
        group_id=group_id,
    )
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_library/<int:material_id>", methods=["GET"])
def api_get_material(material_id: int):
    """获取单个素材详情"""
    from modules.material_library import get_material_by_id

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    item = get_material_by_id(material_id, user["id"])
    if item:
        return jsonify({"ok": True, **item})
    else:
        return jsonify({"ok": False, "error": "素材不存在"}), 404


@app.route("/api/material_library/<int:material_id>", methods=["PUT"])
def api_update_material(material_id: int):
    """更新素材信息"""
    from modules.material_library import update_material

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    title = data.get("title")
    tags = data.get("tags")
    notes = data.get("notes")

    success = update_material(material_id, user["id"], title, tags, notes)
    if success:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "更新失败"}), 500


@app.route("/api/material_library/<int:material_id>", methods=["DELETE"])
def api_delete_material(material_id: int):
    """删除素材"""
    from modules.material_library import delete_material

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    success = delete_material(material_id, user["id"])
    if success:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "删除失败"}), 500


@app.route("/api/material_library/tags", methods=["GET"])
def api_get_material_tags():
    """获取素材库所有标签"""
    from modules.material_library import get_all_tags

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    tags = get_all_tags(user["id"])
    return jsonify({"ok": True, "tags": tags})


@app.route("/api/material_library/image/<filename>")
def api_material_library_image(filename):
    """提供素材库图片"""
    from modules.material_library import MATERIAL_DIR

    # 安全检查：允许 mat_ 和 upload_ 前缀
    if (not filename.startswith("mat_") and not filename.startswith("upload_")) or ".." in filename:
        return "Forbidden", 403

    return send_from_directory(str(MATERIAL_DIR), filename)


@app.route("/api/material_library/upload", methods=["POST"])
def api_upload_material():
    """上传本地图片到素材库"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    from modules.material_library import upload_image

    title = request.form.get("title", "").strip()
    tags = request.form.get("tags", "").strip()
    group_id = request.form.get("group_id", type=int)
    notes = request.form.get("notes", "").strip()

    result = upload_image(
        user_id=user["id"],
        file_data=file.read(),
        original_filename=file.filename,
        title=title,
        tags=tags,
        group_id=group_id,
        notes=notes,
    )

    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


# ── 素材分组 API ──────────────────────────────────────────

@app.route("/api/material_groups", methods=["GET"])
def api_get_material_groups():
    """获取素材分组列表"""
    from modules.material_library import get_groups

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    groups = get_groups(user["id"])
    return jsonify({"ok": True, "data": groups})


@app.route("/api/material_groups", methods=["POST"])
def api_create_material_group():
    """创建素材分组"""
    from modules.material_library import create_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    sort_order = data.get("sort_order", 0)

    if not name:
        return jsonify({"ok": False, "error": "分组名称不能为空"}), 400

    result = create_group(user["id"], name, sort_order)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_groups/<int:group_id>", methods=["PUT"])
def api_update_material_group(group_id: int):
    """更新素材分组"""
    from modules.material_library import update_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    name = data.get("name")
    sort_order = data.get("sort_order")

    result = update_group(group_id, user["id"], name=name, sort_order=sort_order)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_groups/<int:group_id>", methods=["DELETE"])
def api_delete_material_group(group_id: int):
    """删除素材分组"""
    from modules.material_library import delete_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    move_to_none = request.args.get("move", "true") == "true"
    result = delete_group(group_id, user["id"], move_to_none=move_to_none)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_library/<int:material_id>/move", methods=["POST"])
def api_move_material(material_id: int):
    """移动素材到指定分组"""
    from modules.material_library import move_material_to_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    group_id = data.get("group_id")  # None = 移到未分组

    result = move_material_to_group(material_id, user["id"], group_id=group_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


# ════════════════════════════════════════════════════════════
# API：链接改写 V2（五步流水线）
# ════════════════════════════════════════════════════════════

@app.route("/api/rewrite_v2", methods=["POST"])
def api_rewrite_v2():
    """
    链接改写 V2 — 五步流水线：
      1. 提取链接内容
      2. AI 观点提取（风格 + 摘要 + 核心观点）
      3. AI 文章仿写
      4. AI 爆款标题生成
      5. 文章排版（Markdown → 公众号 HTML）
    """
    data = request.json or {}
    task_id = data.get("task_id", "rewrite_v2")
    url = data.get("url", "").strip()
    content = data.get("content", "").strip()
    extra_instructions = data.get("extra_instructions", "")

    if not url and not content:
        return jsonify({"ok": False, "error": "请提供文章链接或文章内容"}), 400

    # 预先获取 user_id
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.article_rewriter import run_rewrite_pipeline

            def on_step(step_num, step_name, step_data):
                """步骤回调，推送进度到前端"""
                step_msg = {"step": step_num, "name": step_name}
                if isinstance(step_data, dict):
                    # 步骤完成：把含数据的完整 dict 序列化成 JSON 推送给前端
                    step_msg.update(step_data)
                    push_log(task_id, json.dumps(step_msg, ensure_ascii=False), "result")
                else:
                    # 步骤开始执行（step_data 为 None），通知前端切换为 running 状态
                    push_log(task_id, json.dumps(step_msg, ensure_ascii=False), "running")
                push_log(task_id, f"   [{step_num}/7] {step_name}", "info")

            print(f"   🚀 开始五步改写流水线...")
            result = run_rewrite_pipeline(
                url=url,
                content=content,
                user_id=current_user_id,
                extra_instructions=extra_instructions,
                on_step=on_step,
            )

            # 推送最终完整结果
            final_result = {
                "title": result.get("title", ""),
                "article_body": result.get("article_body", ""),
                "wechat_html": result.get("wechat_html", ""),
                "analysis": result.get("analysis", {}),
                "original_title": result.get("original_title", ""),
            }

            # 保存 Markdown 文件
            from datetime import datetime
            from modules.ai_writer import OUTPUT_DIR
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', result.get("title", "rewrite")[:30])
            filename = f"{timestamp}_{safe_title}.md"
            saved_path = str(OUTPUT_DIR / filename)

            full_md = f"# {result.get('title', '')}\n\n{result.get('article_body', '')}"
            with open(saved_path, "w", encoding="utf-8") as f:
                f.write(full_md)

            final_result["saved_path"] = saved_path

            # 保存到数据库
            acc_cfg = get_account_config(data.get("account_id", ""))
            account_db_id = acc_cfg.get("id", 0) if acc_cfg else 0
            if account_db_id > 0 and saved_path:
                try:
                    db = UserDB()
                    article_id = db.create_article(
                        user_id=current_user_id,
                        account_db_id=account_db_id,
                        title=result.get("title", "改写文章"),
                        file_path=Path(saved_path).name,
                        status="draft",
                    )
                    if article_id:
                        push_log(task_id, f"   文章已保存到数据库（ID: {article_id}）", "info")
                except Exception as e:
                    push_log(task_id, f"   保存文章到数据库时出错：{e}", "warning")

            push_log(task_id, json.dumps(final_result, ensure_ascii=False), "result")

            # ── Step 6: 自动生成封面 ──
            try:
                on_step(6, "正在生成封面...", None)
                from modules.cover_maker import generate_cover
                article_title = result.get("title", "")
                article_summary = result.get("article_body", "")[:500] if result.get("article_body") else ""
                cover_result = generate_cover(
                    title=article_title,
                    content=article_summary,
                    style="minimal",
                    size="wide",
                    user_id=current_user_id,
                )
                if cover_result.get("ok"):
                    on_step(6, "封面生成完成", {
                        "cover_url": cover_result.get("image_url", ""),
                        "cover_filename": cover_result.get("filename", ""),
                    })
                    final_result["cover_url"] = cover_result.get("image_url", "")
                    final_result["cover_filename"] = cover_result.get("filename", "")
                else:
                    on_step(6, "封面生成跳过", {
                        "cover_error": cover_result.get("error", "未知错误"),
                    })
                    push_log(task_id, f"   ⚠️ 封面生成跳过：{cover_result.get('error', '')}", "warning")
            except Exception as cover_err:
                on_step(6, "封面生成跳过", {"cover_error": str(cover_err)})
                push_log(task_id, f"   ⚠️ 封面生成失败（已跳过）：{cover_err}", "warning")

            # ── Step 7: 自动推送草稿 ──
            try:
                on_step(7, "正在推送草稿...", None)
                acc_cfg = get_account_config(data.get("account_id", ""))
                account_db_id = acc_cfg.get("id", 0) if acc_cfg else 0

                if account_db_id > 0 and saved_path:
                    import main as m
                    publish_result = m.run_publish_pipeline(
                        md_path=saved_path,
                        config=m.load_config(),
                        draft_only=True,
                        preview_only=False,
                        theme="blue",
                        account_db_id=account_db_id,
                        user_id=current_user_id,
                    )
                    if publish_result.get("success"):
                        on_step(7, "草稿推送完成", {
                            "draft_status": "pushed",
                            "media_id": publish_result.get("media_id", ""),
                        })
                    else:
                        on_step(7, "草稿推送失败", {
                            "draft_status": "failed",
                            "draft_error": publish_result.get("msg", "未知错误"),
                        })
                        push_log(task_id, f"   ⚠️ 推送失败：{publish_result.get('msg', '')}", "warning")
                else:
                    on_step(7, "草稿推送跳过", {
                        "draft_status": "skipped",
                        "draft_error": "未配置公众号账号" if account_db_id <= 0 else "文章未保存",
                    })
                    push_log(task_id, "   ⚠️ 草稿推送跳过：未配置公众号账号", "warning")
            except Exception as pub_err:
                on_step(7, "草稿推送跳过", {
                    "draft_status": "skipped",
                    "draft_error": str(pub_err),
                })
                push_log(task_id, f"   ⚠️ 草稿推送失败（已跳过）：{pub_err}", "warning")

            push_log(task_id, "   ✅ 全部流水线完成！", "done")

        except Exception as e:
            push_log(task_id, f"   ❌ 流水线失败：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# API：文档改写
# ════════════════════════════════════════════════════════════

@app.route("/api/document/parse", methods=["POST"])
def api_document_parse():
    """解析上传的文档为纯文本"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    try:
        from modules.document_parser import parse_document
        content = parse_document(file.read(), file.filename)
        return jsonify({"ok": True, "content": content})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 422


@app.route("/api/document/rewrite", methods=["POST"])
def api_document_rewrite():
    """将文档内容改写为公众号文章（SSE 流式）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    content = (data.get("content") or "").strip()
    style = data.get("style", "观点评论")
    word_count = max(500, min(int(data.get("word_count", 2000)), 10000))
    ending_text = (data.get("ending_text") or "").strip()
    no_ending = data.get("no_ending", False)
    task_id = data.get("task_id", str(uuid.uuid4()))
    account_id = (data.get("account_id") or "").strip()

    if not content:
        return jsonify({"error": "内容为空"}), 400
    if len(content) > 100000:
        return jsonify({"error": "内容过长（最大 100KB），请缩减后重试"}), 400
    if not account_id:
        return jsonify({"error": "请选择账号"}), 400

    acc_cfg = get_account_config(account_id)
    if not acc_cfg:
        return jsonify({"error": "账号配置不存在"}), 400

    current_user_id = user["id"]
    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.article_rewriter import rewrite_article
            # 构建额外指令（结尾词）
            extra = ''
            if no_ending:
                extra = '\n## 结尾要求\n文章不要添加任何结尾词或结束语，内容结束即可。'
            elif ending_text:
                extra = f'\n## 结尾要求\n文章结尾必须使用以下文字：{ending_text}'

            # 构建结尾词指令
            ending_text_str = f"\n## 结尾要求\n文章结尾必须使用以下文字：{ending_text}" if ending_text else ""

            result = rewrite_article(
                original_title="文档改写",
                original_content=content,
                user_id=current_user_id,
                word_count=word_count,
                style=style,
                extra_instructions=extra,
                no_ending=no_ending,
                ending_text=ending_text_str,
            )
            push_log(task_id, json.dumps({
                "md_content": result,
                "msg": "__DONE__",
                "level": "done"
            }, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 改写失败：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)
            _log_queues.pop(task_id, None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5678))
    print(f"\n🚀 微信公众号管理界面启动中...")
    print(f"   打开浏览器访问：http://localhost:{port}\n")

    # 初始化默认用户
    with UserDB() as db:
        admin = db.get_user_by_username("admin")
        if not admin:
            db.create_user("admin", "123456", role="admin")
            print("✅ 默认用户已创建：admin / 123456\n")

    # 初始化系统领域分类
    from modules.user_db import init_system_domains
    init_system_domains()

    _init_scheduler()   # 初始化定时调度器

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
