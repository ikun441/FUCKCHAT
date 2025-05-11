#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 认证相关路由
处理用户注册、登录、注销等功能
"""

import os
import logging
import jwt
import bcrypt
import sqlite3
from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, g

# 创建日志记录器
logger = logging.getLogger("FUCKCHAT.auth")

# 创建蓝图
auth_bp = Blueprint('auth', __name__)

# 认证中间件
def auth_required(f):
    """验证请求中的JWT令牌"""
    @wraps(f)  # 保留原始函数的属性
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
        except:
            return jsonify({'message': '无效的认证令牌', 'success': False}), 401
            
        return f(*args, **kwargs)
    
    return decorated

# 路由：用户注册
@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('username') or not data.get('password') or not data.get('nickname'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    username = data.get('username')
    password = data.get('password')
    nickname = data.get('nickname')
    
    # 连接数据库
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return jsonify({'message': '用户名已存在', 'success': False}), 400
        
        # 哈希处理密码
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # 插入新用户
        cursor.execute(
            "INSERT INTO users (username, password_hash, nickname, kunbi, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, nickname, 100, datetime.now())
        )
        conn.commit()
        
        logger.info(f"新用户注册成功: {username}")
        return jsonify({'message': '注册成功', 'success': True}), 201
    
    except Exception as e:
        logger.error(f"用户注册失败: {str(e)}")
        return jsonify({'message': '注册失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：用户登录
@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    # 连接数据库
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row  # 返回字典格式
        cursor = conn.cursor()
        
        # 查询用户
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户名或密码错误', 'success': False}), 401
        
        # 验证密码
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            return jsonify({'message': '用户名或密码错误', 'success': False}), 401
        
        # 生成JWT令牌
        token = jwt.encode(
            {
                'user_id': user['id'],
                'username': user['username'],
                'is_admin': user['is_admin'],
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            current_app.config.get('SECRET_KEY', 'fuckchat_secret'),
            algorithm='HS256'
        )
        
        # 更新最后登录时间和用户状态为在线
        cursor.execute("UPDATE users SET last_login_at = ?, status = 'online' WHERE id = ?",
                      (datetime.now(), user['id']))
        conn.commit()
        
        # 返回用户信息和令牌
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'nickname': user['nickname'],
            'kunbi': user['kunbi'],
            'isAdmin': bool(user['is_admin']),
            'avatar': user['avatar'] or '/src/images/default-avatar.png',
            'status': 'online'
        }
        
        logger.info(f"用户登录成功: {username}")
        return jsonify({
            'message': '登录成功',
            'success': True,
            'token': token,
            'user': user_data
        }), 200
    
    except Exception as e:
        logger.error(f"用户登录失败: {str(e)}")
        return jsonify({'message': '登录失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：验证令牌
@auth_bp.route('/verify', methods=['GET'], endpoint='verify_token_endpoint')
@auth_required
def verify_token():
    """验证用户令牌"""
    return jsonify({'message': '令牌有效', 'success': True, 'user_id': g.user_id}), 200

# 路由：获取用户信息
@auth_bp.route('/profile', methods=['GET'], endpoint='get_profile_endpoint')
@auth_required
def get_profile():
    """获取当前用户信息"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE id = ?", (g.user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'nickname': user['nickname'],
            'kunbi': user['kunbi'],
            'isAdmin': bool(user['is_admin']),
            'avatar': user['avatar'] or '/src/images/default-avatar.png',
            'created_at': user['created_at'],
            'last_login_at': user['last_login_at']
        }
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'user': user_data
        }), 200
    
    except Exception as e:
        logger.error(f"获取用户信息失败: {str(e)}")
        return jsonify({'message': '获取用户信息失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：获取指定用户信息（公开信息）
@auth_bp.route('/user/<int:user_id>', methods=['GET'], endpoint='get_user_profile_endpoint')
@auth_required
def get_user_profile(user_id):
    """获取指定用户的公开信息"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 检查被查看用户是否存在
        cursor.execute("""
            SELECT id, username, nickname, avatar, status, kunbi, gender, 
                   signature, created_at, is_admin
            FROM users 
            WHERE id = ?
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        # 检查是否被拉黑
        cursor.execute(
            "SELECT id FROM blacklist WHERE (user_id = ? AND blocked_user_id = ?) OR (user_id = ? AND blocked_user_id = ?)",
            (g.user_id, user_id, user_id, g.user_id)
        )
        
        is_blocked = cursor.fetchone() is not None
        
        # 组装用户数据（不包含敏感信息）
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'nickname': user['nickname'],
            'avatar': user['avatar'] or '/src/images/default-avatar.png',
            'status': user['status'],
            'kunbi': user['kunbi'],
            'gender': user['gender'] or '未设置',
            'signature': user['signature'] or '这个人很懒，什么都没留下',
            'created_at': user['created_at'],
            'is_admin': bool(user['is_admin']),
            'is_blocked': is_blocked
        }
        
        # 查询是否为好友（如果有好友系统）
        cursor.execute(
            "SELECT id FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
            (g.user_id, user_id, user_id, g.user_id)
        )
        
        user_data['is_friend'] = cursor.fetchone() is not None
        
        return jsonify({
            'message': '获取成功',
            'success': True,
            'user': user_data
        }), 200
    
    except Exception as e:
        logger.error(f"获取用户信息失败: {str(e)}")
        return jsonify({'message': '获取用户信息失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：管理员登录
@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """管理员登录"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    # 连接数据库
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 查询用户并检查是否为管理员
        cursor.execute("SELECT * FROM users WHERE username = ? AND is_admin = 1", (username,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户名或密码错误，或没有管理权限', 'success': False}), 401
        
        # 验证密码
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            return jsonify({'message': '用户名或密码错误', 'success': False}), 401
        
        # 生成JWT令牌，添加管理员标识
        token = jwt.encode(
            {
                'user_id': user['id'],
                'username': user['username'],
                'is_admin': True,
                'exp': datetime.utcnow() + timedelta(hours=12)  # 管理员令牌有效期较短
            },
            current_app.config.get('SECRET_KEY', 'fuckchat_secret'),
            algorithm='HS256'
        )
        
        # 更新最后登录时间
        cursor.execute("UPDATE users SET last_login_at = ? WHERE id = ?",
                      (datetime.now(), user['id']))
        conn.commit()
        
        # 记录管理员登录
        logger.info(f"管理员登录成功: {username}")
        
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'nickname': user['nickname'],
            'isAdmin': True,
            'avatar': user['avatar'] or '/src/images/admin-avatar.png'
        }
        
        return jsonify({
            'message': '管理员登录成功',
            'success': True,
            'token': token,
            'user': user_data
        }), 200
    
    except Exception as e:
        logger.error(f"管理员登录失败: {str(e)}")
        return jsonify({'message': '登录失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：检查用户名是否可用
@auth_bp.route('/check-username', methods=['GET'], endpoint='check_username_endpoint')
def check_username():
    """检查用户名是否可用"""
    username = request.args.get('username')
    
    if not username:
        return jsonify({'message': '缺少用户名参数', 'available': False}), 400
    
    # 连接数据库
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        return jsonify({
            'available': user is None,
            'message': '用户名可用' if user is None else '用户名已被使用'
        }), 200
    
    except Exception as e:
        logger.error(f"检查用户名失败: {str(e)}")
        return jsonify({'message': '检查失败', 'available': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：用户注销
@auth_bp.route('/logout', methods=['POST'], endpoint='logout_endpoint')
@auth_required
def logout():
    """用户注销登录"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 将用户状态设置为离线
        cursor.execute("UPDATE users SET status = 'offline' WHERE id = ?", (g.user_id,))
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 已注销登录")
        return jsonify({'message': '注销成功', 'success': True}), 200
    
    except Exception as e:
        logger.error(f"用户注销失败: {str(e)}")
        return jsonify({'message': '注销失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：更新用户个人资料
@auth_bp.route('/profile', methods=['POST'], endpoint='update_profile_endpoint')
@auth_required
def update_profile():
    """更新用户个人资料"""
    data = request.get_json()
    
    # 检查是否有数据
    if not data:
        return jsonify({'message': '缺少更新数据', 'success': False}), 400
    
    # 可以更新的字段
    allowed_fields = ['nickname', 'gender', 'signature', 'location', 'birthday', 'email', 'phone']
    update_data = {}
    
    # 筛选有效字段
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    if not update_data:
        return jsonify({'message': '没有有效的更新字段', 'success': False}), 400
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 构建UPDATE语句
        fields = ", ".join([f"{key} = ?" for key in update_data.keys()])
        values = list(update_data.values())
        values.append(g.user_id)  # 为WHERE条件添加用户ID
        
        # 执行更新
        cursor.execute(f"UPDATE users SET {fields} WHERE id = ?", values)
        conn.commit()
        
        # 发送用户更新通知（如果有WebSocket连接）
        try:
            from run import socketio
            
            # 将更新后的用户信息广播给所有客户端
            socketio.emit('user_update', {
                'user_id': g.user_id,
                **update_data
            }, broadcast=True)
        except ImportError:
            logger.warning("无法导入socketio，跳过广播用户更新")
        
        logger.info(f"用户 {g.user_id} 更新了个人资料")
        return jsonify({'message': '个人资料更新成功', 'success': True}), 200
    
    except Exception as e:
        logger.error(f"更新用户资料失败: {str(e)}")
        return jsonify({'message': '更新失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：注销账号（删除账号）
@auth_bp.route('/account/delete', methods=['POST'], endpoint='delete_account_endpoint')
@auth_required
def delete_account():
    """注销（删除）用户账号"""
    data = request.get_json()
    
    # 需要密码确认才能删除账号
    if not data or not data.get('password'):
        return jsonify({'message': '需要提供密码确认', 'success': False}), 400
    
    password = data.get('password')
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取用户信息
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (g.user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        # 验证密码
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            return jsonify({'message': '密码不正确', 'success': False}), 401
        
        # 处理用户相关数据（根据实际需求可保留或删除）
        # 1. 将用户消息标记为已删除用户
        cursor.execute("UPDATE messages SET sender_deleted = 1 WHERE sender_id = ?", (g.user_id,))
        
        # 2. 从好友列表中移除
        cursor.execute("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (g.user_id, g.user_id))
        
        # 3. 从群组成员中移除
        cursor.execute("DELETE FROM group_members WHERE user_id = ?", (g.user_id,))
        
        # 4. 将用户标记为已删除（也可以物理删除）
        cursor.execute("UPDATE users SET is_deleted = 1, status = 'deleted', deleted_at = ? WHERE id = ?", 
                       (datetime.now(), g.user_id))
        
        # 提交更改
        conn.commit()
        
        # 发送用户删除通知
        try:
            from run import socketio
            socketio.emit('user_deleted', {'user_id': g.user_id}, broadcast=True)
        except ImportError:
            logger.warning("无法导入socketio，跳过广播用户删除通知")
        
        logger.info(f"用户 {g.user_id} 账号已注销")
        return jsonify({'message': '账号已成功注销', 'success': True}), 200
    
    except Exception as e:
        logger.error(f"注销账号失败: {str(e)}")
        return jsonify({'message': '注销账号失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close()

# 路由：更新用户密码
@auth_bp.route('/password', methods=['POST'], endpoint='update_password_endpoint')
@auth_required
def update_password():
    """更新用户密码"""
    data = request.get_json()
    
    # 检查必要字段
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'message': '缺少必要参数', 'success': False}), 400
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    # 验证新密码长度
    if len(new_password) < 6:
        return jsonify({'message': '新密码长度至少为6个字符', 'success': False}), 400
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取用户信息
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (g.user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'message': '用户不存在', 'success': False}), 404
        
        # 验证当前密码
        if not bcrypt.checkpw(current_password.encode('utf-8'), user['password_hash']):
            return jsonify({'message': '当前密码不正确', 'success': False}), 401
        
        # 生成新密码哈希
        new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # 更新密码
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, g.user_id))
        conn.commit()
        
        logger.info(f"用户 {g.user_id} 已更新密码")
        return jsonify({'message': '密码已成功更新', 'success': True}), 200
    
    except Exception as e:
        logger.error(f"更新密码失败: {str(e)}")
        return jsonify({'message': '更新密码失败', 'success': False}), 500
    
    finally:
        if conn:
            conn.close() 