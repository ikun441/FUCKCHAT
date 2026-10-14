#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 数据库迁移脚本 (v2.0.0)

重构说明：
    原先 init_db.py 建表、update_database.sql 补列，两者重复且无版本管理，
    且 SQL 按分号切分执行会误伤含分号的语句。

    现在统一为「幂等迁移」：
      - 每个迁移步骤只执行一次，失败不回滚
      - 用 PRAGMA table_info 判断列是否存在，避免 ALTER 报错
      - 迁移前自动备份到 backups/ 目录

用法:
    python scripts/migrate_db.py
    python scripts/migrate_db.py --db path/to/fuckchat.db
"""

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("FUCKCHAT.migrate")


def get_columns(conn, table):
    """返回表的列名集合。"""
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    except sqlite3.Error:
        return set()


def table_exists(conn, table):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def add_column_if_missing(conn, table, column, definition):
    """列不存在时才添加，幂等。"""
    if not table_exists(conn, table):
        logger.info("跳过 %s.%s（表不存在）", table, column)
        return False
    columns = get_columns(conn, table)
    if column in columns:
        return False
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')
    logger.info("新增列: %s.%s %s", table, column, definition)
    return True


def index_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def create_index_if_missing(conn, name, table, columns):
    """索引不存在时才创建，返回是否真的发生了变更。"""
    if not table_exists(conn, table):
        return False
    if index_exists(conn, name):
        return False
    conn.execute(f'CREATE INDEX IF NOT EXISTS {name} ON "{table}" ({columns})')
    return True


def create_table_if_missing(conn, name, ddl):
    if table_exists(conn, name):
        return False
    conn.execute(ddl)
    logger.info("新建表: %s", name)
    return True


# ---------------------------------------------------------------------------
# 迁移步骤
# ---------------------------------------------------------------------------


def migration_v2(conn):
    """
    v2.0.0 结构与索引迁移。

    新增 user_logs.detail，用于记录撤回/举报等操作的详情；
    其余为兼容既有结构补齐与索引优化。
    """
    changed = 0

    # user_logs: 补充 detail 字段（重构后用于记录操作详情）
    if add_column_if_missing(conn, "user_logs", "detail", "TEXT DEFAULT ''"):
        changed += 1

    # users: 补齐资料字段（幂等）
    for column, definition in [
        ("signature", "TEXT DEFAULT ''"),
        ("birthday", "TEXT DEFAULT NULL"),
        ("location", "TEXT DEFAULT ''"),
        ("email", "TEXT DEFAULT ''"),
        ("phone", "TEXT DEFAULT ''"),
        ("background_image", "TEXT DEFAULT ''"),
    ]:
        if add_column_if_missing(conn, "users", column, definition):
            changed += 1

    # messages: 补充 message_type（旧版本遗留字段名）
    if add_column_if_missing(conn, "messages", "message_type", "TEXT DEFAULT 'text'"):
        changed += 1

    # 红包相关：沿用 kunbi_transactions 的 parent_id 自引用，
    # 补齐 packet_count 用于拼手气红包
    if add_column_if_missing(conn, "kunbi_transactions", "packet_count", "INTEGER DEFAULT 1"):
        changed += 1

    # 索引优化
    indexes = [
        ("idx_messages_sender", "messages", "sender_id"),
        ("idx_messages_receiver", "messages", "receiver_id"),
        ("idx_messages_group", "messages", "group_id"),
        ("idx_messages_created", "messages", "created_at"),
        ("idx_group_members_group", "group_members", "group_id"),
        ("idx_group_members_user", "group_members", "user_id"),
        ("idx_kunbi_sender", "kunbi_transactions", "sender_id"),
        ("idx_kunbi_receiver", "kunbi_transactions", "receiver_id"),
        ("idx_kunbi_parent", "kunbi_transactions", "parent_id"),
        ("idx_blacklist_user", "blacklist", "user_id"),
        ("idx_notifications_user", "notifications", "user_id"),
        ("idx_friends_user", "friends", "user_id"),
        ("idx_friend_requests_receiver", "friend_requests", "receiver_id"),
        ("idx_user_logs_action", "user_logs", "action"),
        ("idx_system_logs_created", "system_logs", "created_at"),
    ]
    for name, table, columns in indexes:
        if create_index_if_missing(conn, name, table, columns):
            changed += 1

    # 唯一约束兜底：防止重复好友关系
    create_index_if_missing(
        conn, "idx_friends_unique", "friends", "user_id, friend_id"
    )

    return changed


def migration_files_table(conn):
    """
    files 表：重构后上传文件统一登记，便于审计与清理。

    注意：该表结构以 app/routes/files.py 实际写入的字段为准
    （user_id, filename, original_name, file_path, file_size, file_type）。
    """
    return create_table_if_missing(
        conn,
        "files",
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            file_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """,
    )


