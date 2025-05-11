# FUCKCHAT 工具和函数参考

本文档记录了 FUCKCHAT 项目中的主要函数、类和工具，方便查找和修复 BUG。

## 前端模块

### 公共工具函数 (common.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `isLoggedIn()` | templates/js/common.js | 检查用户是否已登录 |
| `getCurrentUser()` | templates/js/common.js | 获取当前登录用户信息 |
| `showToast(message, type, duration)` | templates/js/common.js | 显示提示消息 |
| `formatDateTime(date)` | templates/js/common.js | 格式化日期时间 |
| `formatDate(date)` | templates/js/common.js | 格式化日期 |
| `formatTime(date)` | templates/js/common.js | 格式化时间 |
| `navigateTo(page)` | templates/js/common.js | 页面导航 |
| `logout()` | templates/js/common.js | 用户注销 |
| `validateUsername(username)` | templates/js/common.js | 验证用户名 |
| `validatePassword(password)` | templates/js/common.js | 验证密码 |
| `isMobileDevice()` | templates/js/common.js | 检测是否为移动设备 |
| `isAdmin()` | templates/js/common.js | 检查用户是否为管理员 |
| `updateNavigation()` | templates/js/common.js | 根据登录状态更新导航 |

### 登录模块 (login.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `handleLogin(event)` | templates/js/login.js | 处理登录表单提交 |
| `mockLoginAPI(username, password)` | templates/js/login.js | 模拟登录 API (仅开发测试用) |

### 注册模块 (register.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `handleRegister(event)` | templates/js/register.js | 处理注册表单提交 |
| `mockRegisterAPI(username, nickname, password)` | templates/js/register.js | 模拟注册 API (仅开发测试用) |

### 聊天模块 (chat.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `initUserInfo()` | templates/js/chat.js | 初始化用户信息 |
| `initSocketConnection()` | templates/js/chat.js | 初始化WebSocket连接 |
| `initOnlineUsers()` | templates/js/chat.js | 初始化在线用户列表 |
| `initGroups()` | templates/js/chat.js | 初始化群组列表 |
| `initEventListeners()` | templates/js/chat.js | 初始化事件监听 |
| `openChatWithUser(userId)` | templates/js/chat.js | 打开与用户的聊天 |
| `openChatWithGroup(groupId)` | templates/js/chat.js | 打开与群组的聊天 |
| `loadMessages()` | templates/js/chat.js | 加载聊天消息 |
| `loadChatHistory(chatType, userId, targetId)` | templates/js/chat.js | 加载聊天历史记录 |
| `loadChatHistoryFromFile(chatId)` | templates/js/chat.js | 从JSON文件加载聊天记录 |
| `saveChatHistory(chatId, messageList)` | templates/js/chat.js | 保存聊天记录 |
| `saveChatHistoryToFile(chatId, messageList)` | templates/js/chat.js | 保存聊天记录到JSON文件 |
| `createMessageElement(message)` | templates/js/chat.js | 创建消息元素 |
| `sendMessage()` | templates/js/chat.js | 发送消息 |
| `sendMessageAPI(message, chatId)` | templates/js/chat.js | 通过API发送消息 |
| `toggleEmojiPicker()` | templates/js/chat.js | 切换表情选择器显示 |
| `insertEmoji(emoji)` | templates/js/chat.js | 插入表情到输入框 |
| `toggleKunbiModal()` | templates/js/chat.js | 切换坤币模态框显示 |
| `sendKunbi()` | templates/js/chat.js | 发送坤币红包 |
| `updateUserStatus(userId, isOnline)` | templates/js/chat.js | 更新用户在线状态 |
| `receiveMessage(message)` | templates/js/chat.js | 接收新消息 |
| `playMessageSound()` | templates/js/chat.js | 播放消息提示音 |
| `showNotification(message)` | templates/js/chat.js | 显示通知 |
| `createNotification(message)` | templates/js/chat.js | 创建通知 |
| `generateChatId(type, senderId, targetId)` | templates/js/chat.js | 生成聊天ID，确保私聊双向通信 |
| `initFolders()` | templates/js/chat.js | 初始化必要的文件夹 |
| `handleLogout()` | templates/js/chat.js | 处理退出登录 |
| `showUserInfo(userId)` | templates/js/chat.js | 显示用户详细信息模态框 |
| `addFriend(userId)` | templates/js/chat.js | 向指定用户发送好友请求 |
| `toggleBlacklist(userId)` | templates/js/chat.js | 拉黑或取消拉黑用户 |
| `showChatActions()` | templates/js/chat.js | 显示聊天操作模态框 |
| `clearChatHistory()` | templates/js/chat.js | 清空当前聊天的聊天记录 |
| `reportUser(userId)` | templates/js/chat.js | 显示举报用户表单 |
| `submitReport(userId)` | templates/js/chat.js | 提交用户举报 |
| `initMessageContextMenu()` | templates/js/chat.js | 初始化消息右键菜单/长按功能 |
| `quoteMessage(messageEl)` | templates/js/chat.js | 引用消息 |
| `recallMessage(messageEl)` | templates/js/chat.js | 撤回消息 |
| `mentionUser(messageEl)` | templates/js/chat.js | @用户功能 |

