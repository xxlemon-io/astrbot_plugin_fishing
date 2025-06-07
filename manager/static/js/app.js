// web_admin/static/js/app.js
document.addEventListener('DOMContentLoaded', function () {
    // 查找所有class为'alert'的通知元素
    const autoDismissAlerts = document.querySelectorAll('.alert.alert-dismissible');

    autoDismissAlerts.forEach(function(alert) {
        // 设置一个3秒（3000毫秒）的定时器
        setTimeout(function() {
            // 使用Bootstrap的Alert API来优雅地关闭通知（会触发淡出动画）
            new bootstrap.Alert(alert).close();
        }, 3000);
    });
});