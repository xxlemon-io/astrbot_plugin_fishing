/**
 * 市场管理JavaScript交互逻辑
 * 支持实时刷新、价格修改、商品下架等功能
 */

// 全局状态
let currentMarketId = null;

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeMarketManager();
});

// 也在页面加载后进行初始化（双重保险）
window.addEventListener('load', function() {
    // 检查是否已经初始化
    const editButtons = document.querySelectorAll('.edit-price-btn');
    if (editButtons.length > 0 && !editButtons[0].hasAttribute('data-initialized')) {
        initializeMarketManager();
    }
});

/**
 * 初始化市场管理器
 */
function initializeMarketManager() {
    try {
        // 绑定价格编辑按钮事件
        bindPriceEditEvents();
        
        // 绑定商品下架按钮事件
        bindRemoveItemEvents();
        
        // 绑定筛选表单事件
        bindFilterEvents();
        
        // 设置自动刷新
        setupAutoRefresh();
    } catch (error) {
        console.error('初始化市场管理器时出错:', error);
    }
}

/**
 * 绑定价格编辑相关事件
 */
function bindPriceEditEvents() {
    // 编辑价格按钮
    const editButtons = document.querySelectorAll('.edit-price-btn');
    editButtons.forEach(button => {
        button.setAttribute('data-initialized', 'true');
        button.addEventListener('click', function() {
            const {marketId} = this.dataset;
            enablePriceEdit(marketId);
        });
    });

    // 保存价格按钮
    document.querySelectorAll('.save-price-btn').forEach(button => {
        button.addEventListener('click', function() {
            const {marketId} = this.dataset;
            savePriceChange(marketId);
        });
    });

    // 取消编辑按钮
    document.querySelectorAll('.cancel-price-btn').forEach(button => {
        button.addEventListener('click', function() {
            const {marketId} = this.dataset;
            cancelPriceEdit(marketId);
        });
    });

    // 价格输入框回车事件
    document.querySelectorAll('.price-input').forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const marketId = this.id.replace('price-input-', '');
                savePriceChange(marketId);
            } else if (e.key === 'Escape') {
                const marketId = this.id.replace('price-input-', '');
                cancelPriceEdit(marketId);
            }
        });
    });
}

/**
 * 绑定商品下架相关事件
 */
function bindRemoveItemEvents() {
    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.addEventListener('click', function() {
            const {marketId, itemName, sellerName} = this.dataset;
            
            showRemoveConfirmModal(marketId, itemName, sellerName);
        });
    });

    // 确认下架按钮
    const confirmRemoveBtn = document.getElementById('confirmRemoveBtn');
    if (confirmRemoveBtn) {
        confirmRemoveBtn.addEventListener('click', function() {
            if (currentMarketId) {
                removeMarketItem(currentMarketId);
            }
        });
    }
}

/**
 * 绑定筛选表单事件
 */
function bindFilterEvents() {
    // 实时搜索
    const searchInput = document.getElementById('search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (this.value.length >= 2 || this.value.length === 0) {
                    submitFilterForm();
                }
            }, 500);
        });
    }

    // 筛选条件变化时自动提交
    const filterSelects = document.querySelectorAll('#item_type, #min_price, #max_price');
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            submitFilterForm();
        });
    });
}

/**
 * 设置自动刷新
 */
function setupAutoRefresh() {
    // 每30秒自动刷新一次数据
    setInterval(() => {
        refreshMarketData(false); // 静默刷新
    }, 30000);
}

/**
 * 启用价格编辑模式
 */