### 管理员登录模块 (admin_login.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `handleAdminLogin(event)` | templates/js/admin_login.js | 处理管理员登录表单提交 |
| `isAdminLoggedIn()` | templates/js/admin_login.js | 检查管理员是否已登录 |
| `showToast(message, type, duration)` | templates/js/admin_login.js | 显示提示消息 |

### 管理员控制台模块 (admin.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `isAdminLoggedIn()` | templates/js/admin.js | 检查管理员是否已登录 |
| `getAdminInfo()` | templates/js/admin.js | 获取管理员信息 |
| `updateCurrentTime()` | templates/js/admin.js | 更新当前时间显示 |
| `loadStatistics()` | templates/js/admin.js | 加载系统统计数据 |
| `initCharts()` | templates/js/admin.js | 初始化图表 |
| `loadRecentUsers()` | templates/js/admin.js | 加载最近注册用户 |
| `loadSystemLogs()` | templates/js/admin.js | 加载系统日志 |
| `loadAllUsers(page)` | templates/js/admin.js | 加载所有用户 |
| `loadAllGroups(page)` | templates/js/admin.js | 加载所有群组 |
| `updatePagination(pagination)` | templates/js/admin.js | 更新分页控件 |
| `setActiveSection(sectionId)` | templates/js/admin.js | 设置活跃标签页 |
| `bindEvents()` | templates/js/admin.js | 绑定页面事件 |
| `deleteUser(userId)` | templates/js/admin.js | 删除用户 |
| `showToast(message, type, duration)` | templates/js/admin.js | 显示提示消息 |

### 个人资料模块 (profile.js)

| 函数名 | 路径 | 作用 |
|-------|------|-----|
| `initUserInfo()` | templates/js/profile.js | 初始化用户信息显示 |
| `getUserFromStorage()` | templates/js/profile.js | 从本地存储获取用户信息 |
| `initTabSwitching()` | templates/js/profile.js | 初始化标签切换 |
| `initFormSubmits()` | templates/js/profile.js | 初始化表单提交 |
| `initAvatarUpload()` | templates/js/profile.js | 初始化头像上传 |
| `updateProfileToServer()` | templates/js/profile.js | 向服务器发送更新个人资料请求 |
| `updatePasswordToServer()` | templates/js/profile.js | 向服务器发送更新密码请求 |
| `logoutFromServer()` | templates/js/profile.js | 向服务器发送退出登录请求 |
| `deleteAccountFromServer()` | templates/js/profile.js | 向服务器发送注销账号请求 |
| `showToast()` | templates/js/profile.js | 显示提示消息 |
| `uploadAvatarToServer(file)` | templates/js/profile.js | 上传用户头像到服务器 |

## 后端模块

### 认证路由 (auth.py)

