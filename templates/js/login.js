/**
 * FUCKCHAT 登录页面JavaScript
 * 处理用户登录逻辑
 */

// 当DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 获取登录表单
    const loginForm = document.getElementById('login-form');
    
    // 添加表单提交事件监听
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // 添加输入框动画效果
    animateFormInputs();
});

/**
 * 处理登录表单提交
 * @param {Event} event - 表单提交事件
 */
async function handleLogin(event) {
    // 阻止表单默认提交行为
    event.preventDefault();
    
    // 获取表单数据
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    // 隐藏之前的错误信息
    hideAuthError();
    
    // 简单的表单验证
    if (!username) {
        showAuthError('用户名不能为空');
        focusInput('username');
        return;
    }
    
    if (!password) {
        showAuthError('密码不能为空');
        focusInput('password');
        return;
    }
    
    // 显示加载状态
    const submitBtn = document.querySelector('.form-actions .btn');
    submitBtn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> 登录中...';
    submitBtn.disabled = true;
    
    try {
        // 使用真实的API进行登录
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 存储用户信息和token
            localStorage.setItem('fuckchat_token', data.token);
            localStorage.setItem('fuckchat_user', JSON.stringify(data.user));
            
            showToast('登录成功，正在跳转...', 'success');
            
            // 延迟跳转到聊天页面
            setTimeout(() => {
                window.location.href = '/chat';
            }, 1000);
        } else {
            // 恢复按钮状态
            submitBtn.innerHTML = '登录';
            submitBtn.disabled = false;
            
            // 显示错误信息
            showAuthError(data.message || '用户名或密码错误');
        }
    } catch (error) {
        console.error('登录失败:', error);
        
        // 恢复按钮状态
        submitBtn.innerHTML = '登录';
        submitBtn.disabled = false;
        
        showAuthError('登录失败，请稍后再试');
    }
}

/**
 * 显示认证错误信息
 * @param {string} message - 错误信息
 */
function showAuthError(message) {
    const errorEl = document.getElementById('auth-error');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.add('show');
    }
}

/**
 * 隐藏认证错误信息
 */
function hideAuthError() {
    const errorEl = document.getElementById('auth-error');
    if (errorEl) {
        errorEl.classList.remove('show');
    }
}

/**
 * 聚焦到指定输入框
 * @param {string} inputId - 输入框ID
 */
function focusInput(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        setTimeout(() => {
            input.focus();
        }, 100);
    }
}

/**
 * 添加表单输入框动画效果
 */
function animateFormInputs() {
    const inputs = document.querySelectorAll('.form-group input');
    
    inputs.forEach(input => {
        // 添加焦点效果
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        input.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
        
        // 添加验证效果
        input.addEventListener('input', function() {
            if (this.value.trim() !== '') {
                this.classList.add('has-value');
            } else {
                this.classList.remove('has-value');
            }
        });
    });
} 