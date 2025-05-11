/**
 * FUCKCHAT 个人资料页面JavaScript
 * 处理用户资料设置、账号安全、隐私设置等功能
 */

// 当DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化用户信息
    initUserInfo();
    
    // 初始化标签切换
    initTabSwitching();
    
    // 初始化表单提交
    initFormSubmits();
    
    // 初始化头像上传
    initAvatarUpload();
});

/**
 * 初始化用户信息显示
 */
function initUserInfo() {
    // 从localStorage获取用户信息
    const userInfo = getUserFromStorage();
    
    if (userInfo) {
        // 更新页面上的用户信息
        document.getElementById('user-nickname').textContent = userInfo.nickname || '用户昵称';
        document.getElementById('user-kunbi').textContent = userInfo.kunbi || '0';
        
        if (userInfo.avatar) {
            document.getElementById('current-avatar').src = userInfo.avatar;
        }
        
        // 填充表单字段
        document.getElementById('nickname').value = userInfo.nickname || '';
        
        // 如果有生物信息和性别，也填充
        if (userInfo.bio) {
            document.getElementById('bio').value = userInfo.bio;
        }
        
        if (userInfo.gender) {
            const genderRadio = document.querySelector(`input[name="gender"][value="${userInfo.gender}"]`);
            if (genderRadio) {
                genderRadio.checked = true;
            }
        }
    } else {
        // 如果没有用户信息，重定向到登录页面
        window.location.href = '/login';
    }
}

/**
 * 从本地存储获取用户信息
 */
function getUserFromStorage() {
    const userJson = localStorage.getItem('fuckchat_user');
    return userJson ? JSON.parse(userJson) : null;
}

/**
 * 初始化标签切换
 */
function initTabSwitching() {
    const menuItems = document.querySelectorAll('.menu-item');
    
    menuItems.forEach(item => {
        item.addEventListener('click', function(e) {
            // 仅处理区域内标签，忽略"返回聊天"
            if (this.getAttribute('href').startsWith('#')) {
                e.preventDefault();
                
                // 获取目标标签ID
                const targetId = this.getAttribute('href');
                
                // 移除所有激活状态
                menuItems.forEach(mi => mi.classList.remove('active'));
                document.querySelectorAll('.settings-section').forEach(section => {
                    section.classList.remove('active');
                });
                
                // 设置当前项为激活状态
                this.classList.add('active');
                
                // 显示目标内容
                document.querySelector(targetId).classList.add('active');
            }
        });
    });
}

/**
 * 初始化表单提交
 */
