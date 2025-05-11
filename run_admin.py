#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import yaml
import signal
import logging
import argparse
from pathlib import Path
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import multiprocessing

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 创建参数解析器
parser = argparse.ArgumentParser(description='FUCKCHAT 管理员后台服务')
parser.add_argument('--config', default='config.yaml', help='配置文件路径')
parser.add_argument('--daemon', action='store_true', help='作为守护进程运行')
args = parser.parse_args()

# 加载配置文件
def load_config(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"无法加载配置文件: {e}")
        sys.exit(1)

config = load_config(args.config)

# 设置日志
def setup_logging():
    log_dir = Path(config['logging']['filename']).parent
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, config['logging']['level']),
        format=config['logging']['format'],
        filename=config['logging']['filename'],
        filemode='a'
    )
    
    # 添加控制台处理程序
    if not args.daemon:
        console = logging.StreamHandler()
        console.setLevel(getattr(logging, config['logging']['level']))
        formatter = logging.Formatter(config['logging']['format'])
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

setup_logging()
logger = logging.getLogger('admin_server')

# 创建Flask应用
app = Flask(__name__, 
           template_folder='templates',
           static_folder='templates')

app.secret_key = config['app']['secret_key']
app.config['MAX_CONTENT_LENGTH'] = config['app']['max_content_length']

# 静态文件路由 - CSS文件
@app.route('/css/<path:filename>')
def serve_css(filename):
    return app.send_static_file(f'css/{filename}')

# 静态文件路由 - JS文件
@app.route('/js/<path:filename>')
def serve_js(filename):
    return app.send_static_file(f'js/{filename}')

# 静态文件路由 - 图片文件
@app.route('/src/images/<path:filename>')
def serve_images(filename):
    return app.send_static_file(f'../src/images/{filename}')

# 根路径重定向到管理员登录页面
@app.route('/', methods=['GET'])
def root_redirect():
    logger.info("访问根路径，重定向到管理员登录页面")
    return redirect('/admin')

# 路由：管理员登录页面
@app.route('/admin', methods=['GET'])
def admin_login():
    if 'admin_logged_in' in session and session['admin_logged_in']:
        return redirect('/admin/dashboard')
    return render_template('html/admin/admin_login.html')

# 路由：管理员登录处理
@app.route('/api/admin/login', methods=['POST'])
def admin_login_api():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username == config['admin']['username'] and password == config['admin']['password']:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        logger.info(f"管理员 {username} 登录成功")
        return jsonify({'success': True, 'redirect': '/admin/dashboard'})
    else:
        logger.warning(f"管理员登录失败，用户名: {username}")
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

# 路由：管理员仪表盘
@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    return render_template('html/admin/admin_dashboard.html')

# 路由：管理员退出登录
@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'success': True, 'redirect': '/admin'})

# 路由：管理员退出登录页面
@app.route('/admin/logout', methods=['GET'])
def admin_logout_page():
    session.clear()
    return redirect('/admin')

# 路由：获取系统统计数据
@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    # 简单模拟返回统计数据
    return jsonify({
        'success': True,
        'stats': {
            'user_count': 100,
            'group_count': 10,
            'online_user_count': 15,
            'today_message_count': 500
        }
    })

# 路由：获取所有用户
@app.route('/api/admin/users', methods=['GET'])
def admin_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 模拟用户数据
    users = []
    for i in range(1, 11):
        user_id = (page - 1) * 10 + i
        users.append({
            'id': user_id,
            'username': f'user{user_id}',
            'nickname': f'用户{user_id}',
            'created_at': '2025-05-01T12:00:00Z',
            'last_login_at': '2025-05-10T15:30:00Z',
            'status': 'online' if user_id % 2 == 0 else 'offline',
            'kunbi': user_id * 100,
            'is_admin': user_id == 1
        })
    
    return jsonify({
        'success': True,
        'users': users,
        'pagination': {
            'total': 100,
            'page': page,
            'per_page': per_page,
            'pages': 10
        }
    })

