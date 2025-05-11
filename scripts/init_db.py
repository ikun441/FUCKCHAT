#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 数据库初始化脚本
创建数据库表结构和初始数据
"""

import os
import sys
import sqlite3
import logging
import bcrypt
from datetime import datetime

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FUCKCHAT.init_db")

# 数据库路径
DB_PATH = 'fuckchat.db'

# SQL语句 - 创建用户表
CREATE_USERS_TABLE = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash BLOB NOT NULL,
    nickname TEXT NOT NULL,
    avatar TEXT,
    bio TEXT,
    gender TEXT DEFAULT 'other',
    kunbi INTEGER DEFAULT 100,
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    status TEXT DEFAULT 'offline'
);
'''

# SQL语句 - 创建群组表
CREATE_GROUPS_TABLE = '''
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    avatar TEXT,
    creator_id INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES users (id)
);
'''

# SQL语句 - 创建群组成员表
CREATE_GROUP_MEMBERS_TABLE = '''
CREATE TABLE IF NOT EXISTS group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'member',  -- 'admin', 'member'
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    UNIQUE(group_id, user_id)
);
'''

# SQL语句 - 创建消息表
CREATE_MESSAGES_TABLE = '''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER,
    group_id INTEGER,
    type TEXT DEFAULT 'text',  -- 'text', 'image', 'voice', 'emoji', 'kunbi'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users (id),
    FOREIGN KEY (receiver_id) REFERENCES users (id),
    FOREIGN KEY (group_id) REFERENCES groups (id),
    CHECK (
        (receiver_id IS NOT NULL AND group_id IS NULL) OR 
        (receiver_id IS NULL AND group_id IS NOT NULL)
    )
);
'''

# SQL语句 - 创建黑名单表
CREATE_BLACKLIST_TABLE = '''
CREATE TABLE IF NOT EXISTS blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    blocked_user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (blocked_user_id) REFERENCES users (id),
    UNIQUE(user_id, blocked_user_id)
);
'''

# SQL语句 - 创建坤币交易表
CREATE_KUNBI_TRANSACTIONS_TABLE = '''
CREATE TABLE IF NOT EXISTS kunbi_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER,
    group_id INTEGER,
    parent_id INTEGER,
    amount INTEGER NOT NULL,
    message TEXT,
    status TEXT DEFAULT 'sent',  -- 'sent', 'pending', 'partially_received', 'received'
    packet_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users (id),
    FOREIGN KEY (receiver_id) REFERENCES users (id),
    FOREIGN KEY (group_id) REFERENCES groups (id),
    FOREIGN KEY (parent_id) REFERENCES kunbi_transactions (id)
);
'''

# SQL语句 - 创建系统日志表
CREATE_SYSTEM_LOGS_TABLE = '''
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
'''

# 初始用户数据
INITIAL_USERS = [
    {
        'username': 'admin',
        'password': 'admin123',
        'nickname': '系统管理员',
        'kunbi': 999,
        'is_admin': 1
    },
    {
        'username': 'user',
        'password': 'user123',
        'nickname': '测试用户',
        'kunbi': 100,
        'is_admin': 0
    }
]

# 初始群组数据
INITIAL_GROUPS = [
    {
        'name': '全体成员群',
        'creator_id': 1,  # admin
        'description': 'FUCKCHAT全体成员交流群'
    }
]

def init_database():
    """初始化数据库"""
    # 检查数据库文件是否存在，如果存在则询问是否覆盖
    if os.path.exists(DB_PATH):
        confirm = input(f"数据库文件 {DB_PATH} 已存在。是否清空重建? (y/n): ")
        if confirm.lower() != 'y':
            logger.info("操作已取消")
            return
        os.remove(DB_PATH)
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 创建表
        logger.info("创建数据库表...")
        cursor.execute(CREATE_USERS_TABLE)
        cursor.execute(CREATE_GROUPS_TABLE)
        cursor.execute(CREATE_GROUP_MEMBERS_TABLE)
        cursor.execute(CREATE_MESSAGES_TABLE)
        cursor.execute(CREATE_BLACKLIST_TABLE)
        cursor.execute(CREATE_KUNBI_TRANSACTIONS_TABLE)
        cursor.execute(CREATE_SYSTEM_LOGS_TABLE)
        
        # 添加初始用户数据
        logger.info("添加初始用户数据...")
        for user in INITIAL_USERS:
            # 对密码进行哈希处理
            password_hash = bcrypt.hashpw(user['password'].encode('utf-8'), bcrypt.gensalt())
            
            cursor.execute(
                "INSERT INTO users (username, password_hash, nickname, kunbi, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user['username'], password_hash, user['nickname'], user['kunbi'], user['is_admin'], datetime.now())
            )
        
        # 添加初始群组数据
        logger.info("添加初始群组数据...")
        for group in INITIAL_GROUPS:
            cursor.execute(
                "INSERT INTO groups (name, creator_id, description, created_at) VALUES (?, ?, ?, ?)",
                (group['name'], group['creator_id'], group['description'], datetime.now())
            )
            
            # 获取新插入的群组ID
            group_id = cursor.lastrowid
            
            # 将所有用户添加到该群组
            cursor.execute("SELECT id FROM users")
            user_ids = [row[0] for row in cursor.fetchall()]
            
            for user_id in user_ids:
                role = 'admin' if user_id == group['creator_id'] else 'member'
                cursor.execute(
                    "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                    (group_id, user_id, role, datetime.now())
                )
        
        # 添加系统日志
        cursor.execute(
            "INSERT INTO system_logs (type, content, created_at) VALUES (?, ?, ?)",
            ('SYSTEM', '数据库初始化完成', datetime.now())
        )
        
        # 提交事务
        conn.commit()
        logger.info("数据库初始化成功!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"数据库初始化失败: {str(e)}")
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    init_database() 