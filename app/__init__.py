#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 应用包

提供 create_app 应用工厂，替代原先 run.py 里混杂的全局单例写法。
"""

from .config import get_config, load_config, reset_config
from .responses import ApiError, fail, paginated, success

__all__ = [
    "create_app",
    "get_config",
    "load_config",
    "reset_config",
    "ApiError",
    "fail",
    "paginated",
    "success",
]


def create_app(config=None, config_path=None):
    """
    应用工厂。

    :param config: 已加载的 Config 实例（测试可注入）
    :param config_path: 配置文件路径
    :return: (app, socketio)
    """
    from .factory import build_app

    if config is None:
        config = load_config(config_path)
    return build_app(config)