# ---------------------------------------------------------------------------
# 完整表结构（补齐 init_db.py 未覆盖、原先依赖 update_database.sql 的表）
#
# 背景：init_db.py 只建 7 张基础表，notifications / friends / friend_requests /
# user_logs 等 9 张表原先只存在于 update_database.sql。若使用者跳过了那一步，
# 相关接口会在运行时抛 "no such table"。这里把它们纳入幂等迁移，
# 保证「init_db + migrate_db」两步即可得到完整可用的 schema。
# ---------------------------------------------------------------------------

EXTRA_TABLES = {
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            reference_id INTEGER DEFAULT NULL,
            reference_type TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """,
    "friends": """
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            nickname TEXT DEFAULT '',
            group_name TEXT DEFAULT '我的好友',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (friend_id) REFERENCES users (id),
            UNIQUE(user_id, friend_id)
        )
    """,
    "friend_requests": """
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT DEFAULT NULL,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    """,
    "user_logs": """
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT DEFAULT '',
            device_info TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """,
    "emoji_favorites": """
        CREATE TABLE IF NOT EXISTS emoji_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            emoji_url TEXT NOT NULL,
            emoji_name TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """,
    "user_settings": """
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            theme TEXT DEFAULT 'light',
            notification_sound INTEGER DEFAULT 1,
            message_preview INTEGER DEFAULT 1,
            auto_download_files INTEGER DEFAULT 1,
            language TEXT DEFAULT 'zh-CN',
            font_size TEXT DEFAULT 'medium',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id)
        )
    """,
    "mail": """
        CREATE TABLE IF NOT EXISTS mail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            has_attachment INTEGER DEFAULT 0,
            is_deleted_by_sender INTEGER DEFAULT 0,
            is_deleted_by_receiver INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            read_at TEXT DEFAULT NULL,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    """,
    "mail_attachments": """
        CREATE TABLE IF NOT EXISTS mail_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filesize INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (mail_id) REFERENCES mail (id)
        )
    """,
    "group_announcements": """
        CREATE TABLE IF NOT EXISTS group_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            creator_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT DEFAULT NULL,
            FOREIGN KEY (group_id) REFERENCES groups (id),
            FOREIGN KEY (creator_id) REFERENCES users (id)
        )
    """,
}


def migration_ensure_tables(conn):
    """确保所有业务表存在。"""
    changed = 0
    for name, ddl in EXTRA_TABLES.items():
        if create_table_if_missing(conn, name, ddl):
            changed += 1
    return changed


# 旧库可能缺失的列（update_database.sql 中的 ALTER 项）
EXTRA_COLUMNS = [
    ("messages", "message_type", "TEXT DEFAULT 'text'"),
    ("messages", "extra_data", "TEXT DEFAULT NULL"),
    ("messages", "is_edited", "INTEGER DEFAULT 0"),
    ("messages", "edited_at", "TEXT DEFAULT NULL"),
    ("messages", "reply_to", "INTEGER DEFAULT NULL"),
    ("blacklist", "reason", "TEXT DEFAULT ''"),
]


def migration_extra_columns(conn):
    """补齐旧库缺失的列。"""
    changed = 0
    for table, column, definition in EXTRA_COLUMNS:
        if add_column_if_missing(conn, table, column, definition):
            changed += 1
    return changed


MIGRATIONS = [
    # 顺序很重要：先建表，再补列，最后建索引
    ("v2.0.0-ensure-tables", migration_ensure_tables),
    ("v2.0.0-files", migration_files_table),
    ("v2.0.0-extra-columns", migration_extra_columns),
    ("v2.0.0-structure", migration_v2),
]


def run_migrations(db_path):
    """执行所有迁移，返回是否成功。"""
    db_path = Path(db_path)
    if not db_path.exists():
        logger.error("数据库不存在: %s", db_path)
        logger.error("请先运行: python scripts/init_db.py")
        return False

    # 迁移前备份
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pre_migrate_{stamp}.db"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info("迁移前备份: %s", backup_path.relative_to(BASE_DIR))
    except OSError as exc:
        logger.warning("备份失败，继续迁移: %s", exc)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    total_changes = 0

    try:
        for name, func in MIGRATIONS:
            logger.info("执行迁移: %s", name)
            try:
                changes = func(conn)
                conn.commit()
                total_changes += changes or 0
                logger.info("  -> 完成，变更 %s 项", changes or 0)
            except sqlite3.Error as exc:
                logger.warning("  -> 迁移 %s 失败（跳过）: %s", name, exc)
                conn.rollback()
    finally:
        conn.close()

    logger.info("迁移完成，共变更 %s 项", total_changes)
    return True


def main():
    parser = argparse.ArgumentParser(description="FUCKCHAT 数据库迁移")
    parser.add_argument("--db", default=str(BASE_DIR / "fuckchat.db"), help="数据库路径")
    args = parser.parse_args()

    success = run_migrations(args.db)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
