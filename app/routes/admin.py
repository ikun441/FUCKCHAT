#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 管理后台路由

重构要点：
- 移除裸 except，统一异常与响应格式
- 补齐原前端调用但后端缺失的 10 个管理接口
- 删除/变更操作写入系统日志，可审计
- 分页统一带上限保护
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime

from flask import Blueprint, current_app, g, request

from .. import database as db
from ..responses import ApiError, paginated, success
from ..security import admin_required
from ..validators import (
    clean_text,
    require_fields,
    require_json,
    validate_int,
    validate_pagination,
)

logger = logging.getLogger("FUCKCHAT.admin")

admin_bp = Blueprint("admin", __name__)


def _log_admin(action, detail):
    """记录管理员操作到系统日志。"""
    try:
        db.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            ("ADMIN", f"{action}: {detail}", g.user_id, datetime.now()),
        )
    except Exception as exc:
        logger.debug("写管理员日志失败: %s", exc)


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------


@admin_bp.route("/stats", methods=["GET"])
@admin_required
def get_stats():
    """系统统计信息。"""
    stats = {
        "totalUsers": db.query_scalar("SELECT COUNT(*) FROM users", (), 0),
        "onlineUsers": db.query_scalar(
            "SELECT COUNT(*) FROM users WHERE status = 'online'", (), 0
        ),
        "totalGroups": db.query_scalar("SELECT COUNT(*) FROM groups", (), 0),
        "totalMessages": db.query_scalar("SELECT COUNT(*) FROM messages", (), 0),
        "todayMessages": db.query_scalar(
            "SELECT COUNT(*) FROM messages WHERE date(created_at) = date('now')", (), 0
        ),
        "totalKunbi": db.query_scalar(
            "SELECT COALESCE(SUM(kunbi), 0) FROM users", (), 0
        ),
        "adminCount": db.query_scalar(
            "SELECT COUNT(*) FROM users WHERE is_admin = 1", (), 0
        ),
    }

    # 近 7 天消息趋势，供仪表盘绘图
    trend = db.query_all(
        """
        SELECT date(created_at) AS day, COUNT(*) AS count
        FROM messages
        WHERE created_at >= date('now', '-7 days')
        GROUP BY date(created_at)
        ORDER BY day
        """
    )
    stats["messageTrend"] = [
        {"date": row["day"], "count": row["count"]} for row in trend
    ]
    return success(stats)


# ---------------------------------------------------------------------------
# 用户管理
# ---------------------------------------------------------------------------


