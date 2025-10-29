// Campaign Detail JavaScript functionality
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
    initializeCampaignDetail();
    setupModal();
    setupActionButtons();
});

let campaignId = null;
let contracts = [];
let contractTemplate = null;

function initializeCampaignDetail() {
    // Get campaign ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    campaignId = urlParams.get('id');

    if (!campaignId) {
        showError('No campaign ID provided');
        return;
    }

    loadCampaignInfo();
    loadContracts();
}

// Load campaign information
async function loadCampaignInfo() {
    try {
        const response = await fetch(`/api/campaigns/${campaignId}`);
        const campaign = await response.json();

        // Build company display
        const companyName = campaign.company_name || 'PT Mandom Indonesia';
        const companyTitle = campaign.company_detail
            ? `${companyName} - ${campaign.company_detail}`
            : companyName;

        document.getElementById('campaign-title').innerHTML = `
            <div>${companyName}</div>
            ${campaign.company_detail ? `<div class="text-2xl font-medium text-gray-600 mt-2">${campaign.company_detail}</div>` : ''}
        `;
        document.getElementById('campaign-subtitle').textContent = `Campaign ID: ${campaign.campaign_id} | Created: ${formatDate(campaign.created_at)} | Send Date: ${formatDate(campaign.send_at)} | Due Date: ${formatDate(campaign.due_date)}`;
    } catch (error) {
        console.error('Error loading campaign info:', error);
        document.getElementById('campaign-subtitle').textContent = 'Error loading campaign information';
    }
}

// Load contracts with status information
async function loadContracts() {
    const loadingElement = document.getElementById('loading');
    const tableHeader = document.getElementById('table-header');
    const tableBody = document.getElementById('contracts-table-body');

    try {
        loadingElement.classList.remove('hidden');

        const response = await fetch(`/api/campaigns/${campaignId}/contracts-with-status`);
        contracts = await response.json();

        loadingElement.classList.add('hidden');

        if (contracts.length > 0) {
            // Define desired columns in order
            const displayColumns = [
                'contract_id',
                'campaign_id',
                'contract_num_detail',
                'name',
                'mobile_number',
                'email',
                'send_status',
                'signed_status',
                'signed_at'
            ];

            // Create table headers
            tableHeader.innerHTML = displayColumns.map(header =>
                `<th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: #6B6B6B;">${header}</th>`
            ).join('') + '<th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider" style="color: #6B6B6B;">Actions</th>';

            // Create table rows
            tableBody.innerHTML = contracts.map(contract => {
                const rowCells = displayColumns.map(header => {
                    let value = contract[header];

                    // Format boolean values
                    if (header === 'send_status' || header === 'signed_status') {
                        if (value === true) {
                            value = '<span style="color: #10B981;" class="font-semibold">✓ Yes</span>';
                        } else if (value === false) {
                            value = '<span style="color: #9B9B9B;">✗ No</span>';
                        } else {
                            value = '<span style="color: #9B9B9B;">-</span>';
                        }
                    } else if (header === 'signed_at' && !value) {
                        value = '-';
                    } else if (!value && value !== 0 && value !== false) {
                        value = '-';
                    }

                    return `<td class="px-6 py-4 whitespace-nowrap text-sm" style="color: #1A1A1A;">${value}</td>`;
                }).join('');

                // Add Preview button
                const actionCell = `<td class="px-6 py-4 whitespace-nowrap text-sm">
                    <button class="preview-button" onclick="openContractPreview(${contract.contract_id})">
                        Preview Contract
                    </button>
                </td>`;

                return `<tr class="hover:bg-gray-50">${rowCells}${actionCell}</tr>`;
            }).join('');

            // Load contract template for later use
            loadContractTemplate();
        } else {
            tableHeader.innerHTML = '<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">No Data</th>';
            tableBody.innerHTML = '<tr><td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">No contracts found</td></tr>';
        }
    } catch (error) {
        console.error('Error loading contracts:', error);
        loadingElement.classList.add('hidden');

        tableHeader.innerHTML = '<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error</th>';
        tableBody.innerHTML = '<tr><td class="px-6 py-4 whitespace-nowrap text-sm text-red-500">Error loading data</td></tr>';
    }
}

// Load contract template HTML
async function loadContractTemplate() {
    try {
        const response = await fetch(`/api/campaigns/${campaignId}/contract-template`);
        contractTemplate = await response.json();
    } catch (error) {
        console.error('Error loading contract template:', error);
        contractTemplate = null;
    }
}

// Setup modal functionality
function setupModal() {
    // Close modal handler
    document.getElementById('close-preview-modal').addEventListener('click', function() {
        document.getElementById('contract-preview-modal').classList.add('hidden');
    });

    // Close modal when clicking outside
    document.getElementById('contract-preview-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.add('hidden');
        }
    });
}

// Open contract preview modal with employee data filled in
function openContractPreview(contractId) {
    const modal = document.getElementById('contract-preview-modal');
    const templateContent = document.getElementById('contract-template-content');

    // Create iframe to show PDF
    const iframe = document.createElement('iframe');
    iframe.style.width = '100%';
    iframe.style.height = '1000px';
    iframe.style.border = 'none';
    iframe.style.borderRadius = '4px';
    iframe.src = `/api/contracts/${contractId}/pdf`;

    // Clear existing content and add iframe
    templateContent.innerHTML = '';
    templateContent.appendChild(iframe);

    modal.classList.remove('hidden');
}

