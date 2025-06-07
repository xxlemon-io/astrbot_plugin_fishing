document.addEventListener('DOMContentLoaded', function () {
    const itemModal = document.getElementById('itemModal');
    if (!itemModal) return;

    const modalTitle = itemModal.querySelector('.modal-title');
    const form = itemModal.querySelector('#item-form');

    document.getElementById('addItemBtn').addEventListener('click', function () {
        modalTitle.textContent = '添加新鱼竿';
        form.action = addUrl;
        form.reset();
        // 重置为默认值
        form.querySelector('[name="bonus_fish_quality_modifier"]').value = '1.0';
        form.querySelector('[name="bonus_fish_quantity_modifier"]').value = '1.0';
        form.querySelector('[name="bonus_rare_fish_chance"]').value = '0.0';
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const data = JSON.parse(this.dataset.itemJson);
            modalTitle.textContent = `编辑鱼竿: ${data.name}`;
            form.action = `${editUrlBase}/${data.rod_id}`;
            for (const key in data) {
                if (form.elements[key]) {
                    form.elements[key].value = data[key] === null ? '' : data[key];
                }
            }
        });
    });
});