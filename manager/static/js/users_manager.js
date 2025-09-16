document.addEventListener('DOMContentLoaded', function() {
    // 视图切换
    const listViewRadio = document.getElementById('listView');
    const cardViewRadio = document.getElementById('cardView');
    const listViewContent = document.getElementById('listViewContent');
    const cardViewContent = document.getElementById('cardViewContent');

    listViewRadio.addEventListener('change', function() {
        if (this.checked) {
            listViewContent.style.display = 'block';
            cardViewContent.style.display = 'none';
        }
    });

    cardViewRadio.addEventListener('change', function() {
        if (this.checked) {
            listViewContent.style.display = 'none';
            cardViewContent.style.display = 'block';
        }
    });

    // 搜索功能
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');

    function performSearch() {
        const keyword = searchInput.value.trim();
        if (keyword) {
            window.location.href = usersUrl + '?search=' + encodeURIComponent(keyword);
        } else {
            window.location.href = usersUrl;
        }
    }

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // 查看用户详情
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const userId = this.getAttribute('data-user-id');
            loadUserDetail(userId);
        });
    });

    // 编辑用户
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const userId = this.getAttribute('data-user-id');
            loadUserForEdit(userId);
        });
    });

    // 删除用户
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const userId = this.getAttribute('data-user-id');
            const userName = this.getAttribute('data-user-name');
            if (confirm(`确定要删除用户【${userName}】吗？此操作将删除该用户的所有数据，且无法恢复！`)) {
                deleteUser(userId);
            }
        });
    });

    // 从详情模态框编辑
    document.getElementById('editFromDetailBtn').addEventListener('click', function() {
        const userId = this.getAttribute('data-user-id');
        if (userId) {
            loadUserForEdit(userId);
            bootstrap.Modal.getInstance(document.getElementById('userDetailModal')).hide();
        }
    });

    // 表单提交
    const form = document.getElementById('user-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const userId = formData.get('user_id');
        
            // 将表单数据转换为对象
            const userData = {};
            for (let [key, value] of formData.entries()) {
                if (key === 'auto_fishing_enabled') {
                    userData[key] = true;
                } else if (value !== '') {
                    userData[key] = value;
                }
            }

            // 转换数字字段
            const numberFields = ['coins', 'premium_currency', 'total_fishing_count', 'total_weight_caught', 
                                 'total_coins_earned', 'consecutive_login_days', 'fish_pond_capacity', 'fishing_zone_id'];
            numberFields.forEach(field => {
                if (userData[field] !== undefined) {
                    userData[field] = parseInt(userData[field]) || 0;
                }
            });

            updateUser(userId, userData);
        });
    } else {
        console.error('Form with id "user-form" not found');
    }

    // 加载用户详情
    async function loadUserDetail(userId) {
        try {
            const url = userDetailUrl + userId;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                displayUserDetail(data);
                document.getElementById('editFromDetailBtn').setAttribute('data-user-id', userId);
                new bootstrap.Modal(document.getElementById('userDetailModal')).show();
            } else {
                alert('加载用户详情失败：' + data.message);
            }
        } catch (error) {
            console.error('Error loading user detail:', error);
            alert('加载用户详情时发生错误');
        }
    }

    // 显示用户详情
    function displayUserDetail(data) {
        const user = data.user;
        const content = document.getElementById('userDetailContent');
        
        content.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>基本信息</h6>
                    <table class="table table-sm">
                        <tr><td><strong>用户ID:</strong></td><td><code>${user.user_id}</code></td></tr>
                        <tr><td><strong>昵称:</strong></td><td>${user.nickname || '未设置'}</td></tr>
                        <tr><td><strong>注册时间:</strong></td><td>${user.created_at ? new Date(user.created_at).toLocaleString() : '未知'}</td></tr>
                        <tr><td><strong>最后登录:</strong></td><td>${user.last_login_time ? new Date(user.last_login_time).toLocaleString() : '从未'}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>游戏数据</h6>
                    <table class="table table-sm">
                        <tr><td><strong>金币:</strong></td><td><span class="badge bg-warning text-dark">${user.coins}</span></td></tr>
                        <tr><td><strong>高级货币:</strong></td><td><span class="badge bg-info">${user.premium_currency}</span></td></tr>
                        <tr><td><strong>钓鱼次数:</strong></td><td>${user.total_fishing_count}</td></tr>
                        <tr><td><strong>总重量:</strong></td><td>${user.total_weight_caught}g</td></tr>
                        <tr><td><strong>总赚取金币:</strong></td><td>${user.total_coins_earned}</td></tr>
                        <tr><td><strong>连续登录:</strong></td><td>${user.consecutive_login_days} 天</td></tr>
                    </table>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-md-6">
                    <h6>装备信息</h6>
                    <table class="table table-sm">
                        <tr><td><strong>当前鱼竿:</strong></td><td>${data.equipped_rod ? data.equipped_rod.name + ' (精炼+' + data.equipped_rod.refine_level + ')' : '无'}</td></tr>
                        <tr><td><strong>当前饰品:</strong></td><td>${data.equipped_accessory ? data.equipped_accessory.name + ' (精炼+' + data.equipped_accessory.refine_level + ')' : '无'}</td></tr>
                        <tr><td><strong>当前称号:</strong></td><td>${data.current_title || '无'}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>其他信息</h6>
                    <table class="table table-sm">
                        <tr><td><strong>鱼塘容量:</strong></td><td>${user.fish_pond_capacity}</td></tr>
                        <tr><td><strong>钓鱼区域:</strong></td><td>${user.fishing_zone_id}</td></tr>
                        <tr><td><strong>自动钓鱼:</strong></td><td><span class="badge ${user.auto_fishing_enabled ? 'bg-success' : 'bg-secondary'}">${user.auto_fishing_enabled ? '启用' : '禁用'}</span></td></tr>
                    </table>
                </div>
            </div>
        `;
    }

    // 加载用户进行编辑
    async function loadUserForEdit(userId) {
        try {
            const url = userDetailUrl + userId;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                const user = data.user;
                const form = document.getElementById('user-form');
                
                // 填充表单
                document.getElementById('user_id').value = user.user_id;
                document.getElementById('nickname').value = user.nickname || '';
                document.getElementById('coins').value = user.coins;
                document.getElementById('premium_currency').value = user.premium_currency;
                document.getElementById('total_fishing_count').value = user.total_fishing_count;
                document.getElementById('total_weight_caught').value = user.total_weight_caught;
                document.getElementById('total_coins_earned').value = user.total_coins_earned;
                document.getElementById('consecutive_login_days').value = user.consecutive_login_days;
                document.getElementById('fish_pond_capacity').value = user.fish_pond_capacity;
                document.getElementById('fishing_zone_id').value = user.fishing_zone_id;
                document.getElementById('auto_fishing_enabled').checked = user.auto_fishing_enabled;
                
                // 设置表单动作（虽然我们使用JavaScript处理，但保持一致性）
                const actionUrl = updateUserUrl + userId + '/update';
                form.action = actionUrl;
                
                // 显示模态框
                new bootstrap.Modal(document.getElementById('userModal')).show();
            } else {
                alert('加载用户信息失败：' + data.message);
            }
        } catch (error) {
            console.error('Error loading user for edit:', error);
            alert('加载用户信息时发生错误');
        }
    }

    // 更新用户
    async function updateUser(userId, userData) {
        try {
            const url = updateUserUrl + userId + '/update';
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('用户信息更新成功！');
                bootstrap.Modal.getInstance(document.getElementById('userModal')).hide();
                location.reload();
            } else {
                alert('更新失败：' + data.message);
            }
        } catch (error) {
            console.error('Error updating user:', error);
            alert('更新用户时发生错误');
        }
    }

    // 删除用户
    async function deleteUser(userId) {
        try {
            const url = deleteUserUrl + userId + '/delete';
            const response = await fetch(url, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('用户删除成功！');
                location.reload();
            } else {
                alert('删除失败：' + data.message);
            }
        } catch (error) {
            console.error('Error deleting user:', error);
            alert('删除用户时发生错误');
        }
    }
});
