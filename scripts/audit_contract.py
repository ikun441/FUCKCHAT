#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 前后端契约审计

用途：
    把前端 JS 实际消费的字段，与后端真实返回的字段做逐一比对，
    找出「前端读不到数据」的契约不匹配点。

背景：
    后端重构后接口路径与响应结构发生变化，
    前端 templates/js/*.js 仍按旧契约取值。本脚本用于系统性地
    暴露这些差异，而不是靠人肉翻代码。

用法:
    python scripts/audit_contract.py --url http://127.0.0.1:5100
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:5100"

PASSED = []
FAILED = []


def call(method, path, token=None, body=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except json.JSONDecodeError:
            return exc.code, {}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def has(obj, dotted):
    """检查 obj 是否存在 a.b.c 形式的路径。"""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print(f"  [OK]   {label}")
    else:
        FAILED.append((label, detail))
        print(f"  [MISS] {label}  {detail}")


def section(title):
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=BASE_URL)
    args = parser.parse_args()
    BASE_URL = args.url.rstrip("/")

    # 登录
    st, body = call("POST", "/api/auth/admin/login",
                    body={"username": "admin", "password": "admin123"})
    admin_token = body.get("token") or body.get("data", {}).get("token")
    st, ubody = call("POST", "/api/auth/login",
                     body={"username": "user", "password": "user123"})
    user_token = ubody.get("token") or ubody.get("data", {}).get("token")

    if not admin_token or not user_token:
        print("登录失败，无法继续审计")
        return 1

    # ---------------------------------------------------------------
    section("admin.js 契约")
    # ---------------------------------------------------------------

    st, d = call("GET", "/api/admin/stats", token=admin_token)
    # admin.js:99  data.stats.user_count
    check("stats 提供 data.stats.user_count", has(d, "stats.user_count"),
          f"实际顶层 keys={sorted(d.keys())[:8]}")
    check("stats 提供 data.stats.group_count", has(d, "stats.group_count"))
    check("stats 提供 data.stats.online_user_count", has(d, "stats.online_user_count"))
    check("stats 提供 data.stats.today_message_count", has(d, "stats.today_message_count"))

    st, d = call("GET", "/api/admin/users?page=1&per_page=5", token=admin_token)
    # admin.js:185  data.users.forEach，字段 created_at / kunbi
    check("users 提供 data.users 数组", isinstance(d.get("users"), list),
          f"keys={sorted(d.keys())[:8]}")
    if isinstance(d.get("users"), list) and d["users"]:
        u = d["users"][0]
        for f in ("username", "nickname", "created_at", "kunbi"):
            check(f"users[0].{f} 存在（admin.js 渲染用）", f in u, f"keys={sorted(u.keys())}")

    st, d = call("GET", "/api/admin/logs?page=1&per_page=5", token=admin_token)
    check("logs 提供 data.logs 数组", isinstance(d.get("logs"), list), f"keys={sorted(d.keys())[:8]}")
    if isinstance(d.get("logs"), list) and d["logs"]:
        for f in ("type", "content", "created_at"):
            check(f"logs[0].{f} 存在", f in d["logs"][0])

    st, d = call("GET", "/api/admin/groups?page=1&per_page=10", token=admin_token)
    check("groups 提供 data.groups 数组", isinstance(d.get("groups"), list), f"keys={sorted(d.keys())[:8]}")

    st, d = call("GET", "/api/admin/reported-messages", token=admin_token)
    # admin.js:797 data.reports.forEach
    check("reported-messages 提供 data.reports 数组", isinstance(d.get("reports"), list),
          f"keys={sorted(d.keys())[:8]}")

    st, d = call("GET", "/api/admin/private-chats", token=admin_token)
    # admin.js:714 data.messages.forEach（私聊/群聊表）
    check("private-chats 提供 data.messages 数组", isinstance(d.get("messages"), list),
          f"keys={sorted(d.keys())[:8]}")

    st, d = call("GET", "/api/admin/group-chats", token=admin_token)
    check("group-chats 提供 data.messages 数组", isinstance(d.get("messages"), list),
          f"keys={sorted(d.keys())[:8]}")

    st, d = call("GET", "/api/admin/notifications", token=admin_token)
    check("notifications 提供 data.notifications 数组",
          isinstance(d.get("notifications"), list), f"keys={sorted(d.keys())[:8]}")
    if isinstance(d.get("notifications"), list) and d["notifications"]:
        for f in ("id", "title", "content", "created_at"):
            check(f"notifications[0].{f} 存在", f in d["notifications"][0])

    st, d = call("GET", "/api/admin/notification/stats", token=admin_token)
    check("notification/stats 返回成功", d.get("success") is True, str(d)[:100])

    st, d = call("GET", "/api/admin/database/info", token=admin_token)
    check("database/info 返回成功", d.get("success") is True, str(d)[:100])

    st, d = call("GET", "/api/admin/database/tables", token=admin_token)
    check("database/tables 提供 tables", "tables" in d or has(d, "data.tables"),
          f"keys={sorted(d.keys())[:8]}")

    st, d = call("GET", "/api/admin/database/backups", token=admin_token)
    # admin.js:966 data.backups.forEach，字段 created_at/size/type/filename/id
    check("database/backups 提供 data.backups 数组", isinstance(d.get("backups"), list),
          f"keys={sorted(d.keys())[:8]}")

    st, d = call("GET", "/api/admin/settings", token=admin_token)
    check("settings 返回成功", d.get("success") is True, str(d)[:100])

    # ---------------------------------------------------------------
    section("chat.js 契约")
    # ---------------------------------------------------------------

    st, d = call("GET", "/api/chat/users", token=user_token)
    # chat.js:543 onlineUsers = data.users || []
    check("chat/users 提供 data.users", isinstance(d.get("users"), list), f"keys={sorted(d.keys())[:8]}")
    if isinstance(d.get("users"), list) and d["users"]:
        for f in ("id", "nickname", "avatar", "status"):
            check(f"users[0].{f} 存在（chat.js 渲染用）", f in d["users"][0])

    st, d = call("GET", "/api/chat/contacts", token=user_token)
    check("chat/contacts 提供 data.contacts", isinstance(d.get("contacts"), list))

    st, d = call("GET", "/api/chat/groups", token=user_token)
    check("chat/groups 提供 data.groups", isinstance(d.get("groups"), list))
    if isinstance(d.get("groups"), list) and d["groups"]:
        for f in ("id", "name", "avatar"):
            check(f"groups[0].{f} 存在", f in d["groups"][0])

    st, d = call("GET", "/api/chat/history?chat_id=user_1", token=user_token)
    check("chat/history 提供 data.messages", isinstance(d.get("messages"), list))

    st, d = call("GET", "/api/chat/messages?type=user&target_id=1", token=user_token)
    check("chat/messages 提供 messages", isinstance(d.get("messages"), list))

    # ---------------------------------------------------------------
    section("login.js / profile.js 契约")
    # ---------------------------------------------------------------

    st, d = call("POST", "/api/auth/login", body={"username": "user", "password": "user123"})
    check("login 提供顶层 token（login.js:67）", bool(d.get("token")), f"keys={sorted(d.keys())[:8]}")
    check("login 提供顶层 user（login.js:68）", isinstance(d.get("user"), dict))
    if isinstance(d.get("user"), dict):
        for f in ("id", "username", "nickname", "avatar", "kunbi"):
            check(f"login.user.{f} 存在", f in d["user"])

    st, d = call("GET", "/api/auth/profile", token=user_token)
    check("profile 返回用户信息", bool(d.get("user")) or has(d, "data.user"),
          f"keys={sorted(d.keys())[:8]}")

    # ---------------------------------------------------------------
    section("profile.js / mail.js 使用的社交接口")
    # ---------------------------------------------------------------
    st, d = call("GET", "/api/friends", token=user_token)
    check("friends 返回成功", d.get("success") is True, str(d)[:100])

    st, d = call("GET", "/api/notifications", token=user_token)
    check("notifications 返回成功", d.get("success") is True, str(d)[:100])

    # ---------------------------------------------------------------
    section("汇总")
    # ---------------------------------------------------------------
    total = len(PASSED) + len(FAILED)
    print(f"总计 {total}  通过 {len(PASSED)}  不匹配 {len(FAILED)}")
    if FAILED:
        print("\n不匹配明细:")
        for label, detail in FAILED:
            print(f"  - {label}  {detail}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
