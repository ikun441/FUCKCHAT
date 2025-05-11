/**
 * FUCKCHAT 聊天页面JavaScript
 * 处理聊天功能逻辑
 */

// 全局变量
let currentChat = {
    type: null, // 'user' 或 'group'
    id: null
};

// 当前用户信息
let currentUser = null;

// 用户列表
let onlineUsers = [];
let recentContacts = [];
let groups = [];
let messages = {};

// 聊天记录文件路径前缀
const CHAT_STORAGE_PREFIX = '/src/chat_data/';

/**
 * 生成聊天ID
 * @param {string} type - 聊天类型：'user' 或 'group'
 * @param {number} senderId - 发送者ID
 * @param {number} targetId - 接收者ID或群组ID
 * @returns {string} 聊天唯一标识符
 */
function generateChatId(type, senderId, targetId) {
    if (type === 'user') {
        // 私聊ID格式：user_较小ID_较大ID，确保双向通信使用同一ID
        const ids = [senderId, targetId].sort((a, b) => a - b);
        return `user_${ids[0]}_${ids[1]}`;
    } else {
        // 群聊ID格式：group_群组ID
        return `group_${targetId}`;
    }
}

/**
 * 当DOM加载完成后执行
 */
document.addEventListener('DOMContentLoaded', function() {
    // 初始化必要的文件夹
    initFolders();
    
    // 初始化用户信息
    initUserInfo();
    
    // 初始化Socket连接
    initSocketConnection();
    
    // 初始化事件监听
    initEventListeners();
    
    // 加载缓存的用户状态
    loadCachedUserStatuses();
});

/**
 * 初始化当前用户信息
 */
function initUserInfo() {
    currentUser = getCurrentUser();
    
    if (!currentUser) {
        // 如果没有用户信息，重定向到登录页面
        window.location.href = '/login';
        return;
    }
    
    // 更新用户信息显示
    document.getElementById('user-nickname').textContent = currentUser.nickname;
    document.getElementById('user-kunbi').textContent = `坤币: ${currentUser.kunbi}`;
    
    // 修复头像路径
    const userAvatarImg = document.getElementById('user-avatar');
    userAvatarImg.src = currentUser.avatar || '/css/default-avatar.png';
    userAvatarImg.onerror = function() {
        this.src = '/src/images/avtar.jpg';
        this.onerror = null; // 防止死循环
    };
    
    // 获取在线用户和群组信息
    fetchOnlineUsers();
    fetchRecentContacts();
    fetchGroups();
}

/**
 * 初始化WebSocket连接
 */
function initSocketConnection() {
    // 创建WebSocket连接
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const socketUrl = `${protocol}//${host}`;
    
    // 创建Socket.IO连接（添加更多参数以增强可靠性）
    window.socket = io(socketUrl, {
        reconnection: true,           // 启用重连
        reconnectionAttempts: 5,      // 最大重连次数
        reconnectionDelay: 1000,      // 重连延迟
        timeout: 20000,               // 连接超时
        transports: ['websocket', 'polling'], // 首选WebSocket，备用轮询
        forceNew: true                // 强制创建新连接
    });
    
    // 连接成功事件
    window.socket.on('connect', function() {
        console.log('Socket连接成功');
        
        // 发送用户在线状态
        window.socket.emit('user_status', {
            user_id: currentUser.id,
            username: currentUser.username,
            nickname: currentUser.nickname,
            status: 'online'
        });
        
        // 加入个人聊天室，用于接收私信
        window.socket.emit('join', {
            room: `user_${currentUser.id}`
        });
        
        // 加入已加入的所有群组
        groups.forEach(group => {
            window.socket.emit('join', {
                room: `group_${group.id}`
            });
        });
        
        // 显示连接成功提示
        showToast('聊天服务连接成功', 'success');
        
        // 发送ping消息保持连接活跃
        if (window.pingInterval) {
            clearInterval(window.pingInterval);
        }
        
        window.pingInterval = setInterval(() => {
            if (window.socket.connected) {
                window.socket.emit('ping', { user_id: currentUser.id });
            }
        }, 30000); // 每30秒ping一次
        
        // 连接成功后，请求所有用户的最新状态
        window.socket.emit('request_all_statuses');
        
        // 在连接成功后立即初始化Socket事件监听器
        initSocketEventListeners();
    });
    
    // 连接错误处理
    window.socket.on('connect_error', function(error) {
        console.error('Socket连接失败:', error);
        showToast('聊天服务连接失败，请稍后再试', 'error');
    });
    
    // 重连事件
    window.socket.on('reconnect', function(attemptNumber) {
        console.log(`Socket重连成功，尝试次数: ${attemptNumber}`);
        showToast('聊天服务重新连接成功', 'success');
        
        // 重连成功后重新初始化事件监听
        initSocketEventListeners();
    });
    
    // 重连尝试事件
    window.socket.on('reconnect_attempt', function(attemptNumber) {
        console.log(`正在尝试重连 (${attemptNumber})`);
    });
    
    // 重连失败事件
    window.socket.on('reconnect_failed', function() {
        console.error('Socket重连失败');
        showToast('聊天服务重连失败，请刷新页面', 'error');
    });
    
    // 断开连接事件
    window.socket.on('disconnect', function(reason) {
        console.log(`Socket断开连接，原因: ${reason}`);
        if (reason === 'io server disconnect') {
            // 服务器主动断开，需要手动重连
            window.socket.connect();
        }
    });
    
    // 初始化基础事件监听
    // 监听用户在线状态变化
    window.socket.on('user_online', function(data) {
        console.log('用户上线:', data);
        updateUserStatus(data.user_id, true);
        
        // 若收到用户状态信息，更新用户数据
        if (data.user_id && (data.username || data.nickname)) {
            let found = false;
            
            // 查找并更新在线用户
            for (let i = 0; i < onlineUsers.length; i++) {
                if (onlineUsers[i].id === data.user_id) {
                    onlineUsers[i].status = 'online';
                    onlineUsers[i].online = true;
                    if (data.username) onlineUsers[i].username = data.username;
                    if (data.nickname) onlineUsers[i].nickname = data.nickname;
                    found = true;
                    break;
                }
            }
            
            // 如果不在在线列表中，添加
            if (!found) {
                onlineUsers.push({
                    id: data.user_id,
                    username: data.username || `user_${data.user_id}`,
                    nickname: data.nickname || data.username || `用户${data.user_id}`,
                    status: 'online',
                    online: true
                });
            }
            
            // 同步更新近期联系人列表
            const contactIndex = recentContacts.findIndex(c => c.id === data.user_id);
            if (contactIndex !== -1) {
                recentContacts[contactIndex].status = 'online';
                recentContacts[contactIndex].online = true;
                if (data.username) recentContacts[contactIndex].username = data.username;
                if (data.nickname) recentContacts[contactIndex].nickname = data.nickname;
            }
            
            // 重新渲染用户列表
            renderOnlineUsers();
            renderRecentContacts();
        }
    });
    
    // 监听用户离线状态变化
    window.socket.on('user_offline', function(data) {
        console.log('用户离线:', data);
        updateUserStatus(data.user_id, false);
    });
    
    // 监听新消息
    window.socket.on('new_message', function(data) {
        console.log('收到新消息:', data);
        
        // 接收并处理新消息
        receiveMessage(data);
    });
    
    // 监听普通消息（群组消息等）
    window.socket.on('message', function(data) {
        console.log('收到普通消息:', data);
        
        // 构建完整的消息对象
        const message = {
            id: data.id || Date.now(),
            sender: data.sender,
            sender_id: data.sender,
            receiver: data.receiver,
            receiver_id: data.receiver,
            group: data.group,
            group_id: data.group,
            content: data.message,
            timestamp: data.timestamp,
            type: data.type || 'text'
        };
        
        // 接收并处理消息
        receiveMessage(message);
    });
    
    // 监听群组更新
    window.socket.on('group_update', function(data) {
        console.log('群组更新:', data);
        // 刷新群组列表
        fetchGroups();
    });
    
    // 监听用户信息更新
    window.socket.on('user_update', function(data) {
        console.log('用户信息更新:', data);
        
        if (!data || !data.user_id) return;
        
        // 更新用户列表
        const userId = parseInt(data.user_id);
        
        // 更新在线用户列表中的用户信息
        const userIndex = onlineUsers.findIndex(u => u.id === userId);
        if (userIndex !== -1) {
            // 更新昵称
            if (data.nickname) {
                onlineUsers[userIndex].nickname = data.nickname;
            }
            
            // 更新其他可能的字段
            if (data.avatar) {
                onlineUsers[userIndex].avatar = data.avatar;
            }
        }
        
        // 更新最近联系人列表中的用户信息
        const contactIndex = recentContacts.findIndex(c => c.id === userId);
        if (contactIndex !== -1) {
            // 更新昵称
            if (data.nickname) {
                recentContacts[contactIndex].nickname = data.nickname;
            }
            
            // 更新其他可能的字段
            if (data.avatar) {
                recentContacts[contactIndex].avatar = data.avatar;
            }
        }
        
        // 如果是当前聊天的用户，更新聊天头部信息
        if (currentChat.type === 'user' && currentChat.id === userId && data.nickname) {
            document.getElementById('chat-title').textContent = data.nickname;
        }
        
        // 重新渲染列表
        renderOnlineUsers();
        renderRecentContacts();
    });
    
    // 监听用户删除事件
    window.socket.on('user_deleted', function(data) {
        console.log('用户已删除:', data);
        
        if (!data || !data.user_id) return;
        
        const userId = parseInt(data.user_id);
        
        // 从列表中移除用户
        onlineUsers = onlineUsers.filter(u => u.id !== userId);
        recentContacts = recentContacts.filter(c => c.id !== userId);
        
        // 如果当前正在与该用户聊天，显示用户已删除消息
        if (currentChat.type === 'user' && currentChat.id === userId) {
            const messagesContainer = document.getElementById('messages-container');
            messagesContainer.innerHTML += `
                <div class="system-message">
                    <div class="system-text">该用户已注销账号</div>
                </div>
            `;
            
            // 禁用消息输入
            document.getElementById('message-input').disabled = true;
            document.getElementById('send-btn').disabled = true;
        }
        
        // 重新渲染列表
        renderOnlineUsers();
        renderRecentContacts();
    });
    
    // 监听pong响应
    window.socket.on('pong', function(data) {
        console.log('收到pong响应:', data);
    });
}

/**
 * 从文件加载或创建Socket.IO服务器（如果不存在）
 * 这个函数是为了帮助没有后端服务的环境快速搭建聊天功能
 */
function setupLocalSocketServer() {
    // 检查是否已经有socket服务
    if (window.io) {
        return;
    }
    
    console.log('尝试创建临时Socket服务');
    
    // 创建简单的消息中继系统
    window.messageRelay = {
        listeners: {},
        rooms: {},
        
        // 添加监听器
        addListener: function(event, callback) {
            if (!this.listeners[event]) {
                this.listeners[event] = [];
            }
            this.listeners[event].push(callback);
        },
        
        // 触发事件
        emit: function(event, data, roomName) {
            console.log(`Emitting event: ${event} to ${roomName || 'all'}`, data);
            
            // 如果指定了房间，只发给房间成员
            if (roomName && this.rooms[roomName]) {
                this.rooms[roomName].forEach(userId => {
                    if (this.listeners[`user_${userId}_${event}`]) {
                        this.listeners[`user_${userId}_${event}`].forEach(callback => {
                            callback(data);
                        });
                    }
                });
            } 
            // 否则广播给所有监听器
            else if (this.listeners[event]) {
                this.listeners[event].forEach(callback => {
                    callback(data);
                });
            }
        },
        
        // 加入房间
        joinRoom: function(roomName, userId) {
            if (!this.rooms[roomName]) {
                this.rooms[roomName] = [];
            }
            if (!this.rooms[roomName].includes(userId)) {
                this.rooms[roomName].push(userId);
            }
        },
        
        // 离开房间
        leaveRoom: function(roomName, userId) {
            if (this.rooms[roomName]) {
                this.rooms[roomName] = this.rooms[roomName].filter(id => id !== userId);
            }
        }
    };
    
    // 模拟Socket.io功能
    window.io = function(url, options) {
        console.log('创建本地Socket连接:', url, options);
        
        return {
            connected: true,
            
            // 连接
            connect: function() {
                this.connected = true;
                if (this.listeners['connect']) {
                    this.listeners['connect'].forEach(callback => callback());
                }
            },
            
            // 断开连接
            disconnect: function() {
                this.connected = false;
                if (this.listeners['disconnect']) {
                    this.listeners['disconnect'].forEach(callback => callback('client disconnect'));
                }
            },
            
            // 监听事件
            on: function(event, callback) {
                if (!this.listeners) {
                    this.listeners = {};
                }
                
                if (!this.listeners[event]) {
                    this.listeners[event] = [];
                }
                
                this.listeners[event].push(callback);
                
                // 立即触发connect事件
                if (event === 'connect') {
                    callback();
                }
            },
            
            // 发送事件
            emit: function(event, data) {
                // 处理不同类型的事件
                if (event === 'user_status') {
                    // 广播用户状态
                    setTimeout(() => {
                        window.messageRelay.emit('user_online', data);
                    }, 100);
                }
                else if (event === 'join') {
                    // 加入房间
                    if (data.room && currentUser) {
                        window.messageRelay.joinRoom(data.room, currentUser.id);
                    }
                }
                else if (event === 'message') {
                    // 发送消息
                    setTimeout(() => {
                        window.messageRelay.emit('new_message', data, data.room);
                    }, 100);
                }
                else if (event === 'ping') {
                    // 响应ping
                    setTimeout(() => {
                        if (this.listeners['pong']) {
                            this.listeners['pong'].forEach(callback => {
                                callback({ time: Date.now() });
                            });
                        }
                    }, 50);
                }
            },
            
            // 监听器
            listeners: {}
        };
    };
    
    // 自动触发连接
    setTimeout(() => {
        initSocketConnection();
    }, 500);
}

// 在初始化时设置本地Socket服务（如果需要）
window.addEventListener('load', function() {
    // 如果没有检测到Socket.IO，尝试设置本地服务
    if (typeof io === 'undefined') {
        setupLocalSocketServer();
    }
});

/**
 * 获取在线用户列表
 */
