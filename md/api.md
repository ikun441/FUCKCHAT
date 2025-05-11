# FUCKCHAT API 文档

本文件记录API接口和端点的更新，供开发者参考。

## 认证接口

### 注册用户
- **URL**: `/api/auth/register`
- **方法**: `POST`
- **描述**: 创建新用户账号
- **参数**:
  - `username`: 用户名 (必填)
  - `nickname`: 昵称 (必填)
  - `password`: 密码 (必填)
- **返回**: 
  ```json
  {
    "success": true,
    "user_id": 123,
    "token": "jwt_token_here"
  }
  ```

### 用户登录
- **URL**: `/api/auth/login`
- **方法**: `POST`
- **描述**: 用户登录并获取访问令牌
- **参数**:
  - `username`: 用户名 (必填)
  - `password`: 密码 (必填)
- **返回**: 
  ```json
  {
    "success": true,
    "user": {
      "id": 123,
      "username": "user123",
      "nickname": "昵称",
      "avatar": "/path/to/avatar.jpg",
      "kunbi": 100
    },
    "token": "jwt_token_here"
  }
  ```

### 检查令牌
- **URL**: `/api/auth/verify`
- **方法**: `GET`
- **描述**: 验证用户令牌是否有效
- **头部**:
  - `Authorization`: `Bearer [token]`
- **返回**: 
  ```json
  {
    "valid": true,
    "user_id": 123
  }
  ```

### 获取用户信息
- **URL**: `/api/auth/profile`
- **方法**: `GET`
- **描述**: 获取当前登录用户信息
- **头部**:
  - `Authorization`: `Bearer [token]`
- **返回**: 
  ```json
  {
    "id": 123,
    "username": "user123",
    "nickname": "昵称",
    "avatar": "/path/to/avatar.jpg",
    "kunbi": 100,
    "gender": "男",
    "signature": "个性签名",
    "birthday": "2000-01-01",
    "location": "北京",
    "email": "user@example.com"
  }
  ```

### 更新用户信息
- **URL**: `/api/auth/profile`
- **方法**: `POST`
- **描述**: 更新用户个人资料
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `nickname`: 昵称 (可选)
  - `gender`: 性别 (可选)
  - `signature`: 个性签名 (可选)
  - `birthday`: 生日 (可选)
  - `location`: 位置 (可选)
  - `email`: 邮箱 (可选)
- **返回**: 
  ```json
  {
    "success": true,
    "message": "个人资料已更新"
  }
  ```

### 上传头像
- **URL**: `/api/auth/avatar`
- **方法**: `POST`
- **描述**: 上传用户头像
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - 文件上传: `avatar` (图片文件)
- **返回**: 
  ```json
  {
    "success": true,
    "avatar_url": "/path/to/new_avatar.jpg"
  }
  ```

## 聊天接口

### 获取在线用户
- **URL**: `/api/chat/online_users`
- **方法**: `GET`
- **描述**: 获取当前在线用户列表
- **头部**:
  - `Authorization`: `Bearer [token]`
- **返回**: 
  ```json
  {
    "online_users": [
      {
        "id": 123,
        "username": "user123",
        "nickname": "昵称",
        "avatar": "/path/to/avatar.jpg"
      }
    ]
  }
  ```

### 获取消息历史
- **URL**: `/api/chat/messages`
- **方法**: `GET`
- **描述**: 获取聊天消息历史
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `chat_type`: 聊天类型 (`private` 或 `group`)
  - `target_id`: 目标ID (用户ID或群组ID)
  - `limit`: 消息数量限制 (可选)
  - `before`: 时间戳，获取此时间之前的消息 (可选)
- **返回**: 
  ```json
  {
    "messages": [
      {
        "id": 1,
        "sender_id": 123,
        "sender_name": "用户名",
        "content": "消息内容",
        "created_at": "2023-05-01T12:00:00Z",
        "message_type": "text",
        "extra_data": null
      }
    ]
  }
  ```

### 发送消息
- **URL**: `/api/chat/send`
- **方法**: `POST`
- **描述**: 发送聊天消息
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `chat_type`: 聊天类型 (`private` 或 `group`)
  - `target_id`: 目标ID (用户ID或群组ID)
  - `content`: 消息内容
  - `message_type`: 消息类型 (`text`, `image`, `voice`, 等)
  - `extra_data`: 额外数据 (可选，JSON格式)
  - `reply_to`: 回复的消息ID (可选)
- **返回**: 
  ```json
  {
    "success": true,
    "message_id": 456
  }
  ```

### 撤回消息
- **URL**: `/api/chat/recall`
- **方法**: `POST`
- **描述**: 撤回已发送的消息
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `message_id`: 消息ID
- **返回**: 
  ```json
  {
    "success": true
  }
  ```

### 发送坤币红包
- **URL**: `/api/chat/kunbi/send`
- **方法**: `POST`
- **描述**: 发送坤币红包
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `chat_type`: 聊天类型 (`private` 或 `group`)
  - `target_id`: 目标ID (用户ID或群组ID)
  - `amount`: 金额
  - `message`: 留言
- **返回**: 
  ```json
  {
    "success": true,
    "transaction_id": 789
  }
  ```

### 领取坤币红包
- **URL**: `/api/chat/kunbi/receive`
- **方法**: `POST`
- **描述**: 领取坤币红包
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `transaction_id`: 交易ID
- **返回**: 
  ```json
  {
    "success": true,
    "amount": 50
  }
  ```

## 群组接口

### 获取用户群组
- **URL**: `/api/groups`
- **方法**: `GET`
- **描述**: 获取用户所在的群组列表
- **头部**:
  - `Authorization`: `Bearer [token]`
