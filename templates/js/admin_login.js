/**
 * FUCKCHAT - 管理员登录
 * 处理管理员登录验证
 */

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 检查是否已登录
    if (isAdminLoggedIn()) {
        window.location.href = '/admin/dashboard';
        return;
    }
    
    // 绑定登录表单提交事件
    document.getElementById('admin-login-form').addEventListener('submit', handleAdminLogin);
});

/**
 * 处理管理员登录表单提交
 */
function handleAdminLogin(event) {
    // 阻止表单默认提交
    event.preventDefault();
    
    // 获取表单数据
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    // 简单验证
    if (!username || !password) {
        showToast('请填写完整的登录信息', 'error');
        return;
    }
    
    // 显示加载状态
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '登录中...';
    
    // 使用FormData构建表单数据
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    // 发送登录请求
    fetch('/api/admin/login', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // 恢复按钮状态
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
        
        if (data.success) {
            // 登录成功，显示成功提示
            showToast('管理员登录成功', 'success');
            
            // 将成功信息存入sessionStorage
            sessionStorage.setItem('admin_logged_in', 'true');
            sessionStorage.setItem('admin_username', username);
            
            // 跳转到管理控制台
            setTimeout(() => {
                const redirectUrl = data.redirect || '/admin/dashboard';
                console.log('准备跳转到:', redirectUrl);
                window.location.href = redirectUrl;
            }, 1000);
        } else {
            // 登录失败，显示错误信息
            showToast(data.message || '管理员登录失败，请检查账号和密码', 'error');
        }
    })
    .catch(error => {
        // 恢复按钮状态
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
        
        console.error('登录请求失败:', error);
        showToast('登录请求失败，请稍后再试', 'error');
    });
}

/**
 * 检查管理员是否已登录
 */
function isAdminLoggedIn() {
    return sessionStorage.getItem('admin_logged_in') === 'true';
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