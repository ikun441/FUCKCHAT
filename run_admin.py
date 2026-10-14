#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 独立管理后台服务

重构说明（v2.0.0）：
    原实现问题较多，此处做了几处关键修正：

    1. 口令比对：原先 `password == config['admin']['password']` 明文比较，
       且默认值为 admin/admin。现在：
         - 若配置提供 password_hash 则用 bcrypt 校验
         - 若只提供明文 password，则启动时立即哈希后比对（仍建议改用 hash）
         - 两者都为空时，关闭基于配置的登录入口，改用数据库管理员账号
         - 使用常量时间比较，防时序攻击

    2. 数据真实性：原先 /api/admin/stats、/users、/groups、/logs 全部返回
       硬编码的假数据（"用户1..用户10"、"系统日志内容 1"），删除用户也只是
       写日志不真删。现在全部走真实数据库查询。

    3. 权限：所有管理接口统一要求已登录的会话，不再裸奔。
    4. 会话：设置 HttpOnly/SameSite/有效期，并支持安全退出。

用法:
    python run_admin.py
    python run_admin.py --daemon
    python run_admin.py --config config.yaml
"""

import argparse
import logging
import multiprocessing
import os
import signal
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from app.config import load_config
from app import database as db
from app.logging_config import setup_logging
from app.security import constant_time_compare, hash_password, verify_password
from app.validators import validate_int, validate_pagination


def parse_args():
    parser = argparse.ArgumentParser(description="FUCKCHAT 管理员后台服务")
    parser.add_argument("--config", default=str(BASE_DIR / "config.yaml"), help="配置文件路径")
    parser.add_argument("--daemon", action="store_true", help="作为守护进程运行")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    parser.add_argument("--host", default=None, help="监听地址")
    return parser.parse_args()


args = parse_args()
config = load_config(args.config)
setup_logging(config)

logger = logging.getLogger("admin_server")

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "templates"),
)
app.secret_key = config["app"]["secret_key"]
app.config["MAX_CONTENT_LENGTH"] = int(config["app"].get("max_content_length", 16 * 1024 * 1024))

# 会话安全设置
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,      # JS 不可读，防 XSS 窃取会话
    SESSION_COOKIE_SAMESITE="Lax",     # 缓解 CSRF
    PERMANENT_SESSION_LIFETIME=int(
        config.section("admin").get("session_ttl_hours", 8) * 3600
    ),
    # 局域网部署若启用 HTTPS，可打开下面这行
    # SESSION_COOKIE_SECURE=True,
)

# 绑定数据库配置（复用 app 层的数据访问）
with app.app_context():
    db.init_app(app, config)

# 管理员凭据准备
_admin_conf = config.section("admin")
_admin_username = _admin_conf.get("username") or "admin"
_admin_password_hash = _admin_conf.get("password_hash") or ""
_admin_password_plain = _admin_conf.get("password") or ""

if not _admin_password_hash and _admin_password_plain:
    # 配置里写的是明文，启动时哈希成内存中的 hash，避免明文常驻比较
    if len(_admin_password_plain) < 8:
        logger.warning(
            "配置中的管理员口令过短（建议至少 8 位）。"
            "更安全的做法是改用数据库管理员账号，或用 password_hash 字段。"
        )
    _admin_password_hash = hash_password(_admin_password_plain).decode("utf-8")
    _admin_password_plain = ""
    logger.info("管理员口令已加载并转换为哈希比对")

CONFIG_LOGIN_ENABLED = bool(_admin_password_hash)


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------


def login_required(func):
    """要求已登录管理后台。"""

    @wraps(func)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "未登录", "code": "UNAUTHORIZED"}), 401
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# 静态资源
# ---------------------------------------------------------------------------


@app.route("/css/<path:filename>")
def serve_css(filename):
    return app.send_static_file(f"css/{filename}")


@app.route("/js/<path:filename>")
def serve_js(filename):
    return app.send_static_file(f"js/{filename}")


@app.route("/src/images/<path:filename>")
def serve_images(filename):
    return app.send_static_file(f"../src/images/{filename}")


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def root_redirect():
    return redirect("/admin")


@app.route("/admin", methods=["GET"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect("/admin/dashboard")
    return render_template("html/admin/admin_login.html")


@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect("/admin")
    return render_template("html/admin/admin_dashboard.html")


@app.route("/admin/logout", methods=["GET"])
def admin_logout_page():
    session.clear()
    return redirect("/admin")


# ---------------------------------------------------------------------------
# 认证接口
# ---------------------------------------------------------------------------


@app.route("/api/admin/login", methods=["POST"])
def admin_login_api():
    """管理员登录，支持配置口令与数据库管理员账号两种方式。"""
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"}), 400

    authenticated = False
    auth_source = None

    # 方式一：配置文件中的管理员凭据（哈希比对 + 常量时间）
    if CONFIG_LOGIN_ENABLED:
        if constant_time_compare(username, _admin_username) and verify_password(
            password, _admin_password_hash
        ):
            authenticated = True
            auth_source = "config"

    # 方式二：数据库中的管理员账号（推荐）
    if not authenticated:
        with app.app_context():
            try:
                row = db.query_one(
                    "SELECT id, username, password_hash, is_admin FROM users WHERE username = ? AND is_admin = 1",
                    (username,),
                )
                if row and verify_password(password, row["password_hash"]):
                    authenticated = True
                    auth_source = "database"
            except Exception as exc:  # 数据库异常不应导致 500
                logger.error("查询管理员账号失败: %s", exc)

    if not authenticated:
        logger.warning("管理员登录失败: %s from %s", username, request.remote_addr)
        # 统一提示，不泄漏账号是否存在
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    session.permanent = True
    session["admin_logged_in"] = True
    session["admin_username"] = username
    session["admin_source"] = auth_source

    logger.info("管理员 %s 登录成功（来源: %s）", username, auth_source)
    return jsonify({"success": True, "redirect": "/admin/dashboard"})


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"success": True, "redirect": "/admin"})


# ---------------------------------------------------------------------------
# 管理接口（真实数据）
# ---------------------------------------------------------------------------


@app.route("/api/admin/stats", methods=["GET"])
@login_required
def admin_stats():
    """真实统计数据。"""
    with app.app_context():
        try:
            stats = {
                "user_count": db.query_scalar("SELECT COUNT(*) FROM users", (), 0),
                "group_count": db.query_scalar("SELECT COUNT(*) FROM groups", (), 0),
                "online_user_count": db.query_scalar(
                    "SELECT COUNT(*) FROM users WHERE status = 'online'", (), 0
                ),
                "today_message_count": db.query_scalar(
                    "SELECT COUNT(*) FROM messages WHERE date(created_at) = date('now')", (), 0
                ),
                "total_message_count": db.query_scalar("SELECT COUNT(*) FROM messages", (), 0),
            }
        except Exception as exc:
            logger.error("获取统计数据失败: %s", exc)
            return jsonify({"success": False, "message": "获取统计数据失败"}), 500

    return jsonify({"success": True, "stats": stats})


@app.route("/api/admin/users", methods=["GET"])
@login_required
def admin_users():
    """真实用户列表（分页）。"""
    try:
        page, per_page = validate_pagination(request.args)
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    offset = (page - 1) * per_page
    with app.app_context():
        try:
            total = db.query_scalar("SELECT COUNT(*) FROM users", (), 0)
            rows = db.query_all(
                """
                SELECT id, username, nickname, avatar, kunbi, is_admin, status,
                       created_at, last_login_at
                FROM users ORDER BY id LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            )
        except Exception as exc:
            logger.error("获取用户列表失败: %s", exc)
            return jsonify({"success": False, "message": "获取用户列表失败"}), 500

    users = [
        {
            "id": r["id"],
            "username": r["username"],
            "nickname": r["nickname"],
            "avatar": r["avatar"] or "/src/images/default-avatar.png",
            "kunbi": r["kunbi"],
            "is_admin": bool(r["is_admin"]),
            "status": r["status"],
            "created_at": r["created_at"],
            "last_login_at": r["last_login_at"],
        }
        for r in rows
    ]
    return jsonify(
        {
            "success": True,
            "users": users,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if per_page else 0,
            },
        }
    )


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    """真实删除用户及其关联数据。"""
    with app.app_context():
        try:
            target = db.query_one("SELECT id, username, is_admin FROM users WHERE id = ?", (user_id,))
            if not target:
                return jsonify({"success": False, "message": "用户不存在"}), 404
            if target["is_admin"]:
                return jsonify({"success": False, "message": "不能删除管理员账号"}), 403

            with db.transaction() as conn:
                conn.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
                conn.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM kunbi_transactions WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
                conn.execute("DELETE FROM blacklist WHERE user_id = ? OR blocked_user_id = ?", (user_id, user_id))
                conn.execute("DELETE FROM friend_requests WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
                conn.execute("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (user_id, user_id))
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            db.execute(
                "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, NULL, ?)",
                ("ADMIN", f"管理后台删除用户 {target['username']} (id={user_id})", datetime.now()),
            )
        except Exception as exc:
            logger.error("删除用户失败: %s", exc)
            return jsonify({"success": False, "message": "删除用户失败"}), 500

    logger.info("管理后台删除用户 ID: %s", user_id)
    return jsonify({"success": True, "message": "用户已删除"})


@app.route("/api/admin/groups", methods=["GET"])
@login_required
def admin_groups():
    """真实群组列表（分页）。"""
    try:
        page, per_page = validate_pagination(request.args)
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    offset = (page - 1) * per_page
    with app.app_context():
        try:
            total = db.query_scalar("SELECT COUNT(*) FROM groups", (), 0)
            rows = db.query_all(
                """
                SELECT gp.id, gp.name, gp.description, gp.created_at,
                       u.id AS creator_id, u.username AS creator_username,
                       (SELECT COUNT(*) FROM group_members WHERE group_id = gp.id) AS member_count
                FROM groups gp
                LEFT JOIN users u ON u.id = gp.creator_id
                ORDER BY gp.id LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            )
        except Exception as exc:
            logger.error("获取群组列表失败: %s", exc)
            return jsonify({"success": False, "message": "获取群组列表失败"}), 500

    groups = [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"] or "",
            "member_count": r["member_count"],
            "created_at": r["created_at"],
            "creator": {"id": r["creator_id"], "username": r["creator_username"]},
        }
        for r in rows
    ]
    return jsonify(
        {
            "success": True,
            "groups": groups,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if per_page else 0,
            },
        }
    )


@app.route("/api/admin/logs", methods=["GET"])
@login_required
def admin_logs():
    """真实系统日志（分页）。"""
    try:
        page, per_page = validate_pagination(request.args)
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    offset = (page - 1) * per_page
    with app.app_context():
        try:
            total = db.query_scalar("SELECT COUNT(*) FROM system_logs", (), 0)
            rows = db.query_all(
                """
                SELECT l.id, l.type, l.content, l.created_at, u.username
                FROM system_logs l
                LEFT JOIN users u ON u.id = l.user_id
                ORDER BY l.created_at DESC LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            )
        except Exception as exc:
            logger.error("获取日志失败: %s", exc)
            return jsonify({"success": False, "message": "获取日志失败"}), 500

    logs = [
        {
            "id": r["id"],
            "type": r["type"],
            "content": r["content"],
            "username": r["username"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify(
        {
            "success": True,
            "logs": logs,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if per_page else 0,
            },
        }
    )


@app.route("/admin/health", methods=["GET"])
def health_check():
    """健康检查，同时报告数据库连通性。"""
    db_ok = True
    try:
        with app.app_context():
            db.query_scalar("SELECT 1", (), None)
    except Exception as exc:
        logger.error("健康检查数据库异常: %s", exc)
        db_ok = False

    return (
        jsonify(
            {
                "status": "ok" if db_ok else "degraded",
                "database": "ok" if db_ok else "error",
                "timestamp": datetime.now().isoformat(),
                "service": "admin",
            }
        ),
        200 if db_ok else 503,
    )


# ---------------------------------------------------------------------------
# 守护进程
# ---------------------------------------------------------------------------


def run_server(host, port, debug=False):
    logger.info("=" * 56)
    logger.info("FUCKCHAT 管理后台启动 - http://%s:%s/admin", host, port)
    logger.info("=" * 56)
    app.run(host=host, port=port, debug=debug, use_reloader=False)


def daemonize(host, port):
    """以守护进程方式运行。"""
    pid = os.fork()
    if pid > 0:
        print(f"管理后台已在后台启动 (PID: {pid})")
        sys.exit(0)

    os.setsid()
    os.umask(0)

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    log_path = config.resolve_path(config.section("logging").get("filename", "logs/fuckchat.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_file:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(log_file.fileno(), sys.stdout.fileno())
        os.dup2(log_file.fileno(), sys.stderr.fileno())

    def handle_signal(signum, frame):
        logger.info("收到信号 %s，管理后台退出", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    run_server(host, port)


def main():
    host = args.host or config.section("admin").get("host", "127.0.0.1")
    port = args.port or config.section("admin").get("port", 5004)

    if args.daemon:
        if not hasattr(os, "fork"):
            logger.error("当前系统不支持守护进程模式（仅 Unix）")
            sys.exit(1)
        daemonize(host, port)
    else:
        run_server(host, port)


if __name__ == "__main__":
    main()
