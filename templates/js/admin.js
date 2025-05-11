/**
 * FUCKCHAT - 管理员控制台
 * 实现管理员管理用户、群组、系统通知等功能
 */

// 初始化页面
document.addEventListener('DOMContentLoaded', function() {
    // 检查管理员登录状态
    if (!isAdminLoggedIn()) {
        window.location.href = '/admin';
        return;
    }
    
    // 获取管理员信息
    const admin = getAdminInfo();
    document.getElementById('admin-name').textContent = admin.nickname || admin.username;
    
    // 初始化页面
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    loadStatistics();
    
    try {
        initCharts();
    } catch (error) {
        console.error('初始化图表失败:', error);
    }
    
    // 加载各模块数据
    loadRecentUsers();
    loadSystemLogs();
    
    // 绑定事件
    bindEvents();
    
    // 设置活跃标签页 - 从URL获取当前标签页
    const hash = window.location.hash || '#dashboard';
    const sectionId = hash.substring(1);
    console.log('当前页面标签:', sectionId);
    setTimeout(() => setActiveSection(sectionId), 100);
    
    // 监听hash变化
    window.addEventListener('hashchange', function() {
        const hash = window.location.hash || '#dashboard';
        const sectionId = hash.substring(1);
        console.log('页面标签变更为:', sectionId);
        setActiveSection(sectionId);
    });
});

/**
 * 检查管理员是否已登录
 */
function isAdminLoggedIn() {
    return sessionStorage.getItem('admin_logged_in') === 'true';
}

/**
 * 获取管理员信息
 */
function getAdminInfo() {
    const username = sessionStorage.getItem('admin_username');
    return { 
        username: username || '管理员',
        nickname: username || '管理员'
    };
}

/**
 * 更新当前时间显示
 */
function updateCurrentTime() {
    const now = new Date();
    const options = { 
        year: 'numeric', 
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit'
    };
    
    const timeStr = now.toLocaleString('zh-CN', options);
    document.getElementById('current-time').textContent = timeStr;
}

/**
 * 加载系统统计数据
 */
function loadStatistics() {
    fetch('/api/admin/stats')
    .then(response => {
        if (!response.ok) throw new Error('获取统计数据失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // 更新统计卡片
            document.getElementById('total-users').textContent = data.stats.user_count;
            document.getElementById('total-groups').textContent = data.stats.group_count;
            document.getElementById('online-users-count').textContent = data.stats.online_user_count;
            
            // 计算总消息数
            const totalMessages = data.stats.today_message_count || 0;
            document.getElementById('total-messages').textContent = totalMessages;
        }
    })
    .catch(error => {
        console.error('加载统计数据失败:', error);
        showToast('加载统计数据失败', 'error');
    });
}

/**
 * 初始化图表
 */
