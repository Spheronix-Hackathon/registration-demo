document.addEventListener('DOMContentLoaded', () => {
    const mobileInput = document.getElementById('contactMobile');
    if (!mobileInput) return;

    mobileInput.addEventListener('input', () => {
        mobileInput.value = mobileInput.value.replace(/[^0-9]/g, '');
        if (mobileInput.value.length > 10) {
            mobileInput.value = mobileInput.value.slice(0, 10);
        }
    });

    const contactForm = document.getElementById('contactForm');
    if (!contactForm) return;

    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById('contactName').value;
        const email = document.getElementById('contactEmail').value;
        const mobile = document.getElementById('contactMobile').value;
        const message = document.getElementById('contactMessage').value;
        const statusDiv = document.getElementById('formStatus');
        const submitBtn = document.getElementById('submitBtn');

        // Reset states
        statusDiv.style.display = 'none';

        // Mobile validation
        if (!/^\d{10}$/.test(mobile)) {
            statusDiv.textContent = 'Invalid mobile number format. A 10-digit number is required.';
            statusDiv.style.backgroundColor = '#ffe5e5';
            statusDiv.style.color = '#ff3b30';
            statusDiv.style.display = 'block';
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        try {
            const response = await fetch('/api/contacts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, mobile, message })
            });

            const result = await response.json();

            if (response.ok) {
                statusDiv.textContent = 'Thank you! Your message has been successfully received by our support team.';
                statusDiv.style.backgroundColor = '#e8f5e9';
                statusDiv.style.color = '#2e7d32';
                document.getElementById('contactForm').reset();
            } else {
                statusDiv.textContent = result.detail || 'We encountered an issue submitting your request. Please try again.';
                statusDiv.style.backgroundColor = '#ffe5e5';
                statusDiv.style.color = '#ff3b30';
            }
        } catch (error) {
            statusDiv.textContent = 'A network error occurred. Please verify your connection and try again.';
            statusDiv.style.backgroundColor = '#ffe5e5';
            statusDiv.style.color = '#ff3b30';
        } finally {
            statusDiv.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit';
        }
    });
});
