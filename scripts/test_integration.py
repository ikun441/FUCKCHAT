#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 前后端连通性测试

目的：
    真正验证「前端 JS 的取值逻辑」能拿到数据，而不只是后端自测。

做法：
    1. 从 templates/js/*.js 中抽取前端实际使用的取值表达式
    2. 用真实 HTTP 请求打到运行中的后端
    3. 按前端的解包逻辑（unwrapResponse）取值，断言字段存在且类型正确

这能捕获「后端返回了数据但字段名对不上」这类仅靠后端测试发现不了的问题。

用法:
    python scripts/test_integration.py --url http://127.0.0.1:5100
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:5100"
PASSED = []
FAILED = []


def http(method, path, token=None, body=None, raw=None, content_type=None):
    url = f"{BASE_URL}{path}"
    data = None
    headers = {}
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/octet-stream"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_body = resp.read()
            try:
                return resp.status, json.loads(raw_body.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return resp.status, raw_body
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:  # noqa: BLE001
            return exc.code, {}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def unwrap(raw):
    """复刻 common.js 中 unwrapResponse 的逻辑。"""
    body = raw if isinstance(raw, dict) else {}
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    return {"ok": body.get("success") is True, "data": data,
            "message": body.get("message", ""), "raw": body}


def check(label, cond, detail=""):
    if cond:
        PASSED.append(label)
        print(f"  [PASS] {label}")
    else:
        FAILED.append((label, detail))
        print(f"  [FAIL] {label}  {detail}")


def section(t):
    print(f"\n{'=' * 74}\n{t}\n{'=' * 74}")


def main():
    global BASE_URL
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=BASE_URL)
    args = ap.parse_args()
    BASE_URL = args.url.rstrip("/")

    # ------------------------------------------------------------------
    section("1. login.js 登录流程（localStorage 写入）")
    # ------------------------------------------------------------------
    st, raw = http("POST", "/api/auth/login",
                   body={"username": "user", "password": "user123"})
    r = unwrap(raw)
    check("unwrapResponse().ok 为真", r["ok"], f"raw={str(raw)[:120]}")
    check("payload.token 可取（login.js:67）", bool(r["data"].get("token")),
          f"data keys={list(r['data'].keys())}")
    check("payload.user 可取（login.js:68）", isinstance(r["data"].get("user"), dict))
    user = r["data"].get("user") or {}
    for f in ("id", "username", "nickname", "avatar", "kunbi"):
        check(f"user.{f} 存在（chat.js 全局依赖）", f in user, f"keys={list(user.keys())}")

    token = r["data"].get("token")

    # ------------------------------------------------------------------
    section("2. chat.js 初始化加载")
    # ------------------------------------------------------------------
    st, raw = http("GET", "/api/chat/users", token=token)
    r = unwrap(raw)
    # chat.js: onlineUsers = result.data.users || []
    check("初始化在线用户列表（chat.js fetchUsers）",
          r["ok"] and isinstance(r["data"].get("users"), list),
          f"ok={r['ok']} keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/chat/contacts", token=token)
    r = unwrap(raw)
    check("初始化最近联系人（chat.js fetchContacts）",
          r["ok"] and isinstance(r["data"].get("contacts"), list),
          f"keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/chat/groups", token=token)
    r = unwrap(raw)
    check("初始化群组列表（chat.js fetchGroups）",
          r["ok"] and isinstance(r["data"].get("groups"), list),
          f"keys={list(r['data'].keys())}")
    groups = r["data"].get("groups") or []
    if groups:
        g = groups[0]
        for f in ("id", "name", "avatar"):
            check(f"group.{f} 存在（renderGroups 使用）", f in g, f"keys={list(g.keys())}")

    # ------------------------------------------------------------------
    section("3. chat.js 聊天记录加载")
    # ------------------------------------------------------------------
    st, raw = http("GET", "/api/chat/history?chat_id=user_1", token=token)
    r = unwrap(raw)
    # chat.js: if (result.ok && msgList) { messages[chatId] = msgList }
    check("聊天记录解包成功（chat.js getChatHistory）",
          r["ok"] and isinstance(r["data"].get("messages"), list),
          f"ok={r['ok']} keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/chat/messages?type=user&target_id=1", token=token)
    r = unwrap(raw)
    check("消息查询成功", r["ok"] and isinstance(r["data"].get("messages"), list))

    # ------------------------------------------------------------------
    section("4. 发送消息（HTTP 回退通道）")
    # ------------------------------------------------------------------
    st, raw = http("POST", "/api/chat/messages", token=token,
                   body={"content": "连通性测试消息", "receiver_id": 1, "type": "text"})
    r = unwrap(raw)
    check("发送消息成功（chat.js sendMessageAPI）", r["ok"], f"msg={r['message']}")
    sent_id = r["data"].get("messageId")
    check("返回 messageId", bool(sent_id), f"data={r['data']}")

    # ------------------------------------------------------------------
    section("5. 消息撤回 / 清空（补齐接口）")
    # ------------------------------------------------------------------
    if sent_id:
        st, raw = http("POST", "/api/messages/recall", token=token,
                       body={"message_id": sent_id})
        r = unwrap(raw)
        check("撤回消息成功（chat.js recallMessage）", r["ok"], f"msg={r['message']}")

    st, raw = http("POST", "/api/messages/clear", token=token,
                   body={"chat_id": "user_1"})
    r = unwrap(raw)
    check("清空会话成功（chat.js clearChat）", r["ok"], f"msg={r['message']}")

    # ------------------------------------------------------------------
    section("6. 头像上传（chat.js / profile.js）")
    # ------------------------------------------------------------------
    # 构造一个最小 PNG
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001"
        "0d0a2db40000000049454e44ae426082"
    )
    boundary = "----fuckchatboundary"
    body_bytes = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="t.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + png + f"\r\n--{boundary}--\r\n".encode()

    for path in ("/api/upload/avatar", "/api/user/avatar", "/api/auth/avatar"):
        st, raw = http("POST", path, token=token, raw=body_bytes,
                       content_type=f"multipart/form-data; boundary={boundary}")
        r = unwrap(raw)
        ok = r["ok"] and bool(r["data"].get("avatar") or r["data"].get("avatar_url"))
        check(f"头像上传可用 {path}", ok,
              f"status={st} msg={r['message']} data={r['data']}")

    # ------------------------------------------------------------------
    section("7. 管理员后台（admin.js）")
    # ------------------------------------------------------------------
    st, raw = http("POST", "/api/auth/admin/login",
                   body={"username": "admin", "password": "admin123"})
    r = unwrap(raw)
    admin_token = r["data"].get("token")
    check("管理员登录成功", bool(admin_token))

    st, raw = http("GET", "/api/admin/stats", token=admin_token)
    r = unwrap(raw)
    stats = r["data"].get("stats") or r["data"]
    for f in ("user_count", "group_count", "online_user_count", "today_message_count"):
        check(f"stats.{f} 可取（admin.js:99-104）", f in stats,
              f"keys={list(stats.keys())}")

    st, raw = http("GET", "/api/admin/users?page=1&per_page=5", token=admin_token)
    r = unwrap(raw)
    users = r["data"].get("users") or []
    check("用户列表可取（admin.js:185）", isinstance(r["data"].get("users"), list))
    if users:
        for f in ("username", "nickname", "created_at", "kunbi"):
            check(f"user.{f} 可取（admin.js 渲染行）", f in users[0],
                  f"keys={list(users[0].keys())}")

    st, raw = http("GET", "/api/admin/logs?page=1&per_page=5", token=admin_token)
    r = unwrap(raw)
    logs = r["data"].get("logs") or []
    check("日志列表可取（admin.js:222）", isinstance(r["data"].get("logs"), list))
    if logs:
        for f in ("type", "content", "created_at"):
            check(f"log.{f} 可取", f in logs[0], f"keys={list(logs[0].keys())}")

    st, raw = http("GET", "/api/admin/groups?page=1&per_page=10", token=admin_token)
    r = unwrap(raw)
    check("群组列表可取（admin.js loadAllGroups）",
          isinstance(r["data"].get("groups"), list), f"keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/admin/reported-messages", token=admin_token)
    r = unwrap(raw)
    check("举报列表可取（admin.js:810 data.reports）",
          isinstance(r["data"].get("reports"), list), f"keys={list(r['data'].keys())}")

    for path in ("/api/admin/private-chats", "/api/admin/group-chats"):
        st, raw = http("GET", path, token=admin_token)
        r = unwrap(raw)
        check(f"会话概览可取 {path}（admin.js:718 data.messages）",
              isinstance(r["data"].get("messages"), list), f"keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/admin/database/info", token=admin_token)
    r = unwrap(raw)
    for f in ("size", "table_count", "last_backup", "status"):
        check(f"db info.{f} 可取（admin.js:896）", f in r["data"],
              f"keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/admin/database/tables", token=admin_token)
    r = unwrap(raw)
    tables = r["data"].get("tables") or []
    check("表清单可取（admin.js:919）", isinstance(tables, list))
    if tables:
        for f in ("name", "row_count"):
            check(f"table.{f} 可取", f in tables[0], f"keys={list(tables[0].keys())}")

    st, raw = http("GET", "/api/admin/database/backups", token=admin_token)
    r = unwrap(raw)
    check("备份列表可取（admin.js:979 data.backups）",
          isinstance(r["data"].get("backups"), list))

    st, raw = http("GET", "/api/admin/notification/stats", token=admin_token)
    r = unwrap(raw)
    for f in ("labels", "counts", "read_count", "total_count"):
        check(f"通知统计.{f} 可取（admin.js:1143 图表）", f in r["data"],
              f"keys={list(r['data'].keys())}")

    st, raw = http("GET", "/api/admin/notifications", token=admin_token)
    r = unwrap(raw)
    check("通知列表可取（admin.js:1084）",
          isinstance(r["data"].get("notifications"), list))

    st, raw = http("POST", "/api/admin/database/optimize", token=admin_token)
    r = unwrap(raw)
    check("数据库优化可用", r["ok"], f"msg={r['message']}")

    # ------------------------------------------------------------------
    section("8. 坤币与红包")
    # ------------------------------------------------------------------
    st, raw = http("GET", "/api/kunbi/balance", token=token)
    r = unwrap(raw)
    check("余额可取", r["ok"] and "balance" in r["data"], f"data={r['data']}")

    st, raw = http("GET", "/api/kunbi/transactions", token=token)
    r = unwrap(raw)
    check("流水可取", r["ok"] and isinstance(r["data"].get("transactions"), list),
          f"keys={list(r['data'].keys())}")

    # ------------------------------------------------------------------
    section("9. 错误响应的前端可读性")
    # ------------------------------------------------------------------
    st, raw = http("POST", "/api/auth/login", body={"username": "user", "password": "wrong"})
    r = unwrap(raw)
    check("登录失败时 ok=false", not r["ok"])
    check("登录失败时 message 可展示给用户", bool(r["message"]),
          f"msg={r['message']}")

    st, raw = http("GET", "/api/chat/users")
    r = unwrap(raw)
    check("未登录时 ok=false 且带提示", (not r["ok"]) and bool(r["message"]),
          f"status={st} msg={r['message']}")

    st, raw = http("GET", "/api/chat/messages?type=user&target_id=abc", token=token)
    r = unwrap(raw)
    check("参数错误返回可读提示（非 500）", st == 400 and bool(r["message"]),
          f"status={st} msg={r['message']}")

    # ------------------------------------------------------------------
    section("汇总")
    # ------------------------------------------------------------------
    total = len(PASSED) + len(FAILED)
    print(f"总计 {total}  通过 {len(PASSED)}  失败 {len(FAILED)}")
    if FAILED:
        print("\n失败明细:")
        for label, detail in FAILED:
            print(f"  - {label}  {detail}")
        return 1
    print("\n前后端连通性全部正常 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