| 函数/装饰器 | 路径 | 作用 |
|------------|------|-----|
| `auth_required` | route/auth.py | 认证中间件 |
| `register()` | route/auth.py | 用户注册接口 |
| `login()` | route/auth.py | 用户登录接口 |
| `verify_token()` | route/auth.py | 验证令牌接口 |
| `get_profile()` | route/auth.py | 获取用户信息接口 |
| `admin_login()` | route/auth.py | 管理员登录接口 |
| `check_username()` | route/auth.py | 检查用户名是否可用 |
| `logout()` | route/auth.py | 用户注销接口 |
| `/api/auth/user/<user_id>` | GET | get_user_profile_endpoint | 获取指定用户的公开信息 |
| `/api/auth/profile` | POST | update_profile_endpoint | 更新用户个人资料 |
| `/api/auth/password` | POST | update_password_endpoint | 更新用户密码 |
| `/api/auth/account/delete` | POST | delete_account_endpoint | 注销（删除）用户账号 |

### 聊天路由 (chat.py)

| 函数 | 路径 | 作用 |
|------|------|-----|
| `get_online_users()` | route/chat.py | 获取在线用户列表 |
| `get_recent_contacts()` | route/chat.py | 获取最近联系人列表 |
| `get_groups()` | route/chat.py | 获取用户所在群组列表 |
| `create_group()` | route/chat.py | 创建新群组 |
| `get_group_members()` | route/chat.py | 获取群组成员列表 |
| `join_group()` | route/chat.py | 加入群组 |
| `get_messages()` | route/chat.py | 获取聊天消息历史 |
| `save_chat_history()` | route/chat.py | 保存聊天历史记录到JSON文件 |
| `get_chat_history()` | route/chat.py | 获取聊天历史记录 |
| `upload_json()` | route/chat.py | 上传JSON文件 |
| `send_kunbi()` | route/chat.py | 发送坤币红包 |
| `receive_kunbi()` | route/chat.py | 接收坤币红包 |

### 管理员路由 (admin.py)

| 函数/装饰器 | 路径 | 作用 |
|------------|------|-----|
| `admin_required` | route/admin.py | 管理员权限验证中间件 |
| `get_stats()` | route/admin.py | 获取系统统计信息 |
| `get_all_users()` | route/admin.py | 获取所有用户列表 |
| `update_user()` | route/admin.py | 更新用户信息 |
| `delete_user()` | route/admin.py | 删除用户 |
| `get_all_groups()` | route/admin.py | 获取所有群组列表 |
| `delete_group()` | route/admin.py | 删除群组 |
| `send_notification()` | route/admin.py | 发送系统通知 |
| `get_system_logs()` | route/admin.py | 获取系统日志 |

### 数据库工具

| 函数 | 路径 | 作用 |
|------|------|-----|
| `init_database()` | scripts/init_db.py | 初始化数据库 |
| `read_sql_file()` | scripts/update_db.py | 读取SQL文件内容 |
| `execute_sql_commands()` | scripts/update_db.py | 执行SQL命令更新数据库 |
| `main()` | scripts/update_db.py | 更新数据库主函数 |

### 主程序 (run.py)

| 函数 | 路径 | 作用 |
|------|------|-----|
| `handle_connect()` | run.py | 处理 WebSocket 连接 |
| `handle_disconnect()` | run.py | 处理 WebSocket 断开连接 |
| `handle_user_status(data)` | run.py | 处理用户状态更新 |
| `handle_join(data)` | run.py | 处理用户加入聊天室 |
| `handle_leave(data)` | run.py | 处理用户离开聊天室 |
| `handle_message(data)` | run.py | 处理聊天消息 |
| `handle_private_message(data)` | run.py | 处理私聊消息，确保双向通信 |
| `handle_user_update(data)` | run.py | 广播用户信息更新 |

### 管理员后台脚本 (run_admin.py)

| 函数/类 | 路径 | 作用 |
|-------|------|-----|
| `load_config()` | run_admin.py | 加载配置文件 |
| `setup_logging()` | run_admin.py | 设置日志记录 |
| `admin_login()` | run_admin.py | 管理员登录页面路由 |
| `admin_login_api()` | run_admin.py | 管理员登录API路由 |
| `admin_dashboard()` | run_admin.py | 管理员仪表盘页面路由 |
| `admin_logout()` | run_admin.py | 管理员退出登录API路由 |
| `health_check()` | run_admin.py | 健康检查路由 |
| `Daemon` 类 | run_admin.py | 守护进程管理类，用于后台运行服务 |
| `run_server()` | run_admin.py | 运行Flask服务器 |
| `main()` | run_admin.py | 主函数，处理命令行参数并启动服务 |

