#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 主程序入口（重构版）

原先该文件混杂了配置加载、日志、蓝图注册、页面路由、WebSocket 事件等，
现已拆分到 app/ 包中，这里仅负责启动。

用法:
    python run.py
    python run.py --config path/to/config.yaml
    python run.py --port 8080
"""

import argparse
import logging
import sys

from app import create_app
from app.config import load_config

logger = logging.getLogger("FUCKCHAT")


def parse_args():
    parser = argparse.ArgumentParser(description="FUCKCHAT 主服务")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--host", default=None, help="监听地址")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="开启调试模式")
    return parser.parse_args()


def main():
    args = parse_args()

    config = load_config(args.config)
    app, socketio = create_app(config)

    host = args.host or config.section("server").get("host", "0.0.0.0")
    port = args.port or config.section("server").get("port", 5000)
    debug = args.debug or bool(config.section("server").get("debug", False))

    logger.info("=" * 56)
    logger.info("FUCKCHAT 服务启动")
    logger.info("监听地址: http://%s:%s", host, port)
    logger.info("调试模式: %s", "开启" if debug else "关闭")
    logger.info("=" * 56)

    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True,
            use_reloader=False,
        )
    except OSError as exc:
        logger.error("启动失败: %s", exc)
        logger.error(
            "端口 %s 可能已被占用。可改用其他端口: python run.py --port 5100",
            port,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("服务已停止")


if __name__ == "__main__":
    main()
