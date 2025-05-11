/**
 * FUCKCHAT 邮件页面JavaScript
 * 处理邮件列表和邮件详情的交互
 */

// 当DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化文件夹切换
    initFolderSwitching();
    
    // 初始化邮件列表点击
    initMailItemClicks();
    
    // 初始化邮件操作按钮
    initMailActions();
    
    // 模拟数据加载
    setTimeout(() => {
        document.querySelector('.mail-item[data-id="1"]').classList.add('active');
    }, 500);
});

/**
 * 初始化文件夹切换
 */
function initFolderSwitching() {
    const folderItems = document.querySelectorAll('.folder-item');
    
    folderItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            
            // 移除所有激活状态
            folderItems.forEach(fi => fi.classList.remove('active'));
            
            // 设置当前项为激活状态
            this.classList.add('active');
            
            // 更新邮件列表标题
            const folderName = this.querySelector('span').textContent;
            document.querySelector('.mail-list-header h2').textContent = folderName;
            
            // TODO: 加载对应文件夹的邮件
            // 这里可以根据data-folder属性加载不同的邮件数据
            const folderId = this.getAttribute('data-folder');
            loadMailsByFolder(folderId);
        });
    });
}

/**
 * 加载指定文件夹的邮件
 * @param {string} folderId - 文件夹ID
 */
function loadMailsByFolder(folderId) {
    // 模拟加载中效果
    const mailItems = document.querySelector('.mail-items');
    mailItems.innerHTML = '<div class="loading">加载中...</div>';
    
    // 模拟加载延迟
    setTimeout(() => {
        // 根据文件夹类型筛选显示的邮件
        // 实际应用中，这里应该从服务器获取数据
        switch(folderId) {
            case 'system':
                // 只显示系统相关邮件
                mailItems.innerHTML = document.querySelectorAll('.mail-item[data-id="1"], .mail-item[data-id="3"]')[0].outerHTML + 
                                     document.querySelectorAll('.mail-item[data-id="3"]')[0].outerHTML;
                break;
            case 'kunbi':
                // 只显示坤币相关邮件
                mailItems.innerHTML = document.querySelectorAll('.mail-item[data-id="2"], .mail-item[data-id="5"]')[0].outerHTML + 
                                     document.querySelectorAll('.mail-item[data-id="5"]')[0].outerHTML;
                break;
            case 'friends':
                // 只显示好友请求邮件
                mailItems.innerHTML = document.querySelectorAll('.mail-item[data-id="4"]')[0].outerHTML;
                break;
            default:
                // 恢复所有邮件
                resetMailItems();
                break;
        }
        
        // 重新绑定点击事件
        initMailItemClicks();
    }, 500);
}

/**
 * 重置邮件列表到原始状态
 */
function resetMailItems() {
    // 由于我们没有保存原始HTML，这里为简化实现，刷新页面
    // 实际应用中应该保存原始数据或从服务器重新获取
    window.location.reload();
}

/**
 * 初始化邮件列表项点击事件
 */
function initMailItemClicks() {
    const mailItems = document.querySelectorAll('.mail-item');
    
    mailItems.forEach(item => {
        item.addEventListener('click', function() {
            // 移除所有激活状态
            mailItems.forEach(mi => mi.classList.remove('active'));
            
            // 设置当前项为激活状态
            this.classList.add('active');
            
            // 如果是未读邮件，标记为已读
            if (this.classList.contains('unread')) {
                this.classList.remove('unread');
                
                // 更新未读数量徽章
                updateUnreadBadges();
            }
            
            // 加载邮件详情
            const mailId = this.getAttribute('data-id');
            loadMailDetail(mailId);
            
            // 如果是移动设备，隐藏邮件列表，只显示详情
            if (window.innerWidth < 992) {
                document.querySelector('.mail-list').style.display = 'none';
                document.querySelector('.mail-detail').style.display = 'flex';
            }
        });
    });
    
    // 关闭详情按钮
    const closeDetailBtn = document.querySelector('.close-detail-btn');
    if (closeDetailBtn) {
        closeDetailBtn.addEventListener('click', function() {
            // 如果是移动设备，隐藏详情，显示邮件列表
            if (window.innerWidth < 992) {
                document.querySelector('.mail-list').style.display = 'flex';
                document.querySelector('.mail-detail').style.display = 'none';
            }
        });
    }
}

/**
 * 加载邮件详情
 * @param {string} mailId - 邮件ID
 */