async function fetchOnlineUsers() {
    try {
        const response = await fetch('/api/chat/users', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取在线用户列表失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            onlineUsers = data.users || [];
            
            // 同步用户状态
            syncUserStatuses();
            
            renderOnlineUsers();
        } else {
            console.error('获取在线用户列表失败:', data.message);
            // 失败时使用模拟数据（仅开发阶段）
            useMockOnlineUsers();
        }
    } catch (error) {
        console.error('获取在线用户列表失败:', error);
        // 出错时使用模拟数据（仅开发阶段）
        useMockOnlineUsers();
    }
}

/**
 * 使用模拟数据（仅开发阶段）
 */
function useMockOnlineUsers() {
    onlineUsers = [
        {
            id: 1,
            username: 'admin',
            nickname: '管理员',
            isAdmin: true,
            online: true,
            avatar: '/images/default-avatar.png'
        },
        {
            id: 2,
            username: 'user',
            nickname: '测试用户',
            isAdmin: false,
            online: true,
            avatar: '/images/default-avatar.png'
        },
        {
            id: 3,
            username: 'zhangsan',
            nickname: '张三',
            isAdmin: false,
            online: true,
            avatar: '/images/default-avatar.png'
        }
    ].filter(user => user.id !== currentUser.id);
    
    renderOnlineUsers();
}

/**
 * 获取最近联系人列表
 */
async function fetchRecentContacts() {
    try {
        const response = await fetch('/api/chat/contacts', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取最近联系人列表失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            recentContacts = data.contacts || [];
            
            // 同步用户状态
            syncUserStatuses();
            
            renderRecentContacts();
        } else {
            console.error('获取最近联系人列表失败:', data.message);
            // 失败时使用模拟数据（仅开发阶段）
            useMockRecentContacts();
        }
    } catch (error) {
        console.error('获取最近联系人列表失败:', error);
        // 出错时使用模拟数据（仅开发阶段）
        useMockRecentContacts();
    }
}

/**
 * 使用模拟最近联系人数据（仅开发阶段）
 */
function useMockRecentContacts() {
    recentContacts = [
        {
            id: 4,
            username: 'lisi',
            nickname: '李四',
            online: false,
            avatar: '/images/default-avatar.png',
            lastMessage: '下次再聊',
            lastTime: new Date(Date.now() - 86400000) // 1天前
        },
        {
            id: 5,
            username: 'wangwu',
            nickname: '王五',
            online: true,
            avatar: '/images/default-avatar.png',
            lastMessage: '好的，明天见',
            lastTime: new Date(Date.now() - 172800000) // 2天前
        }
    ];
    
    renderRecentContacts();
}

/**
 * 获取群组列表
 */
async function fetchGroups() {
    try {
        const response = await fetch('/api/chat/groups', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取群组列表失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            groups = data.groups || [];
            renderGroups();
        } else {
            console.error('获取群组列表失败:', data.message);
            // 失败时使用模拟数据（仅开发阶段）
            useMockGroups();
        }
    } catch (error) {
        console.error('获取群组列表失败:', error);
        // 出错时使用模拟数据（仅开发阶段）
        useMockGroups();
    }
}

/**
 * 使用模拟群组数据（仅开发阶段）
 */
function useMockGroups() {
    groups = [
        {
            id: 1,
            name: '全体成员群',
            avatar: '/images/group-avatar.png',
            memberCount: 5,
            unreadCount: 0
        },
        {
            id: 2,
            name: '技术交流群',
            avatar: '/images/group-avatar.png',
            memberCount: 3,
            unreadCount: 2
        }
    ];
    
    renderGroups();
}

/**
 * 渲染在线用户列表
 */
function renderOnlineUsers() {
    const onlineUsersList = document.getElementById('online-users');
    onlineUsersList.innerHTML = '';
    
    if (onlineUsers.length === 0) {
        onlineUsersList.innerHTML = '<div class="empty-list">暂无在线用户</div>';
        return;
    }
    
    // 先按在线状态排序
    const sortedUsers = [...onlineUsers].sort((a, b) => {
        const aOnline = a.status === 'online' || a.online;
        const bOnline = b.status === 'online' || b.online;
        if (aOnline && !bOnline) return -1;
        if (!aOnline && bOnline) return 1;
        return 0;
    });
    
    // 计算在线用户数量（除了当前用户）
    const onlineCount = sortedUsers.filter(user => 
        user.id !== currentUser.id && 
        (user.status === 'online' || user.online)
    ).length;
    
    // 添加在线人数显示
    const countHeader = document.createElement('div');
    countHeader.className = 'online-count';
    countHeader.innerHTML = `在线用户 (${onlineCount}人)`;
    onlineUsersList.appendChild(countHeader);
    
    // 仅显示在线用户
    sortedUsers
        .filter(user => user.id !== currentUser.id && (user.status === 'online' || user.online))
        .forEach(user => {
            const listItem = document.createElement('li');
            listItem.dataset.userId = user.id;
            listItem.addEventListener('click', () => openChatWithUser(user.id));
            
            // 使用正确的头像路径
            let avatarUrl = '/src/images/avtar.jpg';
            if (user.avatar) {
                // 确保头像路径正确
                if (user.avatar.startsWith('http')) {
                    avatarUrl = user.avatar;
                } else {
                    avatarUrl = user.avatar.startsWith('/') ? user.avatar : `/${user.avatar}`;
                }
            }
            
            listItem.innerHTML = `
                <div class="avatar">
                    <img src="${avatarUrl}" alt="${user.nickname || user.username}" loading="lazy" onerror="this.src='/src/images/avtar.jpg'">
                </div>
                <div class="info">
                    <div class="name">${user.nickname || user.username}</div>
                    <div class="status online">在线</div>
                </div>
            `;
            
            onlineUsersList.appendChild(listItem);
        });
}

/**
 * 渲染最近联系人列表
 */
function renderRecentContacts() {
    const recentContactsList = document.getElementById('recent-contacts');
    recentContactsList.innerHTML = '';
    
    if (recentContacts.length === 0) {
        recentContactsList.innerHTML = '<div class="empty-list">暂无最近联系人</div>';
        return;
    }
    
    recentContacts.forEach(contact => {
        // 确保使用最新的在线状态
        const isOnline = contact.status === 'online' || contact.online;
        
        // 同步在线状态（确保与onlineUsers列表保持一致）
        const onlineUser = onlineUsers.find(u => u.id === contact.id);
        if (onlineUser) {
            contact.online = onlineUser.online || onlineUser.status === 'online';
            contact.status = onlineUser.status;
        }
        
        const listItem = document.createElement('li');
        listItem.dataset.userId = contact.id;
        listItem.addEventListener('click', () => openChatWithUser(contact.id));
        
        // 使用正确的头像路径
        let avatarUrl = '/src/images/avtar.jpg';
        if (contact.avatar) {
            // 确保头像路径正确
            if (contact.avatar.startsWith('http')) {
                avatarUrl = contact.avatar;
            } else {
                avatarUrl = contact.avatar.startsWith('/') ? contact.avatar : `/${contact.avatar}`;
            }
        }
        
        listItem.innerHTML = `
            <div class="avatar">
                <img src="${avatarUrl}" alt="${contact.nickname || contact.username}" loading="lazy" onerror="this.src='/src/images/avtar.jpg'">
            </div>
            <div class="info">
                <div class="name">${contact.nickname || contact.username}</div>
                <div class="status ${isOnline ? 'online' : ''}">${isOnline ? '在线' : '离线'}</div>
                ${contact.lastMessage ? `<div class="last-message">${contact.lastMessage}</div>` : ''}
            </div>
        `;
        
        recentContactsList.appendChild(listItem);
    });
}

/**
 * 渲染群组列表
 */
function renderGroups() {
    const groupsList = document.getElementById('my-groups');
    groupsList.innerHTML = '';
    
    if (groups.length === 0) {
        groupsList.innerHTML = '<div class="empty-list">暂无群组</div>';
        return;
    }
    
    groups.forEach(group => {
        const listItem = document.createElement('li');
        listItem.dataset.groupId = group.id;
        listItem.addEventListener('click', () => openChatWithGroup(group.id));
        
        // 使用正确的群组头像
        let avatarUrl = '/src/images/chatgpt.png';
        if (group.avatar) {
            // 确保头像路径正确
            if (group.avatar.startsWith('http')) {
                avatarUrl = group.avatar;
            } else {
                avatarUrl = group.avatar.startsWith('/') ? group.avatar : `/${group.avatar}`;
            }
        }
        
        listItem.innerHTML = `
            <div class="avatar">
                <img src="${avatarUrl}" alt="${group.name}" loading="lazy" onerror="this.src='/src/images/chatgpt.png'">
            </div>
            <div class="info">
                <div class="name">${group.name || '未命名群组'}</div>
                <div class="status">${group.member_count || group.memberCount || 0}人</div>
            </div>
            ${group.unreadCount > 0 ? `<div class="badge">${group.unreadCount}</div>` : ''}
        `;
        
        groupsList.appendChild(listItem);
    });
}

/**
 * 初始化在线用户列表
 */
function initOnlineUsers() {
    const onlineUsersList = document.getElementById('online-users');
    const filteredUsers = onlineUsers.filter(user => user.id !== currentUser.id && user.online);
    
    onlineUsersList.innerHTML = '';
    
    filteredUsers.forEach(user => {
        const listItem = document.createElement('li');
        listItem.dataset.userId = user.id;
        listItem.addEventListener('click', () => openChatWithUser(user.id));
        
        listItem.innerHTML = `
            <div class="avatar">
                <img src="${user.avatar}" alt="${user.nickname}">
            </div>
            <div class="info">
                <div class="name">${user.nickname}</div>
                <div class="status online">在线</div>
            </div>
        `;
        
        onlineUsersList.appendChild(listItem);
    });
    
    // 模拟最近联系人
    const recentContactsList = document.getElementById('recent-contacts');
    recentContactsList.innerHTML = '';
    
    const offlineUsers = onlineUsers.filter(user => user.id !== currentUser.id && !user.online);
    offlineUsers.forEach(user => {
        const listItem = document.createElement('li');
        listItem.dataset.userId = user.id;
        listItem.addEventListener('click', () => openChatWithUser(user.id));
        
        listItem.innerHTML = `
            <div class="avatar">
                <img src="${user.avatar}" alt="${user.nickname}">
            </div>
            <div class="info">
                <div class="name">${user.nickname}</div>
                <div class="status">离线</div>
            </div>
        `;
        
        recentContactsList.appendChild(listItem);
    });
}

/**
 * 初始化群组列表
 */
function initGroups() {
    const groupsList = document.getElementById('my-groups');
    groupsList.innerHTML = '';
    
    groups.forEach(group => {
        const listItem = document.createElement('li');
        listItem.dataset.groupId = group.id;
        listItem.addEventListener('click', () => openChatWithGroup(group.id));
        
        listItem.innerHTML = `
            <div class="avatar">
                <img src="${group.avatar}" alt="${group.name}">
            </div>
            <div class="info">
                <div class="name">${group.name}</div>
                <div class="status">${group.memberCount}人</div>
            </div>
            ${group.unreadCount > 0 ? `<div class="badge">${group.unreadCount}</div>` : ''}
        `;
        
        groupsList.appendChild(listItem);
    });
}

/**
 * 初始化事件监听
 */
function initEventListeners() {
    // 移动设备菜单切换
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', function() {
            this.classList.toggle('active');
            sidebar.classList.toggle('active');
        });
        
        // 点击聊天区域关闭侧边栏
        document.querySelector('.chat-main').addEventListener('click', function() {
            if (window.innerWidth <= 768 && sidebar.classList.contains('active')) {
                mobileMenuBtn.classList.remove('active');
                sidebar.classList.remove('active');
            }
        });
    }
    
    // 标签切换
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 移除所有标签按钮的活动状态
            tabButtons.forEach(btn => btn.classList.remove('active'));
            // 添加当前按钮的活动状态
            this.classList.add('active');
            
            // 获取目标标签内容ID
            const targetTabId = `${this.dataset.tab}-tab`;
            
            // 隐藏所有标签内容
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // 显示目标标签内容
            document.getElementById(targetTabId).classList.add('active');
        });
    });
    
    // 用户搜索功能
    const userSearchInput = document.querySelector('#contacts-tab .search-bar input');
    const userSearchBtn = document.querySelector('#contacts-tab .search-bar button');
    
    if (userSearchInput) {
        userSearchInput.addEventListener('input', function() {
            searchUsers(this.value);
        });
        
        userSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchUsers(this.value);
            }
        });
    }
    
    if (userSearchBtn) {
        userSearchBtn.addEventListener('click', function() {
            searchUsers(userSearchInput.value);
        });
    }
    
    // 群组搜索功能
    const groupSearchInput = document.querySelector('#groups-tab .search-bar input');
    const groupSearchBtn = document.querySelector('#groups-tab .search-bar button');
    
    if (groupSearchInput) {
        groupSearchInput.addEventListener('input', function() {
            searchGroups(this.value);
        });
        
        groupSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchGroups(this.value);
            }
        });
    }
    
    if (groupSearchBtn) {
        groupSearchBtn.addEventListener('click', function() {
            searchGroups(groupSearchInput.value);
        });
    }
    
    // 发送消息按钮
    const sendButton = document.getElementById('send-btn');
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
    
    // 消息输入框回车发送
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // 表情按钮
    const emojiButton = document.getElementById('emoji-btn');
    if (emojiButton) {
        emojiButton.addEventListener('click', toggleEmojiPicker);
    }
    
    // 坤币按钮
    const kunbiButton = document.getElementById('kunbi-btn');
    if (kunbiButton) {
        kunbiButton.addEventListener('click', toggleKunbiModal);
    }
    
    // 关闭模态框按钮
    document.querySelectorAll('.close-btn').forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });
    
    // 发送坤币按钮
    const sendKunbiButton = document.getElementById('send-kunbi-btn');
    if (sendKunbiButton) {
        sendKunbiButton.addEventListener('click', sendKunbi);
    }
    
    // 创建群组按钮
    const createGroupButton = document.getElementById('create-group-btn');
    if (createGroupButton) {
        createGroupButton.addEventListener('click', showCreateGroupModal);
    }

    // 退出登录按钮
    const logoutButton = document.getElementById('logout-btn');
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }

    // 坤币红包点击事件委托
    document.addEventListener('click', function(e) {
        const kunbiContent = e.target.closest('.kunbi-content');
        if (kunbiContent) {
            handleKunbiClick(kunbiContent);
        }
    });

    // 点击消息外区域关闭模态框
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            e.target.classList.remove('active');
        }
    });
    
    // 窗口大小变化时处理
    window.addEventListener('resize', handleWindowResize);
    
    // 添加用户头像点击事件
    addUserAvatarClickEvent();
    
    // 设置头像上传端点
    setupAvatarUploadEndpoint();
    
    // 用户头像点击事件代理
    document.addEventListener('click', function(e) {
        // 点击的是消息中的头像
        const avatarImg = e.target.closest('.message .avatar img');
        if (avatarImg) {
            // 获取消息元素
            const messageEl = avatarImg.closest('.message');
            // 判断是否为自己发送的消息
            if (!messageEl.classList.contains('sent')) {
                // 获取发送者ID（在子元素或属性中存储）
                const senderId = messageEl.dataset.senderId || 
                                  messageEl.querySelector('.content .sender')?.dataset.userId;
                
                if (senderId) {
                    showUserInfo(parseInt(senderId));
                    e.stopPropagation();
                }
            }
        }
        
        // 点击的是联系人列表中的头像
        const contactAvatarImg = e.target.closest('#online-users li .avatar img, #recent-contacts li .avatar img');
        if (contactAvatarImg) {
            const listItem = contactAvatarImg.closest('li');
            const userId = listItem.dataset.userId;
            
            if (userId) {
                showUserInfo(parseInt(userId));
                e.stopPropagation();
            }
        }
    });
    
    // 添加info图标点击事件
    document.addEventListener('click', function(e) {
        const infoIcon = e.target.closest('.fa-info-circle');
        if (infoIcon) {
            const chatHeader = infoIcon.closest('.chat-header');
            if (chatHeader) {
                showChatActions();
                e.stopPropagation();
            }
        }
    });
    
    // 初始化消息右键菜单/长按功能
    initMessageContextMenu();
}

