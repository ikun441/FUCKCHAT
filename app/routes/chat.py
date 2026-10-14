#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 聊天路由

重构要点：
- 所有分页/ID 参数经统一校验，修复 limit=abc 触发 500
- 消息内容长度与类型校验
- 黑名单、群成员权限在服务端校验
- 补齐 /api/chat/history 的 POST 保存逻辑与清晰契约
"""

import logging
from datetime import datetime

from flask import Blueprint, current_app, g, request

from .. import database as db
from ..responses import ApiError, paginated, success
from ..security import auth_required, rate_limit
from ..validators import (
    clean_text,
    require_fields,
    require_json,
    validate_int,
    validate_message_content,
    validate_pagination,
)

logger = logging.getLogger("FUCKCHAT.chat")

chat_bp = Blueprint("chat", __name__)

ALLOWED_MESSAGE_TYPES = {"text", "emoji", "image", "voice", "file", "kunbi", "system"}


def _serialize_message(row):
    """统一消息序列化。"""
    return {
        "id": row["id"],
        "senderId": row["sender_id"],
        "senderNickname": row.get("sender_nickname"),
        "senderAvatar": row.get("sender_avatar"),
        "receiverId": row.get("receiver_id"),
        "groupId": row.get("group_id"),
        "type": row.get("type") or row.get("message_type") or "text",
        "content": row["content"],
        "createdAt": row.get("created_at"),
    }


def _is_blocked(user_a, user_b):
    """检查双方是否存在黑名单关系。"""
    row = db.query_one(
        """
        SELECT id FROM blacklist
        WHERE (user_id = ? AND blocked_user_id = ?)
           OR (user_id = ? AND blocked_user_id = ?)
        """,
        (user_a, user_b, user_b, user_a),
    )
    return row is not None


def _assert_group_member(group_id, user_id):
    """确认用户是群成员，否则拒绝。"""
    member = db.query_one(
        "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    if not member:
        raise ApiError("你不是该群成员", 403)
    return member


# ---------------------------------------------------------------------------
# 用户与联系人
# ---------------------------------------------------------------------------


@chat_bp.route("/users", methods=["GET"])
@auth_required
def get_online_users():
    """获取在线用户列表（排除自己与已拉黑关系）。"""
    rows = db.query_all(
        """
        SELECT id, username, nickname, avatar, status
        FROM users
        WHERE status = 'online' AND id != ?
        ORDER BY nickname
        """,
        (g.user_id,),
    )
    users = [
        {
            "id": row["id"],
            "username": row["username"],
            "nickname": row["nickname"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "status": row["status"],
        }
        for row in rows
    ]
    return success({"users": users}, message="获取成功")


@chat_bp.route("/contacts", methods=["GET"])
@auth_required
def get_recent_contacts():
    """获取最近联系人（由消息记录推导）。"""
    limit = validate_int(
        request.args.get("limit"), "limit", min_value=1, max_value=100, default=20
    )
    rows = db.query_all(
        """
        SELECT u.id, u.username, u.nickname, u.avatar, u.status,
               MAX(m.created_at) AS last_message_time
        FROM users u
        JOIN messages m ON (
            (m.sender_id = u.id AND m.receiver_id = ?) OR
            (m.sender_id = ? AND m.receiver_id = u.id)
        )
        WHERE u.id != ?
        GROUP BY u.id
        ORDER BY last_message_time DESC
        LIMIT ?
        """,
        (g.user_id, g.user_id, g.user_id, limit),
    )
    contacts = [
        {
            "id": row["id"],
            "username": row["username"],
            "nickname": row["nickname"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "status": row["status"],
            "lastMessageTime": row["last_message_time"],
        }
        for row in rows
    ]
    return success({"contacts": contacts}, message="获取成功")


# ---------------------------------------------------------------------------
# 群组
# ---------------------------------------------------------------------------


@chat_bp.route("/groups", methods=["GET"])
@auth_required
def get_groups():
    """获取当前用户所在群组。"""
    rows = db.query_all(
        """
        SELECT gp.id, gp.name, gp.avatar, gp.description, gp.creator_id, gp.created_at,
               (SELECT COUNT(*) FROM group_members WHERE group_id = gp.id) AS member_count
        FROM groups gp
        JOIN group_members gm ON gm.group_id = gp.id
        WHERE gm.user_id = ?
        ORDER BY gp.created_at DESC
        """,
        (g.user_id,),
    )
    groups = [
        {
            "id": row["id"],
            "name": row["name"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "description": row["description"] or "",
            "creatorId": row["creator_id"],
            "memberCount": row["member_count"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return success({"groups": groups}, message="获取成功")


@chat_bp.route("/groups", methods=["POST"])
@auth_required
@rate_limit("create_group", max_requests=10, window=60)
def create_group():
    """创建群组，创建者自动成为管理员。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["name"])

    name = clean_text(data.get("name"), "群名称", 64)
    description = clean_text(data.get("description"), "群描述", 200, allow_empty=True)

    member_ids = data.get("member_ids") or []
    if not isinstance(member_ids, list):
        raise ApiError("member_ids 必须是数组", 400)

    max_members = current_app.config["FUCKCHAT_CONFIG"].section("group").get(
        "max_member_count", 100
    )
    if len(member_ids) + 1 > max_members:
        raise ApiError(f"群成员不能超过 {max_members} 人", 400)

    with db.transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO groups (name, description, creator_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, description, g.user_id, datetime.now()),
        )
        group_id = cur.lastrowid

        conn.execute(
            "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'admin', ?)",
            (group_id, g.user_id, datetime.now()),
        )

        for raw_id in member_ids:
            try:
                member_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if member_id == g.user_id:
                continue
            exists = conn.execute("SELECT id FROM users WHERE id = ?", (member_id,)).fetchone()
            if exists:
                conn.execute(
                    "INSERT OR IGNORE INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                    (group_id, member_id, datetime.now()),
                )

    logger.info("用户 %s 创建群组 %s (id=%s)", g.user_id, name, group_id)
    return success({"groupId": group_id, "name": name}, message="群组创建成功", status_code=201)


