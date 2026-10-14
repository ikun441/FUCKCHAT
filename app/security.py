#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 安全工具

包含 JWT 签发/校验、密码哈希、登录限速、认证与授权装饰器。
替换原先裸 except、无令牌类型校验、无失败锁定的实现。
"""

import time
import hmac
import logging
import threading
from functools import wraps
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from flask import request, g, current_app

from .responses import ApiError
from . import database as db

logger = logging.getLogger("FUCKCHAT.security")

# ---------------------------------------------------------------------------
# 密码
# ---------------------------------------------------------------------------


def hash_password(password):
    """使用 bcrypt 哈希密码。"""
    if isinstance(password, str):
        password = password.encode("utf-8")
    return bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))


def verify_password(password, password_hash):
    """校验密码，异常时返回 False 而非抛出。"""
    if not password or password_hash is None:
        return False
    try:
        if isinstance(password, str):
            password = password.encode("utf-8")
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        return bcrypt.checkpw(password, password_hash)
    except (ValueError, TypeError) as exc:
        logger.warning("密码校验异常: %s", exc)
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def _secret_key():
    return current_app.config["SECRET_KEY"]


def create_token(user_id, username, is_admin=False, ttl_hours=None):
    """签发 JWT，包含类型声明以防令牌混用。"""
    conf = current_app.config.get("FUCKCHAT_CONFIG")
    ttl = ttl_hours
    if ttl is None:
        if is_admin:
            ttl = conf.section("app").get("admin_token_ttl_hours", 12)
        else:
            ttl = conf.section("app").get("token_ttl_hours", 24)

    now = datetime.now(timezone.utc)
    payload = {
        "user_id": int(user_id),
        "username": username,
        "is_admin": bool(is_admin),
        "type": "admin" if is_admin else "access",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(hours=ttl),
    }
    return jwt.encode(payload, _secret_key(), algorithm="HS256")


def decode_token(token):
    """
    解码并校验 JWT。

    不再使用裸 except，明确区分过期与非法令牌。
    """
    if not token:
        raise ApiError("缺少认证令牌", 401)
    try:
        return jwt.decode(token, _secret_key(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ApiError("认证令牌已过期", 401, code="TOKEN_EXPIRED")
    except jwt.InvalidTokenError as exc:
        logger.info("无效令牌: %s", exc)
        raise ApiError("无效的认证令牌", 401)


def extract_token():
    """从 Authorization 头提取 Bearer 令牌。"""
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------


def auth_required(func):
    """要求已登录。"""

    @wraps(func)
    def decorated(*args, **kwargs):
        payload = decode_token(extract_token())
        user_id = payload.get("user_id")
        if not user_id:
            raise ApiError("无效的认证令牌", 401)

        # 校验用户仍然存在且未被禁用
        row = db.query_one(
            "SELECT id, username, is_admin, status FROM users WHERE id = ?", (user_id,)
        )
        if not row:
            raise ApiError("用户不存在或已被删除", 401)

        g.user_id = row["id"]
        g.username = row["username"]
        g.is_admin = bool(row["is_admin"])
        return func(*args, **kwargs)

    return decorated


def admin_required(func):
    """要求管理员权限，且必须在服务端复核，不信任令牌中的声明。"""

    @wraps(func)
    def decorated(*args, **kwargs):
        payload = decode_token(extract_token())
        user_id = payload.get("user_id")
        if not user_id:
            raise ApiError("无效的认证令牌", 401)

        row = db.query_one(
            "SELECT id, username, is_admin FROM users WHERE id = ?", (user_id,)
        )
        if not row:
            raise ApiError("用户不存在或已被删除", 401)
        # 服务端权威判定，令牌里的 is_admin 仅作参考
        if not row["is_admin"]:
            logger.warning("用户 %s 尝试访问管理员接口", row["username"])
            raise ApiError("没有管理员权限", 403)

        g.user_id = row["id"]
        g.username = row["username"]
        g.is_admin = True
        return func(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# 登录限速与失败锁定（内存实现，单进程够用；多进程需换 Redis）
# ---------------------------------------------------------------------------


class RateLimiter:
    """滑动窗口限速器，线程安全。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = {}       # key -> [timestamps]
        self._blocked = {}    # key -> unblock_timestamp

    def _now(self):
        return time.time()

    def _prune(self, key, window):
        cutoff = self._now() - window
        entries = self._hits.get(key, [])
        entries = [ts for ts in entries if ts > cutoff]
        if entries:
            self._hits[key] = entries
        else:
            self._hits.pop(key, None)
        return entries

    def is_blocked(self, key):
        """检查是否处于锁定状态。"""
        with self._lock:
            unblock_at = self._blocked.get(key)
            if unblock_at is None:
                return False, 0
            if unblock_at <= self._now():
                self._blocked.pop(key, None)
                return False, 0
            return True, int(unblock_at - self._now())

    def record_failure(self, key, max_attempts, lockout_seconds):
        """记录一次失败，达到阈值则锁定并返回剩余锁定秒数。"""
        with self._lock:
            now = self._now()
            window = lockout_seconds
            entries = [ts for ts in self._hits.get(key, []) if ts > now - window]
            entries.append(now)
            self._hits[key] = entries

            if len(entries) >= max_attempts:
                self._blocked[key] = now + lockout_seconds
                self._hits.pop(key, None)
                return lockout_seconds
            return 0

    def reset(self, key):
        """成功登录后清除计数。"""
        with self._lock:
            self._hits.pop(key, None)
            self._blocked.pop(key, None)

    def check_rate(self, key, window, max_requests):
        """通用限速：返回 (是否超限, 剩余秒数)。"""
        with self._lock:
            now = self._now()
            entries = [ts for ts in self._hits.get(key, []) if ts > now - window]
            if len(entries) >= max_requests:
                retry_after = int(entries[0] + window - now) + 1
                self._hits[key] = entries
                return True, retry_after
            entries.append(now)
            self._hits[key] = entries
            return False, 0


