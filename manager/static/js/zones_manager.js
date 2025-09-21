document.addEventListener('DOMContentLoaded', function() {
    //
    // Scoped selection state per-modal using WeakMap
    //
    const containerToSelectedIds = new WeakMap();
    function getSelectedSet(container) {
        let set = containerToSelectedIds.get(container);
        if (!set) {
            set = new Set();
            containerToSelectedIds.set(container, set);
        }
        return set;
    }

    function getZoneById(zoneId) {
        return zonesData.find(z => z.id === zoneId);
    }

    function formatDateTimeForInput(dateTimeString) {
        if (!dateTimeString) return '';
        const date = new Date(dateTimeString);
        if (isNaN(date)) return '';

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }
    
    //
    // Dynamic Form Rendering
    //
    function renderForm(zone = null) {
        const isEdit = zone !== null;
        const rarityDistribution = zone?.configs?.rarity_distribution || [0.5, 0.3, 0.15, 0.04, 0.01, 0];
        while (rarityDistribution.length < 6) {
            rarityDistribution.push(0);
        }
        const specificFishIds = zone?.specific_fish_ids || [];

        const fishByRarity = allFishData.reduce((acc, fish) => {
            (acc[fish.rarity] = acc[fish.rarity] || []).push(fish);
            return acc;
        }, {});
        
        let totalFishListHtml = '';
        for (let rarity = 1; rarity <= 10; rarity++) {
            if (fishByRarity[rarity]?.length > 0) {
                const rarityStars = '★'.repeat(rarity);
                totalFishListHtml += `
                    <div class="list-group-item bg-light fw-bold d-flex justify-content-between align-items-center">
                        <span>${rarityStars} ${rarity}星鱼类 (${fishByRarity[rarity].length}种)</span>
                        <div class="form-check">
                            <input class="form-check-input rarity-select-all" type="checkbox" id="rarity-${rarity}" title="选中/取消选中此星级所有鱼类">
                            <label class="form-check-label" for="rarity-${rarity}">全选</label>
                        </div>
                    </div>
                `;
                fishByRarity[rarity].forEach(fish => {
                    const value = fish.base_value.toLocaleString();
                    totalFishListHtml += `
                        <div class="list-group-item fish-item" 
                             data-fish-id="${fish.fish_id}" data-rarity="${fish.rarity}" 
                             data-value="${fish.base_value}" data-name="${fish.name}">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${fish.name}</strong>
                                    <br><small class="text-muted">${rarityStars} 价值: ${value} 金币</small>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" value="${fish.fish_id}">
                                </div>
                            </div>
                        </div>
                    `;
                });
            }
        }

        const itemOptions = allItemsData.map(item => `
            <option value="${item.item_id}" ${zone?.required_item_id == item.item_id ? 'selected' : ''}>
                ${item.name} (ID: ${item.item_id})
            </option>
        `).join('');

        return `
            <form id="${isEdit ? 'edit' : 'create'}-zone-form">
                <!-- Form fields... -->
                <div class="alert alert-danger d-none" role="alert" id="form-error-alert"></div>
                <div class="row">
                    <div class="col-md-3 mb-3">
                        <label for="id" class="form-label">区域 ID</label>
                        <input type="number" class="form-control" name="id" value="${zone?.id || ''}" ${isEdit ? 'readonly' : ''} required>
                    </div>
                    <div class="col-md-9 mb-3">
                        <label for="name" class="form-label">区域名称</label>
                        <input type="text" class="form-control" name="name" value="${zone?.name || ''}" required>
                    </div>
                </div>
                <div class="mb-3">
                    <label for="description" class="form-label">描述</label>
                    <textarea class="form-control" name="description" rows="2">${zone?.description || ''}</textarea>
                </div>
                <div class="row">
                    <div class="col-md-4 mb-3">
                        <label for="daily_rare_fish_quota" class="form-label">稀有鱼每日配额</label>
                        <input type="number" class="form-control" name="daily_rare_fish_quota" value="${zone?.daily_rare_fish_quota || 0}">
                    </div>
                    <div class="col-md-4 mb-3">
                        <label for="fishing_cost" class="form-label">钓鱼消耗 (金币)</label>
                        <input type="number" class="form-control" name="fishing_cost" value="${zone?.fishing_cost || 10}" min="1">
                    </div>
                    <div class="col-md-4 mb-3 d-flex align-items-end">
                        <div class="form-check form-switch mb-0">
                            <input class="form-check-input" type="checkbox" name="is_active" id="is_active" ${zone?.is_active ?? true ? 'checked' : ''}>
                            <label class="form-check-label ms-2" for="is_active">启用区域</label>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label for="available_from" class="form-label">开放时间 (可选)</label>
                        <input type="datetime-local" class="form-control" name="available_from" value="${formatDateTimeForInput(zone?.available_from)}">
                    </div>
                    <div class="col-md-6 mb-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <label for="available_until" class="form-label mb-0">结束时间 (可选)</label>
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" name="limit_time" id="limit_time" ${zone?.available_from || zone?.available_until ? 'checked' : ''}>
                                <label class="form-check-label" for="limit_time">限定开放时间</label>
                            </div>
                        </div>
                        <input type="datetime-local" class="form-control mt-2" name="available_until" value="${formatDateTimeForInput(zone?.available_until)}">
                    </div>
                </div>
                <div class="mb-3">
                    <label>稀有度分布 (概率总和应为 1)</label>
                    <div class="row">
                        ${[...Array(5).keys()].map(i => `
                            <div class="col-md-2 col-4 mb-2">
                                <label>${i+1} 星</label>
                                <input type="number" step="0.001" min="0" max="1" class="form-control rarity-input" name="rarity_${i+1}" value="${rarityDistribution[i]}" placeholder="0.000">
                            </div>
                        `).join('')}
                        <div class="col-md-2 col-4 mb-2">
                            <label>6+ 星</label>
                            <input type="number" step="0.001" min="0" max="1" class="form-control rarity-input" name="rarity_6plus" value="${rarityDistribution[5]}" placeholder="0.000">
                        </div>
                    </div>
                    <div id="rarity-sum-feedback" class="form-text mt-1"></div>
                    <small class="text-muted">提示：6+星包含所有6星及以上稀有度，中奖后随机从高星鱼池选择。</small>
                </div>

                <!-- Fish Selection Component -->
                <div class="mb-3">
                    <label class="form-label">限定鱼类选择 (不选则为全局鱼池)</label>
                    <div class="row mb-3">
                        <div class="col-md-6"><input type="text" class="form-control form-control-sm" id="fishSearch" placeholder="搜索鱼类名称..."></div>
                        <div class="col-md-3">
                            <select class="form-control form-control-sm" id="rarityFilter">
                                <option value="">所有稀有度</option>
                                ${[...Array(10).keys()].map(i => `<option value="${i+1}">${'★'.repeat(i+1)} ${i+1}星</option>`).join('')}
                            </select>
                        </div>
                        <div class="col-md-3">
                             <div class="btn-group btn-group-sm" role="group">
                                <button type="button" class="btn btn-outline-success" id="addSelectedBtn"><i class="fas fa-plus"></i> 添加</button>
                                <button type="button" class="btn btn-outline-danger" id="removeSelectedBtn"><i class="fas fa-minus"></i> 移除</button>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header d-flex justify-content-between align-items-center"><h6 class="mb-0">总鱼池</h6><small class="text-muted" id="totalFishCount">0 种</small></div>
                                <div class="list-group list-group-flush" id="totalFishList" style="max-height: 300px; overflow-y: auto;">${totalFishListHtml}</div>
                            </div>
                        </div>
                        <div class="col-md-6">
                             <div class="card">
                                <div class="card-header d-flex justify-content_between align-items-center">
                                    <h6 class="mb-0">已选择鱼类</h6>
                                    <div>
                                        <small class="text-muted me-2"><span id="selectedCount">0</span> 种 | 总价值: <span id="totalValue">0</span></small>
                                        <button type="button" class="btn btn-sm btn-outline-secondary" id="clearAllBtn"><i class="fas fa-trash"></i></button>
                                    </div>
                                </div>
                                <div class="list-group list-group-flush" id="selectedFishList" style="max-height: 300px; overflow-y: auto;">
                                    <div class="list-group-item text-muted text-center" id="emptySelectedMessage">暂无选择</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <input type="hidden" name="specific_fish_ids" id="specific_fish_ids_input">
                </div>

                <!-- Pass Requirement -->
                <div class="mb-3">
                     <label class="form-label">通行证要求</label>
                     <div class="row">
                         <div class="col-md-6">
                             <div class="form-check form-switch">
                                 <input class="form-check-input" type="checkbox" name="requires_pass" id="requires_pass" ${zone?.requires_pass ? 'checked' : ''}>
                                 <label class="form-check-label" for="requires_pass">需要通行证</label>
                             </div>
                         </div>
                         <div class="col-md-6">
                             <select class="form-control" name="required_item_id" ${!zone?.requires_pass ? 'disabled' : ''}>
                                 <option value="">选择通行证道具</option>
                                 ${itemOptions}
                             </select>
                         </div>
                     </div>
                 </div>

                <!-- Modal Footer -->
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    <button type="submit" class="btn btn-primary">${isEdit ? '更新' : '创建'}</button>
                </div>
            </form>
        `;
    }

    //
    // Fish Selection Logic (scoped to a container)
    //
    function setupFishSelection(container) {
        const totalFishList = container.querySelector('#totalFishList');
        const selectedFishList = container.querySelector('#selectedFishList');
        const fishSearch = container.querySelector('#fishSearch');
        const rarityFilter = container.querySelector('#rarityFilter');
        const selectedSet = getSelectedSet(container);
        
        let clickTimer = null;

        const handleFishClick = (e) => {
            const item = e.currentTarget;
            if (clickTimer) {
                clearTimeout(clickTimer);
                clickTimer = null;
                handleFishDblClick(item);
            } else {
                clickTimer = setTimeout(() => {
                    toggleFishSelection(item, container, e);
                    clickTimer = null;
                }, 220);
            }
        };

        const handleFishDblClick = (item) => {
            const fishId = parseInt(item.dataset.fishId);
            addFishToSelected(fishId, container);
        };

        totalFishList.querySelectorAll('.fish-item').forEach(item => {
            item.addEventListener('click', handleFishClick);
        });
        // Prevent bubbling from checkbox clicks so row handler doesn't invert state
        totalFishList.querySelectorAll('.fish-item input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('click', (e) => e.stopPropagation());
        });
        
        selectedFishList.addEventListener('click', (e) => {
            // If clicking directly on a checkbox inside selected list, don't bubble to row handler
            if (e.target && e.target.matches('input[type="checkbox"]')) {
                e.stopPropagation();
                return;
            }
            const item = e.target.closest('.fish-item');
            if(item) toggleFishSelection(item, container, e);
        });
        // Double-click on selected list removes the fish
        selectedFishList.addEventListener('dblclick', (e) => {
            const item = e.target.closest('.fish-item');
            if (!item) return;
            const fishId = parseInt(item.dataset.fishId);
            removeFishFromSelected(fishId, container);
        });

        const filterFishOptions = () => {
            const searchTerm = fishSearch.value.toLowerCase();
            const rarity = rarityFilter.value;
            let visibleCount = 0;
            totalFishList.querySelectorAll('.fish-item').forEach(item => {
                const fishId = parseInt(item.dataset.fishId);
                const isVisible = 
                    (item.dataset.name.toLowerCase().includes(searchTerm) || !searchTerm) &&
                    (item.dataset.rarity === rarity || !rarity) &&
                    !selectedSet.has(fishId);
                item.style.display = isVisible ? '' : 'none';
                if (isVisible) visibleCount++;
            });
            container.querySelector('#totalFishCount').textContent = `${visibleCount} 种`;
        };

        fishSearch.addEventListener('keyup', filterFishOptions);
        rarityFilter.addEventListener('change', filterFishOptions);

        container.querySelectorAll('.rarity-select-all').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const rarity = e.target.id.split('-')[1];
                const items = totalFishList.querySelectorAll(`.fish-item[data-rarity='${rarity}']`);
                items.forEach(item => {
                    if (item.style.display !== 'none') {
                        item.querySelector('input[type="checkbox"]').checked = e.target.checked;
                    }
                });
                // Keep header state consistent
                updateRarityCheckboxState(totalFishList, rarity, container);
            });
        });

        container.querySelector('#addSelectedBtn').addEventListener('click', () => {
            totalFishList.querySelectorAll('.fish-item input:checked').forEach(cb => {
                addFishToSelected(parseInt(cb.value), container);
            });
        });
        
        container.querySelector('#removeSelectedBtn').addEventListener('click', () => {
            selectedFishList.querySelectorAll('.fish-item input:checked').forEach(cb => {
                removeFishFromSelected(parseInt(cb.value), container);
            });
        });

        container.querySelector('#clearAllBtn').addEventListener('click', () => clearAllSelected(container));

        // Initial count
        filterFishOptions();
    }
    
    function toggleFishSelection(item, container, e = null) {
        const checkbox = item.querySelector('input[type="checkbox"]');
        if (!checkbox) return;
        
        // Only programmatically toggle the checkbox if the click was not on the input itself.
        const targetIsCheckbox = e && e.target.tagName === 'INPUT';
        if (!targetIsCheckbox) {
            checkbox.checked = !checkbox.checked;
        }

        const list = item.closest('#totalFishList, #selectedFishList');
        if(list) {
            updateRarityCheckboxState(list, item.dataset.rarity, container);
        }
    }

    function updateRarityCheckboxState(list, rarity, container) {
        if (!list || !rarity) return;
        const rarityCheckbox = container.querySelector(`#totalFishList #rarity-${rarity}`);
        if (!rarityCheckbox) return;

        const items = container.querySelectorAll(`#totalFishList .fish-item[data-rarity='${rarity}']:not([style*='display: none'])`);
        const checkedItems = container.querySelectorAll(`#totalFishList .fish-item[data-rarity='${rarity}']:not([style*='display: none']) input:checked`);

        if (items.length > 0) {
            rarityCheckbox.checked = items.length === checkedItems.length;
            rarityCheckbox.indeterminate = checkedItems.length > 0 && checkedItems.length < items.length;
        } else {
            rarityCheckbox.checked = false;
            rarityCheckbox.indeterminate = false;
        }
    }

    function _addFishToSelected_internal(fishId, container) {
        const selectedSet = getSelectedSet(container);
        if (selectedSet.has(fishId)) return;
        selectedSet.add(fishId);

        const totalItem = container.querySelector(`#totalFishList .fish-item[data-fish-id='${fishId}']`);
        if (!totalItem) return;
        
        const fishData = totalItem.dataset;
        const rarity = parseInt(fishData.rarity);
        const rarityStars = '★'.repeat(rarity);
        const valueText = Number(fishData.value).toLocaleString();

        const selectedList = container.querySelector('#selectedFishList');

        // Build DOM nodes explicitly to avoid inheriting any classes or inline styles
        const item = document.createElement('div');
        item.className = 'list-group-item fish-item';
        item.dataset.fishId = fishData.fishId;
        item.dataset.rarity = String(rarity);
        item.dataset.value = fishData.value;
        item.dataset.name = fishData.name;
        item.style.display = '';

        const row = document.createElement('div');
        row.className = 'd-flex justify-content-between align-items-center';

        const left = document.createElement('div');
        const nameStrong = document.createElement('strong');
        nameStrong.textContent = fishData.name;
        const br = document.createElement('br');
        const small = document.createElement('small');
        small.className = 'text-muted';
        small.textContent = `${rarityStars} 价值: ${valueText} 金币`;
        left.appendChild(nameStrong);
        left.appendChild(br);
        left.appendChild(small);

        const right = document.createElement('div');
        right.className = 'form-check';
        const cb = document.createElement('input');
        cb.className = 'form-check-input';
        cb.type = 'checkbox';
        cb.value = fishData.fishId;
        cb.checked = false;
        cb.addEventListener('click', (e) => e.stopPropagation());
        right.appendChild(cb);

        row.appendChild(left);
        row.appendChild(right);
        item.appendChild(row);

        selectedList.appendChild(item);
    }

    function addFishToSelected(fishId, container) {
        _addFishToSelected_internal(fishId, container);
        updateSelectedStats(container);
        container.querySelector('#fishSearch').dispatchEvent(new Event('keyup'));
    }

    function removeFishFromSelected(fishId, container) {
        const selectedSet = getSelectedSet(container);
        if (!selectedSet.has(fishId)) return;
        selectedSet.delete(fishId);

        const selectedItem = container.querySelector(`#selectedFishList .fish-item[data-fish-id='${fishId}']`);
        if (selectedItem) selectedItem.remove();

        updateSelectedStats(container);
        // Let the central filter function handle visibility
        container.querySelector('#fishSearch').dispatchEvent(new Event('keyup'));
    }

    function clearAllSelected(container) {
        const selectedSet = getSelectedSet(container);
        const ids = [...selectedSet];
        ids.forEach(id => removeFishFromSelected(id, container));
    }
    
    function updateSelectedStats(container) {
        const selectedSet = getSelectedSet(container);
        const selectedList = container.querySelector('#selectedFishList');
        const count = selectedSet.size;
        let totalValue = 0;
        selectedList.querySelectorAll('.fish-item').forEach(item => {
            totalValue += parseInt(item.dataset.value);
        });

        container.querySelector('#selectedCount').textContent = count;
        container.querySelector('#totalValue').textContent = totalValue.toLocaleString();
        container.querySelector('#emptySelectedMessage').style.display = count > 0 ? 'none' : '';
        container.querySelector('#specific_fish_ids_input').value = Array.from(selectedSet).join(',');

        // Defensively ensure all items in the selected list are visible.
        container.querySelectorAll('#selectedFishList .fish-item').forEach(el => {
            if (el.classList.contains('d-none')) {
                el.classList.remove('d-none');
            }
            if (el.style.display === 'none') {
                el.style.display = '';
            }
        });

        // Update total fish count
        let visibleCount = 0;
        container.querySelectorAll('#totalFishList .fish-item').forEach(item => {
            if (item.style.display !== 'none') {
                 visibleCount++;
            }
        });
        container.querySelector('#totalFishCount').textContent = `${visibleCount} 种`;
    }

    function initializeSelectedFish(ids, container) {
        const selectedSet = getSelectedSet(container);
        selectedSet.clear();
        const selectedList = container.querySelector('#selectedFishList');
        selectedList.innerHTML = '<div class="list-group-item text-muted text-center" id="emptySelectedMessage">暂无选择</div>';
        
        container.querySelectorAll('#totalFishList .fish-item').forEach(item => {
            item.style.display = '';
            const cb = item.querySelector('input[type="checkbox"]');
            if (cb) cb.checked = false;
        });
        container.querySelectorAll('.rarity-select-all').forEach(cb => {
            cb.checked = false;
            cb.indeterminate = false;
        });
        
        ids.forEach(id => _addFishToSelected_internal(id, container));
        
        updateSelectedStats(container);
        container.querySelector('#fishSearch').dispatchEvent(new Event('keyup'));
    }
    
    //
    // Modal and Form Submission Setup
    //
    function setupModal(modalId, formId) {
        const modalEl = document.getElementById(modalId);
        if (!modalEl) return;

        modalEl.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const zoneId = button ? button.getAttribute('data-bs-id') : null;
            const zone = zoneId ? getZoneById(parseInt(zoneId)) : null;
            modalEl._currentZone = zone || null;

            modalEl.querySelector('.modal-body').innerHTML = renderForm(zone);
            
            const form = modalEl.querySelector(formId);
            setupFishSelection(modalEl);
            hookFormHandlers(form, zoneId);
        });

        // Initialize selections only after modal is fully shown to avoid transition races
        modalEl.addEventListener('shown.bs.modal', function() {
            const zone = modalEl._currentZone;
            initializeSelectedFish(zone?.specific_fish_ids || [], modalEl);
        });

        modalEl.addEventListener('hidden.bs.modal', function() {
            // Clear the modal body when it's hidden to prevent focus issues and stale data
            modalEl.querySelector('.modal-body').innerHTML = '';
            modalEl._currentZone = null;
        });
    }

    function hookFormHandlers(form, zoneId) {
        if (!form) return;
        
        const container = form.closest('.modal');
        const selectedSet = getSelectedSet(container);

        // Rarity distribution sum feedback
        form.addEventListener('input', e => {
            if (e.target.classList.contains('rarity-input')) {
                const sum = Array.from(form.querySelectorAll('.rarity-input')).reduce((acc, input) => acc + (parseFloat(input.value) || 0), 0);
                const feedback = form.querySelector('#rarity-sum-feedback');
                feedback.textContent = `当前总和: ${sum.toFixed(4)}`;
                feedback.classList.toggle('text-danger', Math.abs(sum - 1.0) > 1e-4);
            }
        });

        // Pass requirement toggle
        const passToggle = form.querySelector('#requires_pass');
        if (passToggle) {
            passToggle.addEventListener('change', e => {
                form.querySelector('select[name="required_item_id"]').disabled = !e.target.checked;
            });
        }
        
        // Limited time toggle
        const timeToggle = form.querySelector('input[name="limit_time"]');
        const fromInput = form.querySelector('input[name="available_from"]');
        const untilInput = form.querySelector('input[name="available_until"]');
        const applyTimeState = () => {
            const enabled = timeToggle.checked;
            fromInput.disabled = !enabled;
            untilInput.disabled = !enabled;
            if (!enabled) fromInput.value = untilInput.value = '';
        };
        if(timeToggle) {
            timeToggle.addEventListener('change', applyTimeState);
            applyTimeState();
        }

        // Form submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = new FormData(form);
            const payload = {};
            data.forEach((value, key) => payload[key] = value);

            // Data processing
            payload.id = parseInt(payload.id);
            payload.daily_rare_fish_quota = parseInt(payload.daily_rare_fish_quota) || 0;
            payload.fishing_cost = parseInt(payload.fishing_cost) || 10;
            payload.is_active = form.querySelector('input[name="is_active"]').checked;
            if (!form.querySelector('input[name="limit_time"]').checked) {
                payload.available_from = '';
                payload.available_until = '';
            }
            
            const rarityDistribution = [
                ...[...Array(5).keys()].map(i => parseFloat(payload[`rarity_${i+1}`]) || 0),
                parseFloat(payload['rarity_6plus']) || 0
            ];
            if (Math.abs(rarityDistribution.reduce((a, b) => a + b, 0) - 1.0) > 1e-4) {
                showFormError(form, '稀有度分布总和必须为 1');
                return;
            }
            payload.configs = { rarity_distribution: rarityDistribution };
            payload.specific_fish_ids = Array.from(selectedSet);
            payload.requires_pass = form.querySelector('input[name="requires_pass"]').checked;
            payload.required_item_id = payload.requires_pass ? (parseInt(payload.required_item_id) || null) : null;
            
            // API call
            const url = zoneId ? `/admin/api/zones/${zoneId}` : '/admin/api/zones';
            const method = zoneId ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                location.reload();
            } else {
                const result = await response.json();
                showFormError(form, result.message, result.errors);
            }
        });
    }

    function showFormError(form, message, errors = null) {
        const errorAlert = form.querySelector('#form-error-alert');
        let html = `<strong>${message}</strong>`;
        if (errors) {
            html += `<ul>${Object.entries(errors).map(([key, value]) => `<li>${value}</li>`).join('')}</ul>`;
        }
        errorAlert.innerHTML = html;
        errorAlert.classList.remove('d-none');
    }

    //
    // Global Event Listeners
    //
    window.deleteZone = async function(zoneId) {
        if (confirm('确定要删除这个区域吗？')) {
            const response = await fetch(`/admin/api/zones/${zoneId}`, { method: 'DELETE' });
            if (response.ok) {
                document.getElementById(`zone-card-${zoneId}`).remove();
            } else {
                const result = await response.json();
                alert('删除失败: ' + (result.message || '未知错误'));
            }
        }
    };
    
    //
    // Initialization
    //
    setupModal('createZoneModal', '#create-zone-form');
    setupModal('editZoneModal', '#edit-zone-form');
});
