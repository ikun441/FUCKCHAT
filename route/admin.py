#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 管理员相关路由
处理管理员功能，包括用户管理、群组管理、系统通知等
"""

# 如果直接运行此文件，添加项目根目录到系统路径
if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import sqlite3
import jwt
from functools import wraps
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, g
from route.auth import auth_required

# 创建日志记录器
logger = logging.getLogger("FUCKCHAT.admin")

# 创建蓝图
admin_bp = Blueprint('admin', __name__)

# 管理员权限验证中间件
def admin_required(f):
    """验证请求是否来自管理员"""
    @wraps(f)  # 添加wraps装饰器来保留原始函数的属性
    def decorated(*args, **kwargs):
        token = None
        
        # 从请求头获取token
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(' ')[1]
        
        if not token:
            return jsonify({'message': '缺少认证令牌', 'success': False}), 401
        
        try:
            # 解码JWT令牌
            data = jwt.decode(token, current_app.config.get('SECRET_KEY', 'fuckchat_secret'), algorithms=['HS256'])
            g.user_id = data['user_id']
            
            # 检查是否为管理员
            if not data.get('is_admin'):
                return jsonify({'message': '没有管理员权限', 'success': False}), 403
                
        except:
            return jsonify({'message': '无效的认证令牌', 'success': False}), 401
            
        return f(*args, **kwargs)
    
    # 修改装饰器函数名称，避免冲突
    decorated.__name__ = f"{f.__name__}_admin_required"
    return decorated

# 路由：获取统计信息
@admin_bp.route('/stats', methods=['GET'], endpoint='get_stats_endpoint')
@admin_required
def get_stats():
    """获取系统统计信息"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 获取用户数
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        # 获取在线用户数
        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'online'")
        online_user_count = cursor.fetchone()[0]
        
        # 获取群组数
        cursor.execute("SELECT COUNT(*) FROM groups")
        group_count = cursor.fetchone()[0]
        
        # 获取今日消息数
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE date(created_at) = date('now', 'localtime')
        """)
        today_message_count = cursor.fetchone()[0]
        
        # 获取坤币交易数
        cursor.execute("SELECT COUNT(*) FROM kunbi_transactions")
        kunbi_transaction_count = cursor.fetchone()[0]
        
        # 获取坤币总量
        cursor.execute("SELECT SUM(kunbi) FROM users")
        total_kunbi = cursor.fetchone()[0] or 0
        
        stats = {
            'user_count': user_count,
            'online_user_count': online_user_count,
            'group_count': group_count,
            'today_message_count': today_message_count,
            'kunbi_transaction_count': kunbi_transaction_count,
            'total_kunbi': total_kunbi
        }
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'stats': stats
        }), 200
    
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return jsonify({'message': '获取统计信息失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取所有用户
@admin_bp.route('/users', methods=['GET'], endpoint='get_all_users_endpoint')
@admin_required
def get_all_users():
    """获取所有用户列表"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        # 计算分页
        offset = (page - 1) * per_page
        
        # 构建查询
        query = """
            SELECT id, username, nickname, avatar, kunbi, is_admin, 
                   status, created_at, last_login_at
            FROM users
        """
        
        params = []
        if search:
            query += " WHERE username LIKE ? OR nickname LIKE ?"
            params.extend([f'%{search}%', f'%{search}%'])
        
        # 计算总数
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # 添加分页
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        # 执行查询
        cursor.execute(query, params)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row['id'],
                'username': row['username'],
                'nickname': row['nickname'],
                'avatar': row['avatar'] or '/src/images/default-avatar.png',
                'kunbi': row['kunbi'],
                'is_admin': bool(row['is_admin']),
                'status': row['status'],
                'created_at': row['created_at'],
                'last_login_at': row['last_login_at']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'users': users,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        logger.error(f"获取用户列表失败: {str(e)}")
        return jsonify({'message': '获取用户列表失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：更新用户信息
@admin_bp.route('/users/<int:user_id>', methods=['PUT'], endpoint='update_user_endpoint')
@admin_required
def update_user(user_id):
    """更新用户信息"""
    data = request.get_json()
    
    if not data:
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    # 提取可更新的字段
    nickname = data.get('nickname')
    kunbi = data.get('kunbi')
    is_admin = data.get('is_admin')
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查用户是否存在
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        # 构建更新语句
        update_fields = []
        params = []
        
        if nickname is not None:
            update_fields.append("nickname = ?")
            params.append(nickname)
        
        if kunbi is not None:
            update_fields.append("kunbi = ?")
            params.append(kunbi)
        
        if is_admin is not None:
            update_fields.append("is_admin = ?")
            params.append(1 if is_admin else 0)
        
        if not update_fields:
            return jsonify({'message': '没有提供可更新的字段', 'success': False}), 400
        
        # 构建并执行SQL
        sql = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        params.append(user_id)
        
        cursor.execute(sql, params)
        conn.commit()
        
        logger.info(f"管理员更新了用户 {user_id} 的信息")
        
        return jsonify({
            'message': '更新成功',
            'success': True
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"更新用户信息失败: {str(e)}")
        return jsonify({'message': '更新用户信息失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：删除用户
@admin_bp.route('/users/<int:user_id>', methods=['DELETE'], endpoint='delete_user_endpoint')
@admin_required
def delete_user(user_id):
    """删除用户"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查是否为管理员账户
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        # 防止删除管理员账户
        if result[0] == 1:
            return jsonify({'message': '无法删除管理员账户', 'success': False}), 403
        
        # 删除关联数据
        cursor.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        cursor.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM kunbi_transactions WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        cursor.execute("DELETE FROM blacklist WHERE user_id = ? OR blocked_user_id = ?", (user_id, user_id))
        
        # 删除用户
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        # 记录系统日志
        cursor.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            ('USER', f'管理员删除了用户 ID:{user_id}', g.user_id, datetime.now())
        )
        
        conn.commit()
        
        logger.info(f"管理员删除了用户 {user_id}")
        
        return jsonify({
            'message': '删除成功',
            'success': True
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"删除用户失败: {str(e)}")
        return jsonify({'message': '删除用户失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取所有群组
@admin_bp.route('/groups', methods=['GET'], endpoint='get_all_groups_endpoint')
@admin_required
def get_all_groups():
    """获取所有群组列表"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 计算分页
        offset = (page - 1) * per_page
        
        # 计算总数
        cursor.execute("SELECT COUNT(*) FROM groups")
        total = cursor.fetchone()[0]
        
        # 查询群组
        cursor.execute("""
            SELECT 
                g.id, g.name, g.avatar, g.description, g.created_at, 
                u.username as creator_username, u.nickname as creator_nickname,
                COUNT(DISTINCT gm.user_id) as member_count
            FROM groups g
            LEFT JOIN users u ON g.creator_id = u.id
            LEFT JOIN group_members gm ON g.id = gm.group_id
            GROUP BY g.id
            ORDER BY g.created_at DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        groups = []
        for row in cursor.fetchall():
            groups.append({
                'id': row['id'],
                'name': row['name'],
                'avatar': row['avatar'] or '/src/images/group-avatar.png',
                'description': row['description'],
                'creator': {
                    'username': row['creator_username'],
                    'nickname': row['creator_nickname']
                },
                'member_count': row['member_count'],
                'created_at': row['created_at']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'groups': groups,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        logger.error(f"获取群组列表失败: {str(e)}")
        return jsonify({'message': '获取群组列表失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：删除群组
@admin_bp.route('/groups/<int:group_id>', methods=['DELETE'], endpoint='delete_group_endpoint')
@admin_required
def delete_group(group_id):
    """删除群组"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查群组是否存在
        cursor.execute("SELECT name FROM groups WHERE id = ?", (group_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'message': '群组不存在', 'success': False}), 404
        
        group_name = result[0]
        
        # 删除关联数据
        cursor.execute("DELETE FROM messages WHERE group_id = ?", (group_id,))
        cursor.execute("DELETE FROM kunbi_transactions WHERE group_id = ?", (group_id,))
        cursor.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        
        # 删除群组
        cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        
        # 记录系统日志
        cursor.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            ('GROUP', f'管理员删除了群组 {group_name}', g.user_id, datetime.now())
        )
        
        conn.commit()
        
        logger.info(f"管理员删除了群组 {group_id}")
        
        return jsonify({
            'message': '删除成功',
            'success': True
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"删除群组失败: {str(e)}")
        return jsonify({'message': '删除群组失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：发送系统通知
@admin_bp.route('/notification', methods=['POST'], endpoint='send_notification_endpoint')
@admin_required
def send_notification():
    """发送系统通知"""
    data = request.get_json()
    
    if not data or not data.get('content'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    content = data.get('content')
    target_type = data.get('target_type', 'all')  # 'all', 'user', 'group'
    target_id = data.get('target_id')
    
    # 检查目标类型和ID
    if target_type in ['user', 'group'] and not target_id:
        return jsonify({'message': '缺少目标ID', 'success': False}), 400
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 插入系统日志
        cursor.execute(
            "INSERT INTO system_logs (type, content, user_id, created_at) VALUES (?, ?, ?, ?)",
            ('NOTIFICATION', f'发送系统通知: {content}', g.user_id, datetime.now())
        )
        
        # 根据不同目标类型处理
        if target_type == 'all':
            # 全体通知，不需要额外处理
            notification_id = cursor.lastrowid
        elif target_type == 'user':
            # 检查用户是否存在
            cursor.execute("SELECT id FROM users WHERE id = ?", (target_id,))
            if not cursor.fetchone():
                return jsonify({'message': '用户不存在', 'success': False}), 404
                
            # TODO: 实现用户通知逻辑
        elif target_type == 'group':
            # 检查群组是否存在
            cursor.execute("SELECT id FROM groups WHERE id = ?", (target_id,))
            if not cursor.fetchone():
                return jsonify({'message': '群组不存在', 'success': False}), 404
                
            # TODO: 实现群组通知逻辑
        
        conn.commit()
        
        # 在实际项目中，这里需要使用WebSocket将通知推送给客户端
        # 为简化，这里只返回成功状态
        
        logger.info(f"管理员发送了系统通知: {content}")
        
        return jsonify({
            'message': '发送成功',
            'success': True
        }), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"发送系统通知失败: {str(e)}")
        return jsonify({'message': '发送系统通知失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取系统日志
@admin_bp.route('/logs', methods=['GET'], endpoint='get_system_logs_endpoint')
@admin_required
def get_system_logs():
    """获取系统日志"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        log_type = request.args.get('type')
        
        # 计算分页
        offset = (page - 1) * per_page
        
        # 构建查询
        query = """
            SELECT 
                l.id, l.type, l.content, l.created_at,
                u.username, u.nickname
            FROM system_logs l
            LEFT JOIN users u ON l.user_id = u.id
        """
        
        params = []
        if log_type:
            query += " WHERE l.type = ?"
            params.append(log_type)
        
        # 计算总数
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # 添加排序和分页
        query += " ORDER BY l.created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        # 执行查询
        cursor.execute(query, params)
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'id': row['id'],
                'type': row['type'],
                'content': row['content'],
                'user': {
                    'username': row['username'],
                    'nickname': row['nickname']
                } if row['username'] else None,
                'created_at': row['created_at']
            })
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'logs': logs,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        logger.error(f"获取系统日志失败: {str(e)}")
        return jsonify({'message': '获取系统日志失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close() 