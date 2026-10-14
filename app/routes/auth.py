#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 认证路由

重构要点：
- 全面输入校验（长度/格式/密码强度），修复可注册 1 字符密码与超长用户名
- 登录失败锁定，修复可无限爆破
- SQL 列名白名单 + 参数化，消除拼接隐患
- 资料更新字段级校验，修复可写入 100000 字符昵称
- 明确异常处理，替换裸 except
"""

import logging
from datetime import datetime

from flask import Blueprint, current_app, g, request

from .. import database as db
from ..responses import ApiError, success
from ..security import (
    auth_required,
    clear_login_failures,
    create_token,
    get_client_ip,
    hash_password,
    login_guard,
    rate_limit,
    register_login_failure,
    verify_password,
)
from ..validators import (
    PROFILE_TEXT_FIELDS,
    clean_text,
    require_fields,
    require_json,
    validate_email,
    validate_gender,
    validate_password,
    validate_phone,
    validate_username,
)

logger = logging.getLogger("FUCKCHAT.auth")

auth_bp = Blueprint("auth", __name__)


def _serialize_user(row, include_private=False):
    """统一的用户序列化，避免各接口字段不一致。"""
    data = {
        "id": row["id"],
        "username": row["username"],
        "nickname": row["nickname"],
        "avatar": row.get("avatar") or "/src/images/default-avatar.png",
        "gender": row.get("gender") or "other",
        "signature": row.get("signature") or "",
        "location": row.get("location") or "",
        "status": row.get("status") or "offline",
        "isAdmin": bool(row.get("is_admin", 0)),
        "kunbi": row.get("kunbi", 0),
        "createdAt": row.get("created_at"),
    }
    if include_private:
        data.update(
            {
                "email": row.get("email") or "",
                "phone": row.get("phone") or "",
                "birthday": row.get("birthday") or "",
                "lastLoginAt": row.get("last_login_at"),
            }
        )
    return data


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------


@auth_bp.route("/register", methods=["POST"])
@rate_limit("register", max_requests=20, window=60)
def register():
    """用户注册，带完整输入校验。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["username", "password", "nickname"])

    username = validate_username(data.get("username"))
    password = validate_password(data.get("password"))
    nickname = clean_text(data.get("nickname"), "昵称", 32)

    email = validate_email(data.get("email")) if data.get("email") else ""
    if email and db.query_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise ApiError("该邮箱已被注册", 409)

    if db.query_one("SELECT id FROM users WHERE username = ?", (username,)):
        raise ApiError("用户名已存在", 409)

    default_kunbi = current_app.config["FUCKCHAT_CONFIG"].section("user").get(
        "default_kunbi", 100
    )

    user_id = db.execute(
        """
        INSERT INTO users (username, password_hash, nickname, email, kunbi, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'offline')
        """,
        (username, hash_password(password), nickname, email, default_kunbi, datetime.now()),
    )

    logger.info("新用户注册成功: %s (id=%s)", username, user_id)

    row = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return success(
        {"user": _serialize_user(row, include_private=True)}, message="注册成功", status_code=201
    )


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------


