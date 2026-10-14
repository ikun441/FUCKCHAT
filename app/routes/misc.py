#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 杂项路由（好友、通知、举报、消息管理、视频）

补齐原前端调用但后端缺失的接口：
    POST /api/friends/request            好友申请
    GET  /api/friends                    好友列表
    POST /api/friends/respond            处理好友申请
    GET  /api/notifications              我的通知
    POST /api/notifications/read         标记已读
    POST /api/messages/clear             清空会话消息
    POST /api/messages/recall            撤回消息
    POST /api/messages/report            举报消息
    POST /api/messages/forward           转发消息
    GET  /api/messages/search            搜索消息
    POST /api/system/create-folder       创建用户目录
"""

import logging
import os
import re
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

logger = logging.getLogger("FUCKCHAT.misc")

misc_bp = Blueprint("misc", __name__)


# ---------------------------------------------------------------------------
# 好友
# ---------------------------------------------------------------------------


@misc_bp.route("/friends", methods=["GET"])
@auth_required
def list_friends():
    """好友列表。"""
    rows = db.query_all(
        """
        SELECT f.id, f.friend_id, f.nickname, f.group_name, f.created_at,
               u.nickname AS user_nickname, u.avatar, u.status, u.username
        FROM friends f
        LEFT JOIN users u ON u.id = f.friend_id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
        """,
        (g.user_id,),
    )
    friends = [
        {
            "id": row["id"],
            "friendId": row["friend_id"],
            "nickname": row["nickname"] or row["user_nickname"],
            "username": row["username"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "status": row["status"],
            "groupName": row["group_name"] or "默认分组",
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return success({"friends": friends, "total": len(friends)})


@misc_bp.route("/friends/request", methods=["POST"])
@auth_required
@rate_limit("friend_request", max_requests=20, window=60)
def send_friend_request():
    """发送好友申请。"""
    data = require_json(request.get_json(silent=True))

    target_id = data.get("friend_id") or data.get("userId") or data.get("to_user_id")
    if target_id is None:
        raise ApiError("缺少参数 friend_id", 400)
    target_id = validate_int(target_id, "friend_id", min_value=1)

    if target_id == g.user_id:
        raise ApiError("不能添加自己为好友", 400)

    target = db.query_one("SELECT id, nickname FROM users WHERE id = ?", (target_id,))
    if not target:
        raise ApiError("用户不存在", 404)

    if db.query_one(
        "SELECT id FROM friends WHERE user_id = ? AND friend_id = ?", (g.user_id, target_id)
    ):
        raise ApiError("你们已经是好友", 409)

    pending = db.query_one(
        """
        SELECT id FROM friend_requests
        WHERE status = 'pending'
          AND ((sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?))
        """,
        (g.user_id, target_id, target_id, g.user_id),
    )
    if pending:
        raise ApiError("已有待处理的好友申请", 409)

    message = clean_text(data.get("message"), "验证消息", 100, allow_empty=True)

    request_id = db.execute(
        """
        INSERT INTO friend_requests (sender_id, receiver_id, message, status, created_at, updated_at)
        VALUES (?, ?, ?, 'pending', ?, ?)
        """,
        (g.user_id, target_id, message, datetime.now(), datetime.now()),
    )

    _notify(
        target_id,
        "friend_request",
        {"from": g.user_id, "requestId": request_id, "message": message},
    )
    logger.info("用户 %s 向 %s 发送好友申请", g.user_id, target_id)
    return success({"requestId": request_id}, message="好友申请已发送", status_code=201)


@misc_bp.route("/friends/requests", methods=["GET"])
@auth_required
def list_friend_requests():
    """收到的好友申请列表。"""
    status = request.args.get("status", "pending")
    if status not in ("pending", "accepted", "rejected", "all"):
        raise ApiError("status 取值不合法", 400)

    where = "WHERE fr.receiver_id = ?"
    params = [g.user_id]
    if status != "all":
        where += " AND fr.status = ?"
        params.append(status)

    rows = db.query_all(
        f"""
        SELECT fr.id, fr.sender_id, fr.message, fr.status, fr.created_at,
               u.nickname, u.username, u.avatar
        FROM friend_requests fr
        LEFT JOIN users u ON u.id = fr.sender_id
        {where}
        ORDER BY fr.created_at DESC
        """,
        params,
    )
    requests_list = [
        {
            "id": row["id"],
            "senderId": row["sender_id"],
            "nickname": row["nickname"],
            "username": row["username"],
            "avatar": row["avatar"] or "/src/images/default-avatar.png",
            "message": row["message"] or "",
            "status": row["status"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return success({"requests": requests_list, "total": len(requests_list)})


@misc_bp.route("/friends/respond", methods=["POST"])
@auth_required
def respond_friend_request():
    """接受或拒绝好友申请。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["request_id", "action"])

    request_id = validate_int(data.get("request_id"), "request_id", min_value=1)
    action = str(data.get("action")).lower()
    if action not in ("accept", "reject"):
        raise ApiError("action 只能是 accept 或 reject", 400)

    req = db.query_one("SELECT * FROM friend_requests WHERE id = ?", (request_id,))
    if not req:
        raise ApiError("好友申请不存在", 404)
    if req["receiver_id"] != g.user_id:
        raise ApiError("无权处理该申请", 403)
    if req["status"] != "pending":
        raise ApiError("该申请已处理", 409)

    sender_id = req["sender_id"]
    new_status = "accepted" if action == "accept" else "rejected"

    with db.transaction() as conn:
        conn.execute(
            "UPDATE friend_requests SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, datetime.now(), request_id),
        )
        if action == "accept":
            sender = conn.execute(
                "SELECT nickname FROM users WHERE id = ?", (sender_id,)
            ).fetchone()
            me = conn.execute(
                "SELECT nickname FROM users WHERE id = ?", (g.user_id,)
            ).fetchone()
            # 双向建立好友关系
            conn.execute(
                "INSERT OR IGNORE INTO friends (user_id, friend_id, nickname, group_name, created_at) VALUES (?, ?, ?, '默认分组', ?)",
                (g.user_id, sender_id, sender["nickname"] if sender else None, datetime.now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO friends (user_id, friend_id, nickname, group_name, created_at) VALUES (?, ?, ?, '默认分组', ?)",
                (sender_id, g.user_id, me["nickname"] if me else None, datetime.now()),
            )

    _notify(sender_id, "friend_response", {"requestId": request_id, "status": new_status})
    logger.info("用户 %s %s 了 %s 的好友申请", g.user_id, action, sender_id)
    return success({"requestId": request_id, "status": new_status}, message="处理成功")


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------


@misc_bp.route("/notifications", methods=["GET"])
@auth_required
def list_my_notifications():
    """我的通知列表。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size
    only_unread = request.args.get("unread") in ("1", "true", "yes")

    where = "WHERE user_id = ?"
    params = [g.user_id]
    if only_unread:
        where += " AND is_read = 0"

    total = db.query_scalar(f"SELECT COUNT(*) FROM notifications {where}", params, 0)
    rows = db.query_all(
        f"""
        SELECT id, type, title, content, is_read, reference_id, reference_type, created_at
        FROM notifications {where}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )
    items = [
        {
            "id": row["id"],
            "type": row["type"],
            "title": row["title"],
            "content": row["content"],
            "isRead": bool(row["is_read"]),
            "referenceId": row["reference_id"],
            "referenceType": row["reference_type"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    unread = db.query_scalar(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (g.user_id,), 0
    )
    return paginated(items, total, page, page_size, unread=unread)


@misc_bp.route("/notifications/read", methods=["POST"])
@auth_required
def mark_notifications_read():
    """标记通知为已读。"""
    data = request.get_json(silent=True) or {}
    notification_id = data.get("id") or data.get("notification_id")

    if notification_id:
        notification_id = validate_int(notification_id, "id", min_value=1)
        affected = db.query_scalar(
            "SELECT COUNT(*) FROM notifications WHERE id = ? AND user_id = ?",
            (notification_id, g.user_id),
            0,
        )
        if not affected:
            raise ApiError("通知不存在", 404)
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, g.user_id),
        )
        return success({"id": notification_id}, message="已标记为已读")

    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (g.user_id,))
    return success(message="全部通知已标记为已读")


