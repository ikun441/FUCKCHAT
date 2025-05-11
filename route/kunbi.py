#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 坤币相关路由
处理坤币交易、红包等功能
"""

import os
import random
import logging
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, g
from route.auth import auth_required

# 创建日志记录器
logger = logging.getLogger("FUCKCHAT.kunbi")

# 创建蓝图
kunbi_bp = Blueprint('kunbi', __name__)

# 检查用户坤币余额中间件
def check_kunbi_balance(f):
    """检查用户坤币余额是否足够"""
    @wraps(f)
    def decorated(*args, **kwargs):
        data = request.get_json()
        if not data or 'amount' not in data:
            return jsonify({'message': '缺少必要参数', 'success': False}), 400
        
        amount = data.get('amount')
        
        # 验证金额
        try:
            amount = int(amount)
            if amount <= 0:
                return jsonify({'message': '金额必须为正数', 'success': False}), 400
        except ValueError:
            return jsonify({'message': '金额必须为整数', 'success': False}), 400
        
        # 验证用户余额
        try:
            conn = sqlite3.connect('fuckchat.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT kunbi FROM users WHERE id = ?", (g.user_id,))
            user = cursor.fetchone()
            
            if not user:
                return jsonify({'message': '用户不存在', 'success': False}), 404
            
            balance = user[0]
            
            if balance < amount:
                return jsonify({'message': '坤币余额不足', 'success': False}), 400
            
            # 将余额和金额存入 g 对象
            g.balance = balance
            g.amount = amount
            
            return f(*args, **kwargs)
        
        except Exception as e:
            logger.error(f"检查坤币余额失败: {str(e)}")
            return jsonify({'message': '检查坤币余额失败', 'success': False}), 500
        
        finally:
            if conn:
                conn.close()
    
    return decorated

# 路由：获取用户坤币余额
@kunbi_bp.route('/balance', methods=['GET'])
@auth_required
def get_balance():
    """获取当前用户的坤币余额"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT kunbi FROM users WHERE id = ?", (g.user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        balance = user[0]
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'balance': balance
        }), 200
    
    except Exception as e:
        logger.error(f"获取坤币余额失败: {str(e)}")
        return jsonify({'message': '获取坤币余额失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：个人转账
@kunbi_bp.route('/transfer', methods=['POST'])
@auth_required
@check_kunbi_balance
def transfer_kunbi():
    """向指定用户转账坤币"""
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    message = data.get('message', '')
    
    # 验证接收者
    if not receiver_id:
        return jsonify({'message': '缺少接收者ID', 'success': False}), 400
    
    if receiver_id == g.user_id:
        return jsonify({'message': '不能转账给自己', 'success': False}), 400
    
    amount = g.amount  # 从中间件获取
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查接收者是否存在
        cursor.execute("SELECT id FROM users WHERE id = ?", (receiver_id,))
        if not cursor.fetchone():
            return jsonify({'message': '接收者不存在', 'success': False}), 404
        
        # 开始事务
        conn.execute("BEGIN TRANSACTION")
        
        # 扣除发送者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi - ? WHERE id = ?",
            (amount, g.user_id)
        )
        
        # 增加接收者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi + ? WHERE id = ?",
            (amount, receiver_id)
        )
        
        # 记录交易
        cursor.execute(
            """INSERT INTO kunbi_transactions 
               (sender_id, receiver_id, amount, message, status, created_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (g.user_id, receiver_id, amount, message, 'sent', datetime.now())
        )
        
        # 提交事务
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 向用户 {receiver_id} 转账 {amount} 坤币")
        
        return jsonify({
            'message': '转账成功',
            'success': True,
            'balance': g.balance - amount
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"转账失败: {str(e)}")
        return jsonify({'message': '转账失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：发送红包
@kunbi_bp.route('/redpacket/send', methods=['POST'])
@auth_required
@check_kunbi_balance
def send_redpacket():
    """发送坤币红包"""
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    group_id = data.get('group_id')
    message = data.get('message', '恭喜发财，坤坤有礼')
    
    # 验证接收对象
    if not receiver_id and not group_id:
        return jsonify({'message': '缺少接收者ID或群组ID', 'success': False}), 400
    
    if receiver_id and receiver_id == g.user_id:
        return jsonify({'message': '不能给自己发红包', 'success': False}), 400
    
    amount = g.amount  # 从中间件获取
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 验证接收者或群组是否存在
        if receiver_id:
            cursor.execute("SELECT id FROM users WHERE id = ?", (receiver_id,))
            if not cursor.fetchone():
                return jsonify({'message': '接收者不存在', 'success': False}), 404
        elif group_id:
            cursor.execute("SELECT id FROM groups WHERE id = ?", (group_id,))
            if not cursor.fetchone():
                return jsonify({'message': '群组不存在', 'success': False}), 404
            
            # 检查发送者是否在群组中
            cursor.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, g.user_id)
            )
            if not cursor.fetchone():
                return jsonify({'message': '您不是该群组成员', 'success': False}), 403
        
        # 开始事务
        conn.execute("BEGIN TRANSACTION")
        
        # 扣除发送者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi - ? WHERE id = ?",
            (amount, g.user_id)
        )
        
        # 记录红包交易
        if receiver_id:
            cursor.execute(
                """INSERT INTO kunbi_transactions 
                   (sender_id, receiver_id, amount, message, status, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (g.user_id, receiver_id, amount, message, 'pending', datetime.now())
            )
        else:
            cursor.execute(
                """INSERT INTO kunbi_transactions 
                   (sender_id, group_id, amount, message, status, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (g.user_id, group_id, amount, message, 'pending', datetime.now())
            )
        
        transaction_id = cursor.lastrowid
        
        # 提交事务
        conn.commit()
        
        if receiver_id:
            logger.info(f"用户 {g.user_id} 向用户 {receiver_id} 发送红包 {amount} 坤币")
        else:
            logger.info(f"用户 {g.user_id} 向群组 {group_id} 发送红包 {amount} 坤币")
        
        return jsonify({
            'message': '红包发送成功',
            'success': True,
            'transaction_id': transaction_id,
            'balance': g.balance - amount
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"发送红包失败: {str(e)}")
        return jsonify({'message': '发送红包失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：发送多人红包
@kunbi_bp.route('/redpacket/send_multi', methods=['POST'])
@auth_required
@check_kunbi_balance
def send_multi_redpacket():
    """发送多人坤币红包"""
    data = request.get_json()
    group_id = data.get('group_id')
    count = data.get('count', 1)  # 红包个数
    message = data.get('message', '恭喜发财，坤坤有礼')
    
    # 验证接收群组
    if not group_id:
        return jsonify({'message': '缺少群组ID', 'success': False}), 400
    
    # 验证红包个数
    try:
        count = int(count)
        if count <= 0:
            return jsonify({'message': '红包个数必须为正数', 'success': False}), 400
    except ValueError:
        return jsonify({'message': '红包个数必须为整数', 'success': False}), 400
    
    amount = g.amount  # 从中间件获取
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 验证群组是否存在
        cursor.execute("SELECT id FROM groups WHERE id = ?", (group_id,))
        if not cursor.fetchone():
            return jsonify({'message': '群组不存在', 'success': False}), 404
        
        # 检查发送者是否在群组中
        cursor.execute(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id)
        )
        if not cursor.fetchone():
            return jsonify({'message': '您不是该群组成员', 'success': False}), 403
        
        # 获取群组成员数量
        cursor.execute(
            "SELECT COUNT(*) FROM group_members WHERE group_id = ?",
            (group_id,)
        )
        member_count = cursor.fetchone()[0]
        
        # 验证红包个数不能超过群组成员数量
        if count > member_count:
            return jsonify({'message': '红包个数不能超过群组成员数量', 'success': False}), 400
        
        # 开始事务
        conn.execute("BEGIN TRANSACTION")
        
        # 扣除发送者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi - ? WHERE id = ?",
            (amount, g.user_id)
        )
        
        # 记录红包交易
        cursor.execute(
            """INSERT INTO kunbi_transactions 
               (sender_id, group_id, amount, message, status, created_at, packet_count) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (g.user_id, group_id, amount, message, 'pending', datetime.now(), count)
        )
        
        transaction_id = cursor.lastrowid
        
        # 提交事务
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 向群组 {group_id} 发送 {count} 个红包，总金额 {amount} 坤币")
        
        return jsonify({
            'message': '多人红包发送成功',
            'success': True,
            'transaction_id': transaction_id,
            'balance': g.balance - amount,
            'count': count
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"发送多人红包失败: {str(e)}")
        return jsonify({'message': '发送多人红包失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：抢红包
@kunbi_bp.route('/redpacket/grab/<int:transaction_id>', methods=['POST'])
@auth_required
def grab_redpacket(transaction_id):
    """抢红包"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取红包信息
        cursor.execute(
            """SELECT * FROM kunbi_transactions 
               WHERE id = ? AND (status = 'pending' OR status = 'partially_received')""",
            (transaction_id,)
        )
        transaction = cursor.fetchone()
        
        if not transaction:
            return jsonify({'message': '红包不存在或已被领完', 'success': False}), 404
        
        # 检查是否为群红包
        if transaction['group_id'] is None and transaction['receiver_id'] != g.user_id:
            return jsonify({'message': '无权领取此红包', 'success': False}), 403
        
        # 如果是群红包，检查用户是否在群中
        if transaction['group_id'] is not None:
            cursor.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (transaction['group_id'], g.user_id)
            )
            if not cursor.fetchone():
                return jsonify({'message': '您不是该群组成员', 'success': False}), 403
        
        # 检查用户是否已经抢过这个红包
        cursor.execute(
            """SELECT id FROM kunbi_transactions 
               WHERE parent_id = ? AND receiver_id = ?""",
            (transaction_id, g.user_id)
        )
        if cursor.fetchone():
            return jsonify({'message': '您已经领取过此红包', 'success': False}), 400
        
        # 开始事务
        conn.execute("BEGIN TRANSACTION")
        
        # 计算领取金额
        amount = transaction['amount']
        packet_count = transaction.get('packet_count', 1)
        received_count = 0
        
        if packet_count > 1:
            # 多人红包处理
            cursor.execute(
                "SELECT COUNT(*) FROM kunbi_transactions WHERE parent_id = ?",
                (transaction_id,)
            )
            received_count = cursor.fetchone()[0]
            
            # 检查是否已领完
            if received_count >= packet_count:
                return jsonify({'message': '红包已被领完', 'success': False}), 400
            
            # 随机金额（如果是最后一个，则取剩余全部）
            if received_count == packet_count - 1:
                cursor.execute(
                    """SELECT SUM(amount) FROM kunbi_transactions 
                       WHERE parent_id = ?""",
                    (transaction_id,)
                )
                total_received = cursor.fetchone()[0] or 0
                grab_amount = amount - total_received
            else:
                # 剩余金额和红包数
                cursor.execute(
                    """SELECT SUM(amount) FROM kunbi_transactions 
                       WHERE parent_id = ?""",
                    (transaction_id,)
                )
                total_received = cursor.fetchone()[0] or 0
                remaining_amount = amount - total_received
                remaining_count = packet_count - received_count
                
                # 随机金额（保证每人至少1坤币，且不超过剩余的平均值的2倍）
                if remaining_amount <= remaining_count:
                    grab_amount = 1
                else:
                    avg = remaining_amount / remaining_count
                    max_amount = min(remaining_amount - (remaining_count - 1), avg * 2)
                    grab_amount = random.randint(1, int(max_amount))
        else:
            # 单人红包，直接领取全部
            grab_amount = amount
        
        # 增加接收者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi + ? WHERE id = ?",
            (grab_amount, g.user_id)
        )
        
        # 记录领取记录
        cursor.execute(
            """INSERT INTO kunbi_transactions 
               (sender_id, receiver_id, parent_id, amount, message, status, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                transaction['sender_id'], 
                g.user_id, 
                transaction_id, 
                grab_amount, 
                '领取红包', 
                'received', 
                datetime.now()
            )
        )
        
        # 更新原红包状态
        if packet_count > 1 and received_count < packet_count - 1:
            # 多人红包且非最后一个，更新为部分领取
            cursor.execute(
                "UPDATE kunbi_transactions SET status = 'partially_received' WHERE id = ?",
                (transaction_id,)
            )
        else:
            # 单人红包或多人红包的最后一个，更新为已领取
            cursor.execute(
                "UPDATE kunbi_transactions SET status = 'received' WHERE id = ?",
                (transaction_id,)
            )
        
        # 提交事务
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 领取了红包 {transaction_id}，获得 {grab_amount} 坤币")
        
        # 获取用户当前余额
        cursor.execute("SELECT kunbi FROM users WHERE id = ?", (g.user_id,))
        current_balance = cursor.fetchone()[0]
        
        return jsonify({
            'message': '领取红包成功',
            'success': True,
            'amount': grab_amount,
            'balance': current_balance
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"领取红包失败: {str(e)}")
        return jsonify({'message': '领取红包失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取交易记录
@kunbi_bp.route('/transactions', methods=['GET'])
@auth_required
def get_transactions():
    """获取当前用户的坤币交易记录"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 计算分页
        offset = (page - 1) * per_page
        
        # 查询交易记录
        cursor.execute(
            """SELECT t.*, 
                      s.username as sender_username, s.nickname as sender_nickname,
                      r.username as receiver_username, r.nickname as receiver_nickname,
                      g.name as group_name
               FROM kunbi_transactions t
               LEFT JOIN users s ON t.sender_id = s.id
               LEFT JOIN users r ON t.receiver_id = r.id
               LEFT JOIN groups g ON t.group_id = g.id
               WHERE t.sender_id = ? OR t.receiver_id = ?
               ORDER BY t.created_at DESC
               LIMIT ? OFFSET ?""",
            (g.user_id, g.user_id, per_page, offset)
        )
        
        transactions = []
        for row in cursor.fetchall():
            transaction = {
                'id': row['id'],
                'amount': row['amount'],
                'message': row['message'],
                'status': row['status'],
                'created_at': row['created_at'],
                'type': 'sent' if row['sender_id'] == g.user_id else 'received'
            }
            
            # 设置交易对象信息
            if row['group_id'] is not None:
                transaction['target_type'] = 'group'
                transaction['target_name'] = row['group_name']
                transaction['target_id'] = row['group_id']
            else:
                transaction['target_type'] = 'user'
                if row['sender_id'] == g.user_id:
                    transaction['target_name'] = row['receiver_nickname'] or row['receiver_username']
                    transaction['target_id'] = row['receiver_id']
                else:
                    transaction['target_name'] = row['sender_nickname'] or row['sender_username']
                    transaction['target_id'] = row['sender_id']
            
            transactions.append(transaction)
        
        # 获取交易总数
        cursor.execute(
            """SELECT COUNT(*) FROM kunbi_transactions
               WHERE sender_id = ? OR receiver_id = ?""",
            (g.user_id, g.user_id)
        )
        total = cursor.fetchone()[0]
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'transactions': transactions,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        logger.error(f"获取交易记录失败: {str(e)}")
        return jsonify({'message': '获取交易记录失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close() 