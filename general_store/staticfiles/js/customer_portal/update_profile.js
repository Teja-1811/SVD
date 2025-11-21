document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const newPassword = document.getElementById('new_password');
    const confirmPassword = document.getElementById('confirm_password');
    const currentPassword = document.getElementById('current_password');

    // Live validation for new password length
    newPassword.addEventListener('input', function() {
        const value = this.value;
        const feedback = document.createElement('small');
        feedback.id = 'new-password-feedback';
        feedback.className = value.length >= 8 ? 'text-success' : 'text-danger';
        feedback.textContent = value.length >= 8 ? 'Password is strong enough' : 'Password must be at least 8 characters';

        // Remove existing feedback
        const existingFeedback = document.getElementById('new-password-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        this.parentNode.appendChild(feedback);
        this.classList.toggle('is-invalid', value.length < 8);
        this.classList.toggle('is-valid', value.length >= 8);
    });

    // Live validation for confirm password match
    confirmPassword.addEventListener('input', function() {
        const newPass = newPassword.value;
        const confirmPass = this.value;
        const feedback = document.createElement('small');
        feedback.id = 'confirm-password-feedback';
        feedback.className = newPass === confirmPass ? 'text-success' : 'text-danger';
        feedback.textContent = newPass === confirmPass ? 'Passwords match' : "Passwords don't match";

        // Remove existing feedback
        const existingFeedback = document.getElementById('confirm-password-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        this.parentNode.appendChild(feedback);
        this.classList.toggle('is-invalid', newPass !== confirmPass && confirmPass.length > 0);
        this.classList.toggle('is-valid', newPass === confirmPass && confirmPass.length > 0);
    });

    // Toggle password visibility functions
    function togglePasswordVisibility(inputId, eyeId) {
        const input = document.getElementById(inputId);
        const eye = document.getElementById(eyeId);
        const toggle = document.getElementById('toggle-' + inputId);

        if (input.type === 'password') {
            input.type = 'text';
            eye.classList.remove('bi-eye');
            eye.classList.add('bi-eye-slash');
        } else {
            input.type = 'password';
            eye.classList.remove('bi-eye-slash');
            eye.classList.add('bi-eye');
        }
    }

    document.getElementById('toggle-current-password').addEventListener('click', function() {
        togglePasswordVisibility('current_password', 'eye-current');
    });

    document.getElementById('toggle-new-password').addEventListener('click', function() {
        togglePasswordVisibility('new_password', 'eye-new');
    });

    document.getElementById('toggle-confirm-password').addEventListener('click', function() {
        togglePasswordVisibility('confirm_password', 'eye-confirm');
    });

    // On submit validation (fallback)
    form.addEventListener('submit', function(e) {
        const newPass = newPassword.value.trim();
        const confirmPass = confirmPassword.value.trim();
        const currentPass = currentPassword.value.trim();

        // If no password change is intended (new_password empty), allow submission
        if (!newPass) {
            return true;
        }

        // Check if current password is entered
        if (!currentPass) {
            alert('Please enter your current password to change it.');
            e.preventDefault();
            return false;
        }

        // Check new password length
        if (newPass.length < 8) {
            alert('New password must be at least 8 characters long.');
            e.preventDefault();
            return false;
        }

        // Check if new password and confirm match
        if (newPass !== confirmPass) {
            alert("New password and confirm password do not match.");
            e.preventDefault();
            return false;
        }

        return true;
    });
});
