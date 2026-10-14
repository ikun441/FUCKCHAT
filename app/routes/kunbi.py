#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 坤币路由（虚拟货币与红包）

数据模型（沿用既有表结构）：
    kunbi_transactions
        红包主体：sender_id, receiver_id/group_id, amount, message,
                  packet_count, status, parent_id IS NULL
        领取记录：parent_id -> 红包主体 id, receiver_id = 领取人,
                  amount = 实得金额, status = 'received'

重构要点：
- 金额变动全部置于单事务，扣款使用条件更新（kunbi >= amount）防并发双花
- 领取记录用「先查重 + 事务内复查」双保险，杜绝重复领取
- 拼手气金额服务端预分配，保证总和精确、每份 >= 1
- 金额/份数/目标全部校验，修复负数与超限
"""

import logging
import random
from datetime import datetime

from flask import Blueprint, current_app, g, request

from .. import database as db
from ..responses import ApiError, paginated, success
from ..security import auth_required, rate_limit
from ..validators import (
    clean_text,
    require_fields,
    require_json,
    validate_amount,
    validate_int,
    validate_pagination,
)

logger = logging.getLogger("FUCKCHAT.kunbi")

kunbi_bp = Blueprint("kunbi", __name__)

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_PARTIAL = "partially_received"
STATUS_RECEIVED = "received"


def _redpacket_config():
    return current_app.config["FUCKCHAT_CONFIG"].section("chat").get(
        "kunbi_redpacket", {}
    )


def _get_balance(user_id):
    balance = db.query_scalar("SELECT kunbi FROM users WHERE id = ?", (user_id,))
    if balance is None:
        raise ApiError("用户不存在", 404)
    return balance


def _debit(conn, user_id, amount):
    """
    事务内条件扣款。

    使用 `WHERE kunbi >= ?` 保证并发下不会扣成负数；
    返回受影响行数，0 表示余额不足。
    """
    cur = conn.execute(
        "UPDATE users SET kunbi = kunbi - ? WHERE id = ? AND kunbi >= ?",
        (amount, user_id, amount),
    )
    return cur.rowcount


def _credit(conn, user_id, amount):
    conn.execute("UPDATE users SET kunbi = kunbi + ? WHERE id = ?", (amount, user_id))


def _add_transaction(
    conn, sender_id, amount, message, status, receiver_id=None, group_id=None,
    parent_id=None, packet_count=None
):
    cur = conn.execute(
        """
        INSERT INTO kunbi_transactions
            (sender_id, receiver_id, group_id, parent_id, amount, message, status, packet_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sender_id,
            receiver_id,
            group_id,
            parent_id,
            amount,
            message,
            status,
            packet_count,
            datetime.now(),
        ),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# 余额与流水
# ---------------------------------------------------------------------------


@kunbi_bp.route("/balance", methods=["GET"])
@auth_required
def get_balance():
    """查询当前用户坤币余额。"""
    balance = _get_balance(g.user_id)
    return success({"balance": balance, "kunbi": balance})


