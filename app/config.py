#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 应用配置模块

集中管理配置加载与校验，替换原先散落在各处的硬编码值。
支持环境变量覆盖，密钥不再入源码库。
"""

import os
import secrets
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger("FUCKCHAT.config")

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 默认配置，缺项时兜底，避免任何 KeyError
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
        "cors_origins": [],
        # 是否在响应顶层展开 data 字段，以兼容 v1 前端读取方式
        "legacy_response_aliases": True,
        "local_network": {
            "enabled": True,
            "domain": "",
            "broadcast": False,
        },
    },
    "app": {
        "name": "FUCKCHAT",
        "secret_key": "",
        "max_content_length": 16 * 1024 * 1024,
        "allowed_file_extensions": ["jpg", "jpeg", "png", "gif", "mp3", "wav"],
        "token_ttl_hours": 24,
        "admin_token_ttl_hours": 12,
    },
    "database": {
        "type": "sqlite",
        "path": "fuckchat.db",
        "timeout": 10.0,
        "backup_keep": 5,
    },
    "security": {
        "password_min_length": 8,
        "password_max_length": 128,
        "username_min_length": 3,
        "username_max_length": 32,
        "nickname_max_length": 32,
        "message_max_length": 1000,
        "login_max_attempts": 5,
        "login_lockout_seconds": 300,
        "rate_limit_window_seconds": 60,
        "rate_limit_max_requests": 120,
        "trust_proxy": False,
    },
    "chat": {
        "max_message_length": 1000,
        "history_message_count": 100,
        "max_page_size": 100,
        "kunbi_redpacket": {
            "min_amount": 1,
            "max_amount": 10000,
            "animation": True,
        },
    },
    "user": {
        "default_kunbi": 100,
        "avatar_path": "src/images/avatars/",
    },
    "group": {
        "max_member_count": 100,
        "avatar_path": "src/images/groups/",
    },
    "ui": {
        "animations": True,
        "message_animations": True,
        "theme": "light",
        "favicon": "src/images/website.ico",
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "filename": "logs/fuckchat.log",
        "max_bytes": 10 * 1024 * 1024,
        "backup_count": 5,
    },
    "admin": {
        "port": 5004,
        "host": "127.0.0.1",
        "username": "admin",
        "password": "",
        "password_hash": "",
        "session_ttl_hours": 8,
    },
    "email": {
        "enabled": False,
    },
}


def _deep_merge(base, override):
    """递归合并配置，override 覆盖 base，缺失的键保留默认值。"""
    result = dict(base)
    for key, value in (override or {}).items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config):
    """环境变量覆盖，便于部署时注入密钥而不改文件。"""
    env_map = {
        "FUCKCHAT_SECRET_KEY": ("app", "secret_key"),
        "FUCKCHAT_HOST": ("server", "host"),
        "FUCKCHAT_PORT": ("server", "port"),
        "FUCKCHAT_DEBUG": ("server", "debug"),
        "FUCKCHAT_DB_PATH": ("database", "path"),
        "FUCKCHAT_LOG_LEVEL": ("logging", "level"),
        "FUCKCHAT_ADMIN_USERNAME": ("admin", "username"),
        "FUCKCHAT_ADMIN_PASSWORD": ("admin", "password"),
    }
    for env_key, path in env_map.items():
        raw = os.environ.get(env_key)
        if raw is None or raw == "":
            continue
        section, field = path
        if field == "port":
            try:
                config[section][field] = int(raw)
            except ValueError:
                logger.warning("环境变量 %s 不是合法端口，已忽略", env_key)
            continue
        if field == "debug":
            config[section][field] = raw.strip().lower() in ("1", "true", "yes", "on")
            continue
        config[section][field] = raw
    return config


def _resolve_secret_key(config):
    """
    解析密钥，优先级：环境变量 > 配置文件 > 本地密钥文件 > 自动生成。

    自动生成时写入 .secret_key 文件（已加入 .gitignore），
    确保密钥永远不会出现在源码或版本库中。
    """
    secret = os.environ.get("FUCKCHAT_SECRET_KEY") or config["app"].get("secret_key")
    if secret and len(secret) >= 16:
        return secret

    secret_file = BASE_DIR / ".secret_key"
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if len(stored) >= 16:
            return stored

    generated = secrets.token_urlsafe(48)
    try:
        secret_file.write_text(generated, encoding="utf-8")
        os.chmod(secret_file, 0o600)
        logger.warning(
            "未配置 secret_key，已自动生成并写入 %s。"
            "生产环境请通过环境变量 FUCKCHAT_SECRET_KEY 显式指定。",
            secret_file,
        )
    except OSError as exc:
        logger.error("无法写入密钥文件，本次运行使用临时密钥: %s", exc)
    return generated


class Config:
    """配置对象，支持属性式与字典式访问。"""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def section(self, name):
        """返回指定区块，保证一定存在（避免 KeyError）。"""
        return self._data.get(name, {})

    def as_dict(self):
        return self._data

    @property
    def base_dir(self):
        return BASE_DIR

    def resolve_path(self, relative):
        """把配置中的相对路径解析为绝对路径。"""
        path = Path(relative)
        return path if path.is_absolute() else BASE_DIR / path


def load_config(config_path=None):
    """
    加载并规范化配置。

    :param config_path: 配置文件路径，默认使用项目根目录 config.yaml
    :return: Config 实例
    """
    load_dotenv(BASE_DIR / ".env")

    if config_path is None:
        config_path = BASE_DIR / "config.yaml"
    else:
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = BASE_DIR / config_path

    file_config = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                file_config = yaml.safe_load(handle) or {}
            logger.info("配置文件加载成功: %s", config_path)
        except (OSError, yaml.YAMLError) as exc:
            logger.error("加载配置文件失败，使用默认配置: %s", exc)
    else:
        logger.warning("配置文件不存在，使用默认配置: %s", config_path)

    merged = _deep_merge(DEFAULT_CONFIG, file_config)
    merged = _apply_env_overrides(merged)
    merged["app"]["secret_key"] = _resolve_secret_key(merged)
    return Config(merged)


_config = None


def get_config():
    """获取全局配置单例。"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config():
    """重置配置单例（供测试使用）。"""
    global _config
    _config = None