/**
 * 处理退出登录
 */
async function handleLogout() {
    try {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            window.location.href = '/login';
            return;
        }
        
        // 调用注销接口
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        // 清除本地存储的token
        localStorage.removeItem('fuckchat_token');
        localStorage.removeItem('fuckchat_user');
        
        // 断开WebSocket连接
        if (window.socket) {
            // 先发送用户离线状态
            window.socket.emit('user_status', {
                user_id: currentUser.id,
                status: 'offline'
            });
            
            window.socket.disconnect();
        }
        
        // 跳转到登录页面
        window.location.href = '/login';
    } catch (error) {
        console.error('退出登录失败:', error);
        // 无论API是否成功，都清除本地存储并跳转
        localStorage.removeItem('fuckchat_token');
        localStorage.removeItem('fuckchat_user');
        window.location.href = '/login';
    }
}

/**
 * 处理窗口大小变化
 */
function handleWindowResize() {
    // 如果窗口宽度大于768px，确保侧边栏可见
    if (window.innerWidth > 768) {
        document.querySelector('.sidebar').classList.remove('active');
        document.getElementById('mobile-menu-btn').classList.remove('active');
    }
}

/**
 * 打开与用户的聊天
 * @param {number} userId - 用户ID
 */
function openChatWithUser(userId) {
    currentChat = {
        type: 'user',
        id: userId
    };
    
    // 找到用户信息
    const user = [...onlineUsers, ...recentContacts].find(u => u.id === userId);
    if (!user) {
        console.error('未找到用户信息:', userId);
        showToast('无法打开聊天，用户信息不存在', 'error');
        return;
    }
    
    // 更新聊天标题
    document.getElementById('chat-title').textContent = user.nickname || user.username || '未知用户';
    document.getElementById('chat-subtitle').textContent = user.online ? '在线' : '离线';
    
    // 显示聊天区域，隐藏空聊天提示
    document.getElementById('empty-chat').style.display = 'none';
    document.getElementById('chat-area').style.display = 'flex';
    
    // 加载聊天消息
    loadMessages();
    
    // 标记所选用户为活动状态
    document.querySelectorAll('#online-users li, #recent-contacts li').forEach(item => {
        item.classList.remove('active');
    });
    
    document.querySelectorAll(`#online-users li[data-user-id="${userId}"], #recent-contacts li[data-user-id="${userId}"]`).forEach(item => {
        item.classList.add('active');
    });
    
    // 在移动端，点击用户后关闭侧边栏
    if (window.innerWidth <= 768) {
        document.querySelector('.sidebar').classList.remove('active');
        document.getElementById('mobile-menu-btn').classList.remove('active');
    }
}

/**
 * 打开与群组的聊天
 * @param {number} groupId - 群组ID
 */
function openChatWithGroup(groupId) {
    currentChat = {
        type: 'group',
        id: groupId
    };
    
    // 找到群组信息
    const group = groups.find(g => g.id === groupId);
    if (!group) {
        console.error('未找到群组信息:', groupId);
        showToast('无法打开群聊，群组信息不存在', 'error');
        return;
    }
    
    // 更新聊天标题
    document.getElementById('chat-title').textContent = group.name || '未命名群组';
    document.getElementById('chat-subtitle').textContent = `${group.memberCount || group.member_count || 0}人`;
    
    // 显示聊天区域，隐藏空聊天提示
    const emptyChat = document.getElementById('empty-chat');
    if (emptyChat) emptyChat.style.display = 'none';
    
    const chatArea = document.getElementById('chat-area');
    if (chatArea) chatArea.style.display = 'flex';
    
    // 加载聊天消息
    loadMessages();
    
    // 标记所选群组为活动状态
    document.querySelectorAll('#my-groups li').forEach(item => {
        item.classList.remove('active');
    });
    
    const groupItem = document.querySelector(`#my-groups li[data-group-id="${groupId}"]`);
    if (groupItem) {
        groupItem.classList.add('active');
    }
    
    // 清除未读数量
    const badgeElement = document.querySelector(`#my-groups li[data-group-id="${groupId}"] .badge`);
    if (badgeElement) {
        badgeElement.remove();
    }
    
    // 更新群组数据
    const groupIndex = groups.findIndex(g => g.id === groupId);
    if (groupIndex >= 0) {
        groups[groupIndex].unreadCount = 0;
    }
    
    // 在移动端，点击群组后关闭侧边栏（修复移动端问题）
    if (window.innerWidth <= 768) {
        const sidebar = document.querySelector('.sidebar');
        const mobileMenuBtn = document.getElementById('mobile-menu-btn');
        
        if (sidebar) sidebar.classList.remove('active');
        if (mobileMenuBtn) mobileMenuBtn.classList.remove('active');
    }
    
    // 确保加入了群聊频道
    if (window.socket && window.socket.connected) {
        window.socket.emit('join', {
            room: `group_${groupId}`
        });
    }
}

/**
 * 加载聊天消息
 */
function loadMessages() {
    const messagesContainer = document.getElementById('messages-container');
    messagesContainer.innerHTML = '';
    
    // 加载聊天记录
    loadChatHistory(currentChat.type, currentUser.id, currentChat.id)
        .then(chatMessages => {
            // 如果没有消息，显示空消息提示
            if (!chatMessages || chatMessages.length === 0) {
                messagesContainer.innerHTML = `
                    <div class="no-messages">
                        <p>暂无消息记录，发送一条消息开始聊天吧</p>
                    </div>
                `;
                return;
            }
            
            // 添加日期分隔
            let currentDate = null;
            
            chatMessages.forEach(message => {
                const messageDate = new Date(message.timestamp).toDateString();
                
                // 如果日期发生变化，添加日期分隔符
                if (messageDate !== currentDate) {
                    currentDate = messageDate;
                    
                    const dateDivider = document.createElement('div');
                    dateDivider.className = 'message-date-divider';
                    dateDivider.innerHTML = `<span>${formatDate(message.timestamp)}</span>`;
                    messagesContainer.appendChild(dateDivider);
                }
                
                // 创建消息元素
                const messageElement = createMessageElement(message);
                messagesContainer.appendChild(messageElement);
            });
            
            // 滚动到底部
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        })
        .catch(error => {
            console.error('加载消息失败:', error);
            messagesContainer.innerHTML = `
                <div class="load-error">
                    <p>加载消息失败，请重试</p>
                </div>
            `;
        });
}

/**
 * 加载聊天历史记录
 * @param {string} chatType - 聊天类型：'user' 或 'group' 
 * @param {number} userId - 当前用户ID
 * @param {number} targetId - 目标用户ID或群组ID
 * @returns {Promise<Array>} 消息数组
 */