# ---------------------------------------------------------------------------
# 消息管理
# ---------------------------------------------------------------------------


@misc_bp.route("/messages/recall", methods=["POST"])
@auth_required
def recall_message():
    """
    撤回消息（补齐缺失接口）。

    与原 chat.py 的 DELETE 版本等价，但前端调用的是 POST /api/messages/recall，
    这里提供兼容入口。
    """
    data = require_json(request.get_json(silent=True))
    message_id = data.get("message_id") or data.get("messageId") or data.get("id")
    if message_id is None:
        raise ApiError("缺少参数 message_id", 400)
    message_id = validate_int(message_id, "message_id", min_value=1)

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
            pass

    db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    _log_action("RECALL_MESSAGE", f"撤回消息 {message_id}")

    if row.get("receiver_id"):
        _notify(row["receiver_id"], "message_recalled", {"messageId": message_id})
        _notify(g.user_id, "message_recalled", {"messageId": message_id})
    elif row.get("group_id"):
        _broadcast_room(
            f"group_{row['group_id']}", "message_recalled", {"messageId": message_id}
        )

    return success({"messageId": message_id}, message="消息已撤回")


@misc_bp.route("/messages/clear", methods=["POST"])
@auth_required
def clear_messages():
    """
    清空会话消息（补齐缺失接口）。

    支持 chat_id=user_2 / group_1，或显式 target_id + type。
    """
    data = request.get_json(silent=True) or {}
    chat_id = data.get("chat_id")
    target_id = data.get("target_id")
    chat_type = data.get("type")

    if chat_id:
        if "_" not in str(chat_id):
            raise ApiError("chat_id 格式不正确", 400)
        prefix, _, raw_id = str(chat_id).partition("_")
        if prefix not in ("user", "group"):
            raise ApiError("chat_id 格式不正确", 400)
        chat_type = prefix
        try:
            target_id = int(raw_id)
        except ValueError:
            raise ApiError("chat_id 格式不正确", 400)
    elif target_id is not None:
        target_id = validate_int(target_id, "target_id", min_value=1)
        if chat_type not in ("user", "group"):
            raise ApiError("缺少或非法的 type 参数", 400)
    else:
        raise ApiError("缺少参数 chat_id", 400)

    with db.transaction() as conn:
        if chat_type == "user":
            cur = conn.execute(
                """
                DELETE FROM messages
                WHERE group_id IS NULL
                  AND ((sender_id = ? AND receiver_id = ?)
                    OR (sender_id = ? AND receiver_id = ?))
                """,
                (g.user_id, target_id, target_id, g.user_id),
            )
        else:
            member = conn.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (target_id, g.user_id),
            ).fetchone()
            if not member:
                raise ApiError("你不是该群成员", 403)
            cur = conn.execute("DELETE FROM messages WHERE group_id = ?", (target_id,))
        deleted = cur.rowcount

    logger.info("用户 %s 清空会话 %s_%s (%s 条)", g.user_id, chat_type, target_id, deleted)
    return success({"deleted": deleted}, message=f"已清空 {deleted} 条消息")