## 数据库结构

### 用户表 (users)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 用户ID (主键) |
| username | TEXT | 用户名 |
| password_hash | BLOB | 密码哈希 |
| nickname | TEXT | 用户昵称 |
| avatar | TEXT | 头像路径 |
| kunbi | INTEGER | 坤币数量 |
| is_admin | INTEGER | 是否管理员 |
| status | TEXT | 在线状态 |
| created_at | TEXT | 创建时间 |
| last_login_at | TEXT | 最后登录时间 |
| gender | TEXT | 性别 |
| signature | TEXT | 个性签名 |
| birthday | TEXT | 生日 |
| location | TEXT | 所在地 |
| email | TEXT | 邮箱 |
| phone | TEXT | 手机号 |
| background_image | TEXT | 个人主页背景图 |

### 群组表 (groups)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 群组ID (主键) |
| name | TEXT | 群组名称 |
| avatar | TEXT | 群组头像 |
| description | TEXT | 群组描述 |
| creator_id | INTEGER | 创建者ID |
| created_at | TEXT | 创建时间 |

### 群组成员表 (group_members)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 记录ID (主键) |
| group_id | INTEGER | 群组ID |
| user_id | INTEGER | 用户ID |
| role | TEXT | 角色 |
| joined_at | TEXT | 加入时间 |

### 消息表 (messages)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 消息ID (主键) |
| sender_id | INTEGER | 发送者ID |
| receiver_id | INTEGER | 接收者ID |
| group_id | INTEGER | 群组ID |
| content | TEXT | 消息内容 |
| created_at | TEXT | 创建时间 |
| message_type | TEXT | 消息类型 |
| extra_data | TEXT | 额外数据 |
| is_edited | INTEGER | 是否已编辑 |
| edited_at | TEXT | 编辑时间 |
| reply_to | INTEGER | 回复的消息ID |

### 坤币交易表 (kunbi_transactions)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 交易ID (主键) |
| sender_id | INTEGER | 发送者ID |
| receiver_id | INTEGER | 接收者ID |
| group_id | INTEGER | 群组ID |
| amount | INTEGER | 数量 |
| message | TEXT | 留言 |
| created_at | TEXT | 创建时间 |

### 黑名单表 (blacklist)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 记录ID (主键) |
| user_id | INTEGER | 用户ID |
| blocked_user_id | INTEGER | 被拉黑用户ID |
| reason | TEXT | 拉黑原因 |
| created_at | TEXT | 拉黑时间 |

### 系统日志表 (system_logs)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 日志ID (主键) |
| type | TEXT | 日志类型 |
| content | TEXT | 日志内容 |
| user_id | INTEGER | 相关用户ID |
| created_at | TEXT | 创建时间 |

### 邮件表 (mail)

| 字段名 | 类型 | 描述 |
|-------|------|-----|
| id | INTEGER | 邮件ID (主键) |
| sender_id | INTEGER | 发件人ID |
| receiver_id | INTEGER | 收件人ID |
| subject | TEXT | 主题 |
| content | TEXT | 内容 |
| is_read | INTEGER | 是否已读 |
| has_attachment | INTEGER | 是否有附件 |
| is_deleted_by_sender | INTEGER | 发件人是否删除 |
| is_deleted_by_receiver | INTEGER | 收件人是否删除 |
| created_at | TEXT | 创建时间 |
| read_at | TEXT | 阅读时间 |

### 其他表

- mail_attachments - 邮件附件表
- files - 文件表
- friends - 好友关系表
- friend_requests - 好友请求表
- user_settings - 用户设置表
- user_logs - 用户日志表
- emoji_favorites - 表情包收藏表
- notifications - 通知表
- group_announcements - 群组公告表

## 聊天功能增强