function initFormSubmits() {
    // 个人资料表单
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 获取表单数据
            const nickname = document.getElementById('nickname').value;
            const bio = document.getElementById('bio').value;
            const genderElement = document.querySelector('input[name="gender"]:checked');
            const gender = genderElement ? genderElement.value : 'other';
            
            // 验证昵称
            if (!nickname.trim()) {
                showToast('昵称不能为空', 'error');
                return;
            }
            
            // 获取当前用户信息
            const userInfo = getUserFromStorage();
            if (!userInfo) {
                showToast('用户信息不存在，请重新登录', 'error');
                return;
            }
            
            // 准备提交数据
            const updateData = {
                nickname: nickname,
                gender: gender,
                signature: bio // 后端字段是signature
            };
            
            // 显示加载状态
            const submitBtn = profileForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = '保存中...';
            
            // 发送到服务器更新
            updateProfileToServer(updateData)
                .then(success => {
                    if (success) {
                        // 更新本地存储
                        userInfo.nickname = nickname;
                        userInfo.gender = gender;
                        userInfo.bio = bio;
                        localStorage.setItem('fuckchat_user', JSON.stringify(userInfo));
                        
                        // 更新页面显示
                        document.getElementById('user-nickname').textContent = nickname;
                        
                        // 显示成功消息
                        showToast('个人资料已更新', 'success');
                    }
                })
                .catch(error => {
                    console.error('更新个人资料失败:', error);
                    showToast('更新失败: ' + error.message, 'error');
                })
                .finally(() => {
                    // 恢复按钮状态
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalBtnText;
                });
        });
    }
    
    // 密码修改表单
    const passwordForm = document.getElementById('password-form');
    if (passwordForm) {
        passwordForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 获取表单数据
            const currentPassword = document.getElementById('current-password').value;
            const newPassword = document.getElementById('new-password').value;
            const confirmPassword = document.getElementById('confirm-password').value;
            
            // 验证表单
            if (!currentPassword || !newPassword || !confirmPassword) {
                showToast('所有密码字段均为必填', 'error');
                return;
            }
            
            if (newPassword !== confirmPassword) {
                showToast('新密码和确认密码不匹配', 'error');
                return;
            }
            
            if (newPassword.length < 6) {
                showToast('新密码长度至少为6个字符', 'error');
                return;
            }
            
            // 显示加载状态
            const submitBtn = passwordForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = '更新中...';
            
            // 发送到服务器更新密码
            updatePasswordToServer(currentPassword, newPassword)
                .then(success => {
                    if (success) {
                        // 重置表单
                        passwordForm.reset();
                        
                        // 显示成功消息
                        showToast('密码已成功更新', 'success');
                    }
                })
                .catch(error => {
                    console.error('更新密码失败:', error);
                    showToast('更新失败: ' + error.message, 'error');
                })
                .finally(() => {
                    // 恢复按钮状态
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalBtnText;
                });
        });
    }
    
    // 隐私设置保存
    const savePrivacyBtn = document.getElementById('save-privacy');
    if (savePrivacyBtn) {
        savePrivacyBtn.addEventListener('click', function() {
            // 获取隐私设置
            const allowSearch = document.querySelector('input[name="allow_search"]').checked;
            const allowGroup = document.querySelector('input[name="allow_group"]').checked;
            const notifyMessage = document.querySelector('input[name="notify_message"]').checked;
            const notifyKunbi = document.querySelector('input[name="notify_kunbi"]').checked;
            const notifyFriend = document.querySelector('input[name="notify_friend"]').checked;
            
            // 获取当前用户信息
            const userInfo = getUserFromStorage();
            if (!userInfo) {
                showToast('用户信息不存在，请重新登录', 'error');
                return;
            }
            
            // 保存用户隐私设置到本地存储
            userInfo.privacy = {
                allowSearch,
                allowGroup,
                notifyMessage,
                notifyKunbi,
                notifyFriend
            };
            
            localStorage.setItem('fuckchat_user', JSON.stringify(userInfo));
            
            // 显示成功消息
            showToast('隐私设置已保存', 'success');
        });
    }
    
    // 退出登录按钮
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            // 调用API退出登录
            logoutFromServer()
                .then(() => {
                    // 清除本地存储中的用户信息
                    localStorage.removeItem('fuckchat_user');
                    localStorage.removeItem('fuckchat_token');
                    
                    // 重定向到登录页面
                    window.location.href = '/login';
                })
                .catch(error => {
                    console.error('退出登录失败:', error);
                    
                    // 即使API失败，也清除本地存储
                    localStorage.removeItem('fuckchat_user');
                    localStorage.removeItem('fuckchat_token');
                    
                    // 重定向到登录页面
                    window.location.href = '/login';
                });
        });
    }
    
    // 注销账号按钮
    const deleteAccountBtn = document.getElementById('delete-account-btn');
    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener('click', function() {
            // 显示确认模态框
            document.getElementById('delete-account-modal').classList.add('active');
        });
    }
    
    // 关闭模态框
    const closeModalBtns = document.querySelectorAll('.close-btn, .close-modal-btn');
    closeModalBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const modal = btn.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });
    
    // 点击模态框背景关闭
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('active');
            }
        });
    });
    
    // 处理注销账号表单
    const deleteAccountForm = document.getElementById('delete-account-form');
    if (deleteAccountForm) {
        deleteAccountForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const password = document.getElementById('confirm-delete-password').value;
            
            if (!password) {
                showToast('请输入密码确认', 'error');
                return;
            }
            
            // 显示加载状态
            const submitBtn = deleteAccountForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = '处理中...';
            
            // 发送到服务器注销账号
            deleteAccountFromServer(password)
                .then(success => {
                    if (success) {
                        // 清除本地存储中的用户信息
                        localStorage.removeItem('fuckchat_user');
                        localStorage.removeItem('fuckchat_token');
                        
                        // 显示成功消息
                        showToast('账号已成功注销', 'success');
                        
                        // 延迟后重定向到首页
                        setTimeout(() => {
                            window.location.href = '/';
                        }, 2000);
                    }
                })
                .catch(error => {
                    console.error('注销账号失败:', error);
                    showToast('注销失败: ' + error.message, 'error');
                    
                    // 恢复按钮状态
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalBtnText;
                });
        });
    }
}

/**
 * 向服务器发送更新个人资料请求
 * @param {Object} profileData - 需要更新的个人资料数据
 * @returns {Promise<boolean>} 是否更新成功
 */
async function updateProfileToServer(profileData) {
    try {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            throw new Error('未登录，请先登录');
        }
        
        const response = await fetch('/api/auth/profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(profileData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || '更新失败');
        }
        
        return data.success;
    } catch (error) {
        console.error('更新个人资料失败:', error);
        throw error;
    }
}

/**
 * 向服务器发送更新密码请求
 * @param {string} currentPassword - 当前密码
 * @param {string} newPassword - 新密码
 * @returns {Promise<boolean>} 是否更新成功
 */