@kunbi_bp.route("/transactions", methods=["GET"])
@auth_required
def get_transactions():
    """查询与当前用户相关的坤币流水（分页）。"""
    page, page_size = validate_pagination(request.args)
    offset = (page - 1) * page_size

    where = "WHERE (t.sender_id = ? OR t.receiver_id = ?)"
    params = [g.user_id, g.user_id]

    total = db.query_scalar(
        f"SELECT COUNT(*) FROM kunbi_transactions t {where}", params, 0
    )
    rows = db.query_all(
        f"""
        SELECT t.id, t.sender_id, t.receiver_id, t.group_id, t.parent_id,
               t.amount, t.message, t.status, t.packet_count, t.created_at,
               s.nickname AS sender_nickname, r.nickname AS receiver_nickname
        FROM kunbi_transactions t
        LEFT JOIN users s ON s.id = t.sender_id
        LEFT JOIN users r ON r.id = t.receiver_id
        {where}
        ORDER BY t.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )

    items = [
        {
            "id": row["id"],
            "senderId": row["sender_id"],
            "senderNickname": row["sender_nickname"],
            "receiverId": row["receiver_id"],
            "receiverNickname": row["receiver_nickname"],
            "groupId": row["group_id"],
            "parentId": row["parent_id"],
            "amount": row["amount"],
            "message": row["message"],
            "status": row["status"],
            "packetCount": row["packet_count"],
            "createdAt": row["created_at"],
            "direction": "out" if row["sender_id"] == g.user_id else "in",
        }
        for row in rows
    ]
    return paginated(items, total, page, page_size, transactions=items)


# ---------------------------------------------------------------------------
# 转账
# ---------------------------------------------------------------------------


@kunbi_bp.route("/transfer", methods=["POST"])
@auth_required
@rate_limit("kunbi_transfer", max_requests=30, window=60)
def transfer_kunbi():
    """向指定用户转账，事务内双向记账。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["to_user_id", "amount"])

    to_user_id = validate_int(data.get("to_user_id"), "to_user_id", min_value=1)
    amount = validate_amount(data.get("amount"), "转账金额", min_value=1, max_value=100000)
    note = clean_text(data.get("message") or data.get("note"), "备注", 100, allow_empty=True)

    if to_user_id == g.user_id:
        raise ApiError("不能给自己转账", 400)

    if not db.query_one("SELECT id FROM users WHERE id = ?", (to_user_id,)):
        raise ApiError("接收者不存在", 404)

    with db.transaction() as conn:
        if _debit(conn, g.user_id, amount) == 0:
            raise ApiError("坤币余额不足", 400, code="INSUFFICIENT_BALANCE")

        _credit(conn, to_user_id, amount)
        # 转出与转入各记一条，便于双方各自查流水
        _add_transaction(
            conn, g.user_id, amount, note or "转账", STATUS_SENT, receiver_id=to_user_id
        )
        _add_transaction(
            conn, g.user_id, amount, note or "来自转账", STATUS_RECEIVED, receiver_id=g.user_id
        )

    logger.info("转账: %s -> %s, 金额 %s", g.user_id, to_user_id, amount)
    _notify(to_user_id, "kunbi_transfer", {"from": g.user_id, "amount": amount})

    return success({"balance": _get_balance(g.user_id)}, message="转账成功")


# ---------------------------------------------------------------------------
# 红包
# ---------------------------------------------------------------------------


@kunbi_bp.route("/redpacket/send", methods=["POST"])
@auth_required
@rate_limit("redpacket_send", max_requests=20, window=60)
def send_redpacket():
    """发送单人红包。"""
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["receiver_id", "amount"])

    receiver_id = validate_int(data.get("receiver_id"), "receiver_id", min_value=1)
    amount = validate_amount(data.get("amount"), "红包金额", min_value=1, max_value=100000)
    blessing = clean_text(data.get("message") or data.get("blessing"), "祝福语", 100, allow_empty=True)

    if receiver_id == g.user_id:
        raise ApiError("不能给自己发红包", 400)

    cfg = _redpacket_config()
    min_amount = cfg.get("min_amount", 1)
    max_amount = cfg.get("max_amount", 10000)
    if not (min_amount <= amount <= max_amount):
        raise ApiError(f"红包金额需在 {min_amount} - {max_amount} 之间", 400)

    if not db.query_one("SELECT id FROM users WHERE id = ?", (receiver_id,)):
        raise ApiError("接收者不存在", 404)

    with db.transaction() as conn:
        if _debit(conn, g.user_id, amount) == 0:
            raise ApiError("坤币余额不足", 400, code="INSUFFICIENT_BALANCE")

        transaction_id = _add_transaction(
            conn,
            g.user_id,
            amount,
            blessing or "恭喜发财",
            STATUS_PENDING,
            receiver_id=receiver_id,
            packet_count=1,
        )

    logger.info("红包: %s -> %s, 金额 %s", g.user_id, receiver_id, amount)
    _notify(
        receiver_id,
        "kunbi_redpacket",
        {"from": g.user_id, "amount": amount, "transactionId": transaction_id},
    )

    return success(
        {"transactionId": transaction_id, "balance": _get_balance(g.user_id)},
        message="红包发送成功",
        status_code=201,
    )