function loadMailDetail(mailId) {
    // 获取被点击的邮件项
    const mailItem = document.querySelector(`.mail-item[data-id="${mailId}"]`);
    
    if (!mailItem) return;
    
    // 获取邮件相关信息
    const sender = mailItem.querySelector('.sender-name').textContent;
    const subject = mailItem.querySelector('.mail-subject').textContent;
    const content = mailItem.querySelector('.mail-preview').textContent;
    
    // 更新详情视图
    document.querySelector('.mail-detail-title h2').textContent = subject;
    document.querySelector('.mail-detail-meta .sender').innerHTML = `<i class="fas fa-user"></i> ${sender}`;
    
    // 设置时间(这里使用模拟数据)
    const time = new Date().toLocaleString();
    document.querySelector('.mail-detail-meta .time').innerHTML = `<i class="fas fa-clock"></i> ${time}`;
    
    // 根据邮件ID显示不同的内容
    // 实际应用中，这里应该从服务器获取数据
    let detailContent = '';
    let attachmentHTML = '';
    
    switch(mailId) {
        case '1':
            // 欢迎邮件
            detailContent = `
                <p>亲爱的用户：</p>
                <p>您好，欢迎使用FUCKCHAT邮件系统！</p>
                <p>在这里，您可以接收到以下类型的消息：</p>
                <ul>
                    <li><strong>系统通知</strong> - 包括系统维护、功能更新等重要公告</li>
                    <li><strong>坤币交易</strong> - 当您收到或发出坤币时的交易记录</li>
                    <li><strong>好友请求</strong> - 其他用户发送给您的好友添加请求</li>
                    <li><strong>管理员消息</strong> - 管理员发送的个人或群体通知</li>
                </ul>
                <p>如果您有任何问题或建议，可以直接回复此邮件与管理员联系。</p>
                <p>祝您使用愉快！</p>
                <p class="signature">FUCKCHAT 管理团队</p>
            `;
            attachmentHTML = `
                <h3>附件</h3>
                <div class="attachment-item">
                    <i class="fas fa-file-pdf"></i>
                    <span class="attachment-name">FUCKCHAT用户手册.pdf</span>
                    <a href="#" class="download-btn"><i class="fas fa-download"></i></a>
                </div>
            `;
            break;
        case '2':
            // 坤币转账
            detailContent = `
                <p>亲爱的用户：</p>
                <p>恭喜您！您收到了一笔坤币转账。</p>
                <p>详细信息如下：</p>
                <ul>
                    <li><strong>发送者</strong>：管理员</li>
                    <li><strong>金额</strong>：10坤币</li>
                    <li><strong>时间</strong>：${new Date().toLocaleString()}</li>
                    <li><strong>留言</strong>：感谢您参与系统测试</li>
                </ul>
                <p>此坤币已自动添加到您的账户余额中。</p>
                <p class="signature">FUCKCHAT 坤币系统</p>
            `;
            attachmentHTML = '';
            break;
        case '3':
            // 系统维护通知
            detailContent = `
                <p>尊敬的用户：</p>
                <p>为了提供更好的服务体验，我们将于本周六凌晨2点至4点进行系统维护，期间服务可能会短暂不可用。</p>
                <p>维护内容：</p>
                <ul>
                    <li>数据库性能优化</li>
                    <li>系统安全更新</li>
                    <li>新增坤币红包多人发送功能</li>
                </ul>
                <p>感谢您的理解与支持！</p>
                <p class="signature">FUCKCHAT 系统维护团队</p>
            `;
            attachmentHTML = '';
            break;
        case '4':
            // 好友请求
            detailContent = `
                <p>亲爱的用户：</p>
                <p>用户"张三"请求添加您为好友。</p>
                <p>附言："我们在群里聊过，加个好友吧~"</p>
                <p>您可以选择接受或拒绝此请求。</p>
                <div style="margin: 20px 0;">
                    <button style="background-color: #4a6bff; color: white; border: none; padding: 8px 16px; margin-right: 10px; border-radius: 4px; cursor: pointer;">接受请求</button>
                    <button style="background-color: #f5f5f5; color: #333; border: 1px solid #ddd; padding: 8px 16px; border-radius: 4px; cursor: pointer;">拒绝请求</button>
                </div>
                <p class="signature">FUCKCHAT 用户系统</p>
            `;
            attachmentHTML = '';
            break;
        case '5':
            // 注册奖励
            detailContent = `
                <p>亲爱的新用户：</p>
                <p>感谢您注册FUCKCHAT！</p>
                <p>作为欢迎礼物，我们已向您的账户发放了100坤币作为注册奖励。您可以使用这些坤币：</p>
                <ul>
                    <li>发送坤币红包给好友</li>
                    <li>参与群组活动</li>
                    <li>兑换虚拟礼品（即将推出）</li>
                </ul>
                <p>希望您在FUCKCHAT度过愉快的时光！</p>
                <p class="signature">FUCKCHAT 坤币系统</p>
            `;
            attachmentHTML = '';
            break;
        default:
            detailContent = `<p>没有找到邮件内容</p>`;
            attachmentHTML = '';
    }
    
    // 更新内容和附件
    document.querySelector('.mail-detail-content').innerHTML = detailContent;
    document.querySelector('.mail-attachment').innerHTML = attachmentHTML;
}

/**
 * 初始化邮件操作按钮
 */
