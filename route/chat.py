#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 聊天相关路由
处理聊天消息、用户状态、群组等功能
"""

import os
import logging
import sqlite3
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, g, current_app
from flask_socketio import emit, join_room, leave_room
from route.auth import auth_required

# 创建日志记录器
logger = logging.getLogger("FUCKCHAT.chat")

# 创建蓝图
chat_bp = Blueprint('chat', __name__)

# 路由：获取在线用户列表
@chat_bp.route('/users', methods=['GET'], endpoint='get_online_users_endpoint')
@auth_required
def get_online_users():
    """获取在线用户列表"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 查询在线用户
        cursor.execute("""
            SELECT id, username, nickname, avatar, status
            FROM users 
            WHERE status = 'online' AND id != ?
        """, (g.user_id,))
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row['id'],
                'username': row['username'],
                'nickname': row['nickname'],
                'avatar': row['avatar'] or '/src/images/default-avatar.png',
                'status': row['status']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'users': users
        }), 200
    
    except Exception as e:
        logger.error(f"获取在线用户列表失败: {str(e)}")
        return jsonify({'message': '获取在线用户列表失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取最近联系人
@chat_bp.route('/contacts', methods=['GET'], endpoint='get_recent_contacts_endpoint')
@auth_required
def get_recent_contacts():
    """获取最近联系人列表"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 查询最近联系人 (通过消息记录推导)
        cursor.execute("""
            SELECT DISTINCT 
                u.id, u.username, u.nickname, u.avatar, u.status,
                MAX(m.created_at) as last_message_time
            FROM users u
            JOIN messages m ON (
                (m.sender_id = u.id AND m.receiver_id = ?) OR
                (m.sender_id = ? AND m.receiver_id = u.id)
            )
            WHERE u.id != ?
            GROUP BY u.id
            ORDER BY last_message_time DESC
            LIMIT 20
        """, (g.user_id, g.user_id, g.user_id))
        
        contacts = []
        for row in cursor.fetchall():
            contacts.append({
                'id': row['id'],
                'username': row['username'],
                'nickname': row['nickname'],
                'avatar': row['avatar'] or '/src/images/default-avatar.png',
                'status': row['status'],
                'last_message_time': row['last_message_time']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'contacts': contacts
        }), 200
    
    except Exception as e:
        logger.error(f"获取最近联系人失败: {str(e)}")
        return jsonify({'message': '获取最近联系人失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取群组列表
@chat_bp.route('/groups', methods=['GET'], endpoint='get_groups_endpoint')
@auth_required
def get_groups():
    """获取用户所在群组列表"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 查询用户所在的群组
        cursor.execute("""
            SELECT 
                g.id, g.name, g.avatar, g.description, g.created_at,
                gm.role, COUNT(DISTINCT gm2.user_id) as member_count
            FROM groups g
            JOIN group_members gm ON g.id = gm.group_id AND gm.user_id = ?
            JOIN group_members gm2 ON g.id = gm2.group_id
            GROUP BY g.id
            ORDER BY g.created_at DESC
        """, (g.user_id,))
        
        groups = []
        for row in cursor.fetchall():
            groups.append({
                'id': row['id'],
                'name': row['name'],
                'avatar': row['avatar'] or '/src/images/group-avatar.png',
                'description': row['description'],
                'member_count': row['member_count'],
                'role': row['role'],
                'created_at': row['created_at']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'groups': groups
        }), 200
    
    except Exception as e:
        logger.error(f"获取群组列表失败: {str(e)}")
        return jsonify({'message': '获取群组列表失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：创建群组
@chat_bp.route('/groups', methods=['POST'], endpoint='create_group_endpoint')
@auth_required
def create_group():
    """创建新群组"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('name'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    name = data.get('name')
    description = data.get('description', '')
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 插入群组记录
        cursor.execute(
            "INSERT INTO groups (name, creator_id, description, created_at) VALUES (?, ?, ?, ?)",
            (name, g.user_id, description, datetime.now())
        )
        
        group_id = cursor.lastrowid
        
        # 将创建者添加为群管理员
        cursor.execute(
            "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
            (group_id, g.user_id, 'admin', datetime.now())
        )
        
        # 添加系统日志
        cursor.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            ('GROUP', f'创建群组：{name}', g.user_id, datetime.now())
        )
        
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 创建了群组 {name} (ID: {group_id})")
        
        return jsonify({
            'message': '创建成功',
            'success': True,
            'group_id': group_id
        }), 201
    
    except Exception as e:
        conn.rollback()
        logger.error(f"创建群组失败: {str(e)}")
        return jsonify({'message': '创建群组失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取群组成员
@chat_bp.route('/groups/<int:group_id>/members', methods=['GET'], endpoint='get_group_members_endpoint')
@auth_required
def get_group_members(group_id):
    """获取群组成员列表"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 检查用户是否在群组中
        cursor.execute(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id)
        )
        
        if not cursor.fetchone():
            return jsonify({'message': '您不是该群组成员', 'success': False}), 403
        
        # 获取群组成员
        cursor.execute("""
            SELECT 
                u.id, u.username, u.nickname, u.avatar, u.status,
                gm.role, gm.joined_at
            FROM users u
            JOIN group_members gm ON u.id = gm.user_id
            WHERE gm.group_id = ?
            ORDER BY 
                CASE gm.role 
                    WHEN 'admin' THEN 1 
                    ELSE 2 
                END,
                gm.joined_at
        """, (group_id,))
        
        members = []
        for row in cursor.fetchall():
            members.append({
                'id': row['id'],
                'username': row['username'],
                'nickname': row['nickname'],
                'avatar': row['avatar'] or '/src/images/default-avatar.png',
                'status': row['status'],
                'role': row['role'],
                'joined_at': row['joined_at']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'members': members
        }), 200
    
    except Exception as e:
        logger.error(f"获取群组成员失败: {str(e)}")
        return jsonify({'message': '获取群组成员失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：加入群组
@chat_bp.route('/groups/<int:group_id>/join', methods=['POST'], endpoint='join_group_endpoint')
@auth_required
def join_group(group_id):
    """请求加入群组"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查群组是否存在
        cursor.execute("SELECT id FROM groups WHERE id = ?", (group_id,))
        if not cursor.fetchone():
            return jsonify({'message': '群组不存在', 'success': False}), 404
        
        # 检查用户是否已在群组中
        cursor.execute(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id)
        )
        
        if cursor.fetchone():
            return jsonify({'message': '您已经是该群组成员', 'success': False}), 400
        
        # 加入群组
        cursor.execute(
            "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
            (group_id, g.user_id, 'member', datetime.now())
        )
        
        # 添加系统日志
        cursor.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            ('GROUP', f'加入群组 ID: {group_id}', g.user_id, datetime.now())
        )
        
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 加入了群组 {group_id}")
        
        return jsonify({
            'message': '加入成功',
            'success': True
        }), 200
    
    except Exception as e:
        conn.rollback()
        logger.error(f"加入群组失败: {str(e)}")
        return jsonify({'message': '加入群组失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取聊天记录
@chat_bp.route('/messages', methods=['GET'], endpoint='get_messages_endpoint')
@auth_required
def get_messages():
    """获取聊天记录"""
    chat_type = request.args.get('type')
    target_id = request.args.get('target_id')
    limit = int(request.args.get('limit', 50))
    before = request.args.get('before')  # 时间戳，获取此时间之前的消息
    
    if not chat_type or not target_id:
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    if chat_type not in ['user', 'group']:
        return jsonify({'message': '聊天类型错误', 'success': False}), 400
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        messages = []
        
        if chat_type == 'user':
            # 一对一聊天记录
            user_id = int(target_id)
            
            # 检查是否被拉黑
            cursor.execute(
                "SELECT id FROM blacklist WHERE (user_id = ? AND blocked_user_id = ?) OR (user_id = ? AND blocked_user_id = ?)",
                (g.user_id, user_id, user_id, g.user_id)
            )
            
            if cursor.fetchone():
                return jsonify({'message': '无法获取聊天记录', 'success': False}), 403
            
            # 构建查询语句
            query = """
                SELECT 
                    m.id, m.sender_id, m.receiver_id, m.type, m.content, m.created_at,
                    u.username as sender_username, u.nickname as sender_nickname, u.avatar as sender_avatar
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE 
                    ((m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?))
                    AND m.group_id IS NULL
            """
            
            params = [g.user_id, user_id, user_id, g.user_id]
            
            if before:
                query += " AND m.created_at < ?"
                params.append(before)
            
            query += " ORDER BY m.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
        else:  # group
            # 群组聊天记录
            group_id = int(target_id)
            
            # 检查用户是否在群组中
            cursor.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, g.user_id)
            )
            
            if not cursor.fetchone():
                return jsonify({'message': '您不是该群组成员', 'success': False}), 403
            
            # 构建查询语句
            query = """
                SELECT 
                    m.id, m.sender_id, m.group_id, m.type, m.content, m.created_at,
                    u.username as sender_username, u.nickname as sender_nickname, u.avatar as sender_avatar
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.group_id = ?
            """
            
            params = [group_id]
            
            if before:
                query += " AND m.created_at < ?"
                params.append(before)
            
            query += " ORDER BY m.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
        
        # 处理查询结果
        for row in cursor.fetchall():
            message = {
                'id': row['id'],
                'sender_id': row['sender_id'],
                'type': row['type'],
                'content': row['content'],
                'created_at': row['created_at'],
                'sender': {
                    'username': row['sender_username'],
                    'nickname': row['sender_nickname'],
                    'avatar': row['sender_avatar'] or '/src/images/default-avatar.png'
                }
            }
            
            if chat_type == 'user':
                message['receiver_id'] = row['receiver_id']
            else:
                message['group_id'] = row['group_id']
            
            messages.append(message)
        
        # 返回结果，按时间正序排列
        messages.reverse()
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'messages': messages
        }), 200
    
    except Exception as e:
        logger.error(f"获取聊天记录失败: {str(e)}")
        return jsonify({'message': '获取聊天记录失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：发送坤币红包
@chat_bp.route('/kunbi/send', methods=['POST'], endpoint='send_kunbi_endpoint')
@auth_required
def send_kunbi():
    """发送坤币红包"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('amount') or not data.get('target_type') or not data.get('target_id'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    amount = int(data.get('amount'))
    target_type = data.get('target_type')  # 'user' 或 'group'
    target_id = int(data.get('target_id'))
    message = data.get('message', '恭喜发财，大吉大利')
    
    # 验证参数
    if amount <= 0:
        return jsonify({'message': '金额必须大于0', 'success': False}), 400
    
    if target_type not in ['user', 'group']:
        return jsonify({'message': '目标类型错误', 'success': False}), 400
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 检查用户坤币余额
        cursor.execute("SELECT kunbi FROM users WHERE id = ?", (g.user_id,))
        user = cursor.fetchone()
        
        if not user or user['kunbi'] < amount:
            return jsonify({'message': '坤币余额不足', 'success': False}), 400
        
        # 根据目标类型处理
        if target_type == 'user':
            # 检查目标用户是否存在
            cursor.execute("SELECT id FROM users WHERE id = ?", (target_id,))
            if not cursor.fetchone():
                return jsonify({'message': '目标用户不存在', 'success': False}), 404
            
            # 检查是否被拉黑
            cursor.execute(
                "SELECT id FROM blacklist WHERE (user_id = ? AND blocked_user_id = ?) OR (user_id = ? AND blocked_user_id = ?)",
                (g.user_id, target_id, target_id, g.user_id)
            )
            
            if cursor.fetchone():
                return jsonify({'message': '无法发送给该用户', 'success': False}), 403
            
            # 插入坤币交易记录
            cursor.execute(
                "INSERT INTO kunbi_transactions (sender_id, receiver_id, amount, message, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (g.user_id, target_id, amount, message, 'sent', datetime.now())
            )
            
            # 插入消息记录
            cursor.execute(
                "INSERT INTO messages (sender_id, receiver_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (g.user_id, target_id, 'kunbi', message, datetime.now())
            )
            
        else:  # group
            # 检查群组是否存在
            cursor.execute("SELECT id FROM groups WHERE id = ?", (target_id,))
            if not cursor.fetchone():
                return jsonify({'message': '群组不存在', 'success': False}), 404
            
            # 检查用户是否在群组中
            cursor.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (target_id, g.user_id)
            )
            
            if not cursor.fetchone():
                return jsonify({'message': '您不是该群组成员', 'success': False}), 403
            
            # 插入坤币交易记录
            cursor.execute(
                "INSERT INTO kunbi_transactions (sender_id, group_id, amount, message, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (g.user_id, target_id, amount, message, 'sent', datetime.now())
            )
            
            # 插入消息记录
            cursor.execute(
                "INSERT INTO messages (sender_id, group_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (g.user_id, target_id, 'kunbi', message, datetime.now())
            )
        
        # 减少发送者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi - ? WHERE id = ?",
            (amount, g.user_id)
        )
        
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 发送了 {amount} 坤币给 {target_type} {target_id}")
        
        return jsonify({
            'message': '发送成功',
            'success': True
        }), 200
    
    except Exception as e:
        conn.rollback()
        logger.error(f"发送坤币失败: {str(e)}")
        return jsonify({'message': '发送坤币失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：接收坤币红包
@chat_bp.route('/kunbi/receive/<int:transaction_id>', methods=['POST'], endpoint='receive_kunbi_endpoint')
@auth_required
def receive_kunbi(transaction_id):
    """接收坤币红包"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 查询交易记录
        cursor.execute("""
            SELECT * FROM kunbi_transactions 
            WHERE id = ? AND status = 'sent'
        """, (transaction_id,))
        
        transaction = cursor.fetchone()
        
        if not transaction:
            return jsonify({'message': '红包不存在或已被领取', 'success': False}), 404
        
        # 检查是否有权限领取
        if transaction['receiver_id'] is not None:
            # 一对一红包
            if transaction['receiver_id'] != g.user_id:
                return jsonify({'message': '您无权领取该红包', 'success': False}), 403
        else:
            # 群红包
            cursor.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (transaction['group_id'], g.user_id)
            )
            
            if not cursor.fetchone():
                return jsonify({'message': '您不是该群组成员', 'success': False}), 403
            
            # 确保不是自己发的红包
            if transaction['sender_id'] == g.user_id:
                return jsonify({'message': '不能领取自己发送的红包', 'success': False}), 400
        
        # 更新交易状态
        cursor.execute(
            "UPDATE kunbi_transactions SET status = 'received', receiver_id = ? WHERE id = ?",
            (g.user_id, transaction_id)
        )
        
        # 增加接收者坤币
        cursor.execute(
            "UPDATE users SET kunbi = kunbi + ? WHERE id = ?",
            (transaction['amount'], g.user_id)
        )
        
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 领取了交易ID {transaction_id} 的 {transaction['amount']} 坤币")
        
        return jsonify({
            'message': '领取成功',
            'success': True,
            'amount': transaction['amount']
        }), 200
    
    except Exception as e:
        conn.rollback()
        logger.error(f"领取坤币失败: {str(e)}")
        return jsonify({'message': '领取坤币失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：保存聊天历史记录
@chat_bp.route('/history', methods=['POST'], endpoint='save_chat_history_endpoint')
@auth_required
def save_chat_history():
    """保存聊天历史记录到JSON文件"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('chat_id') or not data.get('messages'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    chat_id = data.get('chat_id')
    messages = data.get('messages')
    
    try:
        # 确保聊天数据目录存在
        chat_data_dir = os.path.join(os.getcwd(), 'src', 'chat_data')
        os.makedirs(chat_data_dir, exist_ok=True)
        
        # 文件路径
        file_path = os.path.join(chat_data_dir, f"{chat_id}.json")
        
        # 准备要保存的数据
        chat_data = {
            'chat_id': chat_id,
            'last_updated': datetime.now().isoformat(),
            'messages': messages
        }
        
        # 写入JSON文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"聊天记录已保存: {chat_id}")
        return jsonify({
            'message': '聊天记录保存成功',
            'success': True
        }), 200
    
    except Exception as e:
        logger.error(f"保存聊天记录失败: {str(e)}")
        return jsonify({'message': '保存聊天记录失败', 'success': False}), 500

# 路由：获取聊天历史记录
@chat_bp.route('/history', methods=['GET'], endpoint='get_chat_history_endpoint')
@auth_required
def get_chat_history():
    """获取聊天历史记录"""
    chat_id = request.args.get('chat_id')
    
    if not chat_id:
        return jsonify({'message': '缺少聊天ID', 'success': False}), 400
    
    try:
        # 文件路径
        chat_data_dir = os.path.join(os.getcwd(), 'src', 'chat_data')
        file_path = os.path.join(chat_data_dir, f"{chat_id}.json")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({
                'message': '聊天记录不存在',
                'success': True,
                'messages': []
            }), 200
        
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        logger.info(f"聊天记录已加载: {chat_id}")
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'messages': chat_data.get('messages', [])
        }), 200
    
    except Exception as e:
        logger.error(f"获取聊天记录失败: {str(e)}")
        return jsonify({'message': '获取聊天记录失败', 'success': False}), 500

# 路由：上传JSON文件
@chat_bp.route('/upload/json', methods=['POST'], endpoint='upload_json_endpoint')
@auth_required
def upload_json():
    """上传JSON文件"""
    if 'file' not in request.files:
        return jsonify({'message': '没有文件', 'success': False}), 400
    
    file = request.files['file']
    path = request.form.get('path', '/src/chat_data/')
    
    if not file.filename:
        return jsonify({'message': '没有选择文件', 'success': False}), 400
    
    try:
        # 确保目标目录存在
        full_path = os.path.join(os.getcwd(), path.lstrip('/'))
        os.makedirs(full_path, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(full_path, file.filename)
        file.save(file_path)
        
        logger.info(f"JSON文件已上传: {file_path}")
        
        return jsonify({
            'message': '上传成功',
            'success': True,
            'file_path': file_path
        }), 200
    
    except Exception as e:
        logger.error(f"上传JSON文件失败: {str(e)}")
        return jsonify({'message': '上传失败', 'success': False}), 500 