- **返回**: 
  ```json
  {
    "groups": [
      {
        "id": 1,
        "name": "群组名称",
        "avatar": "/path/to/group_avatar.jpg",
        "member_count": 10
      }
    ]
  }
  ```

### 创建群组
- **URL**: `/api/groups/create`
- **方法**: `POST`
- **描述**: 创建新群组
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `name`: 群组名称
  - `description`: 群组描述 (可选)
  - 文件上传: `avatar` (群组头像，可选)
- **返回**: 
  ```json
  {
    "success": true,
    "group_id": 1
  }
  ```

### 获取群组成员
- **URL**: `/api/groups/:group_id/members`
- **方法**: `GET`
- **描述**: 获取群组成员列表
- **头部**:
  - `Authorization`: `Bearer [token]`
- **返回**: 
  ```json
  {
    "members": [
      {
        "id": 123,
        "username": "user123",
        "nickname": "昵称",
        "avatar": "/path/to/avatar.jpg",
        "role": "owner"
      }
    ]
  }
  ```

### 加入群组
- **URL**: `/api/groups/join`
- **方法**: `POST`
- **描述**: 加入指定群组
- **头部**:
  - `Authorization`: `Bearer [token]`
- **参数**:
  - `group_id`: 群组ID
- **返回**: 
  ```json
  {
    "success": true
  }
  ```

## 管理员接口

### 管理员登录
- **URL**: `/api/admin/login`
- **方法**: `POST`
- **描述**: 管理员登录
- **参数**:
  - `username`: 管理员用户名
  - `password`: 管理员密码
- **返回**: 
  ```json
  {
    "success": true,
    "redirect": "/admin/dashboard"
  }
  ```

### 获取系统统计
- **URL**: `/api/admin/stats`
- **方法**: `GET`
- **描述**: 获取系统统计数据
- **头部**:
  - `Authorization`: `Bearer [admin_token]`
- **返回**: 
  ```json
  {
    "user_count": 100,
    "message_count": 5000,
    "group_count": 20,
    "online_count": 15
  }
  ```

### 获取所有用户
- **URL**: `/api/admin/users`
- **方法**: `GET`
- **描述**: 获取所有用户列表
- **头部**:
  - `Authorization`: `Bearer [admin_token]`
- **参数**:
  - `page`: 页码 (可选)
  - `limit`: 每页数量 (可选)
  - `search`: 搜索关键词 (可选)
- **返回**: 
  ```json
  {
    "users": [
      {
        "id": 123,
        "username": "user123",
        "nickname": "昵称",
        "created_at": "2023-05-01T12:00:00Z",
        "last_login_at": "2023-05-10T15:30:00Z",
        "status": "online"
      }
    ],
    "pagination": {
      "total": 100,
      "page": 1,
      "limit": 20,
      "pages": 5
    }
  }
  ```

### 删除用户
- **URL**: `/api/admin/users/:user_id`
- **方法**: `DELETE`
- **描述**: 删除指定用户
- **头部**:
  - `Authorization`: `Bearer [admin_token]`
- **返回**: 
  ```json
  {
    "success": true
  }
  ```

### 获取系统日志
- **URL**: `/api/admin/logs`
- **方法**: `GET`
- **描述**: 获取系统日志
- **头部**:
  - `Authorization`: `Bearer [admin_token]`
- **参数**:
  - `page`: 页码 (可选)
  - `limit`: 每页数量 (可选)
  - `type`: 日志类型 (可选)
- **返回**: 
  ```json
  {
    "logs": [
      {
        "id": 1,
        "type": "error",
        "content": "日志内容",
        "created_at": "2023-05-01T12:00:00Z"
      }
    ],
    "pagination": {
      "total": 500,
      "page": 1,
      "limit": 20,
      "pages": 25
    }
  }
  ```

### 发送系统通知
- **URL**: `/api/admin/notification`
- **方法**: `POST`
- **描述**: 发送系统通知
- **头部**:
  - `Authorization`: `Bearer [admin_token]`
- **参数**:
  - `target_type`: 目标类型 (`all`, `user`, `group`)
  - `target_id`: 目标ID (如果不是全体通知)
  - `title`: 通知标题
  - `content`: 通知内容
- **返回**: 
  ```json
  {
    "success": true,
    "notification_id": 123
  }
  ```

## WebSocket 事件

### 连接
- **事件**: `connect`
- **认证**: 通过URL参数传递令牌 `?token=jwt_token_here`
- **描述**: 建立WebSocket连接

### 用户状态
- **事件**: `user_status`
- **数据**: 
  ```json
  {
    "user_id": 123,
    "status": "online"
  }
  ```
- **描述**: 更新用户在线状态

### 聊天消息
- **事件**: `chat_message`
- **数据**: 
  ```json
  {
    "id": 456,
    "chat_type": "private",
    "sender_id": 123,
    "sender_name": "用户名",
    "target_id": 456,
    "content": "消息内容",
    "created_at": "2023-05-01T12:00:00Z",
    "message_type": "text",
    "extra_data": null,
    "reply_to": null
  }
  ```
- **描述**: 发送/接收聊天消息

### 消息撤回
- **事件**: `message_recalled`
- **数据**: 
  ```json
  {
    "message_id": 456,
    "chat_type": "private",
    "target_id": 789
  }
  ```
- **描述**: 消息被撤回

### 聊天记录清空
- **事件**: `chat_cleared`
- **数据**: 
  ```json
  {
    "chat_type": "private",
    "target_id": 789
  }
  ```
- **描述**: 聊天记录被清空