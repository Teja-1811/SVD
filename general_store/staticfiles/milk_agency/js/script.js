document.addEventListener('DOMContentLoaded', function () {
    // Automatically dismiss all Bootstrap alert messages after 10 seconds
    const alertList = document.querySelectorAll('.message-container-top-right .alert');
    console.log('Found', alertList.length, 'alert messages for automatic dismissal');
    alertList.forEach((alert, index) => {
        console.log('Setting up automatic dismissal for alert', index);
        setTimeout(() => {
            console.log('Automatically dismissing alert', index);
            // Remove 'show' class to trigger fade out transition
            alert.classList.remove('show');
            // Remove the alert element from DOM after fade out transition (300ms)
            setTimeout(() => {
                console.log('Removing alert', index, 'from DOM');
                alert.remove();
            }, 300);
        }, 10000);
    });

    // Manually handle close button clicks to dismiss alerts
    const closeButtons = document.querySelectorAll('.message-container-top-right .btn-close');
    closeButtons.forEach((button) => {
        button.addEventListener('click', function () {
            const alert = this.closest('.alert');
            if (alert) {
                // Remove 'show' class to trigger fade out transition
                alert.classList.remove('show');
                // Remove the alert element from DOM after fade out transition (300ms)
                setTimeout(() => {
                    alert.remove();
                }, 300);
            }
        });
    });
});