// Show error message
function showError(message) {
    document.getElementById('campaign-title').textContent = 'Error';
    document.getElementById('campaign-subtitle').textContent = message;
    document.getElementById('loading').classList.add('hidden');
}

// Format date helper
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

// Format date to Indonesian format (dd MMMM yyyy)
function formatIndonesianDate(dateString) {
    const monthNames = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ];

    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = monthNames[date.getMonth()];
    const year = date.getFullYear();

    return `${day} ${month} ${year}`;
}

// Format currency with thousand separators
function formatCurrency(value) {
    return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

// Setup action buttons
function setupActionButtons() {
    // Publish Campaign button
    document.getElementById('publish-campaign-btn').addEventListener('click', () => {
        openPublishModal();
    });

    // Send Reminders button
    document.getElementById('send-reminders-btn').addEventListener('click', () => {
        openReminderModal();
    });

    // Publish modal handlers
    document.getElementById('close-publish-modal').addEventListener('click', () => {
        document.getElementById('publish-modal').classList.add('hidden');
    });
    document.getElementById('cancel-publish').addEventListener('click', () => {
        document.getElementById('publish-modal').classList.add('hidden');
    });
    document.getElementById('confirm-publish').addEventListener('click', () => {
        publishCampaign();
    });

    // Reminder modal handlers
    document.getElementById('close-reminder-modal').addEventListener('click', () => {
        document.getElementById('reminder-modal').classList.add('hidden');
    });
    document.getElementById('cancel-reminder').addEventListener('click', () => {
        document.getElementById('reminder-modal').classList.add('hidden');
    });
    document.getElementById('confirm-reminder').addEventListener('click', () => {
        sendReminders();
    });

    // Result modal handlers
    document.getElementById('close-result-modal').addEventListener('click', () => {
        document.getElementById('result-modal').classList.add('hidden');
    });
    document.getElementById('close-result-btn').addEventListener('click', () => {
        document.getElementById('result-modal').classList.add('hidden');
    });
}

// Open publish modal
function openPublishModal() {
    const totalContracts = contracts.length;
    document.getElementById('publish-count').textContent = totalContracts;
    document.getElementById('publish-modal').classList.remove('hidden');
}

// Publish campaign
async function publishCampaign() {
    const confirmBtn = document.getElementById('confirm-publish');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Sending...';

    try {
        const contractIds = contracts.map(c => c.contract_id);

        const response = await fetch('/api/bulk-send-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                contract_ids: contractIds,
                campaign_id: campaignId
            })
        });

        const result = await response.json();

        document.getElementById('publish-modal').classList.add('hidden');
        showResultModal(result);

        // Reload contracts
        await loadContracts();

    } catch (error) {
        console.error('Error publishing campaign:', error);
        alert('Failed to publish campaign. Please try again.');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Confirm & Send';
    }
}

// Open reminder modal
function openReminderModal() {
    const unsignedContracts = contracts.filter(c => !c.signed_status);
    document.getElementById('reminder-count').textContent = unsignedContracts.length;
    document.getElementById('reminder-modal').classList.remove('hidden');
}

// Send reminders
async function sendReminders() {
    const confirmBtn = document.getElementById('confirm-reminder');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Sending...';

    try {
        const unsignedContracts = contracts.filter(c => !c.signed_status);

        const response = await fetch(`/api/campaigns/${campaignId}/send-reminders`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        document.getElementById('reminder-modal').classList.add('hidden');

        if (result.success_count > 0) {
            alert(`Sent ${result.success_count} reminder(s) successfully!`);
        }

        if (result.failed_count > 0) {
            alert(`Failed to send ${result.failed_count} reminder(s)`);
        }

    } catch (error) {
        console.error('Error sending reminders:', error);
        alert('Failed to send reminders. Please try again.');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Confirm & Send';
    }
}

// Show result modal
function showResultModal(result) {
    const resultContent = document.getElementById('result-content');

    let html = `
        <div class="mb-4">
            <h4 class="font-semibold text-lg text-gray-900">Summary</h4>
            <p class="text-sm text-gray-600 mt-2">Successfully sent: <span class="font-medium text-green-600">${result.success?.length || 0}</span></p>
            <p class="text-sm text-gray-600">Failed: <span class="font-medium text-red-600">${result.failed?.length || 0}</span></p>
        </div>
    `;

    if (result.failed && result.failed.length > 0) {
        html += `
            <div class="mt-4">
                <h4 class="font-semibold text-base text-gray-900 mb-2">Failed Emails:</h4>
                <div class="space-y-2 max-h-60 overflow-y-auto">
                    ${result.failed.map(item => `
                        <div class="p-3 bg-red-50 border border-red-200 rounded-md">
                            <p class="text-sm font-medium text-red-900">Contract ID: ${item.contract_id}</p>
                            <p class="text-xs text-red-700">${item.error}</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    resultContent.innerHTML = html;
    document.getElementById('result-modal').classList.remove('hidden');
}