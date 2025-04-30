document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const authForm = document.getElementById('authForm');
    const downloadSection = document.getElementById('downloadSection');
    const errorContainer = document.getElementById('errorContainer');
    const clientIdInput = document.getElementById('clientId');
    const clientSecretInput = document.getElementById('clientSecret');
    const authorizeBtn = document.getElementById('authorizeBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const stepContainers = document.querySelectorAll('.step-container');
    
    // Session state
    let sessionId = null;
    
    // Check for existing session ID in URL
    const urlParams = new URLSearchParams(window.location.search);
    const urlSessionId = urlParams.get('session_id');
    
    if (urlSessionId) {
        // We have a session ID, check if it's valid
        checkSession(urlSessionId);
    }
    
    // Event listeners
    authForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        await authorize();
    });
    
    downloadBtn.addEventListener('click', async function() {
        await downloadSongs();
    });
    
    // Functions
    async function authorize() {
        // Validate inputs
        const clientId = clientIdInput.value.trim();
        const clientSecret = clientSecretInput.value.trim();
        
        if (!clientId || !clientSecret) {
            showError("Please enter both Client ID and Client Secret");
            return;
        }
        
        // Update UI
        setLoading(true, "Connecting to Spotify...");
        setActiveStep(1);
        
        try {
            const response = await fetch('/authorize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    client_id: clientId,
                    client_secret: clientSecret
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || "Authorization failed");
            }
            
            // Store session ID
            sessionId = data.session_id;
            
            // Redirect to Spotify authorization
            window.location.href = data.auth_url;
            
        } catch (error) {
            showError("Authorization failed: " + error.message);
            setLoading(false);
        }
    }
    
    async function checkSession(sid) {
        try {
            const response = await fetch(`/status/${sid}`);
            const data = await response.json();
            
            if (data.valid && data.authorized) {
                // Session is valid and authorized
                sessionId = sid;
                showDownloadSection();
                setCompletedStep(1);
                setActiveStep(2);
            } else {
                // Session is invalid, show auth form
                showError("Session expired or invalid. Please authorize again.");
            }
        } catch (error) {
            showError("Failed to verify session: " + error.message);
        }
    }
    
    async function downloadSongs() {
        if (!sessionId) {
            showError("No active session. Please authorize first.");
            return;
        }
        
        setLoading(true, "Downloading your songs...");
        setActiveStep(2);
        
        try {
            // Create an invisible iframe to handle the file download
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
            
            // Set the source to the download endpoint
            iframe.src = `/download/${sessionId}`;
            
            // Show success message after a delay
            setTimeout(() => {
                setLoading(false);
                setCompletedStep(2);
                showSuccess("Download started successfully! If your browser blocked the download, please check the popup notifications.");
            }, 2000);
            
        } catch (error) {
            showError("Download failed: " + error.message);
            setLoading(false);
        }
    }
    
    function showDownloadSection() {
        authForm.style.display = 'none';
        downloadSection.classList.remove('d-none');
        downloadSection.classList.add('animated-fade');
    }
    
    function setLoading(isLoading, message = null) {
        if (isLoading) {
            loadingSpinner.classList.remove('d-none');
            authorizeBtn.disabled = true;
            downloadBtn.disabled = true;
            
            if (message) {
                loadingSpinner.querySelector('.loading-message').textContent = message;
            }
        } else {
            loadingSpinner.classList.add('d-none');
            authorizeBtn.disabled = false;
            downloadBtn.disabled = false;
        }
    }
    
    function setActiveStep(stepNumber) {
        // Reset all steps
        stepContainers.forEach(container => {
            container.classList.remove('active', 'completed');
        });
        
        // Set the current step as active
        if (stepNumber > 0 && stepNumber <= stepContainers.length) {
            stepContainers[stepNumber - 1].classList.add('active');
        }
        
        // Set all previous steps as completed
        for (let i = 0; i < stepNumber - 1; i++) {
            stepContainers[i].classList.add('completed');
        }
    }
    
    function setCompletedStep(stepNumber) {
        if (stepNumber > 0 && stepNumber <= stepContainers.length) {
            stepContainers[stepNumber - 1].classList.remove('active');
            stepContainers[stepNumber - 1].classList.add('completed');
        }
    }
    
    function showError(message) {
        // Create alert
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show animated-fade';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add to container
        errorContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    }
    
    function showSuccess(message) {
        // Create alert
        const alert = document.createElement('div');
        alert.className = 'alert alert-success alert-dismissible fade show animated-fade';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add to container
        errorContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    }
});