function enablePriceEdit(marketId) {
    const priceDisplay = document.getElementById(`price-display-${marketId}`);
    const priceInput = document.getElementById(`price-input-${marketId}`);
    const editBtn = document.querySelector(`.edit-price-btn[data-market-id="${marketId}"]`);
    const saveBtn = document.querySelector(`.save-price-btn[data-market-id="${marketId}"]`);
    const cancelBtn = document.querySelector(`.cancel-price-btn[data-market-id="${marketId}"]`);

    if (priceDisplay && priceInput && editBtn && saveBtn && cancelBtn) {
        // 隐藏价格显示，显示输入框
        priceDisplay.classList.add('d-none');
        priceInput.classList.remove('d-none');
        
        // 切换按钮显示
        editBtn.classList.add('d-none');
        saveBtn.classList.remove('d-none');
        cancelBtn.classList.remove('d-none');
        
        // 聚焦到输入框并选中文本
        priceInput.focus();
        priceInput.select();
    }
}

/**
 * 取消价格编辑
 */
function cancelPriceEdit(marketId) {
    const priceDisplay = document.getElementById(`price-display-${marketId}`);
    const priceInput = document.getElementById(`price-input-${marketId}`);
    const editBtn = document.querySelector(`.edit-price-btn[data-market-id="${marketId}"]`);
    const saveBtn = document.querySelector(`.save-price-btn[data-market-id="${marketId}"]`);
    const cancelBtn = document.querySelector(`.cancel-price-btn[data-market-id="${marketId}"]`);

    if (priceDisplay && priceInput && editBtn && saveBtn && cancelBtn) {
        // 恢复原始价格
        const originalPrice = priceDisplay.textContent.match(/\d+/)[0];
        priceInput.value = originalPrice;
        
        // 恢复显示状态
        priceDisplay.classList.remove('d-none');
        priceInput.classList.add('d-none');
        
        // 切换按钮显示
        editBtn.classList.remove('d-none');
        saveBtn.classList.add('d-none');
        cancelBtn.classList.add('d-none');
    }
}

/**
 * 保存价格修改
 */
async function savePriceChange(marketId) {
    const priceInput = document.getElementById(`price-input-${marketId}`);
    const newPrice = parseInt(priceInput.value);

    if (!newPrice || newPrice <= 0) {
        showAlert('请输入有效的价格（大于0）', 'warning');
        return;
    }

    try {
        showLoading(true);
        
        const response = await fetch(`/admin/market/${marketId}/price`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ price: newPrice })
        });

        const result = await response.json();

        if (result.success) {
            // 更新页面显示
            updatePriceDisplay(marketId, newPrice);
            showAlert(result.message, 'success');
            cancelPriceEdit(marketId);
        } else {
            showAlert(result.message, 'danger');
        }
    } catch (error) {
        console.error('保存价格失败:', error);
        showAlert('保存价格失败，请重试', 'danger');
    } finally {
        showLoading(false);
    }
}

/**
 * 更新价格显示
 */
function updatePriceDisplay(marketId, newPrice) {
    const priceDisplay = document.getElementById(`price-display-${marketId}`);
    if (priceDisplay) {
        // 使用安全的DOM操作替代innerHTML
        priceDisplay.textContent = '';
        const icon = document.createElement('i');
        icon.className = 'fas fa-coins text-warning';
        const text = document.createTextNode(` ${newPrice}`);
        priceDisplay.appendChild(icon);
        priceDisplay.appendChild(text);
    }
}

/**
 * 显示下架确认模态框
 */
function showRemoveConfirmModal(marketId, itemName, sellerName) {
    currentMarketId = marketId;
    
    const modal = document.getElementById('removeItemModal');
    const itemNameSpan = document.getElementById('modalItemName');
    const sellerNameSpan = document.getElementById('modalSellerName');

    if (modal && itemNameSpan && sellerNameSpan) {
        itemNameSpan.textContent = itemName;
        sellerNameSpan.textContent = sellerName;
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }
}

/**
 * 下架商品
 */
async function removeMarketItem(marketId) {
    try {
        showLoading(true);
        
        const response = await fetch(`/admin/market/${marketId}/remove`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (result.success) {
            // 移除商品行
            const listingRow = document.getElementById(`listing-${marketId}`);
            if (listingRow) {
                listingRow.remove();
            }
            
            showAlert(result.message, 'success');
            
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('removeItemModal'));
            if (modal) {
                modal.hide();
            }
            
            // 更新统计信息
            updateStatsAfterRemoval();
        } else {
            showAlert(result.message, 'danger');
        }
    } catch (error) {
        console.error('下架商品失败:', error);
        showAlert('下架商品失败，请重试', 'danger');
    } finally {
        showLoading(false);
        currentMarketId = null;
    }
}

