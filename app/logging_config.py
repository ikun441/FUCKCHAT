#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 日志配置

替换原先硬编码的 FileHandler("fuckchat.log")，改为读取配置、
支持轮转、目录自动创建。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def setup_logging(config, force=False):
    """
    初始化根日志。

    :param config: Config 实例
    :param force: 强制重新配置（测试用）
    """
    global _configured
    if _configured and not force:
        return logging.getLogger("FUCKCHAT")

    conf = config.section("logging")
    level_name = str(conf.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = conf.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    filename = conf.get("filename", "logs/fuckchat.log")
    max_bytes = int(conf.get("max_bytes", 10 * 1024 * 1024))
    backup_count = int(conf.get("backup_count", 5))

    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # 清理已有 handler，避免重复输出
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level)
    root.addHandler(console)

    # 文件（轮转）
    try:
        log_path = config.resolve_path(filename)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except OSError as exc:
        logging.getLogger("FUCKCHAT.logging").error("无法创建日志文件: %s", exc)

    # 降低 werkzeug 噪音
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)

    _configured = True
    return logging.getLogger("FUCKCHAT")
