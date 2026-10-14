#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 统一响应格式与业务异常

所有接口统一返回 {success, ...} 结构，避免各个路由各写一套。
"""

from flask import jsonify


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


def success(data=None, message="操作成功", status_code=200, **extra):
    """构造成功响应。"""
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload), status_code


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
    """构造分页响应。"""
    payload = {
        "success": True,
        "message": message,
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        },
    }
    payload.update(extra)
    return jsonify(payload), 200
