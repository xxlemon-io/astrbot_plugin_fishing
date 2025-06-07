document.addEventListener('DOMContentLoaded', function () {
    const itemModal = document.getElementById('itemModal');
    if (!itemModal) return;

    const modalTitle = itemModal.querySelector('.modal-title');
    const form = itemModal.querySelector('#item-form');

    document.getElementById('addItemBtn').addEventListener('click', function () {
        modalTitle.textContent = '添加新鱼饵';
        form.action = addUrl;
        form.reset();
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const data = JSON.parse(this.dataset.itemJson);
            modalTitle.textContent = `编辑鱼饵: ${data.name}`;
            form.action = `${editUrlBase}/${data.bait_id}`;
            for (const key in data) {
                if (form.elements[key]) {
                    form.elements[key].value = data[key]  === null ? '' : data[key];
                }
            }
        });
    });
});