-- FUCKCHAT 数据库结构更新脚本
-- 扩展用户表，添加更多用户信息字段
-- 添加邮件系统相关表
-- 优化消息表结构以支持不同类型的消息

-- 更新用户表，添加性别、个性签名等字段
ALTER TABLE users ADD COLUMN gender TEXT DEFAULT 'unknown';  -- 性别：male, female, unknown
ALTER TABLE users ADD COLUMN signature TEXT DEFAULT '';  -- 个性签名
ALTER TABLE users ADD COLUMN birthday TEXT DEFAULT NULL;  -- 生日
ALTER TABLE users ADD COLUMN location TEXT DEFAULT '';  -- 所在地
ALTER TABLE users ADD COLUMN email TEXT DEFAULT '';  -- 邮箱
ALTER TABLE users ADD COLUMN phone TEXT DEFAULT '';  -- 手机号
ALTER TABLE users ADD COLUMN background_image TEXT DEFAULT '';  -- 个人主页背景图

-- 创建邮件系统表
CREATE TABLE IF NOT EXISTS mail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,  -- 发件人ID
    receiver_id INTEGER NOT NULL,  -- 收件人ID
    subject TEXT NOT NULL,  -- 主题
    content TEXT NOT NULL,  -- 内容
    is_read INTEGER DEFAULT 0,  -- 是否已读：0未读，1已读
    has_attachment INTEGER DEFAULT 0,  -- 是否有附件：0无，1有
    is_deleted_by_sender INTEGER DEFAULT 0,  -- 发件人是否删除
    is_deleted_by_receiver INTEGER DEFAULT 0,  -- 收件人是否删除
    created_at TEXT NOT NULL,  -- 创建时间
    read_at TEXT DEFAULT NULL,  -- 阅读时间
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
);

-- 创建邮件附件表
CREATE TABLE IF NOT EXISTS mail_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_id INTEGER NOT NULL,  -- 所属邮件ID
    filename TEXT NOT NULL,  -- 文件名
    filepath TEXT NOT NULL,  -- 文件路径
    filesize INTEGER NOT NULL,  -- 文件大小(字节)
    mime_type TEXT NOT NULL,  -- 文件类型
    created_at TEXT NOT NULL,  -- 创建时间
    FOREIGN KEY (mail_id) REFERENCES mail(id)
);

-- 更新消息表，添加消息类型和额外信息字段
ALTER TABLE messages ADD COLUMN message_type TEXT DEFAULT 'text';  -- 消息类型：text, image, voice, video, file, location, kunbi
ALTER TABLE messages ADD COLUMN extra_data TEXT DEFAULT NULL;  -- 额外数据(JSON格式)
ALTER TABLE messages ADD COLUMN is_edited INTEGER DEFAULT 0;  -- 是否已编辑
ALTER TABLE messages ADD COLUMN edited_at TEXT DEFAULT NULL;  -- 编辑时间
ALTER TABLE messages ADD COLUMN reply_to INTEGER DEFAULT NULL;  -- 回复的消息ID

-- 创建文件表，用于存储用户上传的文件信息
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- 上传用户
    filename TEXT NOT NULL,  -- 原始文件名
    filepath TEXT NOT NULL,  -- 存储路径
    filesize INTEGER NOT NULL,  -- 文件大小(字节)
    mime_type TEXT NOT NULL,  -- 文件类型
    is_public INTEGER DEFAULT 0,  -- 是否公开：0私有，1公开
    download_count INTEGER DEFAULT 0,  -- 下载次数
    created_at TEXT NOT NULL,  -- 上传时间
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建用户好友关系表
CREATE TABLE IF NOT EXISTS friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- 用户ID
    friend_id INTEGER NOT NULL,  -- 好友ID
    nickname TEXT DEFAULT '',  -- 好友备注名
    group_name TEXT DEFAULT '我的好友',  -- 好友分组名称
    created_at TEXT NOT NULL,  -- 添加时间
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (friend_id) REFERENCES users(id),
    UNIQUE(user_id, friend_id)  -- 确保不会重复添加好友
);

