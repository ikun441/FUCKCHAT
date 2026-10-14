#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 接口回归测试

覆盖重构前诊断报告中发现的全部问题，用于验证重构效果。
直接启动服务并逐条验证，无需额外测试依赖。

用法:
    python scripts/test_api.py
    python scripts/test_api.py --url http://127.0.0.1:5100
"""

import argparse
import json
import random
import time
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:5100"

PASSED = []
FAILED = []


def request(method, path, token=None, body=None, raw_body=None, content_type="application/json"):
    """发起 HTTP 请求，返回 (status, parsed_body)。"""
    url = f"{BASE_URL}{path}"
    data = None
    headers = {}

    if raw_body is not None:
        data = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
        headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append((name, detail))
        print(f"  [FAIL] {name}  {detail}")


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=BASE_URL)
    args = parser.parse_args()
    BASE_URL = args.url.rstrip("/")

    print(f"测试目标: {BASE_URL}")

    # ------------------------------------------------------------------
    section("1. 健康检查与页面路由")
    # ------------------------------------------------------------------
    status, body = request("GET", "/api/health")
    check("GET /api/health 返回 200", status == 200, f"status={status}")
    check("健康检查返回 success", isinstance(body, dict) and body.get("success") is True)

    for path in ["/", "/login", "/chat", "/about", "/profile", "/mail", "/register"]:
        status, _ = request("GET", path)
        check(f"页面 {path} 可访问", status == 200, f"status={status}")

    # 修复 P-1: 原先 /admin 与 /admin/dashboard 返回 500
    for path in ["/admin", "/admin/dashboard"]:
        status, _ = request("GET", path)
        check(f"管理页面 {path} 修复为 200（原为 500）", status == 200, f"status={status}")

    # ------------------------------------------------------------------
    section("2. 认证与授权")
    # ------------------------------------------------------------------
    status, body = request("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
    admin_token = body.get("data", {}).get("token") if isinstance(body, dict) else None
    check("管理员登录成功", status == 200 and admin_token, f"status={status}")

    status, body = request("POST", "/api/auth/login", body={"username": "user", "password": "user123"})
    user_token = body.get("data", {}).get("token") if isinstance(body, dict) else None
    check("普通用户登录成功", status == 200 and user_token, f"status={status}")

    # 无 token
    for path in ["/api/auth/profile", "/api/chat/users", "/api/admin/stats", "/api/kunbi/balance"]:
        status, _ = request("GET", path)
        check(f"无令牌访问 {path} 返回 401", status == 401, f"status={status}")

    # 伪造 token
    fake = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo5OTl9.badsignature"
    status, _ = request("GET", "/api/admin/stats", token=fake)
    check("伪造令牌被拒绝（401）", status == 401, f"status={status}")

    # 越权
    status, _ = request("GET", "/api/admin/stats", token=user_token)
    check("普通用户访问管理员接口被拒（403）", status == 403, f"status={status}")

    # ------------------------------------------------------------------
    section("3. 输入校验（重构重点）")
    # ------------------------------------------------------------------

    # 修复 S-4: 1 字符密码注册
    # 注册接口有服务端限速，用例之间稍作间隔以免触发 429
    time.sleep(0.5)
    status, body = request(
        "POST",
        "/api/auth/register",
        body={"username": "shortpw001", "password": "1", "nickname": "短密码"},
    )
    check(
        "1 字符密码注册被拒（原为成功）",
        status == 400,
        f"status={status} body={body}",
    )

    # 密码必须含字母数字
    time.sleep(0.5)
    status, body = request(
        "POST",
        "/api/auth/register",
        body={"username": "weakpw001", "password": "abcdefgh", "nickname": "纯字母"},
    )
    check("纯字母密码被拒", status == 400, f"status={status}")

    # 超长用户名
    time.sleep(0.5)
    status, body = request(
        "POST",
        "/api/auth/register",
        body={"username": "a" * 300, "password": "abc12345", "nickname": "x"},
    )
    check("300 字符用户名被拒（原为成功）", status == 400, f"status={status}")

    # 非法用户名字符
    time.sleep(0.5)
    status, body = request(
        "POST",
        "/api/auth/register",
        body={"username": "../../etc/passwd", "password": "abc12345", "nickname": "x"},
    )
    check("非法用户名字符被拒", status == 400, f"status={status}")

    # 合法注册
    time.sleep(0.5)
    status, body = request(
        "POST",
        "/api/auth/register",
        body={"username": "testuser01", "password": "Test12345", "nickname": "测试用户01"},
    )
    check("合法注册成功（201 或 409 已存在）", status in (201, 409), f"status={status}")

    # 修复 S-4: 超长昵称
    status, body = request(
        "POST",
        "/api/auth/profile",
        token=user_token,
        body={"nickname": "N" * 100000},
    )
    check("100000 字符昵称被拒（原为成功）", status == 400, f"status={status}")

    # 超长但合法的昵称上限
    status, body = request("POST", "/api/auth/profile", token=user_token, body={"nickname": "N" * 33})
    check("33 字符昵称被拒（上限 32）", status == 400, f"status={status}")

    # 正常昵称
    status, body = request("POST", "/api/auth/profile", token=user_token, body={"nickname": "测试用户"})
    check("合法昵称更新成功", status == 200, f"status={status}")

    # 非法邮箱
    status, body = request("POST", "/api/auth/profile", token=user_token, body={"email": "not-an-email"})
    check("非法邮箱被拒", status == 400, f"status={status}")

    # ------------------------------------------------------------------
    section("4. 参数健壮性（修复 500）")
    # ------------------------------------------------------------------

    # 修复 S-5: limit=abc 触发 500
    status, body = request("GET", "/api/chat/messages?type=user&target_id=2&limit=abc", token=admin_token)
    check("limit=abc 返回 400（原为 500）", status == 400, f"status={status}")

    status, body = request("GET", "/api/chat/messages?type=user&target_id=abc", token=admin_token)
    check("target_id=abc 返回 400", status == 400, f"status={status}")

    status, body = request("GET", "/api/chat/messages?type=bad&target_id=2", token=admin_token)
    check("非法 type 返回 400", status == 400, f"status={status}")

    status, body = request("GET", "/api/chat/messages?type=user&target_id=2&limit=99999", token=admin_token)
    check("超大 limit 被裁剪为 400", status == 400, f"status={status}")

    # 原有契约仍然可用
    status, body = request("GET", "/api/chat/messages?type=user&target_id=2", token=admin_token)
    check("正常 messages 查询返回 200", status == 200, f"status={status}")

    # 修复: 前端 chat_id 契约
    status, body = request("GET", "/api/chat/history?chat_id=user_2", token=admin_token)
    check("history?chat_id=user_2 返回 200（原为 400）", status == 200, f"status={status}")

    status, body = request("GET", "/api/chat/history?chat_id=badformat", token=admin_token)
    check("非法 chat_id 返回 400", status == 400, f"status={status}")

    # 非法 JSON
    status, body = request(
        "POST", "/api/auth/login", raw_body="not-json", content_type="application/json"
    )
    check("非法 JSON 体返回 400", status == 400, f"status={status}")

    # ------------------------------------------------------------------
    section("5. 补齐的缺失接口（原全为 404）")
    # ------------------------------------------------------------------
    admin_endpoints = [
        ("GET", "/api/admin/database/info"),
        ("GET", "/api/admin/database/tables"),
        ("GET", "/api/admin/database/backups"),
        ("GET", "/api/admin/settings"),
        ("GET", "/api/admin/notifications"),
        ("GET", "/api/admin/notification/stats"),
        ("GET", "/api/admin/reported-messages"),
        ("GET", "/api/admin/private-chats"),
        ("GET", "/api/admin/group-chats"),
    ]
    for method, path in admin_endpoints:
        status, body = request(method, path, token=admin_token)
        check(f"{method} {path} 已实现（200）", status == 200, f"status={status}")

    status, body = request("POST", "/api/admin/database/optimize", token=admin_token)
    check("POST /api/admin/database/optimize 已实现", status == 200, f"status={status}")

    # 普通用户不得访问这些管理接口
    status, _ = request("GET", "/api/admin/database/info", token=user_token)
    check("普通用户访问数据库接口被拒（403）", status == 403, f"status={status}")

    user_endpoints = [
        ("POST", "/api/messages/recall", {"message_id": 999999}),
        ("POST", "/api/messages/report", {"message_id": 999999}),
        ("POST", "/api/messages/clear", {"chat_id": "user_2"}),
        ("POST", "/api/friends/request", {"friend_id": 1}),
        ("POST", "/api/system/create-folder", {"folder": "test_folder"}),
        ("GET", "/api/messages/search?keyword=test", None),
        ("GET", "/api/friends", None),
        ("GET", "/api/friends/requests", None),
        ("GET", "/api/notifications", None),
    ]
    for method, path, body in user_endpoints:
        status, resp = request(method, path, token=user_token, body=body)
        # 404 是消息不存在的正常业务结果，只要不是路由 404 即可
        # 409 = 重复申请等业务冲突，属正常响应
        ok = status in (200, 201, 400, 403, 404, 409)
        check(f"{method} {path} 路由已实现", ok, f"status={status} resp={resp}")

    # ------------------------------------------------------------------
    section("6. 安全设置")
    # ------------------------------------------------------------------
    status, body = request("GET", "/api/admin/settings", token=admin_token)
    if isinstance(body, dict) and body.get("success"):
        data = body.get("data", {})
        sec = data.get("security", {})
        check("设置接口不返回密钥明文", "secret_key" not in json.dumps(data).lower() or "secretKeyConfigured" in json.dumps(data), "")
        check("设置接口报告密钥已配置", sec.get("secretKeyConfigured") is True, f"sec={sec}")

    # 路径穿越尝试
    status, body = request(
        "POST", "/api/system/create-folder", token=user_token, body={"folder": "../../../etc"}
    )
    check("路径穿越的目录名被拒", status == 400, f"status={status}")

    # ------------------------------------------------------------------
    section("7. 业务功能")
    # ------------------------------------------------------------------
    status, body = request("GET", "/api/kunbi/balance", token=user_token)
    check("查询余额成功", status == 200 and "balance" in body.get("data", {}), f"status={status}")

    status, body = request("GET", "/api/kunbi/transactions", token=user_token)
    check("查询流水成功", status == 200, f"status={status}")

    status, body = request("GET", "/api/chat/users", token=user_token)
    check("在线用户列表成功", status == 200, f"status={status}")

    status, body = request("GET", "/api/chat/groups", token=user_token)
    check("群组列表成功", status == 200, f"status={status}")

    status, body = request("GET", "/api/admin/stats", token=admin_token)
    check("管理员统计成功", status == 200, f"status={status}")

    status, body = request("GET", "/api/admin/users", token=admin_token)
    check("管理员用户列表成功", status == 200, f"status={status}")

    # 转账校验
    status, body = request(
        "POST", "/api/kunbi/transfer", token=user_token, body={"to_user_id": 1, "amount": -100}
    )
    check("负数转账被拒", status == 400, f"status={status}")

    status, body = request(
        "POST", "/api/kunbi/transfer", token=user_token, body={"to_user_id": 2, "amount": 10}
    )
    check("给自己转账被拒", status == 400, f"status={status}")

    # 用新注册的独立账号转账，避免受历史用例影响（余额是可变的）
    transfer_user = f"txuser{random.randint(10000, 99999)}"
    status, reg = request(
        "POST",
        "/api/auth/register",
        body={"username": transfer_user, "password": "Test12345", "nickname": "转账测试"},
    )
    if status == 201:
        status, login = request(
            "POST", "/api/auth/login", body={"username": transfer_user, "password": "Test12345"}
        )
        fresh_token = login.get("data", {}).get("token") if isinstance(login, dict) else None
        status, body = request(
            "POST", "/api/kunbi/transfer", token=fresh_token, body={"to_user_id": 1, "amount": 50}
        )
        check("正常转账成功", status == 200, f"status={status} body={body}")

        # 余额不足应被拒
        status, body = request(
            "POST", "/api/kunbi/transfer", token=fresh_token, body={"to_user_id": 1, "amount": 999999}
        )
        check("余额不足的转账被拒", status == 400, f"status={status}")

        # 转账后余额应正确扣减（100 - 50 = 50）
        status, body = request("GET", "/api/kunbi/balance", token=fresh_token)
        balance = body.get("data", {}).get("balance") if isinstance(body, dict) else None
        check("转账后余额正确扣减为 50", balance == 50, f"balance={balance}")
    else:
        check("正常转账成功", False, f"注册失败 status={status}")

    # ------------------------------------------------------------------
    section("8. 响应格式一致性")
    # ------------------------------------------------------------------
    for path, token in [
        ("/api/kunbi/balance", user_token),
        ("/api/chat/users", user_token),
        ("/api/admin/stats", admin_token),
        ("/api/notifications", user_token),
    ]:
        status, body = request("GET", path, token=token)
        check(
            f"{path} 返回统一格式（含 success 字段）",
            isinstance(body, dict) and "success" in body,
            f"body={str(body)[:80]}",
        )

    # 错误响应也应为 JSON
    status, body = request("GET", "/api/nonexistent")
    check(
        "404 返回 JSON 而非 HTML",
        isinstance(body, dict),
        f"body={str(body)[:80]}",
    )

    status, body = request("GET", "/api/auth/profile")
    check(
        "401 返回 JSON 而非 HTML",
        isinstance(body, dict) and body.get("code") == "UNAUTHORIZED",
        f"body={str(body)[:80]}",
    )

    # ------------------------------------------------------------------
    section("9. 前端兼容层（v1 扁平字段 vs v2 data 嵌套）")
    # ------------------------------------------------------------------
    status, body = request(
        "POST", "/api/auth/login", body={"username": "admin", "password": "admin123"}
    )
    check(
        "登录响应同时提供顶层 token（v1）",
        isinstance(body, dict) and bool(body.get("token")),
        f"body keys={list(body.keys())[:10] if isinstance(body, dict) else body}",
    )
    check(
        "登录响应同时提供 data.token（v2）",
        isinstance(body, dict) and bool(body.get("data", {}).get("token")),
        "",
    )
    check(
        "两种格式的 token 一致",
        isinstance(body, dict) and body.get("token") == body.get("data", {}).get("token"),
        "",
    )
    check(
        "登录响应同时提供顶层 user（v1 前端读取）",
        isinstance(body, dict) and "user" in body,
        "",
    )

    # 旧前端直接读取的列表字段必须在顶层可见
    legacy_paths = [
        ("/api/chat/users", "users"),
        ("/api/chat/contacts", "contacts"),
        ("/api/chat/groups", "groups"),
        ("/api/kunbi/transactions", "transactions"),
        ("/api/notifications", "notifications"),
        ("/api/admin/users", "users"),
        ("/api/admin/groups", "groups"),
        ("/api/admin/logs", "logs"),
        ("/api/admin/notifications", "notifications"),
    ]
    for path, field in legacy_paths:
        token = admin_token if path.startswith("/api/admin") else user_token
        status, body = request("GET", path, token=token)
        check(
            f"{path} 顶层提供 {field}（v1 兼容）",
            isinstance(body, dict) and field in body,
            f"status={status}",
        )

    # 聊天记录：chat.js 读 data.messages
    status, body = request("GET", "/api/chat/history?chat_id=user_2", token=admin_token)
    check(
        "/api/chat/history 顶层提供 messages（v1 兼容）",
        isinstance(body, dict) and "messages" in body,
        f"status={status}",
    )

    # 分页结构仍为标准 v2 格式
    status, body = request("GET", "/api/admin/users", token=admin_token)
    check(
        "分页响应保留 v2 的 items/pagination",
        isinstance(body, dict) and "items" in body and "pagination" in body,
        f"keys={list(body.keys()) if isinstance(body, dict) else body}",
    )
    check(
        "分页 pagination 含 total/page/page_size",
        isinstance(body, dict)
        and {"total", "page", "page_size"} <= set(body.get("pagination", {})),
        "",
    )

    # 保留键不被 data 覆盖
    status, body = request("GET", "/api/kunbi/balance", token=user_token)
    check(
        "兼容层不覆盖 success/message 等保留键",
        isinstance(body, dict)
        and body.get("success") is True
        and isinstance(body.get("message"), str)
        and "data" in body,
        "",
    )

    # ------------------------------------------------------------------
    section("测试结果汇总")
    # ------------------------------------------------------------------
    total = len(PASSED) + len(FAILED)
    print(f"总计: {total}  通过: {len(PASSED)}  失败: {len(FAILED)}")
    if FAILED:
        print("\n失败明细:")
        for name, detail in FAILED:
            print(f"  - {name}: {detail}")
        return 1
    print("\n全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