@admin_bp.route("/users", methods=["GET"])
@admin_required
def get_all_users():
    """用户列表（分页 + 搜索）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size
    keyword = request.args.get("keyword", "").strip()

    where = ""
    params = []
    if keyword:
        where = "WHERE username LIKE ? OR nickname LIKE ?"
        like = f"%{keyword}%"
        params = [like, like]

    total = db.query_scalar(f"SELECT COUNT(*) FROM users {where}", params, 0)
    rows = db.query_all(
        f"""
        SELECT id, username, nickname, avatar, gender, kunbi, is_admin, status,
               created_at, last_login_at
        FROM users {where}
        ORDER BY id
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )

    items = [
        {
            "id": row["id"],
            "username": row["username"],
            "nickname": row["nickname"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "gender": row["gender"],
            "kunbi": row["kunbi"],
            "isAdmin": bool(row["is_admin"]),
            "status": row["status"],
            "createdAt": row["created_at"],
            "lastLoginAt": row["last_login_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, users=items)


@admin_bp.route("/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    """更新用户（昵称/坤币/状态/管理员标记）。"""
    data = require_json(request.get_json(silent=True))
    target = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not target:
        raise ApiError("用户不存在", 404)

    updates = {}
    if "nickname" in data:
        updates["nickname"] = clean_text(data["nickname"], "昵称", 32)
    if "kunbi" in data:
        updates["kunbi"] = validate_int(data["kunbi"], "kunbi", min_value=0, max_value=10**9)
    if "status" in data:
        if data["status"] not in ("online", "offline", "banned"):
            raise ApiError("状态取值不合法", 400)
        updates["status"] = data["status"]
    if "is_admin" in data:
        is_admin = bool(data["is_admin"])
        # 防止把最后一个管理员降级导致系统失去管理入口
        if target["is_admin"] and not is_admin:
            admin_count = db.query_scalar(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1", (), 0
            )
            if admin_count <= 1:
                raise ApiError("不能取消最后一个管理员的权限", 403)
        updates["is_admin"] = 1 if is_admin else 0

    if not updates:
        raise ApiError("没有有效的更新字段", 400)

    allowed = {"nickname", "kunbi", "status", "is_admin"}
    safe = [k for k in updates if k in allowed]
    assignments = ", ".join(f"{k} = ?" for k in safe)
    values = [updates[k] for k in safe] + [user_id]

    db.execute(f"UPDATE users SET {assignments} WHERE id = ?", values)
    _log_admin("UPDATE_USER", f"更新用户 {user_id}: {safe}")

    return success({"userId": user_id, "updated": safe}, message="用户更新成功")


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """删除用户及其关联数据。"""
    target = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not target:
        raise ApiError("用户不存在", 404)

    if target["is_admin"]:
        raise ApiError("无法删除管理员账户", 403)
    if user_id == g.user_id:
        raise ApiError("不能删除自己", 403)

    with db.transaction() as conn:
        conn.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM kunbi_transactions WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM blacklist WHERE user_id = ? OR blocked_user_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM friend_requests WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    _log_admin("DELETE_USER", f"删除用户 {target['username']} (id={user_id})")
    logger.info("管理员 %s 删除用户 %s", g.user_id, user_id)
    return success({"userId": user_id}, message="用户已删除")


# ---------------------------------------------------------------------------
# 群组管理
# ---------------------------------------------------------------------------


@admin_bp.route("/groups", methods=["GET"])
@admin_required
def get_all_groups():
    """群组列表（分页）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size

    total = db.query_scalar("SELECT COUNT(*) FROM groups", (), 0)
    rows = db.query_all(
        """
        SELECT gp.id, gp.name, gp.avatar, gp.description, gp.created_at,
               u.nickname AS creator_nickname,
               (SELECT COUNT(*) FROM group_members WHERE group_id = gp.id) AS member_count
        FROM groups gp
        LEFT JOIN users u ON u.id = gp.creator_id
        ORDER BY gp.id
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "description": row["description"] or "",
            "creatorNickname": row["creator_nickname"],
            "memberCount": row["member_count"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, groups=items)


@admin_bp.route("/groups/<int:group_id>", methods=["DELETE"])
@admin_required
def delete_group(group_id):
    """删除群组。"""
    group = db.query_one("SELECT * FROM groups WHERE id = ?", (group_id,))
    if not group:
        raise ApiError("群组不存在", 404)

    with db.transaction() as conn:
        conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM messages WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))

    _log_admin("DELETE_GROUP", f"删除群组 {group['name']} (id={group_id})")
    logger.info("管理员 %s 删除群组 %s", g.user_id, group_id)
    return success({"groupId": group_id}, message="群组已删除")


# ---------------------------------------------------------------------------
# 消息与举报
# ---------------------------------------------------------------------------


@admin_bp.route("/private-chats", methods=["GET"])
@admin_required
def get_private_chats():
    """私聊会话概览（补齐缺失接口）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size

    total = db.query_scalar(
        """
        SELECT COUNT(*) FROM (
            SELECT MIN(sender_id, receiver_id) AS a, MAX(sender_id, receiver_id) AS b
            FROM messages WHERE group_id IS NULL AND receiver_id IS NOT NULL
            GROUP BY a, b
        )
        """,
        (),
        0,
    )
    rows = db.query_all(
        """
        SELECT MIN(m.sender_id, m.receiver_id) AS user_a,
               MAX(m.sender_id, m.receiver_id) AS user_b,
               COUNT(*) AS message_count,
               MAX(m.created_at) AS last_message_at
        FROM messages m
        WHERE m.group_id IS NULL AND m.receiver_id IS NOT NULL
        GROUP BY user_a, user_b
        ORDER BY last_message_at DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )

    items = []
    for row in rows:
        user_a = db.query_one(
            "SELECT id, nickname, username FROM users WHERE id = ?", (row["user_a"],)
        )
        user_b = db.query_one(
            "SELECT id, nickname, username FROM users WHERE id = ?", (row["user_b"],)
        )
        items.append(
            {
                "userA": user_a or {"id": row["user_a"], "nickname": "已注销用户"},
                "userB": user_b or {"id": row["user_b"], "nickname": "已注销用户"},
                "messageCount": row["message_count"],
                "lastMessageAt": row["last_message_at"],
            }
        )
    return paginated(items, total, page, page_size, message="获取成功", privateChats=items)


@admin_bp.route("/group-chats", methods=["GET"])
@admin_required
def get_group_chats():
    """群聊会话概览（补齐缺失接口）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size

    total = db.query_scalar(
        "SELECT COUNT(DISTINCT group_id) FROM messages WHERE group_id IS NOT NULL", (), 0
    )
    rows = db.query_all(
        """
        SELECT m.group_id, gp.name,
               COUNT(*) AS message_count,
               MAX(m.created_at) AS last_message_at
        FROM messages m
        LEFT JOIN groups gp ON gp.id = m.group_id
        WHERE m.group_id IS NOT NULL
        GROUP BY m.group_id
        ORDER BY last_message_at DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    items = [
        {
            "groupId": row["group_id"],
            "name": row["name"] or "已解散群组",
            "messageCount": row["message_count"],
            "lastMessageAt": row["last_message_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, message="获取成功", groupChats=items)


@admin_bp.route("/reported-messages", methods=["GET"])
@admin_required
def get_reported_messages():
    """
    被举报消息列表（补齐缺失接口）。

    数据来源：user_logs 中 action='REPORT_MESSAGE' 的记录。
    """
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size

    total = db.query_scalar(
        "SELECT COUNT(*) FROM user_logs WHERE action = 'REPORT_MESSAGE'", (), 0
    )
    rows = db.query_all(
        """
        SELECT l.id, l.user_id, l.action, l.created_at, u.nickname, u.username
        FROM user_logs l
        LEFT JOIN users u ON u.id = l.user_id
        WHERE l.action = 'REPORT_MESSAGE'
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    items = [
        {
            "id": row["id"],
            "reporterId": row["user_id"],
            "reporterNickname": row["nickname"],
            "reporterUsername": row["username"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, message="获取成功", reportedMessages=items)


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------


@admin_bp.route("/notification", methods=["POST"])
@admin_required
def send_notification():
    """
    发送系统通知。

    修复：原实现只写日志、TODO 未实现，通知从未真正投递到用户。
    现在写入 notifications 表并通过 WebSocket 实时推送。
    """
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["content"])

    content = clean_text(data.get("content"), "通知内容", 500)
    title = clean_text(data.get("title"), "通知标题", 100, allow_empty=True) or "系统通知"
    target_type = data.get("target_type", "all")
    target_id = data.get("target_id")

    if target_type not in ("all", "user", "group"):
        raise ApiError("target_type 只能是 all/user/group", 400)

    recipient_ids = []
    if target_type == "all":
        recipient_ids = [
            row["id"] for row in db.query_all("SELECT id FROM users WHERE status != 'banned'")
        ]
    elif target_type == "user":
        target_id = validate_int(target_id, "target_id", min_value=1)
        if not db.query_one("SELECT id FROM users WHERE id = ?", (target_id,)):
            raise ApiError("用户不存在", 404)
        recipient_ids = [target_id]
    else:
        target_id = validate_int(target_id, "target_id", min_value=1)
        if not db.query_one("SELECT id FROM groups WHERE id = ?", (target_id,)):
            raise ApiError("群组不存在", 404)
        recipient_ids = [
            row["user_id"]
            for row in db.query_all(
                "SELECT user_id FROM group_members WHERE group_id = ?", (target_id,)
            )
        ]

    for uid in recipient_ids:
        db.execute(
            """
            INSERT INTO notifications (user_id, type, title, content, is_read, created_at)
            VALUES (?, 'system', ?, ?, 0, ?)
            """,
            (uid, title, content, datetime.now()),
        )
        _push_to_user(uid, "system_notification", {"title": title, "content": content})

    _log_admin("SEND_NOTIFICATION", f"向 {len(recipient_ids)} 个用户发送通知: {content[:50]}")
    logger.info("管理员 %s 发送通知给 %s 个用户", g.user_id, len(recipient_ids))

    return success(
        {"recipients": len(recipient_ids)}, message=f"通知已发送给 {len(recipient_ids)} 个用户"
    )


@admin_bp.route("/notifications", methods=["GET"])
@admin_required
def list_notifications():
    """通知列表（补齐缺失接口）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size

    total = db.query_scalar("SELECT COUNT(*) FROM notifications", (), 0)
    rows = db.query_all(
        """
        SELECT n.id, n.user_id, n.type, n.title, n.content, n.is_read, n.created_at,
               u.nickname
        FROM notifications n
        LEFT JOIN users u ON u.id = n.user_id
        ORDER BY n.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    items = [
        {
            "id": row["id"],
            "userId": row["user_id"],
            "nickname": row["nickname"],
            "type": row["type"],
            "title": row["title"],
            "content": row["content"],
            "isRead": bool(row["is_read"]),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, notifications=items)


@admin_bp.route("/notification/stats", methods=["GET"])
@admin_required
def notification_stats():
    """通知统计（补齐缺失接口）。"""
    return success(
        {
            "total": db.query_scalar("SELECT COUNT(*) FROM notifications", (), 0),
            "unread": db.query_scalar(
                "SELECT COUNT(*) FROM notifications WHERE is_read = 0", (), 0
            ),
            "read": db.query_scalar(
                "SELECT COUNT(*) FROM notifications WHERE is_read = 1", (), 0
            ),
            "today": db.query_scalar(
                "SELECT COUNT(*) FROM notifications WHERE date(created_at) = date('now')",
                (),
                0,
            ),
        }
    )


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------


@admin_bp.route("/logs", methods=["GET"])
@admin_required
def get_system_logs():
    """系统日志（分页）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size
    log_type = request.args.get("type")

    where = ""
    params = []
    if log_type:
        where = "WHERE type = ?"
        params = [log_type]

    total = db.query_scalar(f"SELECT COUNT(*) FROM system_logs {where}", params, 0)
    rows = db.query_all(
        f"""
        SELECT l.id, l.type, l.content, l.user_id, l.created_at, u.username
        FROM system_logs l
        LEFT JOIN users u ON u.id = l.user_id
        {where}
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )
    items = [
        {
            "id": row["id"],
            "type": row["type"],
            "content": row["content"],
            "userId": row["user_id"],
            "username": row["username"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, logs=items)


# ---------------------------------------------------------------------------
# 数据库管理（补齐缺失接口）
# ---------------------------------------------------------------------------


@admin_bp.route("/database/info", methods=["GET"])
@admin_required
def database_info():
    """数据库基本信息。"""
    path = db.get_db_path()
    size = os.path.getsize(path) if os.path.exists(path) else 0
    return success(
        {
            "path": path,
            "size": size,
            "sizeHuman": _human_size(size),
            "journalMode": db.query_scalar("PRAGMA journal_mode", (), "unknown"),
            "tableCount": len(_list_tables()),
        }
    )


@admin_bp.route("/database/tables", methods=["GET"])
@admin_required
def database_tables():
    """数据库表清单与行数。"""
    return success({"tables": _list_tables()})


@admin_bp.route("/database/optimize", methods=["POST"])
@admin_required
def database_optimize():
    """执行 VACUUM 与 ANALYZE。"""
    conn = db.get_connection()
    try:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        conn.commit()
    except sqlite3.Error as exc:
        raise ApiError(f"优化失败: {exc}", 500)

    _log_admin("DB_OPTIMIZE", "执行数据库优化")
    return success(message="数据库优化完成")


@admin_bp.route("/database/backups", methods=["GET"])
@admin_required
def database_backups():
    """备份文件列表。"""
    backup_dir = current_app.config["FUCKCHAT_CONFIG"].base_dir / "backups"
    items = []
    if backup_dir.exists():
        for path in sorted(backup_dir.glob("*.db"), reverse=True):
            items.append(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "sizeHuman": _human_size(path.stat().st_size),
                    "createdAt": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                }
            )
    return success({"backups": items})


@admin_bp.route("/database/backup", methods=["POST"])
@admin_required
def database_backup():
    """创建数据库备份，并清理超出保留数量的旧备份。"""
    conf = current_app.config["FUCKCHAT_CONFIG"]
    backup_dir = conf.base_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    keep = int(conf.section("database").get("backup_keep", 5))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"fuckchat_backup_{timestamp}.db"

    try:
        source = db.get_connection()
        with sqlite3.connect(str(target)) as dest:
            source.backup(dest)
    except sqlite3.Error as exc:
        raise ApiError(f"备份失败: {exc}", 500)

    # 清理旧备份
    existing = sorted(backup_dir.glob("fuckchat_backup_*.db"), reverse=True)
    for old in existing[keep:]:
        try:
            old.unlink()
        except OSError as exc:
            logger.warning("清理旧备份失败 %s: %s", old, exc)

    _log_admin("DB_BACKUP", f"创建备份 {target.name}")
    return success(
        {"name": target.name, "size": target.stat().st_size}, message="备份创建成功", status_code=201
    )


# ---------------------------------------------------------------------------
# 系统设置（补齐缺失接口）
# ---------------------------------------------------------------------------


@admin_bp.route("/settings", methods=["GET"])
@admin_required
def get_settings():
    """
    读取系统设置。

    注意：密钥类字段一律脱敏，绝不回传明文。
    """
    conf = current_app.config["FUCKCHAT_CONFIG"]
    return success(
        {
            "app": {
                "name": conf["app"].get("name"),
                "version": conf["app"].get("version", "2.0.0"),
                "maxContentLength": conf["app"].get("max_content_length"),
                "allowedFileExtensions": conf["app"].get("allowed_file_extensions", []),
            },
            "server": {
                "host": conf.section("server").get("host"),
                "port": conf.section("server").get("port"),
                "debug": conf.section("server").get("debug"),
            },
            "security": {
                "passwordMinLength": conf.section("security").get("password_min_length"),
                "loginMaxAttempts": conf.section("security").get("login_max_attempts"),
                "loginLockoutSeconds": conf.section("security").get("login_lockout_seconds"),
                "rateLimitMaxRequests": conf.section("security").get("rate_limit_max_requests"),
                "secretKeyConfigured": bool(conf["app"].get("secret_key")),
            },
            "chat": {
                "maxMessageLength": conf.section("chat").get("max_message_length"),
                "historyMessageCount": conf.section("chat").get("history_message_count"),
            },
            "ui": {
                "animations": conf.section("ui").get("animations"),
                "theme": conf.section("ui").get("theme"),
            },
        }
    )


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _list_tables():
    rows = db.query_all(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = []
    for row in rows:
        name = row["name"]
        try:
            count = db.query_scalar(f'SELECT COUNT(*) FROM "{name}"', (), 0)
        except sqlite3.Error:
            count = -1
        tables.append({"name": name, "rows": count})
    return tables


def _human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _push_to_user(user_id, event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload, room=f"user_{user_id}")
    except Exception as exc:
        logger.debug("推送通知到用户 %s 失败: %s", user_id, exc)
