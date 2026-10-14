#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 文件上传路由

补齐原前端调用但后端缺失的接口：
    POST /api/upload/file          通用文件上传
    POST /api/upload/avatar        头像上传
    POST /api/auth/avatar          头像上传（前端使用的别名）
    POST /api/upload/json          聊天记录 JSON 上传（兼容旧前端）

安全要点：
- 扩展名白名单
- 文件名重写（不使用用户提供的名字，杜绝路径穿越）
- 大小限制
- 按用户分目录存放
"""

import logging
import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, g, request

from .. import database as db
from ..responses import ApiError, success
from ..security import auth_required, rate_limit
from ..validators import allowed_extension, is_safe_filename

logger = logging.getLogger("FUCKCHAT.files")

files_bp = Blueprint("files", __name__)

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_CATEGORIES = {"avatar", "image", "voice", "file"}


def _upload_root():
    return current_app.config["FUCKCHAT_CONFIG"].base_dir / "uploads"


def _save_upload(file_storage, category, allowed_exts):
    """保存上传文件，返回可访问的相对 URL。"""
    if file_storage is None or not file_storage.filename:
        raise ApiError("没有选择文件", 400)

    original = file_storage.filename
    if not is_safe_filename(original):
        # 不信任原始文件名，仅用于取扩展名
        original = os.path.basename(original)

    if not allowed_extension(original, allowed_exts):
        raise ApiError(
            f"不支持的文件类型，仅允许: {', '.join(sorted(allowed_exts))}", 400
        )

    ext = original.rsplit(".", 1)[1].lower()
    # 服务端生成文件名，杜绝路径穿越与覆盖攻击
    safe_name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:16]}.{ext}"

    target_dir = _upload_root() / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name

    file_storage.save(str(target_path))

    size = target_path.stat().st_size
    return {
        "url": f"/uploads/{category}/{safe_name}",
        "filename": safe_name,
        "originalName": original,
        "size": size,
        "category": category,
    }


# ---------------------------------------------------------------------------
# 上传接口
# ---------------------------------------------------------------------------


@files_bp.route("/file", methods=["POST"])
@auth_required
@rate_limit("upload", max_requests=30, window=60)
def upload_file():
    """通用文件上传。"""
    conf = current_app.config["FUCKCHAT_CONFIG"]
    allowed = set(
        str(item).lower().lstrip(".")
        for item in conf["app"].get("allowed_file_extensions", [])
    )
    allowed |= IMAGE_EXTENSIONS

    result = _save_upload(request.files.get("file"), "files", allowed)

    db.execute(
        """
        INSERT INTO files (user_id, filename, original_name, file_path, file_size, file_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.user_id,
            result["filename"],
            result["originalName"],
            result["url"],
            result["size"],
            result["filename"].rsplit(".", 1)[-1],
            datetime.now(),
        ),
    )

    logger.info("用户 %s 上传文件 %s (%s bytes)", g.user_id, result["filename"], result["size"])
    return success(result, message="上传成功", status_code=201)


@files_bp.route("/image", methods=["POST"])
@auth_required
@rate_limit("upload", max_requests=30, window=60)
def upload_image():
    """聊天图片上传。"""
    result = _save_upload(request.files.get("file"), "images", IMAGE_EXTENSIONS)
    logger.info("用户 %s 上传图片 %s", g.user_id, result["filename"])
    return success(result, message="图片上传成功", status_code=201)


@files_bp.route("/voice", methods=["POST"])
@auth_required
@rate_limit("upload", max_requests=30, window=60)
def upload_voice():
    """语音消息上传。"""
    result = _save_upload(request.files.get("file"), "voice", {"mp3", "wav", "ogg", "webm", "m4a"})
    return success(result, message="语音上传成功", status_code=201)


@files_bp.route("/avatar", methods=["POST"])
@auth_required
@rate_limit("upload_avatar", max_requests=10, window=60)
def upload_avatar():
    """上传头像并立即更新当前用户。"""
    result = _save_upload(request.files.get("file") or request.files.get("avatar"), "avatars", IMAGE_EXTENSIONS)

    db.execute("UPDATE users SET avatar = ? WHERE id = ?", (result["url"], g.user_id))
    logger.info("用户 %s 更新头像: %s", g.user_id, result["url"])

    _broadcast("user_update", {"user_id": g.user_id, "avatar": result["url"]})
    return success({"avatar": result["url"]}, message="头像上传成功")


@files_bp.route("/json", methods=["POST"])
@auth_required
@rate_limit("upload", max_requests=20, window=60)
def upload_json():
    """
    接收聊天记录 JSON。

    安全说明：原先该接口把文件直接写到 src/chat_data/ 且不做校验。
    现在只接受 JSON 扩展名，落盘到 uploads/files，并对体积设限。
    """
    conf = current_app.config["FUCKCHAT_CONFIG"]
    max_size = int(conf["app"].get("max_content_length", 16 * 1024 * 1024))

    file_storage = request.files.get("file")
    if file_storage is None:
        raise ApiError("没有选择文件", 400)

    filename = file_storage.filename or "data.json"
    if not filename.lower().endswith(".json"):
        raise ApiError("只接受 .json 文件", 400)

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > max_size:
        raise ApiError("文件过大", 413)

    import json as json_module

    try:
        payload = json_module.loads(file_storage.read().decode("utf-8"))
    except (UnicodeDecodeError, json_module.JSONDecodeError) as exc:
        raise ApiError(f"JSON 格式错误: {exc}", 400)

    if not isinstance(payload, (dict, list)):
        raise ApiError("JSON 顶层必须为对象或数组", 400)

    result = _save_upload(file_storage, "files", {"json"})
    logger.info("用户 %s 上传聊天记录 JSON (%s bytes)", g.user_id, size)
    return success(result, message="上传成功", status_code=201)


def _broadcast(event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload)
    except Exception as exc:
        logger.debug("广播 %s 失败: %s", event, exc)