function initCharts() {
    // 用户活跃度图表
    const userActivityCtx = document.getElementById('user-activity-chart').getContext('2d');
    new Chart(userActivityCtx, {
        type: 'line',
        data: {
            labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
            datasets: [{
                label: '活跃用户',
                data: [12, 19, 15, 17, 21, 25, 18],
                borderColor: '#4CAF50',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                }
            }
        }
    });
    
    // 消息类型分布图表
    const messageTypesCtx = document.getElementById('message-types-chart').getContext('2d');
    new Chart(messageTypesCtx, {
        type: 'doughnut',
        data: {
            labels: ['文本', '图片', '语音', '表情', '坤币红包'],
            datasets: [{
                data: [65, 12, 8, 10, 5],
                backgroundColor: [
                    '#4CAF50',
                    '#2196F3',
                    '#FFC107',
                    '#FF5722',
                    '#9C27B0'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'right',
                }
            }
        }
    });
}

/**
 * 加载最近注册用户
 */
function loadRecentUsers() {
    fetch('/api/admin/users?page=1&per_page=5')
    .then(response => {
        if (!response.ok) throw new Error('获取用户数据失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('recent-users-table');
            tbody.innerHTML = '';
            
            data.users.forEach(user => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const createdDate = new Date(user.created_at);
                const formattedDate = createdDate.toLocaleDateString('zh-CN');
                
                row.innerHTML = `
                    <td>${user.username}</td>
                    <td>${user.nickname}</td>
                    <td>${formattedDate}</td>
                    <td>${user.kunbi}</td>
                `;
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error('加载最近用户数据失败:', error);
    });
}

/**
 * 加载系统日志
 */
function loadSystemLogs() {
    fetch('/api/admin/logs?page=1&per_page=5')
    .then(response => {
        if (!response.ok) throw new Error('获取系统日志失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('system-logs-table');
            tbody.innerHTML = '';
            
            data.logs.forEach(log => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const logDate = new Date(log.created_at);
                const formattedDate = logDate.toLocaleString('zh-CN');
                
                row.innerHTML = `
                    <td>${formattedDate}</td>
                    <td>${log.type}</td>
                    <td>${log.content}</td>
                `;
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error('加载系统日志失败:', error);
    });
}

/**
 * 加载所有用户
 */
function loadAllUsers(page = 1) {
    fetch(`/api/admin/users?page=${page}&per_page=10`)
    .then(response => {
        if (!response.ok) throw new Error('获取用户数据失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('users-table');
            tbody.innerHTML = '';
            
            data.users.forEach(user => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const createdDate = new Date(user.created_at);
                const formattedCreated = createdDate.toLocaleDateString('zh-CN');
                
                let lastLoginText = '未登录';
                if (user.last_login_at) {
                    const lastLoginDate = new Date(user.last_login_at);
                    lastLoginText = lastLoginDate.toLocaleString('zh-CN');
                }
                
                // 创建状态标签
                let statusHtml = '';
                if (user.status === 'online') {
                    statusHtml = `<span class="status-badge online">在线</span>`;
                } else {
                    statusHtml = `<span class="status-badge offline">离线</span>`;
                }
                
                row.innerHTML = `
                    <td><input type="checkbox" data-user-id="${user.id}"></td>
                    <td>${user.id}</td>
                    <td>${user.username}</td>
                    <td>${user.nickname}</td>
                    <td>${formattedCreated}</td>
                    <td>${lastLoginText}</td>
                    <td>${user.kunbi}</td>
                    <td>${statusHtml}</td>
                    <td class="actions">
                        <button class="action-btn edit-user" data-user-id="${user.id}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="action-btn delete-user" data-user-id="${user.id}" ${user.is_admin ? 'disabled' : ''}>
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
            
            // 更新分页
            updatePagination(data.pagination);
        }
    })
    .catch(error => {
        console.error('加载用户数据失败:', error);
        showToast('加载用户数据失败', 'error');
    });
}

/**
 * 加载所有群组
 */
function loadAllGroups(page = 1) {
    fetch(`/api/admin/groups?page=${page}&per_page=10`)
    .then(response => {
        if (!response.ok) throw new Error('获取群组数据失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // 实现群组数据显示
            console.log('群组数据:', data);
        }
    })
    .catch(error => {
        console.error('加载群组数据失败:', error);
        showToast('加载群组数据失败', 'error');
    });
}

/**
 * 更新分页控件
 */
function updatePagination(pagination) {
    const paginationDiv = document.querySelector('.pagination');
    if (!paginationDiv) return;
    
    const pageNumbers = paginationDiv.querySelector('.page-numbers');
    pageNumbers.innerHTML = '';
    
    const currentPage = pagination.page;
    const totalPages = pagination.pages;
    
    // 创建页码按钮
    for (let i = 1; i <= totalPages; i++) {
        if (totalPages > 5 && i > 3 && i < totalPages - 1) {
            if (i === 4) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'ellipsis';
                ellipsis.textContent = '...';
                pageNumbers.appendChild(ellipsis);
            }
            continue;
        }
        
        const button = document.createElement('button');
        button.className = 'page-number' + (i === currentPage ? ' active' : '');
        button.textContent = i;
        button.addEventListener('click', () => {
            // 根据当前活跃的部分决定加载哪类数据
            const activeSection = document.querySelector('.admin-section.active').id;
            if (activeSection === 'users-section') {
                loadAllUsers(i);
            } else if (activeSection === 'groups-section') {
                loadAllGroups(i);
            }
        });
        
        pageNumbers.appendChild(button);
    }
    
    // 更新前后翻页按钮状态
    const prevButton = paginationDiv.querySelector('.page-btn:first-child');
    const nextButton = paginationDiv.querySelector('.page-btn:last-child');
    
    prevButton.disabled = currentPage === 1;
    nextButton.disabled = currentPage === totalPages;
    
    // 添加前后翻页按钮事件
    prevButton.onclick = () => {
        if (currentPage > 1) {
            const activeSection = document.querySelector('.admin-section.active').id;
            if (activeSection === 'users-section') {
                loadAllUsers(currentPage - 1);
            } else if (activeSection === 'groups-section') {
                loadAllGroups(currentPage - 1);
            }
        }
    };
    
    nextButton.onclick = () => {
        if (currentPage < totalPages) {
            const activeSection = document.querySelector('.admin-section.active').id;
            if (activeSection === 'users-section') {
                loadAllUsers(currentPage + 1);
            } else if (activeSection === 'groups-section') {
                loadAllGroups(currentPage + 1);
            }
        }
    };
}

/**
 * 设置活跃标签页
 */
function setActiveSection(sectionId) {
    console.log('正在切换到标签页:', sectionId);
    
    // 移除所有section的active类
    document.querySelectorAll('.admin-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // 移除所有导航项的active类
    document.querySelectorAll('.admin-nav li').forEach(item => {
        item.classList.remove('active');
    });
    
    // 设置当前section为active
    const targetSectionId = `${sectionId}-section`;
    const targetSection = document.getElementById(targetSectionId);
    
    if (targetSection) {
        console.log('找到目标section:', targetSectionId);
        targetSection.classList.add('active');
        
        // 更新面包屑
        const breadcrumbTitle = targetSection.querySelector('h2')?.textContent || 
            document.querySelector(`a[href="#${sectionId}"]`)?.textContent?.trim() || 
            '仪表盘';
            
        document.querySelector('.breadcrumb h2').textContent = breadcrumbTitle;
        console.log('更新面包屑标题为:', breadcrumbTitle);
        
        // 更新导航项
        const navLink = document.querySelector(`.admin-nav a[href="#${sectionId}"]`);
        if (navLink) {
            navLink.parentElement.classList.add('active');
            console.log('更新导航项为活跃状态');
        } else {
            console.warn('未找到对应的导航项:', sectionId);
        }
        
        // 根据不同的section加载数据
        if (sectionId === 'users') {
            console.log('加载用户数据');
            loadAllUsers();
        } else if (sectionId === 'groups') {
            console.log('加载群组数据');
            loadAllGroups();
        }
    } else {
        console.error('未找到目标section:', targetSectionId);
        // 如果找不到指定的section，默认显示仪表盘
        const dashboardSection = document.getElementById('dashboard-section');
        if (dashboardSection) {
            dashboardSection.classList.add('active');
            document.querySelector('.admin-nav li:first-child').classList.add('active');
            document.querySelector('.breadcrumb h2').textContent = '仪表盘';
        }
    }
}

/**
 * 绑定页面事件
 */
function bindEvents() {
    // 导航项点击事件
    document.querySelectorAll('.admin-nav a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = this.getAttribute('href').substring(1);
            setActiveSection(target);
            window.location.hash = `#${target}`;
        });
    });
    
    // 刷新按钮点击事件
    document.getElementById('refresh-btn').addEventListener('click', function() {
        const activeSection = document.querySelector('.admin-section.active').id;
        
        if (activeSection === 'dashboard-section') {
            loadStatistics();
            loadRecentUsers();
            loadSystemLogs();
        } else if (activeSection === 'users-section') {
            loadAllUsers();
        } else if (activeSection === 'groups-section') {
            loadAllGroups();
        } else if (activeSection === 'chats-section') {
            loadChats('private');
        } else if (activeSection === 'database-section') {
            loadDatabaseInfo();
        } else if (activeSection === 'notifications-section') {
            loadNotifications();
        }
        
        showToast('数据刷新成功', 'success');
    });
    
    // 退出登录按钮点击事件
    document.getElementById('admin-logout-btn').addEventListener('click', function() {
        sessionStorage.removeItem('admin_logged_in');
        sessionStorage.removeItem('admin_username');
        fetch('/admin/logout')
            .then(() => {
                window.location.href = '/admin';
            })
            .catch(err => {
                console.error('退出登录请求失败:', err);
                window.location.href = '/admin';
            });
    });
    
    // 添加用户按钮点击事件
    document.getElementById('add-user-btn')?.addEventListener('click', function() {
        const modal = document.getElementById('add-user-modal');
        modal.style.display = 'flex';
    });
    
    // 添加群组按钮点击事件
    document.getElementById('add-group-btn')?.addEventListener('click', function() {
        const modal = document.getElementById('add-group-modal');
        if (modal) {
            modal.style.display = 'flex';
        } else {
            showToast('添加群组功能暂未实现', 'info');
        }
    });
    
    // 发送通知按钮点击事件
    document.getElementById('send-notification-btn')?.addEventListener('click', function() {
        const modal = document.getElementById('notification-modal');
        if (modal) {
            modal.style.display = 'flex';
        } else {
            showToast('通知发送功能暂未实现', 'info');
        }
    });
    
    // 数据库操作按钮
    document.getElementById('backup-db-btn')?.addEventListener('click', function() {
        showToast('数据库备份中...', 'info');
        backupDatabase();
    });
    
    document.getElementById('optimize-db-btn')?.addEventListener('click', function() {
        showToast('数据库优化中...', 'info');
        optimizeDatabase();
    });
    
    // 保存设置按钮
    document.getElementById('save-settings-btn')?.addEventListener('click', function() {
        saveSettings();
    });
    
    // 设置侧边栏点击事件
    document.querySelectorAll('.settings-nav li').forEach(item => {
        item.addEventListener('click', function() {
            // 移除所有active类
            document.querySelectorAll('.settings-nav li').forEach(i => i.classList.remove('active'));
            document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
            
            // 设置当前选中项为active
            this.classList.add('active');
            const target = this.getAttribute('data-settings');
            document.getElementById(`${target}-settings`).classList.add('active');
        });
    });
    
    // 聊天管理标签页点击事件
    document.querySelectorAll('.admin-tabs .tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const parent = this.closest('.admin-tabs');
            const tabContents = parent.nextElementSibling.parentElement.querySelectorAll('.tab-content');
            
            // 移除所有标签页的active类
            parent.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // 设置当前标签页为active
            this.classList.add('active');
            const tabName = this.getAttribute('data-tab');
            document.getElementById(`${tabName}-content`).classList.add('active');
            
            // 加载对应标签页的数据
            if (tabName === 'private-chats') {
                loadChats('private');
            } else if (tabName === 'group-chats') {
                loadChats('group');
            } else if (tabName === 'reported-messages') {
                loadReportedMessages();
            } else if (tabName === 'db-tables') {
                loadDatabaseTables();
            } else if (tabName === 'db-backups') {
                loadDatabaseBackups();
            } else if (tabName === 'sent-notifications') {
                loadNotifications();
            } else if (tabName === 'notification-stats') {
                loadNotificationStats();
            }
        });
    });
    
    // 关闭模态框按钮
    document.querySelectorAll('.close-btn, .btn.secondary').forEach(btn => {
        btn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });
    
    // 添加用户表单提交
    document.getElementById('add-user-form')?.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const username = document.getElementById('new-username').value;
        const nickname = document.getElementById('new-nickname').value;
        const password = document.getElementById('new-password').value;
        const kunbi = document.getElementById('new-kunbi').value;
        
        // 向后端发送添加用户请求
        addUser({ username, nickname, password, kunbi });
        
        document.getElementById('add-user-modal').style.display = 'none';
    });
    
    // 删除用户事件委托
    document.addEventListener('click', function(e) {
        if (e.target.closest('.delete-user')) {
            const userId = e.target.closest('.delete-user').dataset.userId;
            if (confirm('确定要删除该用户吗？此操作不可撤销！')) {
                deleteUser(userId);
            }
        }
    });
}

/**
 * 删除用户
 */
function deleteUser(userId) {
    fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) throw new Error('删除用户失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('用户删除成功', 'success');
            loadAllUsers();
        } else {
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('删除用户失败:', error);
        showToast('删除用户失败', 'error');
    });
}

/**
 * 显示提示消息
 */
function showToast(message, type = 'info', duration = 3000) {
    // 检查是否已有toast元素
    let toast = document.querySelector('.toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    
    // 设置toast内容和类型
    toast.textContent = message;
    toast.className = `toast ${type}`;
    
    // 显示toast
    toast.classList.add('show');
    
    // 定时隐藏
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

/**
 * 加载聊天消息
 */
function loadChats(type = 'private') {
    const endpoint = type === 'private' ? '/api/admin/private-chats' : '/api/admin/group-chats';
    
    fetch(endpoint)
    .then(response => {
        if (!response.ok) throw new Error(`获取${type === 'private' ? '私聊' : '群聊'}消息失败`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tableId = type === 'private' ? 'private-chats-table' : 'group-chats-table';
            const tbody = document.getElementById(tableId);
            if (!tbody) {
                console.error(`未找到表格元素: ${tableId}`);
                return;
            }
            
            tbody.innerHTML = '';
            
            data.messages.forEach(message => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const messageDate = new Date(message.created_at);
                const formattedDate = messageDate.toLocaleString('zh-CN');
                
                // 根据消息类型显示不同图标
                let typeIcon = '';
                switch (message.message_type) {
                    case 'text': typeIcon = '<i class="fas fa-comment"></i>'; break;
                    case 'image': typeIcon = '<i class="fas fa-image"></i>'; break;
                    case 'voice': typeIcon = '<i class="fas fa-microphone"></i>'; break;
                    case 'redpacket': typeIcon = '<i class="fas fa-gift"></i>'; break;
                    default: typeIcon = '<i class="fas fa-comment"></i>';
                }
                
                // 根据消息类型处理内容显示
                let content = message.content;
                if (message.message_type === 'image') {
                    content = `<span class="image-preview">[图片消息]</span>`;
                } else if (message.message_type === 'voice') {
                    content = `<span class="voice-preview">[语音消息]</span>`;
                } else if (message.message_type === 'redpacket') {
                    content = `<span class="redpacket-preview">[红包消息]</span>`;
                }
                
                if (type === 'private') {
                    row.innerHTML = `
                        <td>${message.id}</td>
                        <td>${message.sender_name}</td>
                        <td>${message.receiver_name}</td>
                        <td>${content}</td>
                        <td>${typeIcon} ${message.message_type}</td>
                        <td>${formattedDate}</td>
                        <td class="actions">
                            <button class="action-btn view-message" data-message-id="${message.id}">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="action-btn delete-message" data-message-id="${message.id}">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    `;
                } else {
                    row.innerHTML = `
                        <td>${message.id}</td>
                        <td>${message.sender_name}</td>
                        <td>${message.group_name}</td>
                        <td>${content}</td>
                        <td>${typeIcon} ${message.message_type}</td>
                        <td>${formattedDate}</td>
                        <td class="actions">
                            <button class="action-btn view-message" data-message-id="${message.id}">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="action-btn delete-message" data-message-id="${message.id}">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    `;
                }
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error(`加载${type === 'private' ? '私聊' : '群聊'}消息失败:`, error);
        showToast(`加载${type === 'private' ? '私聊' : '群聊'}消息失败`, 'error');
    });
}

/**
 * 加载举报消息
 */
function loadReportedMessages() {
    fetch('/api/admin/reported-messages')
    .then(response => {
        if (!response.ok) throw new Error('获取举报消息失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('reported-messages-table');
            if (!tbody) {
                console.error('未找到表格元素: reported-messages-table');
                return;
            }
            
            tbody.innerHTML = '';
            
            data.reports.forEach(report => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const reportDate = new Date(report.created_at);
                const formattedDate = reportDate.toLocaleString('zh-CN');
                
                // 状态标签
                let statusHtml = '';
                if (report.status === 'pending') {
                    statusHtml = `<span class="status-badge warning">待处理</span>`;
                } else if (report.status === 'resolved') {
                    statusHtml = `<span class="status-badge success">已处理</span>`;
                } else if (report.status === 'rejected') {
                    statusHtml = `<span class="status-badge danger">已驳回</span>`;
                }
                
                row.innerHTML = `
                    <td>${report.id}</td>
                    <td>${report.reporter_name}</td>
                    <td>${report.message_content}</td>
                    <td>${report.reason}</td>
                    <td>${formattedDate}</td>
                    <td>${statusHtml}</td>
                    <td class="actions">
                        <button class="action-btn view-report" data-report-id="${report.id}">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn resolve-report" data-report-id="${report.id}" ${report.status !== 'pending' ? 'disabled' : ''}>
                            <i class="fas fa-check"></i>
                        </button>
                        <button class="action-btn reject-report" data-report-id="${report.id}" ${report.status !== 'pending' ? 'disabled' : ''}>
                            <i class="fas fa-times"></i>
                        </button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error('加载举报消息失败:', error);
        showToast('加载举报消息失败', 'error');
    });
}

/**
 * 添加用户
 */
function addUser(userData) {
    fetch('/api/admin/users', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(userData)
    })
    .then(response => {
        if (!response.ok) throw new Error('添加用户失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('用户添加成功', 'success');
            loadAllUsers();
        } else {
            showToast(data.message || '添加用户失败', 'error');
        }
    })
    .catch(error => {
        console.error('添加用户失败:', error);
        showToast('添加用户失败', 'error');
    });
}

/**
 * 加载数据库信息
 */
function loadDatabaseInfo() {
    fetch('/api/admin/database/info')
    .then(response => {
        if (!response.ok) throw new Error('获取数据库信息失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            document.getElementById('db-size').textContent = data.size;
            document.getElementById('table-count').textContent = data.table_count;
            document.getElementById('last-backup').textContent = data.last_backup || '无备份';
            document.getElementById('db-status').textContent = data.status;
        }
    })
    .catch(error => {
        console.error('加载数据库信息失败:', error);
        showToast('加载数据库信息失败', 'error');
    });
}

/**
 * 加载数据库表信息
 */
function loadDatabaseTables() {
    fetch('/api/admin/database/tables')
    .then(response => {
        if (!response.ok) throw new Error('获取数据库表信息失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('tables-list');
            if (!tbody) {
                console.error('未找到表格元素: tables-list');
                return;
            }
            
            tbody.innerHTML = '';
            
            data.tables.forEach(table => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const updateDate = new Date(table.last_updated);
                const formattedDate = updateDate.toLocaleString('zh-CN');
                
                row.innerHTML = `
                    <td>${table.name}</td>
                    <td>${table.row_count}</td>
                    <td>${table.size}</td>
                    <td>${formattedDate}</td>
                    <td class="actions">
                        <button class="action-btn optimize-table" data-table="${table.name}">
                            <i class="fas fa-bolt"></i> 优化
                        </button>
                        <button class="action-btn backup-table" data-table="${table.name}">
                            <i class="fas fa-download"></i> 备份
                        </button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error('加载数据库表信息失败:', error);
        showToast('加载数据库表信息失败', 'error');
    });
}

/**
 * 加载数据库备份记录
 */
function loadDatabaseBackups() {
    fetch('/api/admin/database/backups')
    .then(response => {
        if (!response.ok) throw new Error('获取数据库备份记录失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('backups-list');
            if (!tbody) {
                console.error('未找到表格元素: backups-list');
                return;
            }
            
            tbody.innerHTML = '';
            
            data.backups.forEach(backup => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const backupDate = new Date(backup.created_at);
                const formattedDate = backupDate.toLocaleString('zh-CN');
                
                row.innerHTML = `
                    <td>${formattedDate}</td>
                    <td>${backup.size}</td>
                    <td>${backup.type}</td>
                    <td>${backup.filename}</td>
                    <td class="actions">
                        <button class="action-btn download-backup" data-backup="${backup.id}">
                            <i class="fas fa-download"></i> 下载
                        </button>
                        <button class="action-btn restore-backup" data-backup="${backup.id}">
                            <i class="fas fa-undo"></i> 恢复
                        </button>
                        <button class="action-btn delete-backup" data-backup="${backup.id}">
                            <i class="fas fa-trash"></i> 删除
                        </button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error('加载数据库备份记录失败:', error);
        showToast('加载数据库备份记录失败', 'error');
    });
}

/**
 * 备份数据库
 */
function backupDatabase() {
    fetch('/api/admin/database/backup', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) throw new Error('数据库备份失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('数据库备份成功', 'success');
            loadDatabaseBackups();
            loadDatabaseInfo();
        } else {
            showToast(data.message || '数据库备份失败', 'error');
        }
    })
    .catch(error => {
        console.error('数据库备份失败:', error);
        showToast('数据库备份失败', 'error');
    });
}

/**
 * 优化数据库
 */
function optimizeDatabase() {
    fetch('/api/admin/database/optimize', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) throw new Error('数据库优化失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('数据库优化成功', 'success');
            loadDatabaseInfo();
        } else {
            showToast(data.message || '数据库优化失败', 'error');
        }
    })
    .catch(error => {
        console.error('数据库优化失败:', error);
        showToast('数据库优化失败', 'error');
    });
}

/**
 * 加载通知列表
 */
function loadNotifications() {
    fetch('/api/admin/notifications')
    .then(response => {
        if (!response.ok) throw new Error('获取通知列表失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const tbody = document.getElementById('notifications-list');
            if (!tbody) {
                console.error('未找到表格元素: notifications-list');
                return;
            }
            
            tbody.innerHTML = '';
            
            data.notifications.forEach(notification => {
                const row = document.createElement('tr');
                
                // 格式化日期
                const notifyDate = new Date(notification.created_at);
                const formattedDate = notifyDate.toLocaleString('zh-CN');
                
                row.innerHTML = `
                    <td>${notification.id}</td>
                    <td>${notification.title}</td>
                    <td>${notification.content.length > 50 ? notification.content.substring(0, 50) + '...' : notification.content}</td>
                    <td>${notification.target_type === 'all' ? '全体用户' : notification.target_type === 'user' ? '指定用户' : '指定群组'}</td>
                    <td>${formattedDate}</td>
                    <td>${notification.read_count}/${notification.total_count}</td>
                    <td class="actions">
                        <button class="action-btn view-notification" data-notification-id="${notification.id}">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn resend-notification" data-notification-id="${notification.id}">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                        <button class="action-btn delete-notification" data-notification-id="${notification.id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        }
    })
    .catch(error => {
        console.error('加载通知列表失败:', error);
        showToast('加载通知列表失败', 'error');
    });
}

/**
 * 加载通知统计数据
 */
function loadNotificationStats() {
    fetch('/api/admin/notification/stats')
    .then(response => {
        if (!response.ok) throw new Error('获取通知统计数据失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            if (!document.getElementById('notification-stats-chart') || !document.getElementById('notification-read-chart')) {
                console.error('未找到图表元素');
                return;
            }
            
            // 初始化发送统计图表
            const statsCtx = document.getElementById('notification-stats-chart').getContext('2d');
            new Chart(statsCtx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: '通知数量',
                        data: data.counts,
                        backgroundColor: '#4CAF50'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        }
                    }
                }
            });
            
            // 初始化阅读率图表
            const readCtx = document.getElementById('notification-read-chart').getContext('2d');
            new Chart(readCtx, {
                type: 'doughnut',
                data: {
                    labels: ['已读', '未读'],
                    datasets: [{
                        data: [data.read_count, data.total_count - data.read_count],
                        backgroundColor: [
                            '#4CAF50',
                            '#FF5722'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'right',
                        }
                    }
                }
            });
        }
    })
    .catch(error => {
        console.error('加载通知统计数据失败:', error);
        showToast('加载通知统计数据失败', 'error');
    });
}

/**
 * 保存系统设置
 */
function saveSettings() {
    // 收集当前活跃标签页的表单数据
    const activePanel = document.querySelector('.settings-panel.active');
    if (!activePanel) {
        showToast('未找到活跃的设置面板', 'error');
        return;
    }
    
    const formId = activePanel.querySelector('form').id;
    const formData = new FormData(document.getElementById(formId));
    
    // 转换为对象
    const settings = {};
    for (const [key, value] of formData.entries()) {
        settings[key] = value;
    }
    
    // 添加面板标识
    settings.panel = activePanel.id.replace('-settings', '');
    
    // 发送到服务器
    fetch('/api/admin/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
    })
    .then(response => {
        if (!response.ok) throw new Error('保存设置失败');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('设置保存成功', 'success');
        } else {
            showToast(data.message || '保存设置失败', 'error');
        }
    })
    .catch(error => {
        console.error('保存设置失败:', error);
        showToast('保存设置失败', 'error');
    });
} 