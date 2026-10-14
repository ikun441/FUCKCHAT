#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FUCKCHAT - 数据库访问层

替换原先散落在各路由中的 sqlite3.connect('fuckchat.db') 硬编码，
统一提供连接管理、事务、Row 工厂与 WAL 支持。
"""

import sqlite3
import logging
from contextlib import contextmanager

from flask import g

logger = logging.getLogger("FUCKCHAT.db")

# 由 init_app 注入
_db_path = "fuckchat.db"
_db_timeout = 10.0


def init_app(app, config):
    """把数据库配置绑定到应用。"""
    global _db_path, _db_timeout
    db_conf = config.section("database")
    _db_path = str(config.resolve_path(db_conf.get("path", "fuckchat.db")))
    _db_timeout = float(db_conf.get("timeout", 10.0))

    # 确保目录存在
    import os

    directory = os.path.dirname(_db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    app.teardown_appcontext(close_connection)
    logger.info("数据库路径: %s", _db_path)


def get_db_path():
    return _db_path


def connect():
    """创建新连接（用于脚本或后台线程）。"""
    conn = sqlite3.connect(_db_path, timeout=_db_timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_connection():
    """
    获取请求级连接，同一请求内复用，请求结束自动关闭。
    避免原先每个函数都 open/close 的模式。
    """
    if "db_conn" not in g:
        g.db_conn = connect()
    return g.db_conn


def close_connection(exception=None):
    """关闭请求级连接。"""
    conn = g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error as exc:  # pragma: no cover
            logger.warning("关闭数据库连接失败: %s", exc)


@contextmanager
def transaction(immediate=True):
    """
    事务上下文：正常提交，异常回滚。

    默认使用 BEGIN IMMEDIATE 立即获取写锁。原因是：
    sqlite 默认的 deferred 事务在「先读后写」时，读到的可能是旧快照，
    两个并发请求会同时通过业务校验（例如余额校验、红包查重），
    从而产生超发/重复领取。IMMEDIATE 在事务开始就串行化写操作，
    把这类竞态挡在数据库层。

    只读场景可传 immediate=False。

    用法:
        with transaction() as conn:
            conn.execute(...)
    """
    conn = get_connection()
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@contextmanager
def cursor():
    """只读游标上下文。"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()


def query_all(sql, params=()):
    """查询多行，返回 dict 列表。"""
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def query_one(sql, params=()):
    """查询单行，返回 dict 或 None。"""
    with cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def query_scalar(sql, params=(), default=None):
    """查询单个值。"""
    with cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return default
        return row[0]


def execute(sql, params=()):
    """执行写操作并提交，返回 lastrowid。"""
    with transaction() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


def execute_many(sql, seq_of_params):
    """批量执行并提交。"""
    with transaction() as conn:
        cur = conn.executemany(sql, seq_of_params)
        return cur.rowcount


def table_exists(name):
    """检查表是否存在。"""
    row = query_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    )
    return row is not None
