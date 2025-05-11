/**
 * FUCKCHAT 注册页面JavaScript
 * 处理用户注册逻辑
 */

// 当DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 获取注册表单
    const registerForm = document.getElementById('register-form');
    
    // 添加表单提交事件监听
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
    
    // 添加输入框动画效果
    animateFormInputs();
});

/**
 * 处理注册表单提交
 * @param {Event} event - 表单提交事件
 */
async function handleRegister(event) {
    // 阻止表单默认提交行为
    event.preventDefault();
    
    // 获取表单数据
    const username = document.getElementById('username').value.trim();
    const nickname = document.getElementById('nickname').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    // 隐藏之前的错误信息
    hideAuthError();
    
    // 表单验证
    if (!username) {
        showAuthError('用户名不能为空');
        focusInput('username');
        return;
    }
    
    if (!validateUsername(username)) {
        showAuthError('用户名只能包含字母、数字和下划线，长度3-20位');
        focusInput('username');
        return;
    }
    
    if (!nickname) {
        showAuthError('昵称不能为空');
        focusInput('nickname');
        return;
    }
    
    if (!password) {
        showAuthError('密码不能为空');
        focusInput('password');
        return;
    }
    
    if (!validatePassword(password)) {
        showAuthError('密码长度至少为6位');
        focusInput('password');
        return;
    }
    
    if (password !== confirmPassword) {
        showAuthError('两次输入的密码不一致');
        focusInput('confirm-password');
        return;
    }
    
    // 显示加载状态
    const submitBtn = document.querySelector('.form-actions .btn');
    submitBtn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> 注册中...';
    submitBtn.disabled = true;
    
    try {
        // 使用真实的API注册
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, nickname, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('注册成功，即将跳转到登录页面...', 'success');
            
            // 延迟跳转到登录页面
            setTimeout(() => {
                window.location.href = '/login';
            }, 1500);
        } else {
            // 恢复按钮状态
            submitBtn.innerHTML = '注册';
            submitBtn.disabled = false;
            
            // 显示错误信息
            showAuthError(data.message || '注册失败，请稍后再试');
        }
    } catch (error) {
        console.error('注册失败:', error);
        
        // 恢复按钮状态
        submitBtn.innerHTML = '注册';
        submitBtn.disabled = false;
        
        showAuthError('注册失败，请稍后再试');
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
            
            // 实时验证密码确认
            if (this.id === 'confirm-password' || this.id === 'password') {
                const password = document.getElementById('password').value;
                const confirmPassword = document.getElementById('confirm-password').value;
                
                if (confirmPassword && password !== confirmPassword) {
                    document.getElementById('confirm-password').classList.add('error');
                } else {
                    document.getElementById('confirm-password').classList.remove('error');
                }
            }
        });
    });
}

// 实时验证用户名是否可用
async function checkUsernameAvailability(username) {
    if (!username || !validateUsername(username)) return;
    
    try {
        const response = await fetch(`/api/auth/check-username?username=${encodeURIComponent(username)}`);
        const data = await response.json();
        
        const usernameInput = document.getElementById('username');
        if (data.available) {
            usernameInput.classList.remove('error');
            usernameInput.classList.add('valid');
        } else {
            usernameInput.classList.remove('valid');
            usernameInput.classList.add('error');
        }
    } catch (error) {
        console.error('检查用户名失败:', error);
    }
} 