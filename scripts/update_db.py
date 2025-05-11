#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 数据库更新脚本
执行数据库结构更新，添加新的表和字段
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_update.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("FUCKCHAT.DB_UPDATE")

def read_sql_file(file_path):
    """读取SQL文件内容"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def execute_sql_commands(db_path, sql_commands):
    """执行SQL命令"""
    conn = None
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 分割SQL命令
        commands = sql_commands.split(';')
        
        # 执行每条SQL命令
        for command in commands:
            # 跳过空命令
            if command.strip() == '':
                continue
                
            try:
                cursor.execute(command)
                logger.info(f"执行SQL命令成功: {command[:50]}...")
            except sqlite3.Error as e:
                logger.warning(f"执行SQL命令失败: {command[:50]}..., 错误: {str(e)}")
        
        # 提交事务
        conn.commit()
        logger.info("所有SQL命令执行完毕")
        
        # 记录备份
        backup_path = f"fuckchat_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        try:
            with open(db_path, 'rb') as source:
                with open(backup_path, 'wb') as dest:
                    dest.write(source.read())
            logger.info(f"数据库备份成功: {backup_path}")
        except Exception as e:
            logger.error(f"数据库备份失败: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"数据库操作失败: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # SQL文件路径
    sql_file = os.path.join(script_dir, 'update_database.sql')
    
    # 数据库路径
    db_path = os.path.join(os.path.dirname(script_dir), 'fuckchat.db')
    
    logger.info(f"开始更新数据库: {db_path}")
    logger.info(f"使用SQL文件: {sql_file}")
    
    # 检查文件是否存在
    if not os.path.exists(sql_file):
        logger.error(f"SQL文件不存在: {sql_file}")
        return False
    
    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        return False
    
    # 读取SQL文件
    try:
        sql_commands = read_sql_file(sql_file)
    except Exception as e:
        logger.error(f"读取SQL文件失败: {str(e)}")
        return False
    
    # 执行SQL命令
    result = execute_sql_commands(db_path, sql_commands)
    
    if result:
        logger.info("数据库更新成功")
    else:
        logger.error("数据库更新失败")
    
    return result

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 