@auth_bp.route("/login", methods=["POST"])
@rate_limit("login", max_requests=20, window=60)
def login():
    """用户登录，带失败锁定。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["username", "password"])

    username = str(data.get("username")).strip()
    password = str(data.get("password"))

    # 以用户名 + IP 双重维度限速，防止针对单账号爆破
    identifier = f"{username}|{get_client_ip()}"
    max_attempts, lockout = login_guard(identifier)

    row = db.query_one("SELECT * FROM users WHERE username = ?", (username,))
    if not row or not verify_password(password, row["password_hash"]):
        register_login_failure(identifier, max_attempts, lockout)
        # 统一提示，不区分用户名不存在与密码错误
        raise ApiError("用户名或密码错误", 401)

    clear_login_failures(identifier)

    # 更新登录信息与在线状态
    db.execute(
        "UPDATE users SET last_login_at = ?, status = 'online' WHERE id = ?",
        (datetime.now(), row["id"]),
    )

    token = create_token(row["id"], row["username"], is_admin=bool(row["is_admin"]))
    logger.info("用户登录成功: %s", username)

    fresh = db.query_one("SELECT * FROM users WHERE id = ?", (row["id"],))
    return success(
        {"token": token, "user": _serialize_user(fresh, include_private=True)},
        message="登录成功",
    )


# ---------------------------------------------------------------------------
# 令牌校验与资料
# ---------------------------------------------------------------------------


@auth_bp.route("/verify", methods=["GET"])
@auth_required
def verify_token():
    """校验令牌有效性。"""
    return success({"userId": g.user_id, "username": g.username, "isAdmin": g.is_admin})


@auth_bp.route("/profile", methods=["GET"])
@auth_required
def get_profile():
    """获取当前登录用户信息。"""
    row = db.query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    if not row:
        raise ApiError("用户不存在", 404)
    return success({"user": _serialize_user(row, include_private=True)})


@auth_bp.route("/user/<int:user_id>", methods=["GET"])
@auth_required
def get_user_profile(user_id):
    """获取指定用户的公开信息。"""
    row = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not row:
        raise ApiError("用户不存在", 404)

    # 被拉黑则不下发资料
    blocked = db.query_one(
        """
        SELECT id FROM blacklist
        WHERE (user_id = ? AND blocked_user_id = ?)
           OR (user_id = ? AND blocked_user_id = ?)
        """,
        (g.user_id, user_id, user_id, g.user_id),
    )
    if blocked:
        raise ApiError("无法查看该用户资料", 403)

    return success({"user": _serialize_user(row)})


@auth_bp.route("/profile", methods=["POST"])
@auth_required
def update_profile():
    """
    更新个人资料。

    修复点：字段值逐个校验长度与格式；SQL 列名来自固定白名单常量。
    """
    data = require_json(request.get_json(silent=True))

    updates = {}
    for field, max_len in PROFILE_TEXT_FIELDS.items():
        if field not in data:
            continue

        raw = data[field]

        if field == "email":
            updates[field] = validate_email(raw)
        elif field == "phone":
            updates[field] = validate_phone(raw)
        elif field == "gender":
            updates[field] = validate_gender(raw)
        elif field == "nickname":
            updates[field] = clean_text(raw, "昵称", max_len)
        else:
            updates[field] = clean_text(raw, field, max_len, allow_empty=True)

    if not updates:
        raise ApiError("没有有效的更新字段", 400)

    if "email" in updates and updates["email"]:
        existing = db.query_one(
            "SELECT id FROM users WHERE email = ? AND id != ?", (updates["email"], g.user_id)
        )
        if existing:
            raise ApiError("该邮箱已被其他用户使用", 409)

    # 列名来自 PROFILE_TEXT_FIELDS 固定白名单，值全部参数化
    safe_fields = [f for f in updates if f in PROFILE_TEXT_FIELDS]
    assignments = ", ".join(f"{field} = ?" for field in safe_fields)
    values = [updates[field] for field in safe_fields]
    values.append(g.user_id)

    db.execute(f"UPDATE users SET {assignments} WHERE id = ?", values)

    logger.info("用户 %s 更新资料: %s", g.user_id, safe_fields)

    _broadcast("user_update", {"user_id": g.user_id, **{f: updates[f] for f in safe_fields}})

    row = db.query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    return success({"user": _serialize_user(row, include_private=True)}, message="个人资料更新成功")


@auth_bp.route("/password", methods=["POST"])
@auth_required
def update_password():
    """修改密码，需校验原密码并满足强度要求。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["current_password", "new_password"])

    current = str(data["current_password"])
    new_password = validate_password(data["new_password"], "新密码")

    if current == new_password:
        raise ApiError("新密码不能与原密码相同", 400)

    row = db.query_one("SELECT password_hash FROM users WHERE id = ?", (g.user_id,))
    if not row or not verify_password(current, row["password_hash"]):
        raise ApiError("原密码错误", 401)

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), g.user_id),
    )
    logger.info("用户 %s 修改了密码", g.user_id)
    return success(message="密码修改成功")


