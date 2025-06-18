document.addEventListener('DOMContentLoaded', function () {
    const itemModal = document.getElementById('itemModal');
    if (!itemModal) return;

    const modalTitle = itemModal.querySelector('.modal-title');
    const form = itemModal.querySelector('#item-form');
    // 定义所有需要重置为特定值的字段
    const fieldsToReset = {
        'duration_minutes': '0',
        'cost': '0',
        'required_rod_rarity': '0',
        'success_rate_modifier': '0.0',
        'rare_chance_modifier': '0.0',
        'garbage_reduction_modifier': '0.0',
        'value_modifier': '1.0',
        'quantity_modifier': '1.0'
    };

    document.getElementById('addItemBtn').addEventListener('click', function () {
        modalTitle.textContent = '添加新鱼饵';
        form.action = addUrl; // addUrl 是由 baits.html 模板提供的全局变量
        form.reset(); // 重置所有标准输入字段

        // 手动将特定字段重置为它们的默认值
        for (const [name, value] of Object.entries(fieldsToReset)) {
            if (form.elements[name]) {
                form.elements[name].value = value;
            }
        }

        // 确保“是一次性消耗品”复选框在添加时默认为选中状态
        if (form.elements['is_consumable']) {
            form.elements['is_consumable'].checked = true;
        }
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const data = JSON.parse(this.dataset.itemJson);
            modalTitle.textContent = `编辑鱼饵: ${data.name}`;
            form.action = `${editUrlBase}/${data.bait_id}`; // editUrlBase 也是由模板提供

            // 遍历JSON数据，填充所有匹配的表单字段
            for (const key in data) {
                if (form.elements[key]) {
                    const element = form.elements[key];
                    // 特别处理复选框
                    if (element.type === 'checkbox') {
                        // 根据数据库中的值（1或0）来设置选中状态
                        element.checked = !!data[key];
                    } else {
                        // 对其他输入字段，处理 null 值以避免显示 "null"
                        element.value = data[key] === null ? '' : data[key];
                    }
                }
            }
        });
    });
});
