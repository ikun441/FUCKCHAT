#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 全局错误处理

保证任何异常都返回结构化 JSON，而不是 Flask 默认的 HTML 500 页面。
"""

import logging

from werkzeug.exceptions import HTTPException

from .responses import ApiError, fail

logger = logging.getLogger("FUCKCHAT.errors")


def register_error_handlers(app):
    """注册全局错误处理器。"""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        # 业务异常，属预期内，用 info 级别
        logger.info("业务异常: %s (%s)", error.message, error.status_code)
        response, _ = fail(error.message, error.status_code, code=error.code)
        return response, error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        """处理 Werkzeug 抛出的 HTTP 异常，避免返回 HTML。"""
        message = error.description or error.name
        if error.code == 404:
            message = "接口不存在"
        elif error.code == 405:
            message = "请求方法不被允许"
        elif error.code == 413:
            message = "上传内容超过大小限制"
        return fail(message, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """兜底：捕获未预期异常，记录堆栈但不泄漏细节给客户端。"""
        logger.exception("未处理异常: %s", error)
        # 若是 JSON 请求才返回 JSON，页面请求走 500 页面
        from flask import request

        if request.path.startswith("/api/") or request.is_json:
            return fail("服务器内部错误", 500, code="INTERNAL_ERROR")
        return fail("服务器内部错误", 500, code="INTERNAL_ERROR")
