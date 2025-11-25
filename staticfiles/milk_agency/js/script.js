document.addEventListener('DOMContentLoaded', function () {
    // Automatically dismiss all Bootstrap alert messages after 10 seconds
    const alertList = document.querySelectorAll('.message-container-top-right .alert');
    
    alertList.forEach((alert, index) => {
        
        setTimeout(() => {
            
            // Remove 'show' class to trigger fade out transition
            alert.classList.remove('show');
            // Remove the alert element from DOM after fade out transition (300ms)
            setTimeout(() => {
                
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