@kunbi_bp.route("/redpacket/send_multi", methods=["POST"])
@auth_required
@rate_limit("redpacket_send", max_requests=20, window=60)
def send_multi_redpacket():
    """
    发送拼手气红包（多份，可指定群组）。

    修复：原实现按「平均值 2 倍」随机，最后一人可能拿到 0 或超额；
    现改为服务端一次性预分配，保证每份 >= 1 且总和精确等于 total。
    """
    data = require_json(request.get_json(silent=True))
    require_fields(data, ["amount", "count"])

    total = validate_amount(data.get("amount"), "红包总金额", min_value=1, max_value=100000)
    count = validate_int(data.get("count"), "红包个数", min_value=1, max_value=100)
    blessing = clean_text(data.get("message") or data.get("blessing"), "祝福语", 100, allow_empty=True)

    group_id = data.get("group_id")
    if group_id is not None:
        group_id = validate_int(group_id, "group_id", min_value=1)
        member = db.query_one(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id),
        )
        if not member:
            raise ApiError("你不是该群成员", 403)

    if count > total:
        raise ApiError("红包个数不能超过总金额（每份至少 1 坤币）", 400)

    cfg = _redpacket_config()
    if total > cfg.get("max_amount", 10000):
        raise ApiError(f"红包总金额不能超过 {cfg.get('max_amount', 10000)}", 400)

    shares = _split_amount(total, count)

    with db.transaction() as conn:
        if _debit(conn, g.user_id, total) == 0:
            raise ApiError("坤币余额不足", 400, code="INSUFFICIENT_BALANCE")

        transaction_id = _add_transaction(
            conn,
            g.user_id,
            total,
            blessing or "恭喜发财",
            STATUS_PENDING,
            group_id=group_id,
            packet_count=count,
        )
        # 预分配份额：amount 为该份金额，receiver_id 为 NULL 表示未被领取
        for share in shares:
            conn.execute(
                """
                INSERT INTO kunbi_transactions
                    (sender_id, receiver_id, group_id, parent_id, amount, message, status, packet_count, created_at)
                VALUES (?, NULL, ?, ?, ?, '待领取', 'pending', 1, ?)
                """,
                (g.user_id, group_id, transaction_id, share, datetime.now()),
            )

    logger.info("拼手气红包: %s, 总 %s / %s 份", g.user_id, total, count)
    _broadcast(
        "kunbi_redpacket_multi",
        {"transactionId": transaction_id, "sender": g.user_id, "count": count, "groupId": group_id},
    )

    return success(
        {"transactionId": transaction_id, "count": count, "balance": _get_balance(g.user_id)},
        message="红包发送成功",
        status_code=201,
    )