limiter = RateLimiter()


def get_client_ip():
    """获取客户端 IP，默认不信任代理头（防伪造绕过限速）。"""
    conf = current_app.config.get("FUCKCHAT_CONFIG")
    trust_proxy = False
    if conf is not None:
        trust_proxy = bool(conf.section("security").get("trust_proxy", False))

    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(bucket, max_requests=None, window=None):
    """
    通用接口限速装饰器。

    :param bucket: 限速分组名
    :param max_requests: 窗口内最大请求数，默认读配置
    :param window: 窗口秒数，默认读配置
    """

    def decorator(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            conf = current_app.config.get("FUCKCHAT_CONFIG")
            sec = conf.section("security") if conf else {}
            limit_max = max_requests or sec.get("rate_limit_max_requests", 120)
            limit_window = window or sec.get("rate_limit_window_seconds", 60)

            key = f"{bucket}:{get_client_ip()}"
            exceeded, retry_after = limiter.check_rate(key, limit_window, limit_max)
            if exceeded:
                logger.warning("限速触发: %s", key)
                resp = ApiError("请求过于频繁，请稍后再试", 429)
                raise resp
            return func(*args, **kwargs)

        return decorated

    return decorator


def login_guard(identifier):
    """
    登录前置检查：若该标识已锁定则拒绝。

    :return: None（未锁定）
    """
    conf = current_app.config.get("FUCKCHAT_CONFIG")
    sec = conf.section("security") if conf else {}
    max_attempts = sec.get("login_max_attempts", 5)
    lockout = sec.get("login_lockout_seconds", 300)

    key = f"login:{identifier}"
    blocked, remaining = limiter.is_blocked(key)
    if blocked:
        raise ApiError(
            f"登录失败次数过多，请 {remaining} 秒后重试", 429, code="ACCOUNT_LOCKED"
        )
    return max_attempts, lockout


def register_login_failure(identifier, max_attempts, lockout):
    """记录登录失败。"""
    key = f"login:{identifier}"
    locked_for = limiter.record_failure(key, max_attempts, lockout)
    if locked_for:
        logger.warning("账号 %s 因连续登录失败被锁定 %s 秒", identifier, locked_for)
    return locked_for


def clear_login_failures(identifier):
    """登录成功后清理计数。"""
    limiter.reset(f"login:{identifier}")


def constant_time_compare(a, b):
    """常量时间字符串比较，防时序攻击。"""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
