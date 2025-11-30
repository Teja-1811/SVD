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

            // Generate WhatsApp message
            const whatsappMessage = `New Contact Form Inquiry - SVD Milk Agencies\n\n` +
                `Name: ${name}\n` +
                `Phone: ${phone}\n` +
                (email ? `Email: ${email}\n` : '') +
                `Subject: ${subject}\n\n` +
                `Message:\n${message}\n\n` +
                `Inquiry received via SVD Milk Agencies website\n` +
                `We typically respond within 24 hours`;

            // Encode the message for URL
            const encodedMessage = encodeURIComponent(whatsappMessage);

            // WhatsApp URL (using the phone number from the footer)
            const whatsappURL = `https://wa.me/919392890375?text=${encodedMessage}`;

            // Open WhatsApp
            window.open(whatsappURL, '_blank');

            // Optional: Reset form after sending
            // contactForm.reset();
        });
    }
});
