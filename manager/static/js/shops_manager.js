let shops = [];
let currentShopId = null;

document.addEventListener('DOMContentLoaded', function() {
  bindEvents();
  loadShops();
});

function bindEvents() {
  document.getElementById('refresh-shops')?.addEventListener('click', loadShops);
  document.getElementById('submit-shop')?.addEventListener('click', submitShop);
  document.getElementById('add-inventory')?.addEventListener('click', () => openAddInventory());
}

async function loadShops() {
  const res = await fetch('/admin/api/shops');
  const data = await res.json();
  shops = data.shops || [];
  renderShops();
}

function renderShops() {
  const table = document.getElementById('shops-table');
  if (!shops.length) { table.innerHTML = '<p class="text-muted">暂无商店</p>'; return; }
  let html = `<table class="table table-striped"><thead><tr>
      <th>ID</th><th>名称</th><th>类型</th><th>状态</th><th>时间</th><th>操作</th>
    </tr></thead><tbody>`;
  shops.forEach(s => {
    const typeName = s.shop_type === 'premium' ? '高级' : (s.shop_type === 'limited' ? '限时' : '普通');
    const status = s.is_active ? '<span class="badge bg-success">启用</span>' : '<span class="badge bg-secondary">禁用</span>';
    const time = `${s.start_time || '-'} ~ ${s.end_time || '-'}`;
    html += `<tr ${currentShopId===s.shop_id?'class="table-primary"':''}>
      <td>${s.shop_id}</td>
      <td>${s.name}</td>
      <td>${typeName}</td>
      <td>${status}</td>
      <td>${time}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary" onclick="selectShop(${s.shop_id})">选择</button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteShop(${s.shop_id})">删除</button>
      </td>
    </tr>`;
  });
  html += '</tbody></table>';
  table.innerHTML = html;
  if (currentShopId) loadInventory(currentShopId);
}

async function submitShop() {
  const form = document.getElementById('shop-form');
  const formData = new FormData(form);
  const payload = {
    name: formData.get('name'),
    description: formData.get('description') || null,
    shop_type: formData.get('shop_type') || 'normal',
    is_active: formData.get('is_active') === 'on',
    start_time: formData.get('start_time') || null,
    end_time: formData.get('end_time') || null,
    sort_order: parseInt(formData.get('sort_order') || '100')
  };
  const res = await fetch('/admin/api/shops', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const data = await res.json();
  if (data.success) {
    alert('商店保存成功');
    form.reset();
    loadShops();
  } else {
    alert('保存失败: ' + data.message);
  }
}

function selectShop(shopId) {
  currentShopId = shopId;
  document.getElementById('add-inventory').disabled = false;
  renderShops();
}

async function deleteShop(shopId) {
  if (!confirm('确定删除该商店？')) return;
  const res = await fetch(`/admin/api/shops/${shopId}`, {method:'DELETE'});
  const data = await res.json();
  if (data.success) {
    if (currentShopId === shopId) { currentShopId = null; document.getElementById('add-inventory').disabled = true; }
    loadShops();
  } else {
    alert('删除失败: ' + data.message);
  }
}

async function loadInventory(shopId) {
  const res = await fetch(`/admin/api/shops/${shopId}/inventory`);
  const data = await res.json();
  renderInventory(data.inventory || []);
}

function renderInventory(inv) {
  const table = document.getElementById('inventory-table');
  if (!inv.length) { table.innerHTML = '<p class="text-muted">暂无上架</p>'; return; }
  let html = `<table class="table table-striped"><thead><tr>
    <th>ID</th><th>商品ID</th><th>名称</th><th>库存</th><th>总限购/日限购</th><th>状态</th><th>操作</th>
  </tr></thead><tbody>`;
  inv.forEach(r => {
    const stock = r.stock_total == null ? '无限' : `${r.stock_sold || 0}/${r.stock_total}`;
    const limits = `${r.per_user_limit ?? '-'} / ${r.per_user_daily_limit ?? '-'}`;
    const status = r.is_active ? '启用' : '禁用';
    html += `<tr>
      <td>${r.inventory_id}</td>
      <td>${r.offer_id}</td>
      <td>${r.offer_name || ''}</td>
      <td>${stock}</td>
      <td>${limits}</td>
      <td>${status}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary" onclick="editInventory(${r.inventory_id})">编辑</button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteInventory(${r.inventory_id})">删除</button>
      </td>
    </tr>`;
  });
  html += '</tbody></table>';
  table.innerHTML = html;
}

async function openAddInventory() {
  const offerId = prompt('输入要上架的商品ID(OfferID)：');
  if (!offerId) return;
  const payload = { offer_id: parseInt(offerId), is_active: true };
  const res = await fetch(`/admin/api/shops/${currentShopId}/inventory`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const data = await res.json();
  if (data.success) {
    loadInventory(currentShopId);
  } else {
    alert('添加失败: ' + data.message);
  }
}

async function deleteInventory(inventoryId) {
  if (!confirm('确定删除该上架记录？')) return;
  const res = await fetch(`/admin/api/shop/inventory/${inventoryId}`, {method:'DELETE'});
  const data = await res.json();
  if (data.success) loadInventory(currentShopId); else alert('删除失败: ' + data.message);
}

function editInventory(inventoryId) {
  const stock = prompt('设置总库存（留空=无限）：');
  const limit = prompt('设置每人总限购（留空=继承/无限）：');
  const dlimit = prompt('设置每日限购（留空=继承/无限）：');
  const payload = {};
  if (stock !== null && stock !== '') payload.stock_total = parseInt(stock);
  if (limit !== null && limit !== '') payload.per_user_limit = parseInt(limit);
  if (dlimit !== null && dlimit !== '') payload.per_user_daily_limit = parseInt(dlimit);
  fetch(`/admin/api/shop/inventory/${inventoryId}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
    .then(r=>r.json()).then(d=>{ if (d.success) loadInventory(currentShopId); else alert('更新失败: ' + d.message); });
}


