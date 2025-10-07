/**
 * 游戏通用JavaScript - 移动端优化
 */

class GameApp {
    constructor() {
        this.apiBase = '/game/api';
        this.userInfo = null;
        this.refreshInterval = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadUserInfo();
        this.setupBottomNavigation();
        // 移除自动刷新，只在用户操作后更新
    }
    
    setupEventListeners() {
        // 全局错误处理
        window.addEventListener('error', (e) => {
            console.error('Global error:', e.error);
            this.showToast('发生错误，请刷新页面重试', 'danger');
        });
        
        // 网络状态监听
        window.addEventListener('online', () => {
            this.showToast('网络已连接', 'success');
        });
        
        window.addEventListener('offline', () => {
            this.showToast('网络已断开', 'warning');
        });
        
        // 阻止双击缩放
        let lastTouchEnd = 0;
        document.addEventListener('touchend', (e) => {
            const now = new Date().getTime();
            if (now - lastTouchEnd <= 300) {
                e.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
    }
    
    setupBottomNavigation() {
        const navLinks = document.querySelectorAll('.game-bottom-nav .nav-link');
        const currentPath = window.location.pathname;
        
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (currentPath.includes(href.split('/').pop())) {
                link.classList.add('active');
            }
            
            link.addEventListener('click', (e) => {
                // 移除所有active类
                navLinks.forEach(l => l.classList.remove('active'));
                // 添加active类到当前链接
                link.classList.add('active');
            });
        });
    }
    
    
    async loadUserInfo() {
        try {
            const response = await this.apiCall('/profile', 'GET');
            if (response.success) {
                this.userInfo = response.data;
                this.updateUserDisplay();
            }
        } catch (error) {
            console.error('Failed to load user info:', error);
        }
    }
    
    updateUserDisplay() {
        if (!this.userInfo) return;
        
        // 更新金币和钻石显示
        const coinsElement = document.getElementById('userCoins');
        const premiumElement = document.getElementById('userPremium');
        
        if (coinsElement) {
            coinsElement.textContent = this.formatNumber(this.userInfo.coins || 0);
        }
        
        if (premiumElement) {
            premiumElement.textContent = this.formatNumber(this.userInfo.premium_currency || 0);
        }
    }
    
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    async apiCall(endpoint, method = 'GET', data = null) {
        const url = `${this.apiBase}${endpoint}`;
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            const result = await response.json();
            
            // 检查是否需要重新登录
            if (result.redirect && result.redirect.includes('/login')) {
                window.location.href = result.redirect;
                return;
            }
            
            return result;
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }
    
    showLoading(show = true) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            if (show) {
                overlay.classList.remove('d-none');
            } else {
                overlay.classList.add('d-none');
            }
        }
    }
    
    showToast(message, type = 'info', duration = 3000) {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="fas fa-${this.getToastIcon(type)} text-${type} me-2"></i>
                    <strong class="me-auto">${this.getToastTitle(type)}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: duration
        });
        
        toast.show();
        
        // 自动移除DOM元素
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
    
    getToastIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    getToastTitle(type) {
        const titles = {
            'success': '成功',
            'danger': '错误',
            'warning': '警告',
            'info': '提示'
        };
        return titles[type] || '提示';
    }
    
    confirm(message, title = '确认') {
        return new Promise((resolve) => {
            const modalHtml = `
                <div class="modal fade" id="confirmModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">${title}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                ${message}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                                <button type="button" class="btn btn-primary" id="confirmBtn">确认</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
            modal.show();
            
            document.getElementById('confirmBtn').addEventListener('click', () => {
                modal.hide();
                resolve(true);
            });
            
            document.getElementById('confirmModal').addEventListener('hidden.bs.modal', () => {
                document.getElementById('confirmModal').remove();
                resolve(false);
            });
        });
    }
    
    // 防抖函数
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // 节流函数
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    // 格式化时间
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    // 倒计时
    startCountdown(element, seconds, callback) {
        let remaining = seconds;
        
        const updateDisplay = () => {
            if (element) {
                element.textContent = this.formatTime(remaining);
            }
            
            if (remaining <= 0) {
                if (callback) callback();
                return;
            }
            
            remaining--;
            setTimeout(updateDisplay, 1000);
        };
        
        updateDisplay();
    }
    
    // 复制到剪贴板
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('已复制到剪贴板', 'success');
        } catch (err) {
            // 降级方案
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showToast('已复制到剪贴板', 'success');
        }
    }
    
    // 震动反馈（移动端）
    vibrate(pattern = 100) {
        if ('vibrate' in navigator) {
            navigator.vibrate(pattern);
        }
    }
    
    // 清理资源
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

// 全局函数
function logout() {
    if (confirm('确定要退出登录吗？')) {
        gameApp.apiCall('/logout', 'POST').then(() => {
            window.location.href = '/game/login';
        });
    }
}

function showLoading(show = true) {
    if (window.gameApp) {
        window.gameApp.showLoading(show);
    }
}

function showToast(message, type = 'info', duration = 3000) {
    if (window.gameApp) {
        window.gameApp.showToast(message, type, duration);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.gameApp = new GameApp();
});

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    if (window.gameApp) {
        window.gameApp.destroy();
    }
});