async function updatePasswordToServer(currentPassword, newPassword) {
    try {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            throw new Error('未登录，请先登录');
        }
        
        const response = await fetch('/api/auth/password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || '更新密码失败');
        }
        
        return data.success;
    } catch (error) {
        console.error('更新密码失败:', error);
        throw error;
    }
}

/**
 * 向服务器发送退出登录请求
 * @returns {Promise<boolean>} 是否成功退出登录
 */
async function logoutFromServer() {
    try {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            return true; // 已退出登录
        }
        
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        return response.ok;
    } catch (error) {
        console.error('退出登录失败:', error);
        throw error;
    }
}

/**
 * 向服务器发送注销账号请求
 * @param {string} password - 用户密码
 * @returns {Promise<boolean>} 是否成功注销账号
 */
async function deleteAccountFromServer(password) {
    try {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            throw new Error('未登录，请先登录');
        }
        
        const response = await fetch('/api/auth/account/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                password: password
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || '注销账号失败');
        }
        
        return data.success;
    } catch (error) {
        console.error('注销账号失败:', error);
        throw error;
    }
}

/**
 * 初始化头像上传
 */
function initAvatarUpload() {
    const avatarUpload = document.getElementById('avatar-upload');
    
    if (avatarUpload) {
        avatarUpload.addEventListener('change', function() {
            const file = this.files[0];
            
            if (file) {
                // 验证文件类型
                if (!file.type.match('image.*')) {
                    showToast('请选择图片文件', 'error');
                    return;
                }
                
                // 验证文件大小 (最大2MB)
                if (file.size > 2 * 1024 * 1024) {
                    showToast('图片大小不能超过2MB', 'error');
                    return;
                }
                
                // 读取文件并显示预览
                const reader = new FileReader();
                reader.onload = function(e) {
                    const avatarImg = document.getElementById('current-avatar');
                    avatarImg.src = e.target.result;
                    
                    // 准备上传到服务器
                    uploadAvatarToServer(file);
                };
                
                reader.readAsDataURL(file);
            }
        });
    }
}

/**
 * 上传头像到服务器
 * @param {File} file - 头像文件
 */
async function uploadAvatarToServer(file) {
    try {
        const token = localStorage.getItem('fuckchat_token');
        if (!token) {
            throw new Error('未登录，请先登录');
        }
        
        // 创建FormData对象
        const formData = new FormData();
        formData.append('avatar', file);
        
        // 显示上传中提示
        showToast('头像上传中...', 'info');
        
        // 发送上传请求 - 修正API路径
        const response = await fetch('/api/auth/avatar', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || `上传失败 (${response.status})`);
        }
        
        if (data.success) {
            // 获取当前用户信息
            const userInfo = getUserFromStorage();
            if (userInfo) {
                // 更新头像数据
                userInfo.avatar = data.avatar_url || data.avatar;
                
                // 保存到本地存储
                localStorage.setItem('fuckchat_user', JSON.stringify(userInfo));
                
                // 更新头像UI
                updateAvatarUI(userInfo.avatar);
                
                // 显示成功消息
                showToast('头像已更新', 'success');
            }
        } else {
            throw new Error(data.message || '上传失败');
        }
    } catch (error) {
        console.error('上传头像失败:', error);
        showToast('头像上传失败: ' + error.message, 'error');
    }
}

/**
 * 显示提示消息
 * @param {string} message - 提示信息
 * @param {string} type - 提示类型 ('success' 或 'error')
 */
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMessage = toast.querySelector('.toast-message');
    const toastIcon = toast.querySelector('.toast-icon');
    
    // 设置消息内容
    toastMessage.textContent = message;
    
    // 设置图标类型
    toastIcon.className = 'toast-icon';
    toastIcon.classList.add(type);
    
    // 更改图标
    if (type === 'success') {
        toastIcon.className = 'fas fa-check-circle toast-icon success';
    } else {
        toastIcon.className = 'fas fa-times-circle toast-icon error';
    }
    
    // 显示提示
    toast.classList.add('show');
    
    // 3秒后隐藏
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

/**
 * 更新用户界面上的头像
 * @param {string} avatarUrl - 头像URL
 */
function updateAvatarUI(avatarUrl) {
    // 更新所有头像显示
    const avatarElements = document.querySelectorAll('.user-avatar img, .profile-avatar img');
    avatarElements.forEach(img => {
        img.src = avatarUrl;
        // 添加错误处理，确保在加载失败时使用默认头像
        img.onerror = function() {
            this.src = '/src/images/default-avatar.png';
            // 如果默认头像也不存在，使用备用方案
            this.onerror = function() {
                this.src = '/src/images/avtar.jpg';
                this.onerror = null; // 防止死循环
            };
        };
    });
} 