-- 创建好友请求表
CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,  -- 发送者ID
    receiver_id INTEGER NOT NULL,  -- 接收者ID
    message TEXT DEFAULT '',  -- 验证消息
    status TEXT DEFAULT 'pending',  -- 状态：pending待处理, accepted已接受, rejected已拒绝
    created_at TEXT NOT NULL,  -- 创建时间
    updated_at TEXT DEFAULT NULL,  -- 更新时间
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
);

-- 创建用户设置表
CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- 用户ID
    theme TEXT DEFAULT 'light',  -- 主题：light浅色, dark深色
    notification_sound INTEGER DEFAULT 1,  -- 通知声音：0关闭，1开启
    message_preview INTEGER DEFAULT 1,  -- 消息预览：0关闭，1开启
    auto_download_files INTEGER DEFAULT 1,  -- 自动下载文件：0关闭，1开启
    language TEXT DEFAULT 'zh-CN',  -- 语言
    font_size TEXT DEFAULT 'medium',  -- 字体大小：small小, medium中, large大
    updated_at TEXT NOT NULL,  -- 更新时间
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id)  -- 每个用户只有一条设置记录
);

-- 创建用户日志表
CREATE TABLE IF NOT EXISTS user_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- 用户ID
    action TEXT NOT NULL,  -- 操作类型
    ip_address TEXT DEFAULT '',  -- IP地址
    device_info TEXT DEFAULT '',  -- 设备信息
    created_at TEXT NOT NULL,  -- 创建时间
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建表情包收藏表
CREATE TABLE IF NOT EXISTS emoji_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- 用户ID
    emoji_url TEXT NOT NULL,  -- 表情URL
    emoji_name TEXT DEFAULT '',  -- 表情名称
    created_at TEXT NOT NULL,  -- 创建时间
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 更新黑名单表
ALTER TABLE blacklist ADD COLUMN reason TEXT DEFAULT '';  -- 拉黑原因
ALTER TABLE blacklist ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP;  -- 拉黑时间

-- 创建通知表
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- 接收用户ID
    type TEXT NOT NULL,  -- 通知类型：system系统, friend好友, group群组, mail邮件
    title TEXT NOT NULL,  -- 通知标题
    content TEXT NOT NULL,  -- 通知内容
    is_read INTEGER DEFAULT 0,  -- 是否已读：0未读，1已读
    reference_id INTEGER DEFAULT NULL,  -- 相关引用ID
    reference_type TEXT DEFAULT NULL,  -- 引用类型：user, group, mail等
    created_at TEXT NOT NULL,  -- 创建时间
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建群组公告表
CREATE TABLE IF NOT EXISTS group_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,  -- 群组ID
    creator_id INTEGER NOT NULL,  -- 创建者ID
    title TEXT NOT NULL,  -- 公告标题
    content TEXT NOT NULL,  -- 公告内容
    is_pinned INTEGER DEFAULT 0,  -- 是否置顶：0不置顶，1置顶
    created_at TEXT NOT NULL,  -- 创建时间
    updated_at TEXT DEFAULT NULL,  -- 更新时间
    FOREIGN KEY (group_id) REFERENCES groups(id),
    FOREIGN KEY (creator_id) REFERENCES users(id)
);

-- 添加索引以提高性能
CREATE INDEX IF NOT EXISTS idx_messages_sender_receiver ON messages(sender_id, receiver_id);
CREATE INDEX IF NOT EXISTS idx_messages_group ON messages(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_mail_sender ON mail(sender_id);
CREATE INDEX IF NOT EXISTS idx_mail_receiver ON mail(receiver_id);
CREATE INDEX IF NOT EXISTS idx_friends_user ON friends(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_blacklist_user ON blacklist(user_id); 