function initMailActions() {
    // 刷新按钮
    const refreshBtn = document.querySelector('.refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            // 模拟刷新动画
            this.classList.add('rotating');
            
            // 模拟加载延迟
            setTimeout(() => {
                this.classList.remove('rotating');
                // 实际应用中应该从服务器重新获取数据
                showNotification('邮件已刷新');
            }, 1000);
        });
    }
    
    // 标记已读按钮
    const markReadBtn = document.querySelector('.mark-read-btn');
    if (markReadBtn) {
        markReadBtn.addEventListener('click', function() {
            const unreadItems = document.querySelectorAll('.mail-item.unread');
            unreadItems.forEach(item => {
                item.classList.remove('unread');
            });
            
            // 更新未读数量徽章
            updateUnreadBadges();
            
            showNotification('所有邮件已标记为已读');
        });
    }
    
    // 删除按钮
    const deleteBtn = document.querySelector('.delete-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            const activeItem = document.querySelector('.mail-item.active');
            if (activeItem) {
                // 添加淡出动画
                activeItem.style.opacity = '0';
                activeItem.style.transform = 'translateX(20px)';
                
                // 动画完成后移除元素
                setTimeout(() => {
                    activeItem.remove();
                    showNotification('邮件已删除');
                    
                    // 如果删除后没有邮件，显示空状态
                    if (document.querySelectorAll('.mail-item').length === 0) {
                        document.querySelector('.mail-items').innerHTML = 
                            '<div class="empty-mail">没有邮件</div>';
                    }
                }, 300);
                
                // 更新未读数量徽章
                updateUnreadBadges();
            }
        });
    }
    
    // 详情页中的删除按钮
    const detailDeleteBtn = document.querySelector('.mail-detail-actions .delete-btn');
    if (detailDeleteBtn) {
        detailDeleteBtn.addEventListener('click', function() {
            const activeItem = document.querySelector('.mail-item.active');
            if (activeItem) {
                // 添加淡出动画
                activeItem.style.opacity = '0';
                activeItem.style.transform = 'translateX(20px)';
                
                // 动画完成后移除元素
                setTimeout(() => {
                    activeItem.remove();
                    showNotification('邮件已删除');
                    
                    // 如果是移动设备，返回列表视图
                    if (window.innerWidth < 992) {
                        document.querySelector('.mail-list').style.display = 'flex';
                        document.querySelector('.mail-detail').style.display = 'none';
                    }
                    
                    // 如果删除后没有邮件，显示空状态
                    if (document.querySelectorAll('.mail-item').length === 0) {
                        document.querySelector('.mail-items').innerHTML = 
                            '<div class="empty-mail">没有邮件</div>';
                    }
                }, 300);
                
                // 更新未读数量徽章
                updateUnreadBadges();
            }
        });
    }
    
    // 回复按钮
    const replyBtn = document.querySelector('.reply-btn');
    if (replyBtn) {
        replyBtn.addEventListener('click', function() {
            showNotification('回复功能即将上线');
        });
    }
}

/**
 * 更新未读邮件数量徽章
 */
function updateUnreadBadges() {
    // 计算各类型未读邮件数量
    const inboxUnread = document.querySelectorAll('.mail-item.unread').length;
    const systemUnread = document.querySelectorAll('.mail-item.unread .sender-name:not([role=""]):contains("系统")').length;
    const kunbiUnread = document.querySelectorAll('.mail-item.unread .sender-name:contains("坤币")').length;
    
    // 更新徽章显示
    const inboxBadge = document.querySelector('.folder-item[data-folder="inbox"] .badge');
    const systemBadge = document.querySelector('.folder-item[data-folder="system"] .badge');
    const kunbiBadge = document.querySelector('.folder-item[data-folder="kunbi"] .badge');
    
    if (inboxBadge) {
        if (inboxUnread > 0) {
            inboxBadge.textContent = inboxUnread;
            inboxBadge.style.display = 'inline-block';
        } else {
            inboxBadge.style.display = 'none';
        }
    }
    
    if (systemBadge) {
        if (systemUnread > 0) {
            systemBadge.textContent = systemUnread;
            systemBadge.style.display = 'inline-block';
        } else {
            systemBadge.style.display = 'none';
        }
    }
    
    if (kunbiBadge) {
        if (kunbiUnread > 0) {
            kunbiBadge.textContent = kunbiUnread;
            kunbiBadge.style.display = 'inline-block';
        } else {
            kunbiBadge.style.display = 'none';
        }
    }
}

/**
 * 显示通知消息
 * @param {string} message - 通知内容
 */
function showNotification(message) {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = 'mail-notification';
    notification.textContent = message;
    
    // 添加到页面
    document.body.appendChild(notification);
    
    // 显示通知
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // 3秒后移除通知
    setTimeout(() => {
        notification.classList.remove('show');
        
        // 动画结束后删除元素
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// 为字符串添加包含方法（用于未读邮件计数）
if (!String.prototype.contains) {
    String.prototype.contains = function(substr) {
        return this.indexOf(substr) !== -1;
    };
} 