# 路由：获取系统日志
@app.route('/api/admin/logs', methods=['GET'])
def admin_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    
    # 模拟日志数据
    logs = []
    for i in range(1, 6):
        log_id = (page - 1) * 5 + i
        logs.append({
            'id': log_id,
            'type': 'info' if log_id % 3 != 0 else 'error',
            'content': f'系统日志内容 {log_id}',
            'created_at': '2025-05-10T15:30:00Z'
        })
    
    return jsonify({
        'success': True,
        'logs': logs,
        'pagination': {
            'total': 50,
            'page': page,
            'per_page': per_page,
            'pages': 10
        }
    })

# 路由：删除用户
@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    # 模拟删除用户
    logger.info(f"删除用户 ID: {user_id}")
    return jsonify({
        'success': True,
        'message': f'成功删除用户 ID: {user_id}'
    })

# 路由：获取群组
@app.route('/api/admin/groups', methods=['GET'])
def admin_groups():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 模拟群组数据
    groups = []
    for i in range(1, 6):
        group_id = (page - 1) * 5 + i
        groups.append({
            'id': group_id,
            'name': f'群组{group_id}',
            'description': f'这是群组{group_id}的描述',
            'member_count': group_id * 5,
            'created_at': '2025-05-01T12:00:00Z',
            'creator': {
                'id': 1,
                'username': 'admin'
            }
        })
    
    return jsonify({
        'success': True,
        'groups': groups,
        'pagination': {
            'total': 20,
            'page': page,
            'per_page': per_page,
            'pages': 4
        }
    })

# 健康检查路由
@app.route('/admin/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'admin'
    })

# 守护进程类
class Daemon:
    def __init__(self, pid_file):
        self.pid_file = pid_file
        
    def daemonize(self):
        # 创建子进程
        try:
            pid = os.fork()
            if pid > 0:
                # 退出父进程
                sys.exit(0)
        except OSError as e:
            logger.error(f"无法创建子进程: {e}")
            sys.exit(1)
        
        # 分离终端
        os.setsid()
        
        # 创建第二个子进程
        try:
            pid = os.fork()
            if pid > 0:
                # 退出第一个子进程
                sys.exit(0)
        except OSError as e:
            logger.error(f"无法创建第二个子进程: {e}")
            sys.exit(1)
        
        # 改变当前工作目录
        os.chdir('/')
        
        # 设置文件创建掩码
        os.umask(0)
        
        # 关闭所有描述符
        for fd in range(0, 1024):
            try:
                os.close(fd)
            except OSError:
                pass
        
        # 重定向标准输入输出和错误到/dev/null
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        sys.stdin = open(os.devnull, 'r')
        
        # 写入PID文件
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # 设置信号处理
        signal.signal(signal.SIGTERM, self._handle_sigterm)
    
    def _handle_sigterm(self, signum, frame):
        """处理SIGTERM信号，清理PID文件并退出"""
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
        sys.exit(0)
    
    def start(self, func, *args, **kwargs):
        """启动守护进程"""
        self.daemonize()
        func(*args, **kwargs)


# 运行服务器函数
def run_server():
    host = config['admin']['host']
    port = config['admin']['port']
    logger.info(f"启动管理员后台服务 - http://{host}:{port}/admin")
    app.run(host=host, port=port, debug=False, threaded=True)


# 主函数
def main():
    try:
        print(f"FUCKCHAT 管理员后台服务启动中...")
        logger.info("==== FUCKCHAT 管理员后台服务启动 ====")
        
        if args.daemon:
            # 以守护进程模式运行
            print(f"以守护进程模式运行，日志写入: {config['logging']['filename']}")
            pid_file = 'admin_server.pid'
            daemon = Daemon(pid_file)
            daemon.start(run_server)
        else:
            # 以前台模式运行
            run_server()
            
    except KeyboardInterrupt:
        print("\nFUCKCHAT 管理员后台服务已停止")
        logger.info("==== FUCKCHAT 管理员后台服务已停止 ====")
    except Exception as e:
        logger.error(f"服务启动失败: {e}", exc_info=True)
        print(f"服务启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
