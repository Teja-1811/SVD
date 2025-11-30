document.addEventListener('DOMContentLoaded', function() {
    const contactForm = document.getElementById('contactForm');
    const whatsappBtn = document.getElementById('whatsappBtn');

    if (contactForm && whatsappBtn) {
        whatsappBtn.addEventListener('click', function(e) {
            e.preventDefault();

            // Get form data
            const formData = new FormData(contactForm);
            const name = formData.get('name').trim();
            const phone = formData.get('phone').trim();
            const email = formData.get('email').trim();
            const subject = formData.get('subject').trim();
            const message = formData.get('message').trim();

            // Validate required fields
            if (!name || !phone || !subject || !message) {
                alert('Please fill in all required fields.');
                return;
            }

            // Disable button to prevent double submission
            whatsappBtn.disabled = true;
            whatsappBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Sending...';

            // Send data to server
            fetch('/contact/submit/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message
                    alert(data.message);

                    // Open WhatsApp with the generated message
                    if (data.whatsapp_url) {
                        window.open(data.whatsapp_url, '_blank');
                    }

                    // Reset form
                    contactForm.reset();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            })
            .finally(() => {
                // Re-enable button
                whatsappBtn.disabled = false;
                whatsappBtn.innerHTML = '<i class="bi bi-whatsapp me-2"></i>Share via WhatsApp';
            });
        });
    }
});
