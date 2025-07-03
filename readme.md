# FUCKCHAT - 局域网聊天应用

FUCKCHAT 是一个基于 Python 和 Web 技术开发的局域网聊天应用，支持私聊、群聊、表情、图片、语音消息以及坤币红包等功能。

## 最新更新

- ✨ **增强动画效果**：消息发送、接收，页面切换等均添加平滑动画
- 🧧 **坤币红包系统**：全新设计的红包发送与领取动画效果
- 🔌 **局域网配置**：添加局域网连接和广播配置
- 🙏 **贡献者鸣谢**：关于页面新增贡献团队展示
- 🏆 **界面优化**：聊天界面交互体验全面提升

## 功能特点

- 🔒 **局域网安全通信**：数据仅在局域网内传输，保障通信安全性
- 👤 **用户管理**：支持注册、登录、管理个人信息
- 💬 **实时聊天**：支持一对一私聊和多人群聊
- 🌈 **多媒体消息**：支持发送文本、表情、图片、语音等消息类型
- 🧧 **坤币红包**：内置虚拟货币系统，可发送红包增加互动乐趣
- 📱 **响应式设计**：适配电脑和手机等不同尺寸的设备
- 👮 **管理员后台**：提供系统管理、用户管理、聊天管理等功能
- ✨ **动画效果**：丰富的界面动画，提升用户体验

## 技术栈

- **前端**：HTML, CSS, JavaScript, 动画效果
- **后端**：Python, Flask, Flask-SocketIO
- **数据库**：SQLite
- **通信**：WebSocket, HTTP/HTTPS

## 快速开始

### 环境要求

- Python 3.8+
- 网络浏览器（推荐 Chrome, Firefox, Edge 等现代浏览器）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 初始化数据库

```bash
python scripts/init_db.py
python scripts/update_db.py
```

### 启动服务

```bash
# 启动主服务
python run.py

# 启动管理员后台服务
python run_admin.py  # 前台模式
python run_admin.py --daemon  # 后台守护进程模式

# 在Windows系统下，也可以使用批处理文件启动管理员后台
start_admin.bat
```

服务默认在 `http://localhost:5000` 启动，管理员后台在 `http://127.0.0.1:5004/admin` 启动，可通过配置文件修改主机和端口。

### 测试用户

- 管理员：username: `admin`, password: `admin123`（后台管理员账号在confg.yaml中设置）
- 普通用户：username: `user`, password: `user123`

## 新增功能详解

### 坤币红包系统

FUCKCHAT 内置了虚拟货币"坤币"系统，用户可以:

1. 在聊天窗口发送坤币红包
2. 点击红包即可领取并获得奖励
3. 享受精美的发送和领取动画效果

### 动画效果

- 消息动画：发送和接收消息时的平滑过渡
- 页面切换：标签页切换的流畅动效
- 互动动画：点击、悬停等操作的反馈动效
- 模态框动画：弹窗的显示和隐藏动画

### 局域网配置

通过 `config.yaml` 文件可以配置:

```yaml
server:
  local_network:
    enabled: true  # 是否启用局域网访问
    domain: fuckchat.local  # 局域网域名（如有）
    broadcast: true  # 是否在局域网内广播服务
```

## 目录结构

```
FUCKCHAT/
├── config.yaml         # 配置文件
├── fuckchat.db         # SQLite数据库
├── fuckchat.log        # 日志文件
├── md/                 # 文档目录
├── readme.md           # 项目说明
├── requirements.txt    # 依赖列表
├── route/              # 路由目录
│   ├── admin.py        # 管理员接口
│   ├── auth.py         # 认证接口
│   └── chat.py         # 聊天接口
├── run.py              # 主程序入口
├── run_admin.py        # 管理员后台服务入口
├── start_admin.bat     # Windows环境管理员后台启动脚本
├── scripts/            # 脚本目录
│   └── init_db.py      # 数据库初始化脚本
│   └── update_db.py    # 数据库更新脚本
├── src/                # 静态资源
│   └── images/         # 图片资源
└── templates/          # 前端模板
    ├── css/            # CSS样式
    ├── html/           # HTML页面
    └── js/             # JavaScript脚本
```

## 贡献团队

项目由以下成员开发:

- ChatGPT - 架构设计师
- Claude - 全栈工程师
- Cursor - 前端开发
- ikun441 - 技术顾问

## 接口说明

### 认证接口

- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/verify` - 验证令牌
- `GET /api/auth/profile` - 获取用户信息
- `POST /api/auth/admin/login` - 管理员登录

### 聊天接口

- `GET /api/chat/users` - 获取在线用户列表
- `GET /api/chat/groups` - 获取群组列表
- `POST /api/chat/groups` - 创建群组
- `GET /api/chat/messages` - 获取消息历史
- `POST /api/chat/kunbi/send` - 发送坤币红包

### 管理接口

- `GET /api/admin/users` - 获取所有用户
- `GET /api/admin/stats` - 获取统计信息
- `POST /api/admin/notification` - 发送系统通知

## WebSocket 事件

- `connect` - 客户端连接
- `disconnect` - 客户端断开连接
- `join` - 加入聊天室
- `leave` - 离开聊天室
- `message` - 聊天消息
- `kunbi` - 坤币相关事件
- `status` - 状态变更

## 贡献指南

欢迎贡献代码、提交问题和改进建议！

## 许可证

MIT License

## 版本历史

详细的版本更新历史请查看 [version.md](md/version.md) 文件。

## API文档

完整的API接口文档请查看 [api.md](md/api.md) 文件。

## 使用指南

详细的使用说明请查看 [usage.md](md/usage.md) 文件,或者访问[我的博客](https://ilovefirefly.club/xiangmu/fuckchat/)获取更多支持。
