#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 统一响应格式与业务异常

所有接口统一返回 {success, message, data} 结构，避免各个路由各写一套。

关于兼容层：
    v1 的前端（templates/js/*.js）直接读取响应顶层字段，例如
    `data.token`、`data.users`、`data.messages`。v2 把数据规整到 `data`
    之后，这些读取会全部失效。

    为了不改动 14 万字节的前端代码，这里在响应顶层同时展开一份
    `data` 内容作为兼容别名。即：

        {"success": true, "message": "...", "data": {...}, "token": "...", ...}

    这样两代前端都能正常工作。该行为可通过配置
    `server.legacy_response_aliases` 关闭（设为 false 即为纯 v2 格式）。
"""

from flask import current_app, jsonify


class ApiError(Exception):
    """业务异常，携带 HTTP 状态码与错误码。"""

    def __init__(self, message, status_code=400, code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or _default_code(status_code)


def _default_code(status_code):
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }.get(status_code, "ERROR")


def _legacy_aliases_enabled():
    """是否在顶层展开 data 的字段（v1 前端兼容）。"""
    try:
        conf = current_app.config.get("FUCKCHAT_CONFIG")
        if conf is None:
            return True
        return bool(conf.section("server").get("legacy_response_aliases", True))
    except RuntimeError:
        # 脱离应用上下文调用时，按默认开启处理
        return True


# 这些键不允许被 data 覆盖，否则会破坏响应契约
_RESERVED_KEYS = {"success", "message", "code", "data", "items", "pagination"}


def _build_payload(data, message, extra):
    """组装响应体，包含兼容别名。"""
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    payload.update(extra)

    # 兼容层：把 data 里的键展开到顶层（不覆盖保留键）
    if _legacy_aliases_enabled() and isinstance(data, dict):
        for key, value in data.items():
            if key not in _RESERVED_KEYS and key not in payload:
                payload[key] = value

    return payload


def success(data=None, message="操作成功", status_code=200, **extra):
    """构造成功响应。"""
    return jsonify(_build_payload(data, message, extra)), status_code


def fail(message="操作失败", status_code=400, code=None, **extra):
    """构造失败响应。"""
    payload = {
        "success": False,
        "message": message,
        "code": code or _default_code(status_code),
    }
    payload.update(extra)
    return jsonify(payload), status_code


def paginated(items, total, page, page_size, message="获取成功", **extra):
    """
    构造分页响应。

    同时提供新旧两种形式：
      - v2: {items, pagination}
      - v1: 顶层展开 items 中的字段不适用，因此额外提供 data 别名无意义；
            但保留 `items` 的同时，把调用方通过 **extra 传入的键
            （如 users/groups/logs）展开到顶层供旧前端读取。
    """
    # data 载荷：包含列表本身与分页信息，
    # 同时把调用方通过 **extra 传入的键（如 users=items、logs=items）一并放入，
    # 保证前端既能用 data.items 也能用 data.users / data.logs 取值。
    data_payload = {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        },
    }
    for key, value in extra.items():
        if key not in _RESERVED_KEYS:
            data_payload[key] = value

    payload = {
        "success": True,
        "message": message,
        "data": data_payload,
        "items": items,
        "pagination": data_payload["pagination"],
    }
    payload.update(extra)

    # 兼容层：仅保留顶层展开（供尚未迁移的旧调用点）；
    # 前端已统一改用 data.*，顶层展开可随 legacy_response_aliases 关闭。
    if not _legacy_aliases_enabled():
        for key in list(payload.keys()):
            if key in payload and key not in _RESERVED_KEYS and key in extra:
                payload.pop(key, None)

    return jsonify(payload), 200