@auth_bp.route("/logout", methods=["POST"])
@auth_required
def logout():
    """登出，状态置为离线。"""
    db.execute("UPDATE users SET status = 'offline' WHERE id = ?", (g.user_id,))
    _broadcast("user_offline", {"user_id": g.user_id})
    logger.info("用户 %s 已登出", g.user_id)
    return success(message="已退出登录")


@auth_bp.route("/account/delete", methods=["POST"])
@auth_required
def delete_account():
    """注销账号，需密码确认。"""
    data = request.get_json(silent=True) or {}
    require_fields(data, ["password"])
    password = str(data["password"])

    row = db.query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    if not row:
        raise ApiError("用户不存在", 404)

    if row["is_admin"]:
        raise ApiError("管理员账号不能自助注销", 403)

    if not verify_password(password, row["password_hash"]):
        raise ApiError("密码错误", 401)

    with db.transaction() as conn:
        conn.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (g.user_id, g.user_id))
        conn.execute("DELETE FROM group_members WHERE user_id = ?", (g.user_id,))
        conn.execute("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (g.user_id, g.user_id))
        conn.execute("DELETE FROM friend_requests WHERE sender_id = ? OR receiver_id = ?", (g.user_id, g.user_id))
        conn.execute("DELETE FROM blacklist WHERE user_id = ? OR blocked_user_id = ?", (g.user_id, g.user_id))
        conn.execute("DELETE FROM kunbi_transactions WHERE user_id = ?", (g.user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (g.user_id,))

    logger.info("用户 %s 已注销账号", g.user_id)
    return success(message="账号已注销")


# ---------------------------------------------------------------------------
# 辅助接口
# ---------------------------------------------------------------------------


@auth_bp.route("/check-username", methods=["GET"])
@rate_limit("check_username", max_requests=60, window=60)
def check_username():
    """检查用户名是否可用。"""
    username = request.args.get("username", "").strip()
    if not username:
        raise ApiError("缺少用户名参数", 400)
    try:
        username = validate_username(username)
    except ApiError as exc:
        return success({"available": False, "reason": exc.message})

    exists = db.query_one("SELECT id FROM users WHERE username = ?", (username,))
    return success({"available": not exists, "username": username})


@auth_bp.route("/admin/login", methods=["POST"])
@rate_limit("admin_login", max_requests=10, window=60)
def admin_login():
    """
    管理员登录。

    与原实现保持一致（走数据库 + is_admin 校验），
    但补充失败锁定与审计日志。
    """
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["username", "password"])

    username = str(data["username"]).strip()
    password = str(data["password"])

    identifier = f"admin|{username}|{get_client_ip()}"
    max_attempts, lockout = login_guard(identifier)

    row = db.query_one(
        "SELECT * FROM users WHERE username = ? AND is_admin = 1", (username,)
    )
    if not row or not verify_password(password, row["password_hash"]):
        register_login_failure(identifier, max_attempts, lockout)
        logger.warning("管理员登录失败: %s from %s", username, get_client_ip())
        raise ApiError("用户名或密码错误，或没有管理权限", 401)

    clear_login_failures(identifier)

    db.execute(
        "UPDATE users SET last_login_at = ?, status = 'online' WHERE id = ?",
        (datetime.now(), row["id"]),
    )
    _log_system("ADMIN_LOGIN", f"管理员 {username} 登录后台", row["id"])

    token = create_token(row["id"], row["username"], is_admin=True)
    logger.info("管理员登录成功: %s", username)

    return success(
        {"token": token, "user": _serialize_user(row, include_private=True)},
        message="管理员登录成功",
    )


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _broadcast(event, payload):
    """安全地广播 WebSocket 事件（无活跃连接时静默跳过）。"""
    try:
        from ..factory import socketio

        socketio.emit(event, payload)
    except Exception as exc:  # 广播失败不应影响主流程
        logging.getLogger("FUCKCHAT.auth").debug("广播 %s 失败: %s", event, exc)


def _log_system(log_type, content, user_id=None):
    """写入系统日志表，失败不阻断主流程。"""
    try:
        db.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            (log_type, content, user_id, datetime.now()),
        )
    except Exception as exc:
        logging.getLogger("FUCKCHAT.auth").debug("写系统日志失败: %s", exc)