async function loadChatHistory(chatType, userId, targetId) {
    try {
        const chatId = generateChatId(chatType, userId, targetId);
        
        // 尝试从本地缓存获取
        const cachedMessages = messages[chatId];
        if (cachedMessages && cachedMessages.length > 0) {
            return cachedMessages;
        }
        
        // 从服务器加载聊天记录
        const response = await fetch(`/api/chat/history?chat_id=${chatId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            }
        });
        
        if (!response.ok) {
            // 如果API调用失败，尝试从本地JSON文件加载
            return loadChatHistoryFromFile(chatId);
        }
        
        const data = await response.json();
        
        if (data.success && data.messages) {
            // 更新内存中的消息缓存
            messages[chatId] = data.messages;
            return data.messages;
        } else {
            // API返回成功但没有消息，尝试从本地加载
            return loadChatHistoryFromFile(chatId);
        }
    } catch (error) {
        console.error('加载聊天历史失败:', error);
        return loadChatHistoryFromFile(chatId);
    }
}

/**
 * 从本地JSON文件加载聊天记录
 * @param {string} chatId - 聊天ID
 * @returns {Promise<Array>} 消息数组
 */
async function loadChatHistoryFromFile(chatId) {
    try {
        const response = await fetch(`${CHAT_STORAGE_PREFIX}${chatId}.json`);
        
        if (!response.ok) {
            // 文件不存在或无法访问，返回空数组
            messages[chatId] = [];
            return [];
        }
        
        const chatData = await response.json();
        
        // 更新内存中的消息缓存
        messages[chatId] = chatData.messages || [];
        return messages[chatId];
    } catch (error) {
        console.error('从文件加载聊天记录失败:', error);
        messages[chatId] = [];
        return [];
    }
}

/**
 * 保存聊天记录
 * @param {string} chatId - 聊天ID
 * @param {Array} messageList - 消息列表
 */
async function saveChatHistory(chatId, messageList) {
    if (!messageList || messageList.length === 0) return;
    
    try {
        // 准备要保存的数据
        const chatData = {
            chat_id: chatId,
            last_updated: new Date().toISOString(),
            messages: messageList
        };
        
        // 保存到服务器
        const response = await fetch('/api/chat/history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: JSON.stringify(chatData)
        });
        
        if (!response.ok) {
            console.warn('服务器保存聊天记录失败，将尝试保存到本地');
            await saveChatHistoryToFile(chatId, messageList);
        }
    } catch (error) {
        console.error('保存聊天记录失败:', error);
        // 如果服务器保存失败，尝试保存到本地文件
        await saveChatHistoryToFile(chatId, messageList);
    }
}

/**
 * 保存聊天记录到本地JSON文件
 * @param {string} chatId - 聊天ID
 * @param {Array} messageList - 消息列表
 */
async function saveChatHistoryToFile(chatId, messageList) {
    try {
        // 准备要保存的数据
        const chatData = {
            chat_id: chatId,
            last_updated: new Date().toISOString(),
            messages: messageList
        };
        
        // 使用FormData上传JSON文件
        const formData = new FormData();
        const jsonBlob = new Blob([JSON.stringify(chatData, null, 2)], { type: 'application/json' });
        formData.append('file', jsonBlob, `${chatId}.json`);
        formData.append('path', CHAT_STORAGE_PREFIX);
        
        // 上传到服务器
        await fetch('/api/upload/json', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: formData
        });
        
        console.log('聊天记录已保存到本地文件');
    } catch (error) {
        console.error('保存聊天记录到文件失败:', error);
    }
}

/**
 * 格式化日期
 * @param {string|Date} date - 日期对象或日期字符串
 * @returns {string} 格式化后的日期，如：2023年1月1日
 */
function formatDate(date) {
    const d = new Date(date);
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

/**
 * 格式化时间
 * @param {string|Date} time - 时间对象或时间字符串
 * @returns {string} 格式化后的时间，如：12:30
 */
function formatTime(time) {
    const d = new Date(time);
    const hours = d.getHours().toString().padStart(2, '0');
    const minutes = d.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

/**
 * 创建消息元素
 * @param {Object} message - 消息对象
 * @returns {HTMLElement} 消息DOM元素
 */
function createMessageElement(message) {
    const messageDiv = document.createElement('div');
    
    // 确定是否为当前用户发送的消息
    const isSentByCurrentUser = message.sender === currentUser.id || message.sender_id === currentUser.id;
    messageDiv.className = `message ${isSentByCurrentUser ? 'sent' : 'received'}`;
    
    // 设置消息ID和发送者ID属性
    if (message.id) {
        messageDiv.dataset.id = message.id;
    }
    messageDiv.dataset.senderId = message.sender || message.sender_id;
    
    // 获取发送者信息
    let sender = null;
    if (isSentByCurrentUser) {
        sender = currentUser;
    } else {
        // 尝试在所有可能的用户列表中找到发送者
        sender = [...onlineUsers, ...recentContacts].find(u => u.id === message.sender || u.id === message.sender_id);
    }
    
    // 发送者头像 - 使用正确的头像路径
    let avatarUrl = '/src/images/avtar.jpg';
    if (sender && sender.avatar) {
        // 确保头像路径正确
        if (sender.avatar.startsWith('http')) {
            avatarUrl = sender.avatar;
        } else {
            avatarUrl = sender.avatar.startsWith('/') ? sender.avatar : `/${sender.avatar}`;
        }
    }
    
    // 构建消息内容
    let contentHTML = '';
    
    // 检查是否包含引用
    let quoteHtml = '';
    if (message.content && message.content.startsWith('> ')) {
        // 提取引用部分
        const lines = message.content.split('\n\n');
        if (lines.length > 1 && lines[0].startsWith('> ')) {
            const quotedLine = lines[0].substring(2); // 移除 "> " 前缀
            const actualContent = lines.slice(1).join('\n\n');
            
            quoteHtml = `<div class="quoted-message">${quotedLine}</div>`;
            message.content = actualContent; // 更新消息内容为非引用部分
        }
    }
    
    switch (message.type || message.message_type) {
        case 'text':
            contentHTML = `${quoteHtml}<div class="text">${message.content}</div>`;
            break;
        case 'emoji':
            contentHTML = `${quoteHtml}<div class="emoji">${message.content}</div>`;
            break;
        case 'image':
            contentHTML = `${quoteHtml}<div class="image-content"><img src="${message.content}" alt="图片消息" loading="lazy"></div>`;
            break;
        case 'voice':
            contentHTML = `${quoteHtml}
                <div class="voice-content">
                    <button><i class="fas fa-play"></i></button>
                    <span class="duration">${message.duration || '0'}秒</span>
                </div>
            `;
            break;
        case 'kunbi':
            contentHTML = `${quoteHtml}
                <div class="kunbi-content">
                    <div class="kunbi-header">
                        <i class="fas fa-coins"></i>
                        <div class="kunbi-title">坤币红包</div>
                    </div>
                    <div class="kunbi-message">${message.content}</div>
                    <div class="kunbi-action">${isSentByCurrentUser ? '已发送' : '点击领取'}</div>
                </div>
            `;
            break;
        default:
            contentHTML = `${quoteHtml}<div class="text">${message.content}</div>`;
    }
    
    // 构建完整消息
    messageDiv.innerHTML = `
        <div class="avatar">
            <img src="${avatarUrl}" alt="${sender ? (sender.nickname || sender.username) : '未知用户'}" loading="lazy" onerror="this.src='/src/images/avtar.jpg'">
        </div>
        <div class="content">
            ${currentChat.type === 'group' && !isSentByCurrentUser ? `<div class="sender" data-user-id="${message.sender || message.sender_id}">${sender ? (sender.nickname || sender.username) : '未知用户'}</div>` : ''}
            ${contentHTML}
            <div class="time">${formatTime(message.timestamp || message.created_at)}</div>
        </div>
    `;
    
    return messageDiv;
}

/**
 * 发送消息
 */
function sendMessage() {
    // 获取消息内容
    const messageInput = document.getElementById('message-input');
    const messageContent = messageInput.value.trim();
    
    // 如果消息为空，不发送
    if (!messageContent) {
        return;
    }
    
    // 检查是否有当前聊天
    if (!currentChat.type || !currentChat.id) {
        showToast('请先选择一个聊天', 'warning');
        return;
    }
    
    // 创建新消息对象
    const newMessage = {
        id: Date.now(), // 使用时间戳作为临时ID
        sender: currentUser.id,
        sender_id: currentUser.id,
        type: 'text',
        message_type: 'text',
        content: messageContent,
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString()
    };
    
    // 清空输入框
    messageInput.value = '';
    
    try {
        // 根据聊天类型设置接收者
        let chatId = '';
        
        if (currentChat.type === 'user') {
            newMessage.receiver = currentChat.id;
            newMessage.receiver_id = currentChat.id;
            
            // 生成聊天ID - 确保双向通信用同一个ID
            const ids = [currentUser.id, currentChat.id].sort((a, b) => a - b);
            chatId = `user_${ids[0]}_${ids[1]}`;
            
            // 更新或创建聊天记录
            if (!messages[chatId]) {
                messages[chatId] = [];
            }
            messages[chatId].push(newMessage);
            
            // 使用Socket.IO发送私聊消息
            if (window.socket && window.socket.connected) {
                try {
                    // 使用特定的私聊事件发送
                    window.socket.emit('private_message', {
                        sender: currentUser.id,
                        receiver: currentChat.id,
                        message: messageContent,
                        type: 'text',
                        chat_id: chatId,
                        id: newMessage.id,
                        timestamp: newMessage.timestamp
                    });
                    
                    console.log('私聊消息已通过WebSocket发送');
                    
                    // 保存聊天记录到JSON
                    saveChatHistory(chatId, messages[chatId]);
                } catch (err) {
                    console.error('WebSocket发送失败:', err);
                    // 使用API作为备用
                    sendMessageAPI(newMessage, chatId);
                }
            } else {
                console.warn('WebSocket未连接，使用API发送消息');
                // 使用API发送消息（备用方案）
                sendMessageAPI(newMessage, chatId);
            }
            
            // 添加消息到当前界面
            const messagesContainer = document.getElementById('messages-container');
            const messageElement = createMessageElement(newMessage);
            messagesContainer.appendChild(messageElement);
            
            // 平滑滚动到底部
            messagesContainer.scrollTo({
                top: messagesContainer.scrollHeight,
                behavior: 'smooth'
            });
        } else if (currentChat.type === 'group') {
            // 群组消息处理逻辑保持不变
            newMessage.group = currentChat.id;
            newMessage.group_id = currentChat.id;
            
            // 生成群聊ID
            chatId = `group_${currentChat.id}`;
            
            // 更新群组聊天记录
            if (!messages[chatId]) {
                messages[chatId] = [];
            }
            messages[chatId].push(newMessage);
            
            // 保存聊天记录
            saveChatHistory(chatId, messages[chatId]);
            
            // 显示发送成功的提示
            showToast('消息已发送', 'success');
            
            // 使用Socket.IO发送群组消息，如果可用
            if (window.socket && window.socket.connected) {
                try {
                    window.socket.emit('message', {
                        room: `group_${currentChat.id}`,
                        message: messageContent,
                        sender: currentUser.id,
                        group: currentChat.id,
                        type: 'text',
                        chat_id: chatId,
                        id: newMessage.id,
                        timestamp: newMessage.timestamp,
                        created_at: newMessage.created_at
                    });
                    
                    console.log('群组消息已通过WebSocket发送');
                } catch (err) {
                    console.error('WebSocket发送失败:', err);
                    sendMessageAPI(newMessage, chatId);
                }
            } else {
                console.warn('WebSocket未连接，使用API发送群组消息');
                sendMessageAPI(newMessage, chatId);
            }
            
            // 添加消息到当前界面
            const messagesContainer = document.getElementById('messages-container');
            const messageElement = createMessageElement(newMessage);
            messagesContainer.appendChild(messageElement);
            
            // 平滑滚动到底部
            messagesContainer.scrollTo({
                top: messagesContainer.scrollHeight,
                behavior: 'smooth'
            });
        }
    } catch (error) {
        console.error('发送消息失败', error);
        showToast('发送消息失败，请重试', 'error');
    }
}

/**
 * 通过API发送消息（WebSocket不可用时的备用方案）
 * @param {Object} message - 消息对象
 * @param {string} chatId - 聊天ID
 */
async function sendMessageAPI(message, chatId) {
    try {
        const response = await fetch('/api/chat/messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: JSON.stringify({
                ...message,
                chat_id: chatId
            })
        });
        
        if (!response.ok) {
            throw new Error('发送消息失败');
        }
        
        const data = await response.json();
        console.log('消息API响应:', data);
    } catch (error) {
        console.error('API发送消息失败:', error);
        // 即使API失败，UI已经更新，所以不回滚UI更新
    }
}

/**
 * 切换表情选择器显示
 */
function toggleEmojiPicker() {
    const emojiModal = document.getElementById('emoji-modal');
    emojiModal.classList.toggle('active');
    
    // 如果表情选择器为空，加载表情
    const emojiContainer = document.getElementById('emoji-container');
    if (emojiContainer && emojiContainer.children.length === 0) {
        // 常用表情
        const commonEmojis = ['😀', '😁', '😂', '🤣', '😃', '😄', '😅', '😆', '😉', '😊', 
                             '😋', '😎', '😍', '😘', '🥰', '😗', '😙', '😚', '☺️', '🙂',
                             '🤔', '🤨', '😐', '😑', '😶', '🙄', '😏', '😣', '😥', '😮',
                             '🤐', '😯', '😪', '😫', '🥱', '😴', '😌', '😛', '😜', '😝',
                             '🤤', '😒', '😓', '😔', '😕', '🙃', '🤑', '😲', '☹️', '🙁',
                             '😖', '😞', '😟', '😤', '😢', '😭', '😦', '😧', '😨', '😩',
                             '🤯', '😬', '😰', '😱', '🥵', '🥶', '😳', '🤪', '😵', '🥴'];
        
        // 创建表情元素
        commonEmojis.forEach(emoji => {
            const emojiItem = document.createElement('div');
            emojiItem.className = 'emoji-item';
            emojiItem.textContent = emoji;
            emojiItem.addEventListener('click', () => insertEmoji(emoji));
            emojiContainer.appendChild(emojiItem);
        });
    }
}

/**
 * 插入表情到输入框
 * @param {string} emoji - 表情字符
 */
function insertEmoji(emoji) {
    const messageInput = document.getElementById('message-input');
    messageInput.value += emoji;
    messageInput.focus();
    
    // 关闭表情选择器
    document.getElementById('emoji-modal').classList.remove('active');
}

/**
 * 发送坤币红包
 */
function sendKunbi() {
    // 获取坤币数量和留言
    const kunbiAmount = parseInt(document.getElementById('kunbi-amount').value);
    const kunbiMessage = document.getElementById('kunbi-message').value.trim() || '恭喜发财，大吉大利';
    
    // 验证坤币数量
    if (isNaN(kunbiAmount) || kunbiAmount <= 0) {
        showToast('请输入有效的坤币数量', 'error');
        return;
    }
    
    // 检查坤币余额
    if (kunbiAmount > currentUser.kunbi) {
        showToast('坤币余额不足', 'error');
        return;
    }
    
    // 检查是否有当前聊天
    if (!currentChat.type || !currentChat.id) {
        showToast('请先选择一个聊天', 'warning');
        return;
    }
    
    // 创建新坤币红包消息
    const newKunbiMessage = {
        id: Date.now(),
        sender: currentUser.id,
        type: 'kunbi',
        content: kunbiMessage,
        amount: kunbiAmount,
        timestamp: new Date()
    };
    
    // 根据聊天类型设置接收者
    if (currentChat.type === 'user') {
        newKunbiMessage.receiver = currentChat.id;
        
        // 更新或创建聊天记录
        const chatKey = `user_${currentUser.id}_${currentChat.id}`;
        if (!messages[chatKey]) {
            messages[chatKey] = [];
        }
        messages[chatKey].push(newKunbiMessage);
    } else if (currentChat.type === 'group') {
        newKunbiMessage.group = currentChat.id;
        
        // 更新群组聊天记录
        const chatKey = `group_${currentChat.id}`;
        if (!messages[chatKey]) {
            messages[chatKey] = [];
        }
        messages[chatKey].push(newKunbiMessage);
    }
    
    // 扣除用户坤币
    currentUser.kunbi -= kunbiAmount;
    document.getElementById('user-kunbi').textContent = `坤币: ${currentUser.kunbi}`;
    
    // 关闭坤币模态框
    document.getElementById('kunbi-modal').classList.remove('active');
    
    // 重置坤币表单
    document.getElementById('kunbi-amount').value = '10';
    document.getElementById('kunbi-message').value = '';
    
    // 添加消息到当前界面
    const messagesContainer = document.getElementById('messages-container');
    const messageElement = createMessageElement(newKunbiMessage);
    messagesContainer.appendChild(messageElement);
    
    // 平滑滚动到底部
    messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth'
    });
    
    // 播放发送红包音效
    playSendKunbiSound();
    
    // 显示发送成功动画
    showKunbiSendAnimation();
    
    // 显示成功提示
    showToast('坤币红包发送成功', 'success');
}

/**
 * 播放发送红包音效
 */
function playSendKunbiSound() {
    try {
        const audio = new Audio('/images/sounds/send_kunbi.mp3');
        audio.play().catch(e => console.log('无法播放音效', e));
    } catch (e) {
        console.log('播放音效失败', e);
    }
}

/**
 * 显示发送红包动画
 */
function showKunbiSendAnimation() {
    // 创建动画元素
    const animationEl = document.createElement('div');
    animationEl.className = 'kunbi-send-animation';
    animationEl.innerHTML = `
        <img src="/images/red-packet.png" alt="红包" 
             style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                    width: 100px; height: auto; z-index: 9999; opacity: 0;">
    `;
    document.body.appendChild(animationEl);
    
    // 获取图片元素
    const img = animationEl.querySelector('img');
    
    // 应用动画
    img.animate([
        { opacity: 0, transform: 'translate(-50%, -50%) scale(0.5)' },
        { opacity: 1, transform: 'translate(-50%, -50%) scale(1.2)' },
        { opacity: 1, transform: 'translate(-50%, -50%) scale(1.0)' },
        { opacity: 0, transform: 'translate(-50%, -50%) scale(2.0)' }
    ], {
        duration: 1000,
        easing: 'ease-in-out'
    }).onfinish = () => {
        // 动画结束后移除元素
        document.body.removeChild(animationEl);
    };
}

/**
 * 切换坤币模态框显示
 */
function toggleKunbiModal() {
    const kunbiModal = document.getElementById('kunbi-modal');
    kunbiModal.classList.toggle('active');
    
    if (kunbiModal.classList.contains('active')) {
        // 模态框显示时，聚焦金额输入框
        setTimeout(() => {
            document.getElementById('kunbi-amount').focus();
        }, 300);
    }
}

/**
 * 处理坤币红包点击
 * @param {HTMLElement} kunbiContent - 坤币红包元素
 */
function handleKunbiClick(kunbiContent) {
    // 如果是自己发送的红包，不响应点击
    const message = kunbiContent.closest('.message');
    if (message.classList.contains('sent')) {
        return;
    }
    
    // 如果红包已经打开，不响应点击
    if (kunbiContent.classList.contains('kunbi-opened')) {
        return;
    }
    
    // 添加打开动画类
    kunbiContent.classList.add('kunbi-opening');
    
    // 延迟300ms后更新红包状态
    setTimeout(() => {
        // 移除打开动画类
        kunbiContent.classList.remove('kunbi-opening');
        
        // 添加已打开类
        kunbiContent.classList.add('kunbi-opened');
        
        // 随机生成领取的坤币数量 (1-30之间)
        const amount = Math.floor(Math.random() * 30) + 1;
        
        // 更新红包信息
        const actionElement = kunbiContent.querySelector('.kunbi-action');
        if (actionElement) {
            actionElement.textContent = `已领取 ${amount} 坤币`;
            actionElement.classList.add('kunbi-received');
        }
        
        // 更新用户坤币数量
        currentUser.kunbi += amount;
        document.getElementById('user-kunbi').textContent = `坤币: ${currentUser.kunbi}`;
        
        // 显示提示
        showToast(`恭喜！您领取了 ${amount} 坤币`, 'success');
        
        // 播放音效 (如果有)
        playKunbiSound();
        
    }, 300);
}

/**
 * 播放坤币音效
 */
function playKunbiSound() {
    // 如果有音效文件，可以在这里播放
    try {
        const audio = new Audio('/images/sounds/kunbi.mp3');
        audio.play().catch(e => console.log('无法播放音效', e));
    } catch (e) {
        console.log('播放音效失败', e);
    }
}

/**
 * 更新用户状态
 * @param {number} userId - 用户ID
 * @param {boolean} isOnline - 是否在线
 */
function updateUserStatus(userId, isOnline) {
    // 更新本地数据中的用户状态
    const status = isOnline ? 'online' : 'offline';
    
    // 更新在线用户列表
    const userIndex = onlineUsers.findIndex(user => user.id === userId);
    if (userIndex !== -1) {
        onlineUsers[userIndex].status = status;
        onlineUsers[userIndex].online = isOnline;
    }
    
    // 更新最近联系人列表
    const contactIndex = recentContacts.findIndex(contact => contact.id === userId);
    if (contactIndex !== -1) {
        recentContacts[contactIndex].status = status;
        recentContacts[contactIndex].online = isOnline;
    }
    
    // 如果用户在一个列表中但不在另一个列表中，需要确保添加到在线用户列表
    if (isOnline && userIndex === -1 && contactIndex !== -1) {
        // 找到了联系人但不在在线用户列表中
        const contact = recentContacts[contactIndex];
        onlineUsers.push({
            id: contact.id,
            username: contact.username,
            nickname: contact.nickname,
            avatar: contact.avatar,
            status: 'online',
            online: true
        });
    }
    
    // 排序在线用户列表（在线用户优先）
    onlineUsers.sort((a, b) => {
        if ((a.status === 'online' || a.online) && (b.status !== 'online' && !b.online)) return -1;
        if ((a.status !== 'online' && !a.online) && (b.status === 'online' || b.online)) return 1;
        return 0;
    });
    
    // 重新渲染列表
    renderOnlineUsers();
    renderRecentContacts();
    
    // 如果当前正在与该用户聊天，更新聊天标题
    if (currentChat.type === 'user' && currentChat.id === userId) {
        document.getElementById('chat-subtitle').textContent = isOnline ? '在线' : '离线';
    }
    
    // 存储最新的用户状态到sessionStorage，确保页面刷新后状态保持
    try {
        const userStatuses = JSON.parse(sessionStorage.getItem('userStatuses') || '{}');
        userStatuses[userId] = isOnline;
        sessionStorage.setItem('userStatuses', JSON.stringify(userStatuses));
    } catch (e) {
        console.error('存储用户状态失败', e);
    }
}

/**
 * 接收新消息
 * @param {Object} message - 消息对象
 */
function receiveMessage(message) {
    // 确保消息有正确的格式和必要的字段
    if (!message) return;
    
    // 确保消息有内容
    if (!message.content) {
        console.warn('收到空消息内容:', message);
        return;
    }
    
    // 过滤自己发送的消息(通过socket回传的)
    if (message.sender === currentUser.id && !message._forceProcess) {
        console.log('过滤自己发送的消息:', message);
        return;
    }
    
    // 生成聊天ID
    let chatId = '';
    
    if (message.group || message.group_id) {
        // 群组消息
        const groupId = message.group || message.group_id;
        chatId = generateChatId('group', currentUser.id, groupId);
    } else {
        // 私人消息 - 这里确保双向通信使用同一个chatId
        const senderId = message.sender || message.sender_id;
        const receiverId = message.receiver || message.receiver_id || currentUser.id;
        
        // 使用较小的ID作为前缀，确保双向一致
        chatId = `user_${Math.min(senderId, receiverId)}_${Math.max(senderId, receiverId)}`;
    }
    
    // 检查消息是否已存在（防止重复）
    if (!messages[chatId]) {
        messages[chatId] = [];
    }
    
    // 检查是否为重复消息
    const isDuplicate = messages[chatId].some(m => 
        m.id === message.id || 
        (m.sender === message.sender && 
         m.content === message.content && 
         Math.abs(new Date(m.timestamp) - new Date(message.timestamp)) < 1000)
    );
    
    if (isDuplicate) {
        console.log('跳过重复消息:', message);
        return;
    }
    
    // 确保消息有时间戳
    if (!message.timestamp && !message.created_at) {
        message.timestamp = new Date();
        message.created_at = new Date().toISOString();
    }
    
    // 检查当前是否正在与发送者聊天
    const isCurrentChat = (
        (currentChat.type === 'user' && 
         (currentChat.id === (message.sender || message.sender_id))) || 
        (currentChat.type === 'group' && 
         (currentChat.id === (message.group || message.group_id)))
    );
    
    // 添加消息到对应的聊天记录
    messages[chatId].push(message);
    
    // 保存聊天记录
    saveChatHistory(chatId, messages[chatId]);
    
    // 更新未读数量和联系人列表
    if (message.group || message.group_id) {
        // 群组消息
        const groupId = message.group || message.group_id;
        
        // 更新未读数量
        if (!isCurrentChat) {
            const groupIndex = groups.findIndex(g => g.id === groupId);
            if (groupIndex !== -1) {
                groups[groupIndex].unreadCount = (groups[groupIndex].unreadCount || 0) + 1;
                renderGroups();
            }
        }
    } else {
        // 私人消息 - 更新最近联系人
        const senderId = message.sender || message.sender_id;
        
        // 确保不是自己发给自己的消息
        if (senderId === currentUser.id) return;
        
        const sender = [...onlineUsers, ...recentContacts].find(u => u.id === senderId);
        
        if (sender && !isCurrentChat) {
            // 查找此人是否已在最近联系人中
            const contactIndex = recentContacts.findIndex(c => c.id === senderId);
            
            if (contactIndex !== -1) {
                // 已在列表中，更新最后消息
                recentContacts[contactIndex].lastMessage = message.content;
                recentContacts[contactIndex].lastTime = new Date(message.timestamp || message.created_at);
            } else {
                // 不在列表中，添加到最近联系人
                recentContacts.push({
                    id: senderId,
                    username: sender.username,
                    nickname: sender.nickname,
                    avatar: sender.avatar || '/src/images/avtar.jpg',
                    online: sender.online || sender.status === 'online',
                    lastMessage: message.content,
                    lastTime: new Date(message.timestamp || message.created_at)
                });
            }
            
            // 重新渲染最近联系人
            renderRecentContacts();
        }
    }
    
    // 如果当前正在与发送者聊天，直接显示消息
    if (isCurrentChat) {
        const messagesContainer = document.getElementById('messages-container');
        const messageElement = createMessageElement(message);
        messagesContainer.appendChild(messageElement);
        
        // 平滑滚动到底部
        messagesContainer.scrollTo({
            top: messagesContainer.scrollHeight,
            behavior: 'smooth'
        });
        
        // 播放消息提示音
        playMessageSound();
    } else {
        // 显示通知
        showNotification(message);
    }
}

/**
 * 播放消息提示音
 */
function playMessageSound() {
    try {
        const audio = new Audio('/images/sounds/message.mp3');
        audio.volume = 0.5;
        audio.play().catch(e => console.log('无法播放提示音', e));
    } catch (e) {
        console.log('播放提示音失败', e);
    }
}

/**
 * 显示通知
 * @param {Object} message - 消息对象
 */
function showNotification(message) {
    // 检查通知权限
    if (!("Notification" in window)) {
        console.log("浏览器不支持通知");
        return;
    }
    
    // 如果已经有权限，直接发送通知
    if (Notification.permission === "granted") {
        createNotification(message);
    }
    // 否则请求权限
    else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function (permission) {
            if (permission === "granted") {
                createNotification(message);
            }
        });
    }
}

/**
 * 创建通知
 * @param {Object} message - 消息对象
 */
function createNotification(message) {
    // 查找发送者信息
    let sender = null;
    let avatar = '/images/default-avatar.png';
    let title = '';
    let body = '';
    
    if (message.group) {
        // 群组消息
        const group = groups.find(g => g.id === message.group);
        if (group) {
            title = `${group.name}`;
            avatar = group.avatar;
        }
        
        // 查找发送者
        sender = onlineUsers.find(u => u.id === message.sender);
        if (sender) {
            body = `${sender.nickname}: ${message.content}`;
        } else {
            body = message.content;
        }
    } else {
        // 私人消息
        sender = onlineUsers.find(u => u.id === message.sender);
        if (sender) {
            title = sender.nickname;
            avatar = sender.avatar;
            body = message.content;
        }
    }
    
    // 创建通知
    const notification = new Notification(title, {
        body: body,
        icon: avatar
    });
    
    // 通知点击事件
    notification.onclick = function() {
        window.focus();
        if (message.group) {
            openChatWithGroup(message.group);
        } else {
            openChatWithUser(message.sender);
        }
    };
    
    // 通知会在5秒后自动关闭
    setTimeout(() => {
        notification.close();
    }, 5000);
}

/**
 * 显示创建群组模态框
 */
function showCreateGroupModal() {
    // 检查是否已存在模态框，如果不存在则创建
    let createGroupModal = document.getElementById('create-group-modal');
    
    if (!createGroupModal) {
        // 创建模态框
        createGroupModal = document.createElement('div');
        createGroupModal.id = 'create-group-modal';
        createGroupModal.className = 'modal';
        
        createGroupModal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>创建新群聊</h3>
                    <button class="close-btn"><i class="fas fa-times"></i></button>
                </div>
                <div class="group-form">
                    <div class="form-group avatar-upload">
                        <label>群组头像</label>
                        <div class="avatar-preview">
                            <img id="group-avatar-preview" src="/src/images/default-group.png" alt="群组头像">
                            <div class="avatar-upload-btn">
                                <i class="fas fa-camera"></i>
                                <input type="file" id="group-avatar-upload" accept="image/*">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="group-name">群组名称</label>
                        <input type="text" id="group-name" placeholder="输入群组名称" required>
                    </div>
                    <div class="form-group">
                        <label for="group-description">群组描述</label>
                        <textarea id="group-description" placeholder="输入群组描述（可选）"></textarea>
                    </div>
                    <div class="form-group">
                        <label>选择成员</label>
                        <div class="member-selection" id="member-selection">
                            <div class="loading-members">加载成员中...</div>
                        </div>
                    </div>
                    <button class="btn primary" id="confirm-create-group">创建群聊</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(createGroupModal);
        
        // 添加关闭按钮事件
        createGroupModal.querySelector('.close-btn').addEventListener('click', function() {
            createGroupModal.classList.remove('active');
        });
        
        // 添加头像上传事件
        const avatarUpload = createGroupModal.querySelector('#group-avatar-upload');
        if (avatarUpload) {
            avatarUpload.addEventListener('change', handleGroupAvatarUpload);
        }
        
        // 添加创建群组按钮事件
        createGroupModal.querySelector('#confirm-create-group').addEventListener('click', createGroup);
        
        // 加载可选成员
        loadMembersForSelection();
    }
    
    // 显示模态框
    createGroupModal.classList.add('active');
}

/**
 * 处理群组头像上传
 * @param {Event} event - 上传事件
 */
function handleGroupAvatarUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 验证文件类型
    if (!file.type.match('image.*')) {
        showToast('请上传图片文件', 'error');
        return;
    }
    
    // 验证文件大小（最大2MB）
    if (file.size > 2 * 1024 * 1024) {
        showToast('图片大小不能超过2MB', 'error');
        return;
    }
    
    // 读取文件并预览
    const reader = new FileReader();
    reader.onload = function(e) {
        const preview = document.getElementById('group-avatar-preview');
        if (preview) {
            preview.src = e.target.result;
        }
    };
    
    reader.readAsDataURL(file);
}

/**
 * 上传用户头像
 */
function uploadUserAvatar() {
    // 创建头像上传模态框
    let avatarModal = document.getElementById('avatar-upload-modal');
    
    if (!avatarModal) {
        avatarModal = document.createElement('div');
        avatarModal.id = 'avatar-upload-modal';
        avatarModal.className = 'modal';
        
        avatarModal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>上传头像</h3>
                    <button class="close-btn"><i class="fas fa-times"></i></button>
                </div>
                <div class="avatar-form">
                    <div class="avatar-preview-container">
                        <img id="user-avatar-preview" src="${currentUser.avatar || '/src/images/avtar.jpg'}" alt="头像预览">
                    </div>
                    <div class="avatar-upload-controls">
                        <input type="file" id="user-avatar-upload" accept="image/*" style="display: none;">
                        <button id="select-avatar-btn" class="btn secondary">选择图片</button>
                        <button id="confirm-avatar-btn" class="btn primary">确认上传</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(avatarModal);
        
        // 添加关闭按钮事件
        avatarModal.querySelector('.close-btn').addEventListener('click', function() {
            avatarModal.classList.remove('active');
        });
        
        // 选择图片按钮事件
        const selectBtn = avatarModal.querySelector('#select-avatar-btn');
        const fileInput = avatarModal.querySelector('#user-avatar-upload');
        
        selectBtn.addEventListener('click', function() {
            fileInput.click();
        });
        
        // 文件选择事件
        fileInput.addEventListener('change', handleUserAvatarSelect);
        
        // 确认上传按钮事件
        avatarModal.querySelector('#confirm-avatar-btn').addEventListener('click', confirmUserAvatarUpload);
    }
    
    // 显示模态框
    avatarModal.classList.add('active');
}

/**
 * 处理用户头像选择
 * @param {Event} event - 文件选择事件
 */
function handleUserAvatarSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 验证文件类型
    if (!file.type.match('image.*')) {
        showToast('请上传图片文件', 'error');
        return;
    }
    
    // 验证文件大小（最大2MB）
    if (file.size > 2 * 1024 * 1024) {
        showToast('图片大小不能超过2MB', 'error');
        return;
    }
    
    // 读取文件并预览
    const reader = new FileReader();
    reader.onload = function(e) {
        const preview = document.getElementById('user-avatar-preview');
        if (preview) {
            preview.src = e.target.result;
        }
    };
    
    reader.readAsDataURL(file);
}

/**
 * 确认上传用户头像
 */
async function confirmUserAvatarUpload() {
    const fileInput = document.getElementById('user-avatar-upload');
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('请先选择头像图片', 'warning');
        return;
    }
    
    const uploadBtn = document.getElementById('confirm-avatar-btn');
    const originalBtnText = uploadBtn.textContent;
    uploadBtn.disabled = true;
    uploadBtn.textContent = '上传中...';
    
    try {
        // 创建FormData对象
        const formData = new FormData();
        formData.append('avatar', file);
        formData.append('path', '/src/images/');
        formData.append('filename', `user_${currentUser.id}_${Date.now()}.png`);
        
        // 上传头像
        const response = await fetch('/api/user/avatar', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('头像上传失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            // 更新用户头像
            currentUser.avatar = data.avatar_url;
            
            // 更新本地存储的用户信息
            const userInfo = JSON.parse(localStorage.getItem('fuckchat_user') || '{}');
            userInfo.avatar = data.avatar_url;
            localStorage.setItem('fuckchat_user', JSON.stringify(userInfo));
            
            // 更新界面显示
            const userAvatarImg = document.getElementById('user-avatar');
            if (userAvatarImg) {
                userAvatarImg.src = data.avatar_url;
            }
            
            // 关闭模态框
            document.getElementById('avatar-upload-modal').classList.remove('active');
            
            // 显示成功提示
            showToast('头像上传成功', 'success');
        } else {
            showToast(data.message || '头像上传失败', 'error');
        }
    } catch (error) {
        console.error('头像上传失败:', error);
        showToast('头像上传失败，请稍后再试', 'error');
    } finally {
        // 恢复按钮状态
        uploadBtn.disabled = false;
        uploadBtn.textContent = originalBtnText;
    }
}

/**
 * 创建头像上传服务器端点（如果不存在）
 * 此函数会检查是否有上传头像的接口，如果不存在会创建一个简易的实现
 */
async function setupAvatarUploadEndpoint() {
    try {
        // 检查用户头像上传端点
        const response = await fetch('/api/user/avatar', {
            method: 'OPTIONS'
        });
        
        if (response.status === 404) {
            console.warn('用户头像上传端点不存在，创建一个简易的实现');
            
            // 创建简易的文件上传处理
            document.addEventListener('submit', function(e) {
                const form = e.target;
                
                if (form.action.includes('/api/user/avatar') || form.action.includes('/api/upload/')) {
                    e.preventDefault();
                    
                    // 获取文件
                    const fileInput = form.querySelector('input[type="file"]');
                    if (!fileInput || !fileInput.files[0]) return;
                    
                    const file = fileInput.files[0];
                    
                    // 读取文件
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        // 这里可以实现将文件保存到服务器的逻辑
                        console.log('文件已读取:', file.name, file.size);
                        
                        // 模拟上传成功
                        const uploadPath = '/src/images/' + file.name;
                        
                        // 返回成功消息
                        const successEvent = new CustomEvent('uploadSuccess', {
                            detail: {
                                success: true,
                                avatar_url: uploadPath
                            }
                        });
                        document.dispatchEvent(successEvent);
                    };
                    
                    reader.readAsDataURL(file);
                }
            });
        }
    } catch (error) {
        console.error('检查头像上传端点失败:', error);
    }
}

// 初始化时添加用户头像点击事件
function addUserAvatarClickEvent() {
    const userAvatar = document.getElementById('user-avatar');
    if (userAvatar) {
        userAvatar.addEventListener('click', uploadUserAvatar);
    }
}

/**
 * 搜索用户
 * @param {string} keyword - 搜索关键词
 */
function searchUsers(keyword) {
    keyword = keyword.trim().toLowerCase();
    
    // 如果关键词为空，恢复原始列表
    if (!keyword) {
        renderOnlineUsers();
        renderRecentContacts();
        return;
    }
    
    // 创建一个复制的用户列表用于搜索
    const allUsers = [...onlineUsers, ...recentContacts].filter((user, index, self) => 
        index === self.findIndex(u => u.id === user.id)
    );
    
    // 过滤匹配的用户
    const matchedUsers = allUsers.filter(user => 
        (user.username && user.username.toLowerCase().includes(keyword)) || 
        (user.nickname && user.nickname.toLowerCase().includes(keyword))
    );
    
    // 显示搜索结果
    displaySearchResults(matchedUsers, 'users');
}

/**
 * 搜索群组
 * @param {string} keyword - 搜索关键词
 */
function searchGroups(keyword) {
    keyword = keyword.trim().toLowerCase();
    
    // 如果关键词为空，恢复原始列表
    if (!keyword) {
        renderGroups();
        return;
    }
    
    // 过滤匹配的群组
    const matchedGroups = groups.filter(group => 
        (group.name && group.name.toLowerCase().includes(keyword)) || 
        (group.description && group.description.toLowerCase().includes(keyword))
    );
    
    // 显示搜索结果
    displaySearchResults(matchedGroups, 'groups');
}

/**
 * 显示搜索结果
 * @param {Array} results - 搜索结果
 * @param {string} type - 结果类型，'users' 或 'groups'
 */
function displaySearchResults(results, type) {
    if (type === 'users') {
        const onlineUsersList = document.getElementById('online-users');
        const recentContactsList = document.getElementById('recent-contacts');
        
        // 清空列表
        onlineUsersList.innerHTML = '';
        recentContactsList.innerHTML = '';
        
        // 添加搜索结果标题
        const searchHeader = document.createElement('div');
        searchHeader.className = 'search-result-header';
        searchHeader.textContent = `搜索结果 (${results.length})`;
        onlineUsersList.appendChild(searchHeader);
        
        if (results.length === 0) {
            // 无结果
            const noResult = document.createElement('div');
            noResult.className = 'empty-list';
            noResult.textContent = '无匹配结果';
            onlineUsersList.appendChild(noResult);
        } else {
            // 显示匹配结果
            results.forEach(user => {
                const listItem = document.createElement('li');
                listItem.dataset.userId = user.id;
                listItem.addEventListener('click', () => openChatWithUser(user.id));
                
                // 修复头像路径
                const avatarPath = user.avatar || '/images/default-avatar.png';
                const fixedAvatarPath = avatarPath.startsWith('/src/') ? avatarPath.replace('/src/', '/') : avatarPath;
                
                listItem.innerHTML = `
                    <div class="avatar">
                        <img src="${fixedAvatarPath}" alt="${user.nickname}" onerror="this.src='/images/default-avatar.png'">
                    </div>
                    <div class="info">
                        <div class="name">${user.nickname || user.username}</div>
                        <div class="status ${user.status === 'online' || user.online ? 'online' : ''}">${user.status === 'online' || user.online ? '在线' : '离线'}</div>
                    </div>
                `;
                
                onlineUsersList.appendChild(listItem);
            });
        }
    } else if (type === 'groups') {
        const groupsList = document.getElementById('my-groups');
        
        // 清空列表
        groupsList.innerHTML = '';
        
        // 添加搜索结果标题
        const searchHeader = document.createElement('div');
        searchHeader.className = 'search-result-header';
        searchHeader.textContent = `搜索结果 (${results.length})`;
        groupsList.appendChild(searchHeader);
        
        if (results.length === 0) {
            // 无结果
            const noResult = document.createElement('div');
            noResult.className = 'empty-list';
            noResult.textContent = '无匹配结果';
            groupsList.appendChild(noResult);
        } else {
            // 显示匹配结果
            results.forEach(group => {
                const listItem = document.createElement('li');
                listItem.dataset.groupId = group.id;
                listItem.addEventListener('click', () => openChatWithGroup(group.id));
                
                // 修复头像路径
                const avatarPath = group.avatar || '/images/group-avatar.png';
                const fixedAvatarPath = avatarPath.startsWith('/src/') ? avatarPath.replace('/src/', '/') : avatarPath;
                
                listItem.innerHTML = `
                    <div class="avatar">
                        <img src="${fixedAvatarPath}" alt="${group.name}" onerror="this.src='/images/group-avatar.png'">
                    </div>
                    <div class="info">
                        <div class="name">${group.name}</div>
                        <div class="status">${group.member_count || 0}人</div>
                        ${group.description ? `<div class="description">${group.description}</div>` : ''}
                    </div>
                    ${group.unreadCount > 0 ? `<div class="badge">${group.unreadCount}</div>` : ''}
                `;
                
                groupsList.appendChild(listItem);
            });
        }
    }
}

/**
 * 显示消息提示
 * @param {string} message - 提示消息
 * @param {string} type - 提示类型：'success', 'error', 'warning', 'info'
 */
function showToast(message, type = 'info') {
    // 检查是否已存在toast容器
    let toastContainer = document.getElementById('toast-container');
    
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // 设置图标
    let icon = '';
    switch (type) {
        case 'success':
            icon = '<i class="fas fa-check-circle"></i>';
            break;
        case 'error':
            icon = '<i class="fas fa-times-circle"></i>';
            break;
        case 'warning':
            icon = '<i class="fas fa-exclamation-circle"></i>';
            break;
        default:
            icon = '<i class="fas fa-info-circle"></i>';
    }
    
    // 设置内容
    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-message">${message}</div>
    `;
    
    // 添加到容器
    toastContainer.appendChild(toast);
    
    // 显示动画
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // 3秒后自动关闭
    setTimeout(() => {
        toast.classList.remove('show');
        
        // 动画结束后移除元素
        setTimeout(() => {
            toastContainer.removeChild(toast);
        }, 300);
    }, 3000);
}

/**
 * 获取当前用户信息
 */
function getCurrentUser() {
    try {
        const userInfoStr = localStorage.getItem('fuckchat_user');
        if (!userInfoStr) return null;
        
        return JSON.parse(userInfoStr);
    } catch (error) {
        console.error('获取用户信息失败:', error);
        return null;
    }
}

/**
 * 上传文件到服务器
 * @param {File} file - 要上传的文件
 * @param {string} path - 上传路径
 * @param {string} filename - 文件名
 * @returns {Promise<string>} 上传后的文件URL
 */
async function uploadFile(file, path = '/src/images/', filename = null) {
    // 使用当前时间戳和随机数生成唯一文件名
    const targetFilename = filename || `${Date.now()}_${Math.floor(Math.random() * 10000)}_${file.name}`;
    const formData = new FormData();
    
    // 添加文件和路径信息
    formData.append('file', file);
    formData.append('path', path);
    formData.append('filename', targetFilename);
    
    try {
        // 上传文件
        const response = await fetch('/api/upload/file', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('文件上传失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            return data.file_url || `${path}${targetFilename}`;
        } else {
            throw new Error(data.message || '文件上传失败');
        }
    } catch (error) {
        console.error('上传文件失败:', error);
        throw error;
    }
}

/**
 * 创建文件夹（如果不存在）
 * @param {string} path - 文件夹路径
 */
async function createFolderIfNotExists(path) {
    try {
        const response = await fetch('/api/system/create-folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: JSON.stringify({ path })
        });
        
        if (!response.ok) {
            console.warn(`创建文件夹 ${path} 失败，可能已存在`);
        }
    } catch (error) {
        console.error(`创建文件夹失败: ${path}`, error);
    }
}

/**
 * 初始化必要的文件夹
 */
async function initFolders() {
    try {
        // 创建用户头像目录
        await createFolderIfNotExists('/src/images/avatars/');
        
        // 创建群组头像目录
        await createFolderIfNotExists('/src/images/groups/');
        
        // 创建上传文件目录
        await createFolderIfNotExists('/src/images/uploads/');
        
        // 创建聊天数据目录
        await createFolderIfNotExists('/src/chat_data/');
        
        console.log('文件夹初始化完成');
    } catch (error) {
        console.error('初始化文件夹失败:', error);
    }
}

/**
 * 加载可选成员列表
 */
async function loadMembersForSelection() {
    const memberSelectionDiv = document.getElementById('member-selection');
    
    try {
        // 获取所有用户
        const response = await fetch('/api/chat/users', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取用户列表失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            const users = data.users || [];
            
            if (users.length === 0) {
                memberSelectionDiv.innerHTML = '<div class="no-members">没有可选成员</div>';
                return;
            }
            
            // 清空加载提示
            memberSelectionDiv.innerHTML = '';
            
            // 添加自己为第一个选项（已勾选且禁用）
            const currentUserItem = document.createElement('div');
            currentUserItem.className = 'member-item current-user';
            
            // 获取当前用户头像
            let currentUserAvatar = currentUser.avatar || '/src/images/avtar.jpg';
            if (currentUserAvatar && !currentUserAvatar.startsWith('http') && !currentUserAvatar.startsWith('/')) {
                currentUserAvatar = '/' + currentUserAvatar;
            }
            
            currentUserItem.innerHTML = `
                <input type="checkbox" id="member-${currentUser.id}" value="${currentUser.id}" class="member-checkbox" checked disabled>
                <label for="member-${currentUser.id}" class="member-label">
                    <div class="member-avatar">
                        <img src="${currentUserAvatar}" alt="${currentUser.nickname}" onerror="this.src='/src/images/avtar.jpg'">
                    </div>
                    <div class="member-name">${currentUser.nickname || currentUser.username} (我)</div>
                </label>
            `;
            
            memberSelectionDiv.appendChild(currentUserItem);
            
            // 添加其他成员选择框
            users.forEach(user => {
                if (user.id !== currentUser.id) {
                    const memberItem = document.createElement('div');
                    memberItem.className = 'member-item';
                    
                    // 修复头像路径
                    let avatarUrl = user.avatar || '/src/images/avtar.jpg';
                    if (avatarUrl && !avatarUrl.startsWith('http') && !avatarUrl.startsWith('/')) {
                        avatarUrl = '/' + avatarUrl;
                    }
                    
                    memberItem.innerHTML = `
                        <input type="checkbox" id="member-${user.id}" value="${user.id}" class="member-checkbox">
                        <label for="member-${user.id}" class="member-label">
                            <div class="member-avatar">
                                <img src="${avatarUrl}" alt="${user.nickname}" onerror="this.src='/src/images/avtar.jpg'">
                            </div>
                            <div class="member-name">${user.nickname || user.username}</div>
                        </label>
                    `;
                    
                    memberSelectionDiv.appendChild(memberItem);
                }
            });
        } else {
            memberSelectionDiv.innerHTML = '<div class="error-message">获取用户列表失败</div>';
        }
    } catch (error) {
        console.error('加载可选成员失败:', error);
        memberSelectionDiv.innerHTML = '<div class="error-message">加载成员失败</div>';
    }
}

/**
 * 创建群组
 */
async function createGroup() {
    const groupName = document.getElementById('group-name').value.trim();
    const groupDescription = document.getElementById('group-description').value.trim();
    
    // 验证群组名
    if (!groupName) {
        showToast('请输入群组名称', 'warning');
        return;
    }
    
    // 获取选中的成员ID
    const selectedMembers = [];
    document.querySelectorAll('.member-checkbox:checked').forEach(checkbox => {
        selectedMembers.push(parseInt(checkbox.value));
    });
    
    // 至少选择一个成员
    if (selectedMembers.length === 0) {
        showToast('请至少选择一个成员', 'warning');
        return;
    }
    
    // 添加自己为成员（确保自己在群组中）
    if (!selectedMembers.includes(currentUser.id)) {
        selectedMembers.push(currentUser.id);
    }
    
    // 显示加载状态
    const createBtn = document.getElementById('confirm-create-group');
    const originalBtnText = createBtn.textContent;
    createBtn.disabled = true;
    createBtn.textContent = '创建中...';
    
    try {
        // 准备群组头像
        let groupAvatar = document.getElementById('group-avatar-preview');
        let avatarFile = null;
        
        if (groupAvatar && groupAvatar.src && !groupAvatar.src.includes('default-group.png')) {
            // 将Data URL转换为Blob
            if (groupAvatar.src.startsWith('data:')) {
                const response = await fetch(groupAvatar.src);
                avatarFile = await response.blob();
            }
        }
        
        // 准备请求数据
        const formData = new FormData();
        formData.append('name', groupName);
        formData.append('description', groupDescription);
        formData.append('members', JSON.stringify(selectedMembers));
        
        if (avatarFile) {
            formData.append('avatar', avatarFile, `group_${Date.now()}.png`);
            // 保存到服务器的指定位置
            formData.append('avatar_path', '/src/images/groups/');
        }
        
        // 调用API创建群组
        const response = await fetch('/api/chat/groups', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('创建群组失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            // 关闭模态框
            document.getElementById('create-group-modal').classList.remove('active');
            
            // 刷新群组列表
            fetchGroups();
            
            // 显示成功提示
            showToast('群组创建成功', 'success');
            
            // 加入群组频道
            if (window.socket && window.socket.connected) {
                window.socket.emit('join', {
                    room: `group_${data.group_id}`
                });
                
                // 广播群组更新消息
                window.socket.emit('group_update', {
                    group_id: data.group_id,
                    action: 'create',
                    creator: currentUser.id
                });
            }
            
            // 打开新创建的群组
            if (data.group_id) {
                setTimeout(() => {
                    openChatWithGroup(data.group_id);
                }, 500);
            }
        } else {
            showToast(data.message || '创建群组失败', 'error');
        }
    } catch (error) {
        console.error('创建群组失败:', error);
        showToast('创建群组失败，请稍后再试', 'error');
    } finally {
        // 恢复按钮状态
        createBtn.disabled = false;
        createBtn.textContent = originalBtnText;
    }
}

/**
 * 加载缓存的用户状态
 */
function loadCachedUserStatuses() {
    try {
        const userStatuses = JSON.parse(sessionStorage.getItem('userStatuses') || '{}');
        
        // 应用缓存的状态到用户列表
        for (const userId in userStatuses) {
            if (userStatuses.hasOwnProperty(userId)) {
                const isOnline = userStatuses[userId];
                const userIdNum = parseInt(userId);
                
                // 应用到在线用户列表
                const userIndex = onlineUsers.findIndex(u => u.id === userIdNum);
                if (userIndex !== -1) {
                    onlineUsers[userIndex].status = isOnline ? 'online' : 'offline';
                    onlineUsers[userIndex].online = isOnline;
                }
                
                // 应用到最近联系人列表
                const contactIndex = recentContacts.findIndex(c => c.id === userIdNum);
                if (contactIndex !== -1) {
                    recentContacts[contactIndex].status = isOnline ? 'online' : 'offline';
                    recentContacts[contactIndex].online = isOnline;
                }
            }
        }
        
        // 重新渲染用户列表
        renderOnlineUsers();
        renderRecentContacts();
    } catch (e) {
        console.error('加载缓存的用户状态失败', e);
    }
}

/**
 * 同步用户列表中的在线状态
 */
function syncUserStatuses() {
    // 如果两个列表都已加载
    if (onlineUsers.length > 0 && recentContacts.length > 0) {
        // 同步在线状态
        for (const user of onlineUsers) {
            if (user.status === 'online' || user.online) {
                // 找到对应的联系人并更新状态
                const contact = recentContacts.find(c => c.id === user.id);
                if (contact) {
                    contact.status = 'online';
                    contact.online = true;
                }
            }
        }
        
        for (const contact of recentContacts) {
            if (contact.status === 'online' || contact.online) {
                // 找到对应的在线用户并更新状态
                const user = onlineUsers.find(u => u.id === contact.id);
                if (user) {
                    user.status = 'online';
                    user.online = true;
                } else {
                    // 如果在线用户列表中没有这个联系人，但他是在线的，就添加到在线用户列表
                    onlineUsers.push({
                        id: contact.id,
                        username: contact.username,
                        nickname: contact.nickname,
                        avatar: contact.avatar,
                        status: 'online',
                        online: true
                    });
                }
            }
        }
        
        // 重新渲染用户列表
        renderOnlineUsers();
        renderRecentContacts();
    }
}

/**
 * 显示用户信息模态框
 * @param {number} userId - 用户ID
 */
async function showUserInfo(userId) {
    try {
        // 防止用户查看自己的详细信息
        if (userId === currentUser.id) {
            showToast('不能对自己执行此操作', 'warning');
            return;
        }
        
        // 查找用户信息
        const user = [...onlineUsers, ...recentContacts].find(u => u.id === userId);
        
        if (!user) {
            showToast('未找到用户信息', 'error');
            return;
        }
        
        // 检查用户是否已被拉黑
        const blacklistedUsers = JSON.parse(localStorage.getItem('blacklisted_users') || '[]');
        const isBlacklisted = blacklistedUsers.includes(userId);
        
        // 创建/更新用户信息模态框
        let userInfoModal = document.getElementById('user-info-modal');
        
        if (!userInfoModal) {
            userInfoModal = document.createElement('div');
            userInfoModal.id = 'user-info-modal';
            userInfoModal.className = 'modal';
            
            document.body.appendChild(userInfoModal);
        }
        
        // 使用正确的头像路径
        let avatarUrl = '/src/images/avtar.jpg';
        if (user.avatar) {
            // 确保头像路径正确
            if (user.avatar.startsWith('http')) {
                avatarUrl = user.avatar;
            } else {
                avatarUrl = user.avatar.startsWith('/') ? user.avatar : `/${user.avatar}`;
            }
        }
        
        userInfoModal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>用户信息</h3>
                    <button class="close-btn"><i class="fas fa-times"></i></button>
                </div>
                <div class="user-info-container">
                    <div class="user-info-avatar">
                        <img src="${avatarUrl}" alt="${user.nickname || user.username}" onerror="this.src='/src/images/avtar.jpg'">
                    </div>
                    <div class="user-info-details">
                        <h4>${user.nickname || user.username}</h4>
                        <p class="user-status ${user.online || user.status === 'online' ? 'online' : ''}">${user.online || user.status === 'online' ? '在线' : '离线'}</p>
                    </div>
                    <div class="user-actions">
                        <button id="start-chat-btn" data-user-id="${userId}" class="btn primary">
                            <i class="fas fa-comment"></i> 发起聊天
                        </button>
                        <button id="blacklist-btn" data-user-id="${userId}" class="btn ${isBlacklisted ? 'success' : 'warning'}">
                            <i class="fas fa-${isBlacklisted ? 'user-check' : 'user-slash'}"></i> ${isBlacklisted ? '取消拉黑' : '拉黑用户'}
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // 显示模态框
        userInfoModal.classList.add('active');
        
        // 添加关闭按钮事件
        userInfoModal.querySelector('.close-btn').addEventListener('click', function() {
            userInfoModal.classList.remove('active');
        });
        
        // 添加发起聊天按钮事件
        document.getElementById('start-chat-btn').addEventListener('click', function() {
            userInfoModal.classList.remove('active');
            openChatWithUser(userId);
        });
        
        // 添加拉黑/取消拉黑按钮事件
        document.getElementById('blacklist-btn').addEventListener('click', function() {
            toggleBlacklist(userId);
            userInfoModal.classList.remove('active');
        });
        
        // 模态框背景点击关闭
        userInfoModal.addEventListener('click', function(e) {
            if (e.target === userInfoModal) {
                userInfoModal.classList.remove('active');
            }
        });
    } catch (error) {
        console.error('显示用户信息失败:', error);
        showToast('无法显示用户信息', 'error');
    }
}

/**
 * 拉黑或取消拉黑用户
 * @param {number} userId - 用户ID
 */
function toggleBlacklist(userId) {
    try {
        // 从本地存储获取黑名单
        const blacklistedUsers = JSON.parse(localStorage.getItem('blacklisted_users') || '[]');
        const isBlacklisted = blacklistedUsers.includes(userId);
        
        if (isBlacklisted) {
            // 从黑名单中移除
            const index = blacklistedUsers.indexOf(userId);
            blacklistedUsers.splice(index, 1);
            showToast('已将用户从黑名单中移除', 'success');
        } else {
            // 添加到黑名单
            blacklistedUsers.push(userId);
            showToast('已将用户加入黑名单', 'success');
            
            // 如果正在和该用户聊天，关闭聊天窗口
            if (currentChat.type === 'user' && currentChat.id === userId) {
                // 显示空聊天区域
                document.getElementById('empty-chat').style.display = 'flex';
                document.getElementById('chat-area').style.display = 'none';
                
                // 重置当前聊天
                currentChat = {
                    type: null,
                    id: null
                };
            }
        }
        
        // 保存到本地存储
        localStorage.setItem('blacklisted_users', JSON.stringify(blacklistedUsers));
        
        // 更新界面
        renderOnlineUsers();
        renderRecentContacts();
    } catch (error) {
        console.error('操作黑名单失败:', error);
        showToast('操作失败，请重试', 'error');
    }
}

/**
 * 添加好友
 * @param {number} userId - 要添加的用户ID
 */
async function addFriend(userId) {
    try {
        // 发送好友请求
        const response = await fetch('/api/friends/request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('fuckchat_token')}`
            },
            body: JSON.stringify({
                target_id: userId
            })
        });
        
        if (!response.ok) {
            throw new Error('发送好友请求失败');
        }
        
        const data = await response.json();
        
        if (data.success) {
            showToast('好友请求已发送', 'success');
            // 更新按钮状态
            const addFriendBtn = document.getElementById('add-friend-btn');
            addFriendBtn.textContent = '请求已发送';
            addFriendBtn.disabled = true;
        } else {
            showToast(data.message || '发送好友请求失败', 'error');
        }
    } catch (error) {
        console.error('发送好友请求失败:', error);
        showToast('发送好友请求失败，请稍后再试', 'error');
    }
}

/**
 * 显示聊天操作对话框
 */
function showChatActions() {
    // 检查当前是否有活动的聊天
    if (!currentChat.type || !currentChat.id) {
        showToast('请先选择一个聊天', 'warning');
        return;
    }
    
    // 创建/更新聊天操作模态框
    let chatActionsModal = document.getElementById('chat-actions-modal');
    
    if (!chatActionsModal) {
        chatActionsModal = document.createElement('div');
        chatActionsModal.id = 'chat-actions-modal';
        chatActionsModal.className = 'modal';
        
        document.body.appendChild(chatActionsModal);
    }
    
    // 准备标题
    let title = '';
    if (currentChat.type === 'user') {
        const user = [...onlineUsers, ...recentContacts].find(u => u.id === currentChat.id);
        title = user ? (user.nickname || user.username || '未知用户') : '聊天';
    } else {
        const group = groups.find(g => g.id === currentChat.id);
        title = group ? (group.name || '未命名群组') : '群聊';
    }
    
    chatActionsModal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>${title}聊天选项</h3>
                <button class="close-btn"><i class="fas fa-times"></i></button>
            </div>
            <div class="chat-actions-container">
                <button id="clear-chat-btn" class="action-btn">
                    <i class="fas fa-trash"></i> 清空聊天记录
                </button>
                ${currentChat.type === 'user' ? `
                <button id="report-user-btn" class="action-btn">
                    <i class="fas fa-flag"></i> 举报用户
                </button>
                ` : ''}
            </div>
        </div>
    `;
    
    // 显示模态框
    chatActionsModal.classList.add('active');
    
    // 添加关闭按钮事件
    chatActionsModal.querySelector('.close-btn').addEventListener('click', function() {
        chatActionsModal.classList.remove('active');
    });
    
    // 添加清空聊天记录按钮事件
    document.getElementById('clear-chat-btn').addEventListener('click', function() {
        clearChatHistory();
        chatActionsModal.classList.remove('active');
    });
    
    // 添加举报用户按钮事件（如果是私聊）
    if (currentChat.type === 'user') {
        document.getElementById('report-user-btn').addEventListener('click', function() {
            reportUser(currentChat.id);
            chatActionsModal.classList.remove('active');
        });
    }
    
    // 模态框背景点击关闭
    chatActionsModal.addEventListener('click', function(e) {
        if (e.target === chatActionsModal) {
            chatActionsModal.classList.remove('active');
        }
    });
}

/**
 * 清空聊天记录
 */
function clearChatHistory() {
    if (!currentChat.type || !currentChat.id) {
        showToast('无效的聊天室', 'error');
        return;
    }
    
    if (confirm('确定要清空所有聊天记录吗？此操作对所有用户可见且不可恢复。')) {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            showToast('请先登录', 'error');
            return;
        }
        
        // 向服务器发送清空聊天记录的请求
        fetch('/api/messages/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                roomId: currentChat.id,
                chatType: currentChat.type
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 清空本地聊天容器
                const chatContainer = document.querySelector('.messages-container');
                chatContainer.innerHTML = '';
                
                // 添加系统消息
                appendSystemMessage('聊天记录已被清空');
                
                // 如果WebSocket连接可用，广播清空聊天记录事件
                if (window.socket && window.socket.connected) {
                    const currentUser = getUserFromStorage();
                    window.socket.emit('clear_chat', {
                        roomId: currentChat.id,
                        chatType: currentChat.type,
                        userId: currentUser.id,
                        username: currentUser.nickname || currentUser.username
                    });
                }
                
                showToast('聊天记录已清空', 'success');
            } else {
                showToast(data.message || '清空聊天记录失败', 'error');
            }
        })
        .catch(error => {
            console.error('清空聊天记录失败:', error);
            showToast('清空聊天记录失败，请重试', 'error');
        });
    }
}

/**
 * 添加系统消息
 * @param {string} message - 系统消息内容
 */
function appendSystemMessage(message) {
    const messagesContainer = document.querySelector('.messages-container');
    const systemMessageDiv = document.createElement('div');
    systemMessageDiv.className = 'system-message';
    systemMessageDiv.innerHTML = `<div class="system-text">${message}</div>`;
    messagesContainer.appendChild(systemMessageDiv);
    
    // 滚动到底部
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * 举报用户
 * @param {number} userId - 被举报用户ID
 */
function reportUser(userId) {
    try {
        // 查找用户信息
        const user = [...onlineUsers, ...recentContacts].find(u => u.id === userId);
        const username = user ? (user.nickname || user.username) : '未知用户';
        
        // 创建举报表单模态框
        let reportModal = document.getElementById('report-modal');
        
        if (!reportModal) {
            reportModal = document.createElement('div');
            reportModal.id = 'report-modal';
            reportModal.className = 'modal';
            
            document.body.appendChild(reportModal);
        }
        
        reportModal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>举报用户</h3>
                    <button class="close-btn"><i class="fas fa-times"></i></button>
                </div>
                <div class="report-form">
                    <p>您正在举报 <strong>${username}</strong></p>
                    <div class="form-group">
                        <label for="report-reason">举报原因</label>
                        <select id="report-reason" class="form-control">
                            <option value="">请选择举报原因</option>
                            <option value="spam">垃圾信息/广告</option>
                            <option value="harassment">骚扰/侮辱</option>
                            <option value="illegal">违法内容</option>
                            <option value="fake">虚假信息</option>
                            <option value="other">其他</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="report-description">详细描述</label>
                        <textarea id="report-description" class="form-control" rows="4" placeholder="请详细描述问题..."></textarea>
                    </div>
                    <button id="submit-report-btn" class="btn primary">提交举报</button>
                </div>
            </div>
        `;
        
        // 显示模态框
        reportModal.classList.add('active');
        
        // 添加关闭按钮事件
        reportModal.querySelector('.close-btn').addEventListener('click', function() {
            reportModal.classList.remove('active');
        });
        
        // 提交举报按钮
        document.getElementById('submit-report-btn').addEventListener('click', function() {
            submitReport(userId);
        });
        
        // 模态框背景点击关闭
        reportModal.addEventListener('click', function(e) {
            if (e.target === reportModal) {
                reportModal.classList.remove('active');
            }
        });
    } catch (error) {
        console.error('显示举报表单失败:', error);
        showToast('无法显示举报表单', 'error');
    }
}

