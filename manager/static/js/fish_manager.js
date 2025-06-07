document.addEventListener('DOMContentLoaded', function () {
    const itemModal = document.getElementById('fishModal');
    if (!itemModal) return;

    const modalTitle = itemModal.querySelector('.modal-title');
    const form = itemModal.querySelector('#fish-form');

    document.getElementById('addFishBtn').addEventListener('click', function () {
        modalTitle.textContent = '添加新鱼';
        form.action = addUrl; // 使用从HTML传入的全局变量
        form.reset();
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const data = JSON.parse(this.dataset.itemJson);
            modalTitle.textContent = `编辑鱼类: ${data.name}`;
            form.action = `${editUrlBase}/${data.fish_id}`; // 使用从HTML传入的全局变量
            for (const key in data) {
                if (form.elements[key]) {
                    form.elements[key].value = data[key] || '';
                }
            }
        });
    });
});