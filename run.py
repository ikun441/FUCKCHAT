#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FUCKCHAT - 一个局域网聊天应用
主程序入口
"""

import os
import sys
import yaml
import logging
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fuckchat.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("FUCKCHAT")

# 初始化Flask应用
app = Flask(__name__, static_folder="src", template_folder="templates/html")
CORS(app)  # 启用跨域

# 设置密钥
app.config['SECRET_KEY'] = 'fuckchat_secret_key_very_secure'

# 加载配置
try:
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info("配置文件加载成功")
except Exception as e:
    logger.error(f"加载配置文件失败: {str(e)}")
    config = {
        "server": {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": True
        },
        "database": {
            "type": "sqlite",
            "path": "fuckchat.db"
        }
    }

# 添加一个网站图标路由
@app.route('/favicon.ico')
def favicon():
    favicon_path = config.get('ui', {}).get('favicon', 'src/images/website.ico')
    return send_from_directory(os.path.dirname(favicon_path), os.path.basename(favicon_path), mimetype='image/vnd.microsoft.icon')

# 初始化Socket.IO - 不使用eventlet
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 导入路由
try:
    from route.auth import auth_bp, auth_required
    from route.admin import admin_bp, admin_required
    from route.chat import chat_bp
    from route.kunbi import kunbi_bp

    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(kunbi_bp, url_prefix='/api/kunbi')
except ImportError as e:
    logger.error(f"导入路由模块失败: {str(e)}")
    # 创建临时路由，避免应用崩溃
    @app.route('/api/status')
    def api_status():
        return jsonify({"status": "初始化中，路由模块未加载", "error": str(e)})

# 静态文件路由
@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('templates/js', filename)

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('templates/css', filename)

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('src/images', filename)

# 页面路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/mail')
def mail():
    return render_template('mail.html')

# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    logger.info(f"客户端连接: {request.sid}")
    emit('connect_response', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"客户端断开连接: {request.sid}")
    # 尝试更新用户状态为离线
    if hasattr(request, 'user_id'):
        try:
            conn = sqlite3.connect('fuckchat.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET status = 'offline' WHERE id = ?", (request.user_id,))
            conn.commit()
            
            # 广播用户离线状态
            emit('user_offline', {'user_id': request.user_id}, broadcast=True)
            
            logger.info(f"用户 {request.user_id} 状态已更新为离线")
        except Exception as e:
            logger.error(f"更新用户状态失败: {str(e)}")
        finally:
            if conn:
                conn.close()

@socketio.on('user_status')
def handle_user_status(data):
    """处理用户状态更新"""
    user_id = data.get('user_id')
    status = data.get('status', 'online')
    
    if not user_id:
        return
    
    # 保存用户ID到request对象，方便断开连接时使用
    request.user_id = user_id
    
    try:
        conn = sqlite3.connect('fuckchat.db')
        cursor = conn.cursor()
        
        # 更新用户状态
        cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
        conn.commit()
        
        # 广播用户状态变化
        if status == 'online':
            emit('user_online', {'user_id': user_id}, broadcast=True)
        else:
            emit('user_offline', {'user_id': user_id}, broadcast=True)
        
        logger.info(f"用户 {user_id} 状态已更新为 {status}")
    except Exception as e:
        logger.error(f"更新用户状态失败: {str(e)}")
    finally:
        if conn:
            conn.close()

@socketio.on('request_all_statuses')
def handle_status_request():
    """处理获取所有用户状态的请求"""
    try:
        conn = sqlite3.connect('fuckchat.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取所有用户状态
        cursor.execute("SELECT id, username, nickname, status FROM users WHERE status = 'online'")
        online_users = cursor.fetchall()
        
        # 逐个发送在线用户状态
        for user in online_users:
            emit('user_online', {
                'user_id': user['id'],
                'username': user['username'],
                'nickname': user['nickname'],
                'status': 'online'
            })
        
        logger.info(f"已向客户端 {request.sid} 发送所有用户状态")
    except Exception as e:
        logger.error(f"获取所有用户状态失败: {str(e)}")
    finally:
        if conn:
            conn.close()

# 用户信息更新广播事件
@socketio.on('broadcast_user_update')
def handle_user_update(data):
    """广播用户信息更新"""
    # 验证请求
    if not hasattr(request, 'user_id'):
        return
    
    user_id = request.user_id
    
    # 确保是用户自己的更新
    if str(user_id) != str(data.get('user_id')):
        return
    
    # 广播用户更新
    emit('user_update', data, broadcast=True)
    logger.info(f"广播用户 {user_id} 信息更新")

@socketio.on('join')
def handle_join(data):
    """处理用户加入聊天室"""
    room = data.get('room')
    if room:
        join_room(room)
        logger.info(f"用户 {request.sid} 加入房间 {room}")
        emit('status', {'msg': f'用户加入房间 {room}'}, room=room)

@socketio.on('leave')
def handle_leave(data):
    """处理用户离开聊天室"""
    room = data.get('room')
    if room:
        leave_room(room)
        logger.info(f"用户 {request.sid} 离开房间 {room}")
        emit('status', {'msg': f'用户离开房间 {room}'}, room=room)

@socketio.on('message')
def handle_message(data):
    """处理聊天消息"""
    room = data.get('room')
    message = data.get('message')
    sender = data.get('sender')
    message_type = data.get('type', 'text')
    timestamp = datetime.now().isoformat()
    
    if room and message:
        logger.info(f"消息: {sender} -> {room}: {message}")
        emit('message', {
            'sender': sender,
            'message': message,
            'type': message_type,
            'timestamp': timestamp
        }, room=room)

@socketio.on('private_message')
def handle_private_message(data):
    """处理私聊消息，确保双向通信"""
    sender_id = data.get('sender')
    receiver_id = data.get('receiver')
    message = data.get('message')
    chat_id = data.get('chat_id')
    message_type = data.get('type', 'text')
    timestamp = data.get('timestamp', datetime.now().isoformat())
    
    if not sender_id or not receiver_id or not message:
        return
    
    try:
        # 生成消息ID
        message_id = data.get('id', int(datetime.now().timestamp() * 1000))
        
        # 构建完整消息对象
        message_obj = {
            'id': message_id,
            'sender': sender_id,
            'sender_id': sender_id,
            'receiver': receiver_id,
            'receiver_id': receiver_id,
            'content': message,
            'type': message_type,
            'timestamp': timestamp,
            'created_at': timestamp
        }
        
        # 发送到接收者的私人频道
        emit('new_message', message_obj, room=f"user_{receiver_id}")
        
        # 同时发送到发送者的私人频道(解决某些客户端无法接收自己发送的消息的问题)
        emit('new_message', message_obj, room=f"user_{sender_id}")
        
        logger.info(f"私聊消息: {sender_id} -> {receiver_id}: {message}")
        
        # 保存消息到数据库
        try:
            conn = sqlite3.connect('fuckchat.db')
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO messages (sender_id, receiver_id, type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (sender_id, receiver_id, message_type, message, timestamp)
            )
            
            conn.commit()
            logger.info(f"私聊消息已保存到数据库")
        except Exception as e:
            logger.error(f"保存消息到数据库失败: {str(e)}")
        finally:
            if conn:
                conn.close()
        
    except Exception as e:
        logger.error(f"处理私聊消息失败: {str(e)}")

# 主程序入口
if __name__ == '__main__':
    host = config['server'].get('host', '0.0.0.0')
    port = config['server'].get('port', 5000)
    debug = config['server'].get('debug', True)
    
    logger.info(f"启动FUCKCHAT服务，监听地址: {host}:{port}")
    try:
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"启动服务失败: {str(e)}")
        logger.info("尝试使用普通Flask服务器启动...")
        app.run(host=host, port=port, debug=debug)