/**
 * 提交举报
 * @param {number} userId - 被举报用户ID
 */
async function submitReport(userId) {
    // 获取表单数据
    const reason = document.getElementById('report-reason').value;
    const description = document.getElementById('report-description').value.trim();
    
    // 验证输入
    if (!reason) {
        showToast('请选择举报原因', 'warning');
        return;
    }
    
    if (!description) {
        showToast('请填写详细描述', 'warning');
        return;
    }
    
    // 禁用提交按钮
    const submitBtn = document.getElementById('submit-report-btn');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';
    
    try {
        // 发送举报请求
        // 这里可以根据实际API实现，这是一个模拟实现
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // 关闭模态框
        document.getElementById('report-modal').classList.remove('active');
        
        // 显示成功消息
        showToast('举报已提交，我们会尽快处理', 'success');
    } catch (error) {
        console.error('提交举报失败:', error);
        showToast('提交举报失败，请重试', 'error');
    } finally {
        // 恢复提交按钮
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

/**
 * 初始化消息右键菜单/长按功能
 */
function initMessageContextMenu() {
    // 保存触摸开始时间 - 用于检测长按
    let touchStartTime = 0;
    let touchTimeout = null;
    
    // 当前选中的消息元素
    let selectedMessage = null;
    
    // 创建右键菜单
    let contextMenu = document.getElementById('message-context-menu');
    if (!contextMenu) {
        contextMenu = document.createElement('div');
        contextMenu.id = 'message-context-menu';
        contextMenu.className = 'context-menu';
        contextMenu.style.display = 'none';
        
        document.body.appendChild(contextMenu);
    }
    
    // 触摸开始事件 - 适用于移动设备
    document.addEventListener('touchstart', function(e) {
        const messageEl = e.target.closest('.message');
        if (messageEl) {
            touchStartTime = Date.now();
            selectedMessage = messageEl;
            
            // 设置长按检测计时器
            touchTimeout = setTimeout(() => {
                showMessageContextMenu(selectedMessage, e.touches[0].clientX, e.touches[0].clientY);
                e.preventDefault(); // 阻止默认行为
            }, 800); // 800ms 长按
        }
    });
    
    // 触摸结束事件
    document.addEventListener('touchend', function() {
        clearTimeout(touchTimeout);
    });
    
    // 触摸移动事件
    document.addEventListener('touchmove', function() {
        clearTimeout(touchTimeout);
    });
    
    // 右键点击事件 - 适用于桌面设备
    document.addEventListener('contextmenu', function(e) {
        const messageEl = e.target.closest('.message');
        if (messageEl) {
            e.preventDefault(); // 阻止默认右键菜单
            selectedMessage = messageEl;
            showMessageContextMenu(messageEl, e.clientX, e.clientY);
        }
    });
    
    // 点击任何地方关闭右键菜单
    document.addEventListener('click', function() {
        contextMenu.style.display = 'none';
    });
    
    // 点击右键菜单选项
    contextMenu.addEventListener('click', function(e) {
        // 获取选项
        const action = e.target.dataset.action;
        
        if (action && selectedMessage) {
            switch (action) {
                case 'quote':
                    quoteMessage(selectedMessage);
                    break;
                case 'recall':
                    recallMessage(selectedMessage);
                    break;
                case 'mention':
                    mentionUser(selectedMessage);
                    break;
            }
        }
    });
    
    /**
     * 显示消息右键菜单
     * @param {HTMLElement} messageEl - 消息元素
     * @param {number} x - 横坐标
     * @param {number} y - 纵坐标
     */
    function showMessageContextMenu(messageEl, x, y) {
        // 判断是否为自己发送的消息
        const isSentByMe = messageEl.classList.contains('sent');
        
        // 构建菜单项
        let menuItems = `
            <div class="menu-item" data-action="quote">
                <i class="fas fa-quote-right"></i> 引用
            </div>
        `;
        
        // 仅对自己发送的消息显示撤回选项
        if (isSentByMe) {
            menuItems += `
                <div class="menu-item" data-action="recall">
                    <i class="fas fa-undo"></i> 撤回
                </div>
            `;
        }
        
        // 仅对他人发送的消息显示@选项 (在群聊中)
        if (!isSentByMe && currentChat.type === 'group') {
            menuItems += `
                <div class="menu-item" data-action="mention">
                    <i class="fas fa-at"></i> @Ta
                </div>
            `;
        }
        
        // 设置菜单内容
        contextMenu.innerHTML = menuItems;
        
        // 计算菜单位置，确保在可视区域内
        const rect = document.body.getBoundingClientRect();
        const menuWidth = 150; // 估计菜单宽度
        const menuHeight = 120; // 估计菜单高度
        
        // 确保X坐标不超出右边界
        const posX = Math.min(x, rect.width - menuWidth);
        
        // 确保Y坐标不超出下边界
        const posY = Math.min(y, rect.height - menuHeight);
        
        // 设置菜单位置
        contextMenu.style.left = `${posX}px`;
        contextMenu.style.top = `${posY}px`;
        
        // 显示菜单
        contextMenu.style.display = 'block';
    }
    
    /**
     * 引用消息
     * @param {HTMLElement} messageEl - 消息元素
     */
    function quoteMessage(messageEl) {
        try {
            // 获取消息内容
            const contentEl = messageEl.querySelector('.content .text');
            if (!contentEl) return;
            
            const messageText = contentEl.textContent.trim();
            
            // 获取发送者ID
            const senderId = messageEl.dataset.senderId;
            
            // 获取当前用户信息和所有可能的用户列表
            const currentUser = getUserFromStorage();
            const allUsers = [...onlineUsers, ...recentContacts];
            
            // 获取发送者信息
            let senderName = '未知用户';
            
            if (currentUser && senderId === currentUser.id.toString()) {
                // 如果是自己的消息
                senderName = '我';
            } else {
                // 尝试在各种用户列表中查找发送者信息
                const sender = allUsers.find(u => u.id.toString() === senderId);
                if (sender) {
                    senderName = sender.nickname || sender.username || `用户${senderId}`;
                } else {
                    // 尝试从消息元素获取发送者名称
                    const senderEl = messageEl.querySelector('.content .sender');
                    if (senderEl) {
                        senderName = senderEl.textContent.trim();
                    }
                }
            }
            
            // 如果仍然是未知用户，但有sender-id属性，添加ID信息
            if (senderName === '未知用户' && senderId) {
                senderName = `用户${senderId}`;
            }
            
            // 构建引用文本
            const quoteText = `> ${senderName}: ${messageText}\n\n`;
            
            // 插入到输入框
            const messageInput = document.getElementById('message-input');
            messageInput.value = quoteText + messageInput.value;
            messageInput.focus();
            
            // 将光标移动到引用文本后面
            messageInput.setSelectionRange(quoteText.length, quoteText.length);
        } catch (error) {
            console.error('引用消息失败:', error);
            showToast('引用消息失败', 'error');
        }
    }
    
    /**
     * 撤回消息
     * @param {HTMLElement} messageEl - 消息元素
     */
    function recallMessage(messageEl) {
        // 获取消息 ID
        const messageId = messageEl.dataset.id;
        if (!messageId) return;
        
        // 获取当前用户信息
        const currentUser = getUserFromStorage();
        if (!currentUser) return;
        
        // 检查是否是自己的消息
        const senderId = messageEl.dataset.senderId;
        if (senderId !== currentUser.id.toString()) {
            showToast('只能撤回自己的消息', 'error');
            return;
        }
        
        // 确认是否撤回
        if (confirm('确定要撤回这条消息吗？撤回后所有人都将看不到消息内容。')) {
            // 向服务器发送撤回请求
            const token = localStorage.getItem('fuckchat_token');
            if (!token) {
                showToast('请先登录', 'error');
                return;
            }
            
            fetch('/api/messages/recall', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    messageId: messageId,
                    roomId: currentChat.id,
                    chatType: currentChat.type
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 本地UI更新
                    updateRecalledMessageUI(messageEl);
                    
                    // 如果WebSocket连接可用，广播撤回消息事件
                    if (window.socket && window.socket.connected) {
                        window.socket.emit('recall_message', {
                            messageId: messageId,
                            userId: currentUser.id,
                            username: currentUser.nickname || currentUser.username,
                            roomId: currentChat.id,
                            chatType: currentChat.type
                        });
                    }
                    
                    showToast('消息已撤回', 'success');
                } else {
                    showToast(data.message || '撤回失败', 'error');
                }
            })
            .catch(error => {
                console.error('撤回消息失败:', error);
                showToast('撤回失败，请重试', 'error');
            });
        }
    }
    
    /**
     * 更新撤回消息的UI
     * @param {Element} messageEl - 消息元素
     */
    function updateRecalledMessageUI(messageEl) {
        if (!messageEl) return;
        
        // 将消息标记为已撤回
        messageEl.classList.add('recalled-message');
        
        // 替换所有可能的内容元素
        const contentElements = messageEl.querySelectorAll('.text, .image-content, .voice-content, .emoji, .kunbi-content');
        if (contentElements.length > 0) {
            contentElements.forEach(el => {
                el.innerHTML = '<div class="recalled">此消息已被撤回</div>';
                el.classList.add('recalled-content');
            });
        } else {
            // 如果没有找到特定内容元素，寻找主要内容容器
            const contentContainer = messageEl.querySelector('.content');
            if (contentContainer) {
                // 保留发送者信息
                const senderEl = contentContainer.querySelector('.sender');
                const timeEl = contentContainer.querySelector('.time');
                
                // 重构内容
                let newContent = '';
                if (senderEl) {
                    newContent += senderEl.outerHTML;
                }
                newContent += '<div class="text recalled">此消息已被撤回</div>';
                if (timeEl) {
                    newContent += timeEl.outerHTML;
                }
                
                contentContainer.innerHTML = newContent;
            }
        }
        
        // 移除消息操作按钮
        const actionsElement = messageEl.querySelector('.message-actions');
        if (actionsElement) {
            actionsElement.remove();
        }
        
        // 移除可能的引用区域
        const quotedElement = messageEl.querySelector('.quoted-message');
        if (quotedElement) {
            quotedElement.remove();
        }
    }
    
    /**
     * @用户
     * @param {HTMLElement} messageEl - 消息元素
     */
    function mentionUser(messageEl) {
        try {
            // 获取发送者ID
            const senderId = messageEl.dataset.senderId;
            if (!senderId) return;
            
            // 获取发送者昵称
            let senderName = '未知用户';
            const senderEl = messageEl.querySelector('.content .sender');
            
            if (senderEl) {
                senderName = senderEl.textContent.trim();
            } else {
                // 尝试从用户列表中获取
                const sender = [...onlineUsers, ...recentContacts].find(u => u.id.toString() === senderId);
                if (sender) {
                    senderName = sender.nickname || sender.username;
                }
            }
            
            // 插入@文本
            const messageInput = document.getElementById('message-input');
            
            // 在光标位置或结尾插入@
            const atText = `@${senderName} `;
            const cursorPos = messageInput.selectionStart;
            
            messageInput.value = messageInput.value.substring(0, cursorPos) + 
                                 atText + 
                                 messageInput.value.substring(messageInput.selectionEnd);
            
            // 更新光标位置
            const newCursorPos = cursorPos + atText.length;
            messageInput.setSelectionRange(newCursorPos, newCursorPos);
            
            // 聚焦输入框
            messageInput.focus();
        } catch (error) {
            console.error('@用户失败:', error);
            showToast('@用户失败', 'error');
        }
    }
}

