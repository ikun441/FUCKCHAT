#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 应用工厂实现

集中完成：配置装载、日志、数据库、扩展、蓝图注册、页面路由、错误处理。
原先这些都堆在 run.py 顶层，导致循环导入与硬编码。
"""

import logging
import os

from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

from . import database as db
from .errors import register_error_handlers
from .logging_config import setup_logging
from .responses import fail, success

logger = logging.getLogger("FUCKCHAT.factory")

socketio = SocketIO()


def build_app(config):
    """根据配置构建 Flask 应用与 SocketIO。"""
    setup_logging(config)

    base_dir = config.base_dir
    app = Flask(
        __name__.split(".")[0],
        static_folder=str(base_dir / "src"),
        template_folder=str(base_dir / "templates" / "html"),
    )

    # --- 核心配置 ---
    app.config["SECRET_KEY"] = config["app"]["secret_key"]
    app.config["MAX_CONTENT_LENGTH"] = int(
        config["app"].get("max_content_length", 16 * 1024 * 1024)
    )
    app.config["JSON_SORT_KEYS"] = False
    app.config["FUCKCHAT_CONFIG"] = config
    app.config["PROPAGATE_EXCEPTIONS"] = False

    # --- CORS：默认不放开，显式配置才允许 ---
    cors_origins = config.section("server").get("cors_origins") or []
    if cors_origins:
        CORS(app, origins=cors_origins, supports_credentials=True)
        logger.info("CORS 已启用，允许来源: %s", cors_origins)
    else:
        logger.info("CORS 未启用（默认仅同源访问）")

    # --- 数据库 ---
    db.init_app(app, config)

    # --- SocketIO ---
    socketio.init_app(
        app,
        cors_allowed_origins=cors_origins or None,
        async_mode="threading",
        logger=False,
        engineio_logger=False,
    )

    # --- 蓝图 ---
    from .routes.admin import admin_bp
    from .routes.auth import auth_bp
    from .routes.chat import chat_bp
    from .routes.files import files_bp
    from .routes.kunbi import kunbi_bp
    from .routes.misc import misc_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(kunbi_bp, url_prefix="/api/kunbi")
    app.register_blueprint(files_bp, url_prefix="/api/upload")
    app.register_blueprint(misc_bp, url_prefix="/api")

    # --- 静态资源路由（兼容前端既有路径） ---
    @app.route("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(str(base_dir / "templates" / "js"), filename)

    @app.route("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(str(base_dir / "templates" / "css"), filename)

    @app.route("/images/<path:filename>")
    def serve_images(filename):
        return send_from_directory(str(base_dir / "src" / "images"), filename)

    @app.route("/favicon.ico")
    def favicon():
        favicon_rel = config.section("ui").get("favicon", "src/images/website.ico")
        favicon_path = config.resolve_path(favicon_rel)
        return send_from_directory(
            str(favicon_path.parent),
            favicon_path.name,
            mimetype="image/vnd.microsoft.icon",
        )

    @app.route("/uploads/<path:filename>")
    def serve_uploads(filename):
        return send_from_directory(str(base_dir / "uploads"), filename)

    # --- 健康检查 ---
    @app.route("/api/health")
    def health():
        return success(
            {
                "status": "ok",
                "name": config["app"].get("name", "FUCKCHAT"),
                "version": config["app"].get("version", "2.0.0"),
            },
            message="服务正常",
        )

    # --- 页面路由 ---
    # 修复：模板实际位于 templates/html/<name>.html 与 templates/html/admin/<name>.html
    page_defs = {
        "/": "index.html",
        "/login": "login.html",
        "/register": "register.html",
        "/chat": "chat.html",
        "/about": "about.html",
        "/profile": "profile.html",
        "/mail": "mail.html",
    }
    for rule, template in page_defs.items():
        app.add_url_rule(
            rule,
            endpoint=f"page_{template.replace('.', '_')}",
            view_func=_make_page_view(template),
        )

    # 管理后台页面（修复原先的 TemplateNotFound 500）
    app.add_url_rule(
        "/admin",
        endpoint="page_admin_login",
        view_func=_make_page_view("admin/admin_login.html"),
    )
    app.add_url_rule(
        "/admin/dashboard",
        endpoint="page_admin_dashboard",
        view_func=_make_page_view("admin/admin_dashboard.html"),
    )

    # --- SocketIO 事件 ---
    from .socket_events import register_socket_events

    register_socket_events(socketio)

    # 确保上传目录存在
    for sub in ("avatars", "files", "images", "voice"):
        os.makedirs(base_dir / "uploads" / sub, exist_ok=True)

    register_error_handlers(app)

    logger.info(
        "应用构建完成: %s v%s",
        config["app"].get("name", "FUCKCHAT"),
        config["app"].get("version", "2.0.0"),
    )
    return app, socketio


def _make_page_view(template_name):
    """生成页面视图函数，模板缺失时返回友好错误而非 500 堆栈。"""

    def view():
        try:
            return render_template(template_name)
        except Exception as exc:  # jinja2.TemplateNotFound 等
            logger.error("渲染模板失败 %s: %s", template_name, exc)
            return (
                render_template("error.html", message="页面模板缺失") 
                if _template_exists(template_name)
                else _plain_error("页面暂时不可用")
            )

    view.__name__ = f"view_{template_name.replace('/', '_').replace('.', '_')}"
    return view


def _template_exists(name):
    from flask import current_app

    return name in current_app.jinja_env.list_templates()


def _plain_error(message):
    return f"<h1>{message}</h1>", 500