@misc_bp.route("/messages/report", methods=["POST"])
@auth_required
@rate_limit("report", max_requests=10, window=60)
def report_message():
    """举报消息（补齐缺失接口）。"""
    data = require_json(request.get_json(silent=True))
    message_id = data.get("message_id") or data.get("messageId")
    if message_id is None:
        raise ApiError("缺少参数 message_id", 400)
    message_id = validate_int(message_id, "message_id", min_value=1)
    reason = clean_text(data.get("reason"), "举报原因", 200, allow_empty=True)

    row = db.query_one("SELECT * FROM messages WHERE id = ?", (message_id,))
    if not row:
        raise ApiError("消息不存在", 404)

    _log_action("REPORT_MESSAGE", f"举报消息 {message_id}: {reason}")
    logger.info("用户 %s 举报消息 %s", g.user_id, message_id)
    return success({"messageId": message_id}, message="举报已提交，我们会尽快处理")


@misc_bp.route("/messages/forward", methods=["POST"])
@auth_required
@rate_limit("forward", max_requests=60, window=60)
def forward_message():
    """转发消息（补齐缺失接口）。"""
    data = require_json(request.get_json(silent=True))
    message_id = data.get("message_id") or data.get("messageId")
    if message_id is None:
        raise ApiError("缺少参数 message_id", 400)
    message_id = validate_int(message_id, "message_id", min_value=1)

    source = db.query_one("SELECT * FROM messages WHERE id = ?", (message_id,))
    if not source:
        raise ApiError("消息不存在", 404)

    receiver_id = data.get("receiver_id") or data.get("receiverId")
    group_id = data.get("group_id") or data.get("groupId")
    if not receiver_id and not group_id:
        raise ApiError("必须指定接收者", 400)

    content = validate_message_content(source["content"])
    timestamp = datetime.now()

    if receiver_id:
        receiver_id = validate_int(receiver_id, "receiver_id", min_value=1)
        if not db.query_one("SELECT id FROM users WHERE id = ?", (receiver_id,)):
            raise ApiError("接收者不存在", 404)
        new_id = db.execute(
            "INSERT INTO messages (sender_id, receiver_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, receiver_id, source["type"] or "text", content, timestamp),
        )
        _notify(
            receiver_id,
            "new_message",
            {"id": new_id, "senderId": g.user_id, "content": content, "type": source["type"]},
        )
    else:
        group_id = validate_int(group_id, "group_id", min_value=1)
        member = db.query_one(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id),
        )
        if not member:
            raise ApiError("你不是该群成员", 403)
        new_id = db.execute(
            "INSERT INTO messages (sender_id, group_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, group_id, source["type"] or "text", content, timestamp),
        )
        _broadcast_room(
            f"group_{group_id}",
            "new_message",
            {"id": new_id, "senderId": g.user_id, "groupId": group_id, "content": content},
        )

    return success({"messageId": new_id}, message="转发成功", status_code=201)