### 头像上传功能
- `uploadAvatarToServer(file)` - 位于 `/templates/js/profile.js`
  - 功能: 上传用户头像到服务器
  - 参数: `file` - 头像文件对象

### 用户管理功能
- `showUserInfo(userId)` - 位于 `/templates/js/chat.js`
  - 功能: 显示用户信息模态框
  - 参数: `userId` - 用户ID
  
- `toggleBlacklist(userId)` - 位于 `/templates/js/chat.js`
  - 功能: 拉黑或取消拉黑用户
  - 参数: `userId` - 用户ID

### 聊天操作功能
- `showChatActions()` - 位于 `/templates/js/chat.js`
  - 功能: 显示聊天操作模态框(当点击info图标时)
  
- `clearChatHistory()` - 位于 `/templates/js/chat.js`
  - 功能: 清空当前聊天的聊天记录
  
- `reportUser(userId)` - 位于 `/templates/js/chat.js`
  - 功能: 显示举报用户表单
  - 参数: `userId` - 被举报用户ID
  
- `submitReport(userId)` - 位于 `/templates/js/chat.js`
  - 功能: 提交用户举报
  - 参数: `userId` - 被举报用户ID

### 消息操作功能
- `initMessageContextMenu()` - 位于 `/templates/js/chat.js`
  - 功能: 初始化消息右键菜单/长按功能
  
- `quoteMessage(messageEl)` - 位于 `/templates/js/chat.js` 内部函数
  - 功能: 引用消息
  - 参数: `messageEl` - 消息元素
  
- `recallMessage(messageEl)` - 位于 `/templates/js/chat.js` 内部函数
  - 功能: 撤回消息
  - 参数: `messageEl` - 消息元素
  
- `mentionUser(messageEl)` - 位于 `/templates/js/chat.js` 内部函数
  - 功能: @用户功能
  - 参数: `messageEl` - 消息元素

## 问题修复 2023-05-11

### 头像上传修复
- 修改了 `templates/js/profile.js` 中的头像上传API路径，从 `/api/user/avatar` 改为 `/api/auth/avatar`
- 添加了 `updateAvatarUI` 函数，确保在头像加载失败时使用默认头像
- 创建了默认头像文件 `src/images/default-avatar.png`

### 聊天功能增强
- 修改了 `templates/js/chat.js` 中的消息撤回功能，使其向服务器发送请求并广播给所有用户
- 修改了清空聊天记录功能，确保操作对所有用户可见
- 添加了 WebSocket 事件监听，处理消息撤回 (`message_recalled`) 和聊天记录清空 (`chat_cleared`) 的同步
- 添加了 `appendSystemMessage` 函数，用于显示系统消息

### 引用消息功能
- 改进了 `templates/js/chat.js` 中的 `quoteMessage` 函数，优化引用用户的识别逻辑
- 修改了 `createMessageElement` 函数，支持显示引用消息
- 在 `templates/css/common.css` 中添加了引用消息和撤回消息的样式

### 已修复问题
1. 头像上传失败问题（404 错误）
2. 清空聊天记录和撤回消息操作不会同步到其他用户的问题
3. 引用消息样式缺失的问题
4. 引用未知用户消息识别问题

## 问题修复 2023-05-12

### 聊天功能修复
- 修复了消息撤回功能不正常的问题，完善了 `updateRecalledMessageUI` 函数实现
- 修复了引用消息显示"未知用户"的问题，改进了用户信息查找逻辑
- 增强了 WebSocket 连接和事件监听的稳定性
- 修复并改进了消息撤回的样式显示

### 修复的主要函数
- `updateRecalledMessageUI` - 改进撤回消息UI更新逻辑，确保所有类型消息正确显示撤回状态
- `quoteMessage` - 改进了用户信息查找逻辑，解决引用消息显示"未知用户"的问题
- `initSocketEventListeners` - 增加了日志，改进了消息元素查找方式
- `initSocketConnection` - 增强了连接错误处理和重连机制

### CSS样式改进
- 添加了 `.recalled-message`、`.recalled-content` 样式，改进撤回消息的视觉效果