/**
 * 下架后更新统计信息
 */
function updateStatsAfterRemoval() {
    // 简单的统计更新，减少总商品数
    const totalListingsElement = document.querySelector('.card.bg-primary h4');
    if (totalListingsElement) {
        const current = parseInt(totalListingsElement.textContent);
        totalListingsElement.textContent = current - 1;
    }
}

/**
 * 提交筛选表单
 */
function submitFilterForm() {
    const form = document.getElementById('filterForm');
    if (form) {
        form.submit();
    }
}

/**
 * 清空筛选条件
 */
function clearFilters() {
    const form = document.getElementById('filterForm');
    if (form) {
        // 清空所有输入框和选择框
        form.querySelectorAll('input, select').forEach(element => {
            if (element.type === 'number' || element.type === 'text') {
                element.value = '';
            } else if (element.type === 'select-one') {
                element.selectedIndex = 0;
            }
        });
        
        // 提交表单
        form.submit();
    }
}

/**
 * 刷新市场数据
 */
function refreshMarketData(showMessage = true) {
    if (showMessage) {
        showLoading(true);
    }
    
    // 重新加载当前页面
    const currentUrl = new URL(window.location);
    
    fetch(currentUrl.toString())
        .then(response => response.text())
        .then(html => {
            // 创建临时DOM解析响应
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // 更新商品列表
            const newTable = doc.querySelector('.table-responsive');
            const currentTable = document.querySelector('.table-responsive');
            if (newTable && currentTable) {
                // 使用安全的方法替换内容
                currentTable.textContent = '';
                Array.from(newTable.childNodes).forEach(node => {
                    currentTable.appendChild(node.cloneNode(true));
                });
            }
            
            // 更新统计信息
            const newStats = doc.querySelectorAll('.card h4');
            const currentStats = document.querySelectorAll('.card h4');
            newStats.forEach((stat, index) => {
                if (currentStats[index]) {
                    currentStats[index].textContent = stat.textContent;
                }
            });
            
            // 重新绑定事件
            bindPriceEditEvents();
            bindRemoveItemEvents();
            
            if (showMessage) {
                showAlert('数据已刷新', 'info');
            }
        })
        .catch(error => {
            console.error('刷新数据失败:', error);
            if (showMessage) {
                showAlert('刷新数据失败', 'danger');
            }
        })
        .finally(() => {
            if (showMessage) {
                showLoading(false);
            }
        });
}

/**
 * 显示/隐藏加载指示器
 */
function showLoading(show) {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        if (show) {
            loadingIndicator.classList.remove('d-none');
        } else {
            loadingIndicator.classList.add('d-none');
        }
    }
}

/**
 * 显示警告消息
 */
function showAlert(message, type = 'info') {
    // 创建警告元素
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    
    // 使用安全的DOM操作
    const messageText = document.createTextNode(message);
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');
    
    alertDiv.appendChild(messageText);
    alertDiv.appendChild(closeButton);
    
    // 插入到主容器顶部
    const mainContainer = document.querySelector('main .container');
    if (mainContainer) {
        mainContainer.insertBefore(alertDiv, mainContainer.firstChild);
        
        // 3秒后自动关闭
        setTimeout(() => {
            alertDiv.remove();
        }, 3000);
    }
}

/**
 * 格式化数字显示
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * 验证价格输入
 */
function validatePrice(price) {
    const num = parseInt(price);
    return !isNaN(num) && num > 0 && num <= 999999999;
}

// 导出函数供全局使用
window.refreshMarketData = refreshMarketData;
window.clearFilters = clearFilters;
window.initializeMarketManager = initializeMarketManager;

// 如果DOM已经准备好，立即初始化
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(initializeMarketManager, 0);
}
