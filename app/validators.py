#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 输入校验与清洗

集中处理所有外部输入的长度、格式、类型校验，替换原先
"什么都不校验" 的实现（曾可写入 100000 字符昵称、1 字符密码）。
"""

import re
import html
import logging

from .responses import ApiError

logger = logging.getLogger("FUCKCHAT.validators")

# 用户名：字母开头，允许字母数字下划线连字符
USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
# 邮箱：宽松校验
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
# 手机号：可选的国际区号 + 数字
PHONE_PATTERN = re.compile(r"^\+?[0-9]{5,20}$")
# HTML 标签检测
HTML_TAG_PATTERN = re.compile(r"<[^>]*>")

# 允许的资料字段（显式白名单，配合参数化 SQL 使用）
PROFILE_TEXT_FIELDS = {
    "nickname": 32,
    "signature": 200,
    "location": 64,
    "gender": 16,
    "birthday": 32,
    "email": 128,
    "phone": 32,
}


def _config():
    from .config import get_config

    return get_config()


def require_json(data):
    """确保请求体是 JSON 对象。"""
    if not isinstance(data, dict):
        raise ApiError("请求体必须是 JSON 对象", 400)
    return data


def require_fields(data, fields):
    """确保必填字段存在且非空。"""
    missing = []
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    if missing:
        raise ApiError(f"缺少必要参数: {', '.join(missing)}", 400)
    return data


def clean_text(value, field, max_length, allow_empty=False):
    """
    清洗文本：去首尾空白、剔除 HTML 标签、长度校验。

    返回清洗后的字符串。
    """
    if value is None:
        if allow_empty:
            return ""
        raise ApiError(f"{field} 不能为空", 400)

    if not isinstance(value, str):
        value = str(value)

    cleaned = value.strip()
    if not cleaned and not allow_empty:
        raise ApiError(f"{field} 不能为空", 400)

    # 剔除 HTML 标签，防止存储型 XSS
    if HTML_TAG_PATTERN.search(cleaned):
        cleaned = HTML_TAG_PATTERN.sub("", cleaned).strip()

    if len(cleaned) > max_length:
        raise ApiError(f"{field} 长度不能超过 {max_length} 个字符", 400)

    return cleaned


def validate_username(value):
    """校验用户名格式与长度。"""
    conf = _config().section("security")
    min_len = conf.get("username_min_length", 3)
    max_len = conf.get("username_max_length", 32)

    if not isinstance(value, str):
        raise ApiError("用户名格式不正确", 400)
    username = value.strip()

    if len(username) < min_len:
        raise ApiError(f"用户名长度至少 {min_len} 个字符", 400)
    if len(username) > max_len:
        raise ApiError(f"用户名长度不能超过 {max_len} 个字符", 400)
    if not USERNAME_PATTERN.match(username):
        raise ApiError("用户名只能包含字母、数字、下划线和连字符，且必须以字母开头", 400)

    return username


def validate_password(value, field="密码"):
    """校验密码强度。"""
    conf = _config().section("security")
    min_len = conf.get("password_min_length", 8)
    max_len = conf.get("password_max_length", 128)

    if not isinstance(value, str) or not value:
        raise ApiError(f"{field} 不能为空", 400)
    if len(value) < min_len:
        raise ApiError(f"{field}长度至少 {min_len} 个字符", 400)
    if len(value) > max_len:
        raise ApiError(f"{field}长度不能超过 {max_len} 个字符", 400)
    # bcrypt 只取前 72 字节，超长密码会被静默截断
    if len(value.encode("utf-8")) > 72:
        raise ApiError(f"{field}过长（超过 72 字节）", 400)

    has_letter = any(ch.isalpha() for ch in value)
    has_digit = any(ch.isdigit() for ch in value)
    if not (has_letter and has_digit):
        raise ApiError(f"{field}必须同时包含字母和数字", 400)

    return value


def validate_email(value, allow_empty=True):
    if value is None or value == "":
        if allow_empty:
            return ""
        raise ApiError("邮箱不能为空", 400)
    if not isinstance(value, str):
        raise ApiError("邮箱格式不正确", 400)
    email = value.strip()
    if not email and allow_empty:
        return ""
    if len(email) > 128 or not EMAIL_PATTERN.match(email):
        raise ApiError("邮箱格式不正确", 400)
    return email


def validate_phone(value, allow_empty=True):
    if value is None or value == "":
        if allow_empty:
            return ""
        raise ApiError("手机号不能为空", 400)
    if not isinstance(value, str):
        raise ApiError("手机号格式不正确", 400)
    phone = value.strip()
    if not phone and allow_empty:
        return ""
    if not PHONE_PATTERN.match(phone):
        raise ApiError("手机号格式不正确", 400)
    return phone


def validate_gender(value):
    allowed = ("male", "female", "other", "男", "女", "其他", "")
    if value is None:
        return "other"
    if not isinstance(value, str) or value not in allowed:
        raise ApiError("性别取值不合法", 400)
    return value or "other"


def validate_int(value, field, min_value=None, max_value=None, default=None):
    """
    安全地解析整数。

    原先 int(request.args.get('limit')) 遇到非法值直接 500，
    这里统一转为 400。
    """
    if value is None or value == "":
        if default is not None:
            return default
        raise ApiError(f"缺少参数: {field}", 400)

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} 必须是整数", 400)

    if min_value is not None and parsed < min_value:
        raise ApiError(f"{field} 不能小于 {min_value}", 400)
    if max_value is not None and parsed > max_value:
        raise ApiError(f"{field} 不能大于 {max_value}", 400)

    return parsed


def validate_amount(value, field, min_value=1, max_value=100000):
    """校验金额（坤币），必须为整数。"""
    return validate_int(value, field, min_value=min_value, max_value=max_value)


def validate_pagination(args):
    """解析分页参数，带上限保护。"""
    conf = _config().section("chat")
    max_page_size = conf.get("max_page_size", 100)

    page = validate_int(args.get("page"), "page", min_value=1, default=1)
    page_size = validate_int(
        args.get("page_size") or args.get("per_page"),
        "page_size",
        min_value=1,
        max_value=max_page_size,
        default=20,
    )
    return page, page_size


def validate_message_content(value):
    """校验消息内容长度。"""
    conf = _config().section("chat")
    max_len = conf.get("max_message_length", 1000)
    if not isinstance(value, str):
        raise ApiError("消息内容格式不正确", 400)
    if not value.strip():
        raise ApiError("消息内容不能为空", 400)
    if len(value) > max_len:
        raise ApiError(f"消息长度不能超过 {max_len} 个字符", 400)
    return value


def sanitize_output(text):
    """输出转义，用于非 JSON 场景。"""
    if not isinstance(text, str):
        return text
    return html.escape(text)


def is_safe_filename(filename):
    """检查文件名是否安全（防路径穿越）。"""
    if not filename or not isinstance(filename, str):
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return bool(re.match(r"^[\w\-. ]+$", filename))


def allowed_extension(filename, allowed):
    """检查扩展名是否在白名单内。"""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in [str(item).lower().lstrip(".") for item in allowed]
