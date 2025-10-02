document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('login-form');
    const errorMessage = document.getElementById('error-message');

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Hide error message
        errorMessage.classList.add('hidden');

        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const remember = document.getElementById('remember').checked;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    remember: remember
                })
            });

            if (response.ok) {
                // Redirect to dashboard on success
                window.location.href = '/';
            } else {
                const data = await response.json();
                showError(data.detail || 'Invalid email or password');
            }
        } catch (error) {
            showError('An error occurred. Please try again.');
        }
    });

    function showError(message) {
        errorMessage.querySelector('p').textContent = message;
        errorMessage.classList.remove('hidden');
    }
});
