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
                if (value !== '') {
                    userData[key] = value;
                }
            }

            // 处理checkbox字段（checkbox未选中时不会出现在FormData中）
            const autoFishingCheckbox = document.getElementById('auto_fishing_enabled');
            userData['auto_fishing_enabled'] = autoFishingCheckbox ? autoFishingCheckbox.checked : false;

            // 转换数字字段
            const numberFields = ['coins', 'premium_currency', 'total_fishing_count', 'total_weight_caught', 
                                 'total_coins_earned', 'consecutive_login_days', 'fish_pond_capacity', 'fishing_zone_id'];
            numberFields.forEach(field => {
                if (userData[field] !== undefined) {
                    userData[field] = parseInt(userData[field]) || 0;
                }
            });

            // 根据模式选择创建或更新
            if (form.dataset.mode === 'create') {
                (async () => {
                    try {
                        const url = baseUrl + '/users/create';
                        const resp = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(userData)});
                        const data = await resp.json();
                        if (data.success) {
                            alert('用户创建成功！');
                            bootstrap.Modal.getInstance(document.getElementById('userModal')).hide();
                            location.reload();
                        } else {
                            alert('创建失败：' + data.message);
                        }
                    } catch (err) {
                        console.error('Error creating user:', err);
                        alert('创建用户时发生错误');
                    }
                })();
            } else {
                updateUser(userId, userData);
            }
        });
    } else {
        console.error('Form with id "user-form" not found');
    }

    // 加载用户详情
    const loadUserDetail = async (userId) => {
        try {
            const url = userDetailUrl + encodeURIComponent(userId);
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
    const displayUserDetail = (data) => {
        const {user} = data;
        const content = document.getElementById('userDetailContent');

        // 创建安全的DOM结构，避免直接拼接用户数据到innerHTML
        content.innerHTML = '';
        const row1 = document.createElement('div'); row1.className = 'row';
        const col1 = document.createElement('div'); col1.className = 'col-md-6';
        col1.innerHTML = '<h6>基本信息</h6>';
        const table1 = document.createElement('table'); table1.className = 'table table-sm';
        const addRow = (label, valueNode) => {
            const tr = document.createElement('tr');
            const td1 = document.createElement('td'); td1.innerHTML = '<strong>' + label + '</strong>';
            const td2 = document.createElement('td'); td2.appendChild(valueNode);
            tr.appendChild(td1); tr.appendChild(td2); table1.appendChild(tr);
        };
        const codeId = document.createElement('code'); codeId.textContent = user.user_id;
        addRow('用户ID:', codeId);
        const nickNode = document.createElement('span'); nickNode.textContent = user.nickname || '未设置';
        addRow('昵称:', nickNode);
        const createdNode = document.createElement('span'); createdNode.textContent = user.created_at ? new Date(user.created_at).toLocaleString() : '未知';
        addRow('注册时间:', createdNode);
        const lastLoginNode = document.createElement('span'); lastLoginNode.textContent = user.last_login_time ? new Date(user.last_login_time).toLocaleString() : '从未';
        addRow('最后登录:', lastLoginNode);
        col1.appendChild(table1);

        const col2 = document.createElement('div'); col2.className = 'col-md-6';
        col2.innerHTML = '<h6>游戏数据</h6>';
        const table2 = document.createElement('table'); table2.className = 'table table-sm';
        const addStatRow = (label, value, asBadge=false, badgeClass='') => {
            const tr = document.createElement('tr');
            const td1 = document.createElement('td'); td1.innerHTML = '<strong>' + label + '</strong>';
            const td2 = document.createElement('td');
            if (asBadge) { const span = document.createElement('span'); span.className = 'badge ' + badgeClass; span.textContent = String(value); td2.appendChild(span); }
            else { td2.textContent = String(value); }
            tr.appendChild(td1); tr.appendChild(td2); table2.appendChild(tr);
        };
        addStatRow('金币:', user.coins, true, 'bg-warning text-dark');
        addStatRow('高级货币:', user.premium_currency, true, 'bg-info');
        addStatRow('钓鱼次数:', user.total_fishing_count);
        addStatRow('总重量:', user.total_weight_caught + 'g');
        addStatRow('总赚取金币:', user.total_coins_earned);
        addStatRow('连续登录:', user.consecutive_login_days + ' 天');
        col2.appendChild(table2);

        row1.appendChild(col1); row1.appendChild(col2);

        const row2 = document.createElement('div'); row2.className = 'row mt-3';
        const col3 = document.createElement('div'); col3.className = 'col-md-6'; col3.innerHTML = '<h6>装备信息</h6>';
        const table3 = document.createElement('table'); table3.className = 'table table-sm';
        const addTextRow = (label, text) => {
            const tr = document.createElement('tr');
            const td1 = document.createElement('td'); td1.innerHTML = '<strong>' + label + '</strong>';
            const td2 = document.createElement('td'); td2.textContent = text; tr.appendChild(td1); tr.appendChild(td2); table3.appendChild(tr);
        };
        addTextRow('当前鱼竿:', data.equipped_rod ? `${data.equipped_rod.name} (精炼+${data.equipped_rod.refine_level})` : '无');
        addTextRow('当前饰品:', data.equipped_accessory ? `${data.equipped_accessory.name} (精炼+${data.equipped_accessory.refine_level})` : '无');
        addTextRow('当前称号:', data.current_title || '无');
        col3.appendChild(table3);

        const col4 = document.createElement('div'); col4.className = 'col-md-6'; col4.innerHTML = '<h6>其他信息</h6>';
        const table4 = document.createElement('table'); table4.className = 'table table-sm';
        const badgeRow = (label, text, badgeClass) => {
            const tr = document.createElement('tr');
            const td1 = document.createElement('td'); td1.innerHTML = '<strong>' + label + '</strong>';
            const td2 = document.createElement('td'); const badge = document.createElement('span'); badge.className = 'badge ' + badgeClass; badge.textContent = text; td2.appendChild(badge);
            tr.appendChild(td1); tr.appendChild(td2); table4.appendChild(tr);
        }
        addTextRow('鱼塘容量:', String(user.fish_pond_capacity));
        addTextRow('钓鱼区域:', String(user.fishing_zone_id));
        badgeRow('自动钓鱼:', user.auto_fishing_enabled ? '启用' : '禁用', user.auto_fishing_enabled ? 'bg-success' : 'bg-secondary');
        col4.appendChild(table4);

        row2.appendChild(col3); row2.appendChild(col4);
        content.appendChild(row1);
        content.appendChild(row2);

        // 称号列表（仅查看，不提供编辑功能）
        const row3 = document.createElement('div'); row3.className = 'row mt-3';
        const col5 = document.createElement('div'); col5.className = 'col-12';
        const titleHeading = document.createElement('h6');
        titleHeading.textContent = '拥有的称号';
        col5.appendChild(titleHeading);
        
        if (data.titles && data.titles.length > 0) {
            const titleUl = document.createElement('ul');
            titleUl.className = 'list-group mt-2';
            data.titles.forEach(title => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                const titleInfo = document.createElement('span');
                
                // 安全地创建DOM元素，避免XSS攻击
                const strong = document.createElement('strong');
                strong.textContent = title.name;
                titleInfo.appendChild(strong);
                
                if (title.is_current) {
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-success ms-2';
                    badge.textContent = '当前装备';
                    titleInfo.appendChild(badge);
                }
                
                li.appendChild(titleInfo);
                titleUl.appendChild(li);
            });
            col5.appendChild(titleUl);
        } else {
            const emptyMsg = document.createElement('p');
            emptyMsg.className = 'text-muted mb-0';
            emptyMsg.textContent = '该用户暂无称号';
            col5.appendChild(emptyMsg);
        }
        
        row3.appendChild(col5);
        content.appendChild(row3);
    }

    // 加载可用称号列表
    const loadAvailableTitles = async (selectElement) => {
        try {
            const response = await fetch(baseUrl + '/api/titles');
            const data = await response.json();
            if (data.success && data.titles) {
                data.titles.forEach(title => {
                    const option = document.createElement('option');
                    option.value = title.name;
                    option.textContent = title.name;
                    selectElement.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading titles:', error);
        }
    };

    // 授予称号给用户
    const grantTitleToUser = async (userId, titleName, reloadInEdit = false) => {
        if (!confirm(`确定要授予用户称号 "${titleName}" 吗？`)) {
            return;
        }
        try {
            const response = await fetch(baseUrl + '/users/' + encodeURIComponent(userId) + '/grant_title', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title_name: titleName })
            });
            const result = await response.json();
            if (result.success) {
                alert(result.message);
                // 根据上下文重新加载
                if (reloadInEdit) {
                    // 在编辑模态框中，重新加载用户数据并更新称号管理部分
                    const detailResponse = await fetch(userDetailUrl + encodeURIComponent(userId));
                    const detailData = await detailResponse.json();
                    if (detailData.success) {
                        loadTitleManagementSection(userId, detailData);
                    }
                } else {
                    // 在详情模态框中，重新加载用户详情
                    loadUserDetail(userId);
                }
            } else {
                alert('授予失败：' + result.message);
            }
        } catch (error) {
            console.error('Error granting title:', error);
            alert('授予称号时发生错误');
        }
    };

    // 移除用户的称号
    const revokeTitleFromUser = async (userId, titleName, reloadInEdit = false) => {
        if (!confirm(`确定要移除用户的称号 "${titleName}" 吗？`)) {
            return;
        }
        try {
            const response = await fetch(baseUrl + '/users/' + encodeURIComponent(userId) + '/revoke_title', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title_name: titleName })
            });
            const result = await response.json();
            if (result.success) {
                alert(result.message);
                // 根据上下文重新加载
                if (reloadInEdit) {
                    // 在编辑模态框中，重新加载用户数据并更新称号管理部分
                    const detailResponse = await fetch(userDetailUrl + encodeURIComponent(userId));
                    const detailData = await detailResponse.json();
                    if (detailData.success) {
                        loadTitleManagementSection(userId, detailData);
                    }
                } else {
                    // 在详情模态框中，重新加载用户详情
                    loadUserDetail(userId);
                }
            } else {
                alert('移除失败：' + result.message);
            }
        } catch (error) {
            console.error('Error revoking title:', error);
            alert('移除称号时发生错误');
        }
    };

    // 加载用户进行编辑
    const loadUserForEdit = async (userId) => {
        try {
            const url = userDetailUrl + encodeURIComponent(userId);
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                const {user} = data;
                const form = document.getElementById('user-form');
                
                // 填充表单
                document.getElementById('user_id').value = user.user_id;
                document.getElementById('user_id').readOnly = true;
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
                
                // 加载称号管理部分
                loadTitleManagementSection(userId, data);
                
                // 标记为编辑模式并设置表单动作
                form.dataset.mode = 'edit';
                const actionUrl = updateUserUrl + encodeURIComponent(userId) + '/update';
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

    // 加载称号管理部分到编辑模态框
    const loadTitleManagementSection = (userId, data) => {
        const titleSection = document.getElementById('titleManagementSection');
        titleSection.innerHTML = '';
        
        // 显示用户拥有的称号
        const titlesList = document.createElement('div');
        titlesList.className = 'mb-3';
        if (data.titles && data.titles.length > 0) {
            const titleListTitle = document.createElement('strong');
            titleListTitle.textContent = '拥有的称号:';
            titlesList.appendChild(titleListTitle);
            const titleUl = document.createElement('ul');
            titleUl.className = 'list-group mt-2';
            data.titles.forEach(title => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                const titleInfo = document.createElement('span');
                
                // 安全地创建DOM元素，避免XSS攻击
                const strong = document.createElement('strong');
                strong.textContent = title.name;
                titleInfo.appendChild(strong);
                
                if (title.is_current) {
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-success ms-2';
                    badge.textContent = '当前装备';
                    titleInfo.appendChild(badge);
                }
                
                li.appendChild(titleInfo);
                if (!title.is_current) {
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'btn btn-sm btn-danger';
                    removeBtn.textContent = '移除';
                    removeBtn.onclick = () => {
                        revokeTitleFromUser(userId, title.name, true);
                    };
                    li.appendChild(removeBtn);
                }
                titleUl.appendChild(li);
            });
            titlesList.appendChild(titleUl);
        } else {
            const emptyMsg = document.createElement('p');
            emptyMsg.className = 'text-muted mb-0';
            emptyMsg.textContent = '该用户暂无称号';
            titlesList.appendChild(emptyMsg);
        }
        titleSection.appendChild(titlesList);
        
        // 授予称号功能
        const grantTitleDiv = document.createElement('div');
        grantTitleDiv.className = 'input-group';
        const titleSelect = document.createElement('select');
        titleSelect.className = 'form-select';
        titleSelect.id = 'titleSelect_edit_' + userId;
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '选择称号...';
        titleSelect.appendChild(defaultOption);
        grantTitleDiv.appendChild(titleSelect);
        const grantBtn = document.createElement('button');
        grantBtn.className = 'btn btn-success';
        grantBtn.type = 'button';
        grantBtn.textContent = '授予称号';
        grantBtn.onclick = () => {
            const selectedTitle = titleSelect.value;
            if (selectedTitle) {
                grantTitleToUser(userId, selectedTitle, true);
            } else {
                alert('请选择要授予的称号');
            }
        };
        grantTitleDiv.appendChild(grantBtn);
        titleSection.appendChild(grantTitleDiv);
        
        // 加载所有可用称号
        loadAvailableTitles(titleSelect);
    }

    // 更新用户
    const updateUser = async (userId, userData) => {
        try {
            const url = updateUserUrl + encodeURIComponent(userId) + '/update';
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
    const deleteUser = async (userId) => {
        try {
            const url = deleteUserUrl + encodeURIComponent(userId) + '/delete';
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

    // 添加用户支持：点击“添加用户”按钮时，重置表单并切换提交为创建
    const addUserBtn = document.getElementById('addUserBtn');
    if (addUserBtn) {
        addUserBtn.addEventListener('click', () => {
            const form = document.getElementById('user-form');
            form.reset();
            document.getElementById('user_id').readOnly = false;
            document.getElementById('userModalLabel').textContent = '添加用户';
            // 设置表单模式为创建，复用统一提交逻辑
            form.dataset.mode = 'create';
        });
    }
});