@kunbi_bp.route("/redpacket/grab/<int:transaction_id>", methods=["POST"])
@auth_required
@rate_limit("redpacket_grab", max_requests=60, window=60)
def grab_redpacket(transaction_id):
    """
    领取红包。

    并发安全（关键）：
        原先只在事务外做"是否已领取"的查重，同一用户并发发多个请求时
        全部能通过查重，从而一次抢到多份。现改为把查重也放进同一个
        写事务里，靠 sqlite 的串行写锁 + BEGIN IMMEDIATE 保证互斥：

        1. 事务内先 `BEGIN IMMEDIATE` 取写锁（避免读快照导致的重复通过）
        2. 事务内复查该用户是否已领取，已领则直接拒绝
        3. 再原子抢占一个 receiver_id IS NULL 的份额，并把 receiver_id
           一并写成本用户，杜绝同一份额被两人拿到
    """
    redpacket = db.query_one(
        "SELECT * FROM kunbi_transactions WHERE id = ? AND parent_id IS NULL",
        (transaction_id,),
    )
    if not redpacket:
        raise ApiError("红包不存在", 404)

    if redpacket["sender_id"] == g.user_id:
        raise ApiError("不能领取自己发的红包", 403)

    group_id = redpacket.get("group_id")
    if group_id:
        member = db.query_one(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id),
        )
        if not member:
            raise ApiError("你不是该群成员", 403)

    packet_count = int(redpacket.get("packet_count") or 1)
    amount = 0

    conn = db.get_connection()
    try:
        # BEGIN IMMEDIATE：立即获取写锁，保证「查重 + 抢占」整体互斥
        conn.execute("BEGIN IMMEDIATE")

        # 事务内复查：该用户是否已领取（修复并发下重复领取）
        existing = conn.execute(
            """
            SELECT id FROM kunbi_transactions
            WHERE parent_id = ? AND receiver_id = ?
            """,
            (transaction_id, g.user_id),
        ).fetchone()
        if existing:
            conn.rollback()
            raise ApiError("你已经领取过该红包", 409, code="ALREADY_GRABBED")

        # 原子抢占一个未被领取的份额，同时写入领取者
        cur = conn.execute(
            """
            UPDATE kunbi_transactions
            SET receiver_id = ?, status = 'received', created_at = ?
            WHERE id = (
                SELECT id FROM kunbi_transactions
                WHERE parent_id = ? AND receiver_id IS NULL
                ORDER BY id LIMIT 1
            )
              AND receiver_id IS NULL
            """,
            (g.user_id, datetime.now(), transaction_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise ApiError("红包已被领完", 400, code="REDPACKET_EMPTY")

        row = conn.execute(
            """
            SELECT id, amount FROM kunbi_transactions
            WHERE parent_id = ? AND receiver_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (transaction_id, g.user_id),
        ).fetchone()
        if row is None:
            conn.rollback()
            raise ApiError("领取失败，请重试", 500)

        amount = int(row["amount"] or 0)
        conn.execute(
            "UPDATE kunbi_transactions SET message = '领取红包' WHERE id = ?", (row["id"],)
        )
        conn.execute(
            "UPDATE users SET kunbi = kunbi + ? WHERE id = ?", (amount, g.user_id)
        )

        grabbed = conn.execute(
            "SELECT COUNT(*) FROM kunbi_transactions WHERE parent_id = ? AND receiver_id IS NOT NULL",
            (transaction_id,),
        ).fetchone()[0]
        new_status = STATUS_RECEIVED if grabbed >= packet_count else STATUS_PARTIAL
        conn.execute(
            "UPDATE kunbi_transactions SET status = ? WHERE id = ?",
            (new_status, transaction_id),
        )

        conn.commit()
    except ApiError:
        raise
    except Exception:
        conn.rollback()
        raise

    logger.info("用户 %s 领取红包 %s, 金额 %s", g.user_id, transaction_id, amount)
    return success(
        {"amount": amount, "balance": _get_balance(g.user_id)},
        message=f"领取成功，获得 {amount} 坤币",
    )


@kunbi_bp.route("/redpacket/<int:transaction_id>", methods=["GET"])
@auth_required
def get_redpacket_info(transaction_id):
    """查看红包状态与领取记录。"""
    redpacket = db.query_one(
        "SELECT * FROM kunbi_transactions WHERE id = ? AND parent_id IS NULL",
        (transaction_id,),
    )
    if not redpacket:
        raise ApiError("红包不存在", 404)

    grabs = db.query_all(
        """
        SELECT t.amount, t.created_at, t.receiver_id,
               u.nickname, u.avatar
        FROM kunbi_transactions t
        LEFT JOIN users u ON u.id = t.receiver_id
        WHERE t.parent_id = ? AND t.receiver_id IS NOT NULL
        ORDER BY t.created_at
        """,
        (transaction_id,),
    )

    packet_count = int(redpacket.get("packet_count") or 1)
    return success(
        {
            "id": redpacket["id"],
            "senderId": redpacket["sender_id"],
            "groupId": redpacket.get("group_id"),
            "amount": redpacket["amount"],
            "message": redpacket.get("message") or "",
            "status": redpacket.get("status"),
            "packetCount": packet_count,
            "grabbedCount": len(grabs),
            "grabs": [
                {
                    "userId": row["receiver_id"],
                    "nickname": row["nickname"],
                    "avatar": row["avatar"],
                    "amount": row["amount"],
                    "createdAt": row["created_at"],
                }
                for row in grabs
            ],
        }
    )


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _split_amount(total, count):
    """
    拼手气红包金额分配。

    先给每份预留 1，余量随机分配，最后打乱顺序。
    保证：每份 >= 1，总和精确等于 total。
    """
    if count == 1:
        return [total]
    if count > total:
        raise ApiError("红包个数不能超过总金额", 400)

    shares = [1] * count
    remainder = total - count
    for _ in range(remainder):
        shares[random.randrange(count)] += 1
    random.shuffle(shares)
    return shares


def _notify(user_id, event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload, room=f"user_{user_id}")
    except Exception as exc:
        logger.debug("通知用户 %s 失败: %s", user_id, exc)


def _broadcast(event, payload):
    try:
        from ..factory import socketio

        socketio.emit(event, payload)
    except Exception as exc:
        logger.debug("广播 %s 失败: %s", event, exc)
