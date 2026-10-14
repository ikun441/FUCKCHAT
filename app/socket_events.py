#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - WebSocket 事件处理

重构要点：
- 断线清理不再依赖 request.user_id（Flask 中该属性在断线回调不可靠），
  改为维护 sid -> user_id 内存映射，修复用户永久停留在 online 的问题
- 每个事件都做参数校验与异常兜底，单个事件出错不影响连接
- 消息落库统一走 database 层
"""

import logging
from datetime import datetime

from flask import request
from flask_socketio import emit, join_room, leave_room

from . import database as db

logger = logging.getLogger("FUCKCHAT.socket")

# sid -> user_id 映射
_sid_to_user = {}
# user_id -> set(sid) 支持多设备登录
_user_sids = {}
_lock = __import__("threading").Lock()


def register_socket_events(socketio):
    """注册所有 WebSocket 事件。"""

    @socketio.on("connect")
    def handle_connect():
        logger.info("客户端连接: %s", request.sid)
        emit("connect_response", {"status": "connected", "sid": request.sid})

    @socketio.on("disconnect")
    def handle_disconnect():
        """断线时清理在线状态，使用映射表而非 request 属性。"""
        sid = request.sid
        with _lock:
            user_id = _sid_to_user.pop(sid, None)
            if user_id is not None:
                sids = _user_sids.get(user_id, set())
                sids.discard(sid)
                if not sids:
                    _user_sids.pop(user_id, None)
                still_online = bool(_user_sids.get(user_id))

        if user_id is None:
            logger.info("未认证客户端断开: %s", sid)
            return

        if not still_online:
            try:
                db.execute("UPDATE users SET status = 'offline' WHERE id = ?", (user_id,))
                socketio.emit("user_offline", {"user_id": user_id})
                logger.info("用户 %s 已离线（所有连接断开）", user_id)
            except Exception as exc:
                logger.error("更新离线状态失败: %s", exc)

    @socketio.on("user_status")
    def handle_user_status(data):
        """更新并广播用户在线状态，同时建立 sid 映射。"""
        if not isinstance(data, dict):
            return
        user_id = data.get("user_id")
        status = data.get("status", "online")
        if not user_id:
            return
        if status not in ("online", "offline", "away"):
            return

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return

        sid = request.sid
        with _lock:
            _sid_to_user[sid] = user_id
            _user_sids.setdefault(user_id, set()).add(sid)

        # 确保用户加入自己的私有房间，用于定向推送
        join_room(f"user_{user_id}")

        try:
            db.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
            event = "user_online" if status == "online" else "user_offline"
            socketio.emit(event, {"user_id": user_id, "status": status})
            logger.info("用户 %s 状态更新为 %s", user_id, status)
        except Exception as exc:
            logger.error("更新用户状态失败: %s", exc)

    @socketio.on("request_all_statuses")
    def handle_status_request():
        """下发所有在线用户状态。"""
        try:
            rows = db.query_all(
                "SELECT id, username, nickname, status FROM users WHERE status = 'online'"
            )
            for row in rows:
                emit(
                    "user_online",
                    {
                        "user_id": row["id"],
                        "username": row["username"],
                        "nickname": row["nickname"],
                        "status": "online",
                    },
                )
        except Exception as exc:
            logger.error("获取所有用户状态失败: %s", exc)

    @socketio.on("broadcast_user_update")
    def handle_user_update(data):
        """广播用户资料更新，仅允许广播自己的信息。"""
        if not isinstance(data, dict):
            return
        sid = request.sid
        with _lock:
            user_id = _sid_to_user.get(sid)

        if user_id is None:
            return

        payload_id = data.get("user_id")
        try:
            if payload_id is not None and int(payload_id) != user_id:
                logger.warning("用户 %s 试图广播他人资料更新", user_id)
                return
        except (TypeError, ValueError):
            return

        # 只透传安全的展示字段
        safe = {
            k: v
            for k, v in data.items()
            if k in ("user_id", "nickname", "avatar", "signature", "gender", "location", "status")
        }
        safe["user_id"] = user_id
        socketio.emit("user_update", safe)
        logger.info("广播用户 %s 资料更新", user_id)

    @socketio.on("join")
    def handle_join(data):
        """加入房间，带权限校验。"""
        if not isinstance(data, dict):
            return
        room = data.get("room")
        if not room or not isinstance(room, str) or len(room) > 64:
            return

        with _lock:
            user_id = _sid_to_user.get(request.sid)

        # 私有房间只能加入自己的
        if room.startswith("user_"):
            if user_id is None or room != f"user_{user_id}":
                logger.warning("拒绝 %s 加入房间 %s", user_id, room)
                return
        # 群组房间需校验成员身份
        elif room.startswith("group_"):
            try:
                group_id = int(room.split("_", 1)[1])
            except (ValueError, IndexError):
                return
            if user_id is None:
                return
            member = db.query_one(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, user_id),
            )
            if not member:
                logger.warning("用户 %s 不是群 %s 成员，拒绝加入", user_id, group_id)
                return
        else:
            return

        join_room(room)
        logger.info("用户 %s 加入房间 %s", user_id, room)

    @socketio.on("leave")
    def handle_leave(data):
        if not isinstance(data, dict):
            return
        room = data.get("room")
        if not room:
            return
        leave_room(room)

    @socketio.on("message")
    def handle_message(data):
        """
        房间消息。

        安全说明：sender 一律取服务端会话中的 user_id，
        不信任客户端传入的 sender 字段（原先直接透传给房间内所有人）。
        """
        if not isinstance(data, dict):
            return

        with _lock:
            user_id = _sid_to_user.get(request.sid)
        if user_id is None:
            emit("error", {"message": "未认证，请先发送 user_status"})
            return

        room = data.get("room")
        content = data.get("message")
        message_type = data.get("type", "text")

        if not room or not isinstance(content, str) or not content.strip():
            return

        conf_max = 1000
        if len(content) > conf_max:
            emit("error", {"message": "消息过长"})
            return
        if message_type not in ("text", "emoji", "image", "voice", "file"):
            message_type = "text"

        timestamp = datetime.now().isoformat()

        # 群组消息落库
        group_id = None
        if isinstance(room, str) and room.startswith("group_"):
            try:
                group_id = int(room.split("_", 1)[1])
            except (ValueError, IndexError):
                group_id = None

        if group_id:
            member = db.query_one(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, user_id),
            )
            if not member:
                emit("error", {"message": "你不是该群成员"})
                return

        message_id = None
        try:
            message_id = db.execute(
                "INSERT INTO messages (sender_id, group_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, group_id, message_type, content, timestamp),
            )
        except Exception as exc:
            logger.error("保存房间消息失败: %s", exc)

        emit(
            "message",
            {
                "id": message_id,
                "sender": user_id,
                "senderId": user_id,
                "message": content,
                "type": message_type,
                "timestamp": timestamp,
            },
            room=room,
        )

    @socketio.on("private_message")
    def handle_private_message(data):
        """
        私聊消息（WebSocket 通道）。

        修复：sender 取服务端会话，不信任客户端传值；
        增加黑名单与接存在性校验。
        """
        if not isinstance(data, dict):
            return

        with _lock:
            sender_id = _sid_to_user.get(request.sid)
        if sender_id is None:
            emit("error", {"message": "未认证"})
            return

        receiver_id = data.get("receiver") or data.get("receiver_id") or data.get("receiverId")
        content = data.get("message") or data.get("content")
        message_type = data.get("type", "text")
        client_id = data.get("id")

        if not receiver_id or not isinstance(content, str) or not content.strip():
            return
        if len(content) > 1000:
            emit("error", {"message": "消息过长"})
            return

        try:
            receiver_id = int(receiver_id)
        except (TypeError, ValueError):
            return

        if receiver_id == sender_id:
            return

        if not db.query_one("SELECT id FROM users WHERE id = ?", (receiver_id,)):
            emit("error", {"message": "接收者不存在"})
            return

        blocked = db.query_one(
            """
            SELECT id FROM blacklist
            WHERE (user_id = ? AND blocked_user_id = ?)
               OR (user_id = ? AND blocked_user_id = ?)
            """,
            (sender_id, receiver_id, receiver_id, sender_id),
        )
        if blocked:
            emit("error", {"message": "消息发送失败"})
            return

        timestamp = data.get("timestamp") or datetime.now().isoformat()
        if message_type not in ("text", "emoji", "image", "voice", "file"):
            message_type = "text"

        message_id = client_id
        try:
            message_id = db.execute(
                "INSERT INTO messages (sender_id, receiver_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (sender_id, receiver_id, message_type, content, timestamp),
            )
        except Exception as exc:
            logger.error("保存私聊消息失败: %s", exc)
            if message_id is None:
                message_id = int(datetime.now().timestamp() * 1000)

        payload = {
            "id": message_id,
            "sender": sender_id,
            "sender_id": sender_id,
            "senderId": sender_id,
            "receiver": receiver_id,
            "receiver_id": receiver_id,
            "content": content,
            "message": content,
            "type": message_type,
            "timestamp": timestamp,
            "created_at": timestamp,
        }

        # 发给接收者与发送者各自的私有房间
        socketio.emit("new_message", payload, room=f"user_{receiver_id}")
        socketio.emit("new_message", payload, room=f"user_{sender_id}")
        logger.info("私聊消息: %s -> %s", sender_id, receiver_id)

    @socketio.on("typing")
    def handle_typing(data):
        """正在输入状态转发。"""
        if not isinstance(data, dict):
            return
        with _lock:
            user_id = _sid_to_user.get(request.sid)
        if user_id is None:
            return

        target = data.get("receiver") or data.get("group_id")
        if not target:
            return
        try:
            target = int(target)
        except (TypeError, ValueError):
            return

        if data.get("group_id"):
            socketio.emit("typing", {"user_id": user_id, "groupId": target}, room=f"group_{target}", skip_sid=request.sid)
        else:
            socketio.emit("typing", {"user_id": user_id}, room=f"user_{target}")

    @socketio.on("ping_server")
    def handle_ping():
        emit("pong", {"timestamp": datetime.now().isoformat()})

    logger.info("WebSocket 事件注册完成")