@misc_bp.route("/messages/search", methods=["GET"])
@auth_required
def search_messages():
    """搜索当前用户可见的消息。"""
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        raise ApiError("缺少参数 keyword", 400)
    if len(keyword) > 100:
        raise ApiError("关键词过长", 400)

    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size
    like = f"%{keyword}%"

    # 只搜索自己参与的会话
    base = """
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE m.content LIKE ?
          AND (
                (m.group_id IS NULL AND (m.sender_id = ? OR m.receiver_id = ?))
             OR (m.group_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM group_members gm
                    WHERE gm.group_id = m.group_id AND gm.user_id = ?))
          )
    """
    params = [like, g.user_id, g.user_id, g.user_id]

    total = db.query_scalar(f"SELECT COUNT(*) {base}", params, 0)
    rows = db.query_all(
        f"""
        SELECT m.id, m.sender_id, m.receiver_id, m.group_id, m.type, m.content, m.created_at,
               u.nickname AS sender_nickname
        {base}
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )

    items = [
        {
            "id": row["id"],
            "senderId": row["sender_id"],
            "senderNickname": row["sender_nickname"],
            "receiverId": row["receiver_id"],
            "groupId": row["group_id"],
            "type": row["type"],
            "content": row["content"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size)


# ---------------------------------------------------------------------------
# 用户目录
# ---------------------------------------------------------------------------


@misc_bp.route("/system/create-folder", methods=["POST"])
@auth_required
@rate_limit("create_folder", max_requests=20, window=60)
def create_folder():
    """
    为用户创建聊天记录目录（补齐缺失接口）。

    安全说明：原前端期望在 src/chat_data 下建目录，
    这里改为在 uploads/chat_data 下按用户 ID 隔离，并做目录名校验。
    """
    data = request.get_json(silent=True) or {}
    folder = str(data.get("folder") or data.get("name") or "").strip()

    if not folder:
        raise ApiError("缺少参数 folder", 400)
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", folder):
        raise ApiError("目录名只能包含字母、数字、下划线和连字符", 400)

    base = current_app.config["FUCKCHAT_CONFIG"].base_dir / "uploads" / "chat_data"
    target = base / f"user_{g.user_id}" / folder

    # 二次确认解析后的路径仍在允许范围内，防路径穿越
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        raise ApiError("非法的目录路径", 400)

    target.mkdir(parents=True, exist_ok=True)
    return success(
        {"path": str(target.relative_to(current_app.config["FUCKCHAT_CONFIG"].base_dir))},
        message="目录创建成功",
        status_code=201,
    )


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _notify(user_id, event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload, room=f"user_{user_id}")
    except Exception as exc:
        logger.debug("通知用户 %s 失败: %s", user_id, exc)


def _broadcast_room(room, event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload, room=room)
    except Exception as exc:
        logger.debug("广播房间 %s 失败: %s", room, exc)


def _log_action(action, detail):
    try:
        db.execute(
            "INSERT INTO user_logs (user_id, action, device_info, created_at) VALUES (?, ?, ?, ?)",
            (g.user_id, action, detail, datetime.now()),
        )
    except Exception as exc:
        logger.debug("写用户日志失败: %s", exc)


# ---------------------------------------------------------------------------
# 头像上传兼容入口
#
# 前端 chat.js 调用 /api/user/avatar，profile.js 调用 /api/auth/avatar，
# 而新实现是 /api/upload/avatar。这里做别名转发，避免改动前端行为。
# ---------------------------------------------------------------------------


def _handle_avatar_upload():
    """复用 files 蓝图的头像上传逻辑。"""
    from .files import upload_avatar

    return upload_avatar()


misc_bp.add_url_rule(
    "/user/avatar",
    endpoint="user_avatar_alias",
    view_func=auth_required(rate_limit("upload_avatar", max_requests=10, window=60)(_handle_avatar_upload)),
    methods=["POST"],
)

misc_bp.add_url_rule(
    "/auth/avatar",
    endpoint="auth_avatar_alias",
    view_func=auth_required(rate_limit("upload_avatar", max_requests=10, window=60)(_handle_avatar_upload)),
    methods=["POST"],
)