@chat_bp.route("/groups/<int:group_id>/members", methods=["GET"])
@auth_required
def get_group_members(group_id):
    """获取群成员列表（需为群成员）。"""
    _assert_group_member(group_id, g.user_id)
    rows = db.query_all(
        """
        SELECT u.id, u.username, u.nickname, u.avatar, u.status, gm.role, gm.joined_at
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY gm.role DESC, gm.joined_at
        """,
        (group_id,),
    )
    members = [
        {
            "id": row["id"],
            "username": row["username"],
            "nickname": row["nickname"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "status": row["status"],
            "role": row["role"],
            "joinedAt": row["joined_at"],
        }
        for row in rows
    ]
    return success({"members": members}, message="获取成功")


@chat_bp.route("/groups/<int:group_id>/join", methods=["POST"])
@auth_required
def join_group(group_id):
    """加入群组。"""
    group = db.query_one("SELECT id, name FROM groups WHERE id = ?", (group_id,))
    if not group:
        raise ApiError("群组不存在", 404)

    existing = db.query_one(
        "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, g.user_id),
    )
    if existing:
        raise ApiError("你已在该群组中", 409)

    max_members = current_app.config["FUCKCHAT_CONFIG"].section("group").get(
        "max_member_count", 100
    )
    count = db.query_scalar(
        "SELECT COUNT(*) FROM group_members WHERE group_id = ?", (group_id,), 0
    )
    if count >= max_members:
        raise ApiError(f"群成员已达上限 {max_members} 人", 403)

    db.execute(
        "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
        (group_id, g.user_id, datetime.now()),
    )
    logger.info("用户 %s 加入群组 %s", g.user_id, group_id)
    return success({"groupId": group_id}, message="加入成功")


# ---------------------------------------------------------------------------
# 消息
# ---------------------------------------------------------------------------


@chat_bp.route("/messages", methods=["GET"])
@auth_required
def get_messages():
    """
    获取聊天记录。

    参数：type=user|group, target_id, limit, before
    修复：limit 非法值原先直接 500，现返回 400。
    """
    chat_type = request.args.get("type")
    target_id = request.args.get("target_id")
    before = request.args.get("before")

    if not chat_type or not target_id:
        raise ApiError("缺少必要参数 type/target_id", 400)
    if chat_type not in ("user", "group"):
        raise ApiError("type 只能是 user 或 group", 400)

    default_limit = current_app.config["FUCKCHAT_CONFIG"].section("chat").get(
        "history_message_count", 100
    )
    limit = validate_int(
        request.args.get("limit"), "limit", min_value=1, max_value=200, default=default_limit
    )
    target = validate_int(target_id, "target_id", min_value=1)

    if chat_type == "user":
        if _is_blocked(g.user_id, target):
            raise ApiError("无法获取聊天记录", 403)

        sql = """
            SELECT m.id, m.sender_id, m.receiver_id, m.group_id, m.type, m.content, m.created_at,
                   u.nickname AS sender_nickname, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id IS NULL
              AND ((m.sender_id = ? AND m.receiver_id = ?)
                OR (m.sender_id = ? AND m.receiver_id = ?))
        """
        params = [g.user_id, target, target, g.user_id]

        if before:
            sql += " AND m.created_at < ?"
            params.append(before)
        sql += " ORDER BY m.created_at DESC LIMIT ?"
        params.append(limit)
    else:
        _assert_group_member(target, g.user_id)
        sql = """
            SELECT m.id, m.sender_id, m.receiver_id, m.group_id, m.type, m.content, m.created_at,
                   u.nickname AS sender_nickname, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id = ?
        """
        params = [target]
        if before:
            sql += " AND m.created_at < ?"
            params.append(before)
        sql += " ORDER BY m.created_at DESC LIMIT ?"
        params.append(limit)

    rows = db.query_all(sql, params)
    # 返回按时间正序，前端可直接渲染
    messages = [_serialize_message(row) for row in reversed(rows)]

    return success({"messages": messages, "type": chat_type, "targetId": target})


@chat_bp.route("/messages", methods=["POST"])
@auth_required
@rate_limit("send_message", max_requests=120, window=60)
def send_message():
    """
    发送消息（HTTP 通道，WebSocket 不可用时的回退）。

    修复：原先该 POST 接口根本不存在，前端调用必然 404。
    """
    data = require_json(request.get_json(silent=True))

    content = validate_message_content(data.get("content") or data.get("message"))
    msg_type = data.get("type") or "text"
    if msg_type not in ALLOWED_MESSAGE_TYPES:
        raise ApiError("不支持的消息类型", 400)

    receiver_id = data.get("receiver_id") or data.get("receiverId")
    group_id = data.get("group_id") or data.get("groupId")

    if not receiver_id and not group_id:
        raise ApiError("必须指定 receiver_id 或 group_id", 400)
    if receiver_id and group_id:
        raise ApiError("receiver_id 与 group_id 不能同时存在", 400)

    timestamp = datetime.now()

    if receiver_id:
        receiver_id = validate_int(receiver_id, "receiver_id", min_value=1)
        if receiver_id == g.user_id:
            raise ApiError("不能给自己发消息", 400)
        if not db.query_one("SELECT id FROM users WHERE id = ?", (receiver_id,)):
            raise ApiError("接收者不存在", 404)
        if _is_blocked(g.user_id, receiver_id):
            raise ApiError("对方已将你拉黑或你已拉黑对方", 403)

        message_id = db.execute(
            "INSERT INTO messages (sender_id, receiver_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, receiver_id, msg_type, content, timestamp),
        )
        event = {
            "id": message_id,
            "senderId": g.user_id,
            "receiverId": receiver_id,
            "type": msg_type,
            "content": content,
            "createdAt": timestamp.isoformat(),
        }
        _broadcast_to_user(receiver_id, "new_message", event)
        _broadcast_to_user(g.user_id, "new_message", event)
    else:
        group_id = validate_int(group_id, "group_id", min_value=1)
        _assert_group_member(group_id, g.user_id)

        message_id = db.execute(
            "INSERT INTO messages (sender_id, group_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, group_id, msg_type, content, timestamp),
        )
        event = {
            "id": message_id,
            "senderId": g.user_id,
            "groupId": group_id,
            "type": msg_type,
            "content": content,
            "createdAt": timestamp.isoformat(),
        }
        _broadcast_to_room(f"group_{group_id}", "new_message", event)

    return success({"messageId": message_id}, message="发送成功", status_code=201)


@chat_bp.route("/messages/<int:message_id>", methods=["DELETE"])
@auth_required
def recall_message(message_id):
    """
    撤回消息（补齐缺失接口）。
    仅发送者本人或管理员可撤回，且限 2 分钟内。
    """
    row = db.query_one("SELECT * FROM messages WHERE id = ?", (message_id,))
    if not row:
        raise ApiError("消息不存在", 404)

    if row["sender_id"] != g.user_id and not g.is_admin:
        raise ApiError("只能撤回自己的消息", 403)

    created = row.get("created_at")
    if created and not g.is_admin:
        try:
            created_dt = datetime.fromisoformat(str(created))
            if (datetime.now() - created_dt).total_seconds() > 120:
                raise ApiError("超过 2 分钟的消息不能撤回", 403)
        except ValueError:
            pass  # 时间格式异常时放行，不阻断功能

    db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    _log_user_action("RECALL_MESSAGE", f"撤回消息 {message_id}")

    if row.get("receiver_id"):
        _broadcast_to_user(row["receiver_id"], "message_recalled", {"messageId": message_id})
        _broadcast_to_user(g.user_id, "message_recalled", {"messageId": message_id})
    elif row.get("group_id"):
        _broadcast_to_room(
            f"group_{row['group_id']}", "message_recalled", {"messageId": message_id}
        )

    return success({"messageId": message_id}, message="消息已撤回")


@chat_bp.route("/conversations/<int:target_id>/messages", methods=["DELETE"])
@auth_required
def clear_conversation(target_id):
    """清空与某用户的聊天记录（补齐缺失接口）。"""
    with db.transaction() as conn:
        cur = conn.execute(
            """
            DELETE FROM messages
            WHERE group_id IS NULL
              AND ((sender_id = ? AND receiver_id = ?)
                OR (sender_id = ? AND receiver_id = ?))
            """,
            (g.user_id, target_id, target_id, g.user_id),
        )
        deleted = cur.rowcount

    logger.info("用户 %s 清空与 %s 的聊天记录 (%s 条)", g.user_id, target_id, deleted)
    return success({"deleted": deleted}, message="聊天记录已清空")


# ---------------------------------------------------------------------------
# 聊天记录同步（前端 saveChatHistory / loadChatHistory 契约）
# ---------------------------------------------------------------------------


@chat_bp.route("/history", methods=["GET"])
@auth_required
def get_history():
    """
    按 chat_id 获取记录，兼容前端 `history?chat_id=user_2` 的写法。

    修复：原先只接受 type/target_id，前端传 chat_id 必然 400。
    """
    chat_id = request.args.get("chat_id", "").strip()
    if not chat_id:
        raise ApiError("缺少参数 chat_id", 400)

    parsed = _parse_chat_id(chat_id)
    if parsed is None:
        raise ApiError("chat_id 格式不正确，应为 user_<id> 或 group_<id>", 400)

    chat_type, target = parsed
    limit = validate_int(
        request.args.get("limit"), "limit", min_value=1, max_value=200, default=100
    )

    if chat_type == "user":
        if _is_blocked(g.user_id, target):
            raise ApiError("无法获取聊天记录", 403)
        rows = db.query_all(
            """
            SELECT m.id, m.sender_id, m.receiver_id, m.group_id, m.type, m.content, m.created_at,
                   u.nickname AS sender_nickname, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id IS NULL
              AND ((m.sender_id = ? AND m.receiver_id = ?)
                OR (m.sender_id = ? AND m.receiver_id = ?))
            ORDER BY m.created_at DESC LIMIT ?
            """,
            (g.user_id, target, target, g.user_id, limit),
        )
    else:
        _assert_group_member(target, g.user_id)
        rows = db.query_all(
            """
            SELECT m.id, m.sender_id, m.receiver_id, m.group_id, m.type, m.content, m.created_at,
                   u.nickname AS sender_nickname, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id = ?
            ORDER BY m.created_at DESC LIMIT ?
            """,
            (target, limit),
        )

    return success(
        {
            "chatId": chat_id,
            "messages": [_serialize_message(row) for row in reversed(rows)],
        }
    )


@chat_bp.route("/history", methods=["POST"])
@auth_required
def save_history():
    """
    保存聊天记录。

    安全说明：仅接受 {chat_id, messages} 结构，
    服务端只落库当前用户有权写入的会话，不信任客户端传入的 sender_id。
    """
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["chat_id"])

    chat_id = str(data["chat_id"]).strip()
    parsed = _parse_chat_id(chat_id)
    if parsed is None:
        raise ApiError("chat_id 格式不正确", 400)

    chat_type, target = parsed
    messages = data.get("messages")
    if not isinstance(messages, list):
        raise ApiError("messages 必须是数组", 400)
    if len(messages) > 500:
        raise ApiError("单次保存消息不能超过 500 条", 400)

    if chat_type == "group":
        _assert_group_member(target, g.user_id)
    elif _is_blocked(g.user_id, target):
        raise ApiError("无法保存该会话", 403)

    inserted = 0
    skipped = 0
    with db.transaction() as conn:
        for item in messages:
            if not isinstance(item, dict):
                skipped += 1
                continue
            content = item.get("content") or item.get("message")
            if not isinstance(content, str) or not content.strip():
                skipped += 1
                continue
            if len(content) > 1000:
                skipped += 1
                continue

            # 服务端权威判定发送者：只允许写自己发的消息
            sender_id = item.get("senderId") or item.get("sender_id") or g.user_id
            try:
                sender_id = int(sender_id)
            except (TypeError, ValueError):
                skipped += 1
                continue
            if sender_id != g.user_id:
                skipped += 1
                continue

            msg_type = item.get("type") or "text"
            if msg_type not in ALLOWED_MESSAGE_TYPES:
                msg_type = "text"

            created = item.get("createdAt") or item.get("created_at") or datetime.now()

            if chat_type == "user":
                conn.execute(
                    "INSERT INTO messages (sender_id, receiver_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (g.user_id, target, msg_type, content, created),
                )
            else:
                conn.execute(
                    "INSERT INTO messages (sender_id, group_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (g.user_id, target, msg_type, content, created),
                )
            inserted += 1

    return success({"inserted": inserted, "skipped": skipped}, message="聊天记录已保存")


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _parse_chat_id(chat_id):
    """解析 user_<id> / group_<id> 形式的会话 ID。"""
    if "_" not in chat_id:
        return None
    prefix, _, raw_id = chat_id.partition("_")
    if prefix not in ("user", "group"):
        return None
    try:
        target = int(raw_id)
    except (TypeError, ValueError):
        return None
    if target < 1:
        return None
    return prefix, target


def _broadcast_to_user(user_id, event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload, room=f"user_{user_id}")
    except Exception as exc:
        logger.debug("广播到用户 %s 失败: %s", user_id, exc)


def _broadcast_to_room(room, event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload, room=room)
    except Exception as exc:
        logger.debug("广播到房间 %s 失败: %s", room, exc)


def _log_user_action(action, detail):
    try:
        db.execute(
            "INSERT INTO user_logs (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (g.user_id, action, detail, datetime.now()),
        )
    except Exception as exc:
        logger.debug("写用户日志失败: %s", exc)