// 初始化socket连接后添加这些监听器
function initSocketEventListeners() {
    if (!window.socket) return;
    
    // 移除可能的重复监听器
    window.socket.off('message_recalled');
    window.socket.off('chat_cleared');
    
    // 监听消息撤回事件
    window.socket.on('message_recalled', (data) => {
        console.log('收到消息撤回事件:', data);
        const { messageId, userId, username } = data;
        
        // 查找所有可能匹配的消息元素
        // 注意：消息可能有不同的选择器标识
        const messageElements = document.querySelectorAll(`.message-item[data-id="${messageId}"], .message[data-id="${messageId}"]`);
        
        if (messageElements.length > 0) {
            messageElements.forEach(element => {
                updateRecalledMessageUI(element);
            });
            
            // 添加系统提示
            appendSystemMessage(`${username || '用户'} 撤回了一条消息`);
        } else {
            console.warn(`未找到要撤回的消息元素: ${messageId}`);
        }
    });
    
    // 监听清空聊天记录事件
    window.socket.on('chat_cleared', (data) => {
        console.log('收到清空聊天记录事件:', data);
        const { roomId, chatType, userId, username } = data;
        
        if ((chatType === currentChat.type) && (roomId === currentChat.id)) {
            // 清空聊天容器
            const chatContainer = document.querySelector('.messages-container');
            if (chatContainer) {
                chatContainer.innerHTML = '';
                
                // 添加系统消息
                appendSystemMessage(`${username || '管理员'} 清空了聊天记录`);
            }
        }
    });
}