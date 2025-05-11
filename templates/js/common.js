/**
 * FUCKCHAT 公共JavaScript函数
 * 包含整个应用中共享的函数和工具方法
 */

// 检查用户是否已登录
function isLoggedIn() {
    return localStorage.getItem('fuckchat_token') !== null;
}

// 获取当前用户信息
function getCurrentUser() {
    const userJson = localStorage.getItem('fuckchat_user');
    return userJson ? JSON.parse(userJson) : null;
}

// 简单的Toast提示
function showToast(message, type = 'info', duration = 3000) {
    // 检查是否已存在toast容器
    let toastContainer = document.querySelector('.toast-container');
    
    // 如果不存在，创建一个
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
        
        // 添加CSS
        const style = document.createElement('style');
        style.textContent = `
            .toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
            }
            .toast {
                padding: 12px 20px;
                margin-bottom: 10px;
                border-radius: 4px;
                color: white;
                font-size: 14px;
                opacity: 0;
                transform: translateX(100%);
                transition: all 0.3s ease;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            .toast.show {
                opacity: 1;
                transform: translateX(0);
            }
            .toast.info {
                background-color: #4a6bff;
            }
            .toast.success {
                background-color: #20c997;
            }
            .toast.warning {
                background-color: #ffc107;
                color: #333;
            }
            .toast.error {
                background-color: #dc3545;
            }
        `;
        document.head.appendChild(style);
    }
    
    // 创建Toast元素
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    // 添加到容器
    toastContainer.appendChild(toast);
    
    // 显示Toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // 自动移除
    setTimeout(() => {
        toast.classList.remove('show');
        
        setTimeout(() => {
            toastContainer.removeChild(toast);
        }, 300);
    }, duration);
}

// 格式化日期时间
function formatDateTime(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    return `${date.getFullYear()}-${padZero(date.getMonth() + 1)}-${padZero(date.getDate())} ${padZero(date.getHours())}:${padZero(date.getMinutes())}:${padZero(date.getSeconds())}`;
}

// 格式化日期
function formatDate(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    return `${date.getFullYear()}-${padZero(date.getMonth() + 1)}-${padZero(date.getDate())}`;
}

// 格式化时间
function formatTime(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    return `${padZero(date.getHours())}:${padZero(date.getMinutes())}`;
}

// 补零
function padZero(num) {
    return num < 10 ? `0${num}` : num;
}

// 检查网络连接状态
function checkNetworkStatus() {
    return navigator.onLine;
}

// 简单的防抖函数
function debounce(func, wait = 300) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// 简单的节流函数
function throttle(func, limit = 300) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 路由到指定页面
function navigateTo(page) {
    // 将.html结尾的路径转换为正确的路由格式
    if (page.endsWith('.html')) {
        page = '/' + page.replace('.html', '');
    }
    window.location.href = page;
}

// 退出登录
function logout() {
    localStorage.removeItem('fuckchat_token');
    localStorage.removeItem('fuckchat_user');
    navigateTo('/login');
}

// 表单验证 - 用户名
function validateUsername(username) {
    return /^[a-zA-Z0-9_]{3,20}$/.test(username);
}

// 表单验证 - 密码
function validatePassword(password) {
    return password.length >= 6;
}

// 检测移动设备
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// 检查是否为管理员
function isAdmin() {
    const user = getCurrentUser();
    return user && user.isAdmin;
}

// 页面加载时执行的初始化函数
document.addEventListener('DOMContentLoaded', function() {
    // 根据登录状态调整导航
    updateNavigation();
    
    // 添加注销按钮事件
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
});

// 根据登录状态更新导航
function updateNavigation() {
    // 检查是否在登录后的页面
    const path = window.location.pathname;
    const isAuthPage = path === '/' || 
                      path === '/login' || 
                      path === '/register' || 
                      path === '/about';
    
    // 如果已登录且在登录/注册/首页，跳转到聊天页
    if (isLoggedIn() && isAuthPage) {
        const excludedPaths = ['/admin', '/admin/dashboard'];
        
        if (!excludedPaths.includes(path)) {
            navigateTo('/chat');
        }
    }
    
    // 如果未登录且在需要登录的页面，跳转到登录页
    if (!isLoggedIn() && path === '/chat') {
        navigateTo('/login');
    }
}