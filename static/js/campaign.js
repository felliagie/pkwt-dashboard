// Campaign JavaScript functionality
async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/login';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/login';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initializeCampaign();
});

let currentStep = 1;
let campaignId = null;

function initializeCampaign() {
    setupCompanySearch();
    setupFileUpload();
    setupContractFileUpload();
    setupFormSubmission();
    setupModals();
    setupDocumentsPreview();
}

// Company search functionality
function setupCompanySearch() {
    const companyInput = document.getElementById('company');
    const suggestionsContainer = document.getElementById('company-suggestions');

    companyInput.addEventListener('input', debounce(async function(e) {
        const query = e.target.value.trim();

        if (query.length < 2) {
            suggestionsContainer.style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`/api/companies/search?q=${encodeURIComponent(query)}`);
            const companies = await response.json();

            if (companies.length > 0) {
                displayCompanySuggestions(companies, suggestionsContainer);
            } else {
                suggestionsContainer.style.display = 'none';
            }
        } catch (error) {
            console.error('Error searching companies:', error);
            suggestionsContainer.style.display = 'none';
        }
    }, 300));

    // Hide suggestions when clicking outside
    document.addEventListener('click', function(e) {
        if (!companyInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
            suggestionsContainer.style.display = 'none';
        }
    });
}

function displayCompanySuggestions(companies, container) {
    container.innerHTML = companies.map(company =>
        `<div class="company-suggestion" data-company="${company.company}">${company.company}</div>`
    ).join('');

    // Add click handlers for suggestions
    container.querySelectorAll('.company-suggestion').forEach(suggestion => {
        suggestion.addEventListener('click', function() {
            document.getElementById('company').value = this.dataset.company;
            container.style.display = 'none';
        });
    });

    container.style.display = 'block';
}

// Form submission for campaign creation
function setupFormSubmission() {
    const form = document.getElementById('campaign-form');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData(form);
        const campaignData = {
            company: formData.get('company'),
            send_date: formData.get('send_date'),
            due_date: formData.get('due_date')
        };

        try {
            const response = await fetch('/api/campaigns', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(campaignData)
            });

            if (response.ok) {
                const result = await response.json();
                campaignId = result.campaign_id;
                moveToNextStep();
            } else {
                const error = await response.json();
                alert('Error creating campaign: ' + (error.detail || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error creating campaign:', error);
            alert('Error creating campaign. Please try again.');
        }
    });
}

// File upload functionality
function setupFileUpload() {
    const fileInput = document.getElementById('employee-file');
    const uploadContainer = document.querySelector('.file-upload-container');
    const uploadBtn = document.getElementById('upload-btn');

    // File input change handler
    fileInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            updateFileDisplay(file);
            uploadBtn.disabled = false;
        } else {
            resetFileDisplay();
            uploadBtn.disabled = true;
        }
    });

    // Drag and drop handlers
    uploadContainer.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('dragover');
    });

    uploadContainer.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
    });

    uploadContainer.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (isValidFileType(file)) {
                fileInput.files = files;
                updateFileDisplay(file);
                uploadBtn.disabled = false;
            } else {
                alert('Please upload only XLS, XLSX, or CSV files.');
            }
        }
    });

    // Upload button handler
    uploadBtn.addEventListener('click', function() {
        if (fileInput.files[0]) {
            uploadEmployeeFile(fileInput.files[0]);
        }
    });
}

function updateFileDisplay(file) {
    const uploadDisplay = document.querySelector('.file-upload-display');
    uploadDisplay.innerHTML = `
        <div class="file-upload-icon">📋</div>
        <div class="file-upload-text">
            <span class="file-upload-title">${file.name}</span>
            <span class="file-upload-subtitle">${formatFileSize(file.size)}</span>
        </div>
    `;
}

function resetFileDisplay() {
    const uploadDisplay = document.querySelector('.file-upload-display');
    uploadDisplay.innerHTML = `
        <div class="file-upload-icon">🗂</div>
        <div class="file-upload-text">
            <span class="file-upload-title">Choose file or drag here</span>
            <span class="file-upload-subtitle">Supports XLS, XLSX, CSV files</span>
        </div>
    `;
}

function isValidFileType(file) {
    const validTypes = [
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv'
    ];
    return validTypes.includes(file.type) ||
           file.name.toLowerCase().endsWith('.xls') ||
           file.name.toLowerCase().endsWith('.xlsx') ||
           file.name.toLowerCase().endsWith('.csv');
}

async function uploadEmployeeFile(file) {
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const uploadBtn = document.getElementById('upload-btn');

    // Show progress bar
    progressContainer.classList.remove('hidden');
    uploadBtn.disabled = true;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('campaign_id', campaignId);

    try {
        // Simulate progress animation
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 20;
            if (progress > 90) {
                clearInterval(progressInterval);
                progress = 90;
            }
            updateProgress(progress, 'Processing file...');
        }, 200);

        const response = await fetch('/api/campaigns/upload-employees', {
            method: 'POST',
            body: formData
        });

        clearInterval(progressInterval);

        if (response.ok) {
            const result = await response.json();
            updateProgress(100, `Successfully processed ${result.processed_count} employees`);

            setTimeout(() => {
                moveToNextStep();
            }, 1500);
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        progressContainer.classList.add('hidden');
        uploadBtn.disabled = false;
        alert('Error uploading file: ' + error.message);
    }
}

function updateProgress(percentage, text) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    progressBar.style.width = `${percentage}%`;
    progressText.textContent = text;
}

// Timeline navigation
function moveToNextStep() {
    if (currentStep < 4) {
        // Mark current step as completed
        markStepCompleted(currentStep);

        // Move to next step
        currentStep++;
        showStep(currentStep);
        markStepActive(currentStep);
    }
}

function showStep(stepNumber) {
    // Hide all steps
    document.querySelectorAll('.process-step').forEach(step => {
        step.classList.add('hidden');
    });

    // Show current step
    document.getElementById(`step-${stepNumber}`).classList.remove('hidden');
}

function markStepActive(stepNumber) {
    // Remove active class from all steps
    document.querySelectorAll('.timeline-step').forEach(step => {
        step.classList.remove('active');
    });

    // Add active class to current step
    document.querySelector(`.timeline-step[data-step="${stepNumber}"]`).classList.add('active');
}

function markStepCompleted(stepNumber) {
    const step = document.querySelector(`.timeline-step[data-step="${stepNumber}"]`);
    step.classList.remove('active');
    step.classList.add('completed');

    // Mark connector as completed if not the last step
    if (stepNumber < 4) {
        const connectors = document.querySelectorAll('.timeline-connector');
        if (connectors[stepNumber - 1]) {
            connectors[stepNumber - 1].classList.add('completed');
        }
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Setup modals
function setupModals() {
    // Contract preview modal
    document.getElementById('close-preview').addEventListener('click', function() {
        document.getElementById('contract-preview-modal').classList.add('hidden');
    });

    document.getElementById('confirm-contract').addEventListener('click', function() {
        document.getElementById('contract-preview-modal').classList.add('hidden');
        const fileInput = document.getElementById('contract-file');
        if (fileInput.files[0]) {
            uploadContractFile(fileInput.files[0]);
        }
    });
}

// Contract file upload setup
function setupContractFileUpload() {
    const fileInput = document.getElementById('contract-file');
    const uploadContainer = fileInput.closest('.file-upload-container');
    const uploadBtn = document.getElementById('upload-contract-btn');

    // File input change handler
    fileInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            updateContractFileDisplay(file);
            uploadBtn.disabled = false;
        } else {
            resetContractFileDisplay();
            uploadBtn.disabled = true;
        }
    });

    // Drag and drop handlers
    uploadContainer.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('dragover');
    });

    uploadContainer.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
    });

    uploadContainer.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (isValidContractFileType(file)) {
                fileInput.files = files;
                updateContractFileDisplay(file);
                uploadBtn.disabled = false;
            } else {
                alert('Please upload only DOC, DOCX, or PDF files.');
            }
        }
    });

    // Upload button handler
    uploadBtn.addEventListener('click', function() {
        if (fileInput.files[0]) {
            uploadContractFile(fileInput.files[0]);
        }
    });
}

function updateContractFileDisplay(file) {
    const uploadDisplay = document.querySelector('#step-3 .file-upload-display');
    uploadDisplay.innerHTML = `
        <div class="file-upload-icon">📄</div>
        <div class="file-upload-text">
            <span class="file-upload-title">${file.name}</span>
            <span class="file-upload-subtitle">${formatFileSize(file.size)}</span>
        </div>
    `;
}

function resetContractFileDisplay() {
    const uploadDisplay = document.querySelector('#step-3 .file-upload-display');
    uploadDisplay.innerHTML = `
        <div class="file-upload-icon">📄</div>
        <div class="file-upload-text">
            <span class="file-upload-title">Choose contract file or drag here</span>
            <span class="file-upload-subtitle">Supports DOC, DOCX, PDF files</span>
        </div>
    `;
}

function isValidContractFileType(file) {
    const validTypes = [
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/pdf'
    ];
    return validTypes.includes(file.type) ||
           file.name.toLowerCase().endsWith('.doc') ||
           file.name.toLowerCase().endsWith('.docx') ||
           file.name.toLowerCase().endsWith('.pdf');
}

async function previewContractFile(file) {
    try {
        document.getElementById('contract-preview-content').innerHTML = `
            <div class="text-sm text-gray-700 p-4">
                <p><strong>File:</strong> ${file.name}</p>
                <p><strong>Size:</strong> ${formatFileSize(file.size)}</p>
                <p><strong>Type:</strong> ${file.type}</p>
                <p class="mt-4 text-gray-600">Contract preview will be processed and displayed here when uploaded to the database.</p>
            </div>
        `;
        document.getElementById('contract-preview-modal').classList.remove('hidden');
    } catch (error) {
        alert('Error previewing contract file: ' + error.message);
    }
}

async function uploadContractFile(file) {
    const progressContainer = document.getElementById('contract-progress-container');
    const progressBar = document.getElementById('contract-progress-bar');
    const progressText = document.getElementById('contract-progress-text');
    const uploadBtn = document.getElementById('upload-contract-btn');

    // Show progress bar
    progressContainer.classList.remove('hidden');
    uploadBtn.disabled = true;

    try {
        // Simulate progress animation
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 20;
            if (progress > 90) {
                clearInterval(progressInterval);
                progress = 90;
            }
            updateContractProgress(progress, 'Processing contract file...');
        }, 200);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('campaign_id', campaignId);

        const response = await fetch('/api/campaigns/upload-contract', {
            method: 'POST',
            body: formData
        });

        clearInterval(progressInterval);

        if (response.ok) {
            const result = await response.json();
            updateContractProgress(100, 'Contract uploaded successfully');

            // Store dates for final step
            const sendDate = document.getElementById('send-date').value;
            const dueDate = document.getElementById('due-date').value;
            document.getElementById('send-date-display').textContent = sendDate;
            document.getElementById('due-date-display').textContent = dueDate;

            setTimeout(() => {
                moveToNextStep();
            }, 1500);
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
    } catch (error) {
        console.error('Error uploading contract file:', error);
        progressContainer.classList.add('hidden');
        uploadBtn.disabled = false;
        alert('Error uploading contract file: ' + error.message);
    }
}

function updateContractProgress(percentage, text) {
    const progressBar = document.getElementById('contract-progress-bar');
    const progressText = document.getElementById('contract-progress-text');

    progressBar.style.width = `${percentage}%`;
    progressText.textContent = text;
}

// Setup documents preview modal
function setupDocumentsPreview() {
    // Preview Documents button handler
    document.getElementById('preview-documents-btn').addEventListener('click', function() {
        loadModalContractsAndTemplate();
        document.getElementById('documents-preview-modal').classList.remove('hidden');
    });

    // Close modal handler
    document.getElementById('close-documents-preview').addEventListener('click', function() {
        document.getElementById('documents-preview-modal').classList.add('hidden');
    });

    // Close modal when clicking outside
    document.getElementById('documents-preview-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.add('hidden');
        }
    });
}

// Load contracts table and template in modal
async function loadModalContractsAndTemplate() {
    await loadModalContractsTable();
    await loadModalContractTemplate();
    await populateContractStatus();
}

// Load contracts table for modal
async function loadModalContractsTable() {
    try {
        const response = await fetch(`/api/campaigns/${campaignId}/contracts`);
        const contracts = await response.json();

        const tableHeader = document.getElementById('modal-contract-table-header');
        const tableBody = document.getElementById('modal-contract-table-body');

        if (contracts.length > 0) {
            // Create table headers
            const headers = Object.keys(contracts[0]);
            tableHeader.innerHTML = headers.map(header =>
                `<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${header}</th>`
            ).join('');

            // Create table rows
            tableBody.innerHTML = contracts.map(contract =>
                `<tr class="hover:bg-gray-50">
                    ${headers.map(header =>
                        `<td class="px-4 py-2 whitespace-nowrap text-sm text-gray-900">${contract[header] || ''}</td>`
                    ).join('')}
                </tr>`
            ).join('');
        } else {
            tableHeader.innerHTML = '<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">No Data</th>';
            tableBody.innerHTML = '<tr><td class="px-4 py-2 whitespace-nowrap text-sm text-gray-500">No contracts found</td></tr>';
        }
    } catch (error) {
        console.error('Error loading contracts table:', error);
        const tableHeader = document.getElementById('modal-contract-table-header');
        const tableBody = document.getElementById('modal-contract-table-body');

        tableHeader.innerHTML = '<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error</th>';
        tableBody.innerHTML = '<tr><td class="px-4 py-2 whitespace-nowrap text-sm text-red-500">Error loading data</td></tr>';
    }
}

// Load contract template HTML for modal
async function loadModalContractTemplate() {
    try {
        const response = await fetch(`/api/campaigns/${campaignId}/contract-template`);
        const template = await response.json();

        const templateContent = document.getElementById('modal-contract-template-content');
        if (template.html_page) {
            // Create iframe to isolate contract HTML
            const iframe = document.createElement('iframe');
            iframe.style.width = '100%';
            iframe.style.height = '400px';
            iframe.style.border = 'none';
            iframe.style.borderRadius = '4px';

            // Clear existing content and add iframe
            templateContent.innerHTML = '';
            templateContent.appendChild(iframe);

            // Write contract HTML to iframe
            iframe.contentDocument.open();
            iframe.contentDocument.write(template.html_page);
            iframe.contentDocument.close();
        } else {
            templateContent.innerHTML = '<p class="text-gray-500">No contract template found</p>';
        }
    } catch (error) {
        console.error('Error loading contract template:', error);
        const templateContent = document.getElementById('modal-contract-template-content');
        templateContent.innerHTML = '<p class="text-red-500">Error loading contract template</p>';
    }
}

// Populate contract status after processes 1-3 complete
async function populateContractStatus() {
    try {
        const response = await fetch(`/api/campaigns/${campaignId}/populate-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            throw new Error('Failed to populate contract status');
        }

        const result = await response.json();
        console.log('Contract status populated:', result);
    } catch (error) {
        console.error('Error populating contract status:', error);
    }
}