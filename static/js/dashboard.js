// Dashboard JavaScript functionality
let currentContract = null;
let allContracts = [];
let filteredContracts = [];
let allCampaigns = [];
let selectedCampaign = null;
let selectedContracts = [];
let hourlyChart = null;
let bulkMode = 'all';

// Logout function
async function logout() {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = '/login';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/login';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadDashboardStats();
    loadContractsTable();
    loadHourlyAnalytics();
    setupModalHandlers();
    setupFilterHandlers();
});

// Load dashboard statistics
async function loadDashboardStats() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/dashboard-stats');
        const data = await response.json();

        document.getElementById('target-count').textContent = data.target;
        document.getElementById('sent-count').textContent = data.sent;
        document.getElementById('signed-count').textContent = data.signed;
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
        // Set default values on error
        document.getElementById('target-count').textContent = '0';
        document.getElementById('sent-count').textContent = '0';
        document.getElementById('signed-count').textContent = '0';
    }
}

// Load contracts table
async function loadContractsTable() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/contracts-with-status');
        const contracts = await response.json();

        allContracts = contracts;
        filteredContracts = contracts;

        renderTable(filteredContracts);
    } catch (error) {
        console.error('Error loading contracts table:', error);
        const tableBody = document.getElementById('contracts-table-body');
        tableBody.innerHTML = '<tr><td colspan="11" class="px-6 py-4 text-center text-sm text-red-500">Error loading data</td></tr>';
    }
}

// Render table
function renderTable(contracts) {
    const tableBody = document.getElementById('contracts-table-body');
    document.getElementById('contract-count').textContent = `${contracts.length} contracts`;

    if (contracts.length > 0) {
        tableBody.innerHTML = contracts.map((contract, index) => {
            const emailStatus = contract.send_status ?
                '<span class="badge-sent">Terkirim</span>' :
                '<span class="badge-unsent">Belum Terkirim</span>';

            const signStatus = contract.signed_status ?
                '<span class="badge-signed">Ditandatangani</span>' :
                '<span class="badge-unsigned">Belum Ditandatangani</span>';

            return `
                <tr class="table-row">
                    <td class="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">${index + 1}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-700">${contract.contract_num_detail || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900 font-medium">${contract.name || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">${contract.nik || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">${contract.nip || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-700">${contract.job_description || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">${contract.mobile_number || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">${contract.email || '-'}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">${emailStatus}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">${signStatus}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                        <button onclick="showEmailPreview(${contract.contract_id})" class="px-4 py-2 text-xs font-semibold rounded-lg text-white bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 transition-all shadow-sm hover:shadow-md">
                            📧 Send
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } else {
        tableBody.innerHTML = '<tr><td colspan="11" class="px-6 py-8 text-center text-sm text-gray-500">No contracts found</td></tr>';
    }
}

// Load hourly analytics
async function loadHourlyAnalytics() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/analytics/hourly');

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        const ctx = document.getElementById('hourlyChart');
        if (!ctx) {
            console.error('Hourly chart canvas not found');
            return;
        }

        if (hourlyChart) hourlyChart.destroy();

        hourlyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.hours ? data.hours.map(h => `${h}:00`) : [],
                datasets: [
                    {
                        label: 'Emails Sent',
                        data: data.emails_sent || [],
                        backgroundColor: 'rgba(102, 126, 234, 0.8)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 2,
                        borderRadius: 6
                    },
                    {
                        label: 'Contracts Signed',
                        data: data.contracts_signed || [],
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderColor: 'rgba(16, 185, 129, 1)',
                        borderWidth: 2,
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: {
                                size: 12,
                                weight: 'bold'
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        cornerRadius: 8
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading hourly analytics:', error);
    }
}

// Setup modal handlers
function setupModalHandlers() {
    const modal = document.getElementById('email-modal');
    const closeBtn = document.getElementById('close-modal');
    const cancelBtn = document.getElementById('cancel-send');
    const sendBtn = document.getElementById('send-email-btn');

    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    sendBtn.addEventListener('click', sendEmail);

    // Campaign selector modal handlers
    const campaignSelectorBtn = document.getElementById('open-campaign-selector');
    const campaignSelectorModal = document.getElementById('campaign-selector-modal');
    const closeCampaignSelector = document.getElementById('close-campaign-selector');

    campaignSelectorBtn.addEventListener('click', openCampaignSelector);
    closeCampaignSelector.addEventListener('click', () => {
        campaignSelectorModal.classList.add('hidden');
    });

    // Bulk modal handlers
    const bulkModal = document.getElementById('bulk-modal');
    const closeBulkBtn = document.getElementById('close-bulk-modal');
    const cancelBulkBtn = document.getElementById('cancel-bulk');
    const confirmBulkBtn = document.getElementById('confirm-bulk');

    closeBulkBtn.addEventListener('click', closeBulkModal);
    cancelBulkBtn.addEventListener('click', closeBulkModal);
    confirmBulkBtn.addEventListener('click', confirmBulkSend);

    // Result modal handlers
    const resultModal = document.getElementById('result-modal');
    const closeResultBtn = document.getElementById('close-result-modal');
    const closeResultBtn2 = document.getElementById('close-result-btn');

    closeResultBtn.addEventListener('click', closeResultModal);
    closeResultBtn2.addEventListener('click', closeResultModal);

    // Campaign action buttons
    document.getElementById('send-all-selected').addEventListener('click', () => {
        openBulkConfirmation('all');
    });

    document.getElementById('send-unsent-only').addEventListener('click', () => {
        openBulkConfirmation('unsent');
    });
}

// Setup filter handlers
function setupFilterHandlers() {
    const searchInput = document.getElementById('search-input');
    const emailFilter = document.getElementById('email-status-filter');
    const signFilter = document.getElementById('sign-status-filter');
    const resetBtn = document.getElementById('reset-filters');

    searchInput.addEventListener('input', applyFilters);
    emailFilter.addEventListener('change', applyFilters);
    signFilter.addEventListener('change', applyFilters);
    resetBtn.addEventListener('click', () => {
        searchInput.value = '';
        emailFilter.value = 'all';
        signFilter.value = 'all';
        applyFilters();
    });
}

// Apply filters
function applyFilters() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const emailStatus = document.getElementById('email-status-filter').value;
    const signStatus = document.getElementById('sign-status-filter').value;

    filteredContracts = allContracts.filter(contract => {
        const matchesSearch = !searchTerm ||
            (contract.name && contract.name.toLowerCase().includes(searchTerm)) ||
            (contract.nik && contract.nik.toLowerCase().includes(searchTerm)) ||
            (contract.nip && contract.nip.toLowerCase().includes(searchTerm));

        const matchesEmail = emailStatus === 'all' ||
            (emailStatus === 'sent' && contract.send_status) ||
            (emailStatus === 'unsent' && !contract.send_status);

        const matchesSign = signStatus === 'all' ||
            (signStatus === 'signed' && contract.signed_status) ||
            (signStatus === 'unsigned' && !contract.signed_status);

        return matchesSearch && matchesEmail && matchesSign;
    });

    renderTable(filteredContracts);
}

// Show email preview modal
async function showEmailPreview(contractId) {
    const contract = allContracts.find(c => c.contract_id === contractId);
    currentContract = contract;

    // Fetch email preview from backend
    const formData = new FormData();
    formData.append('contract_id', contractId);

    const response = await fetch('http://127.0.0.1:8000/api/email-preview', {
        method: 'POST',
        body: formData
    });

    const data = await response.json();

    document.getElementById('email-to').textContent = data.recipient;
    document.getElementById('email-body').textContent = data.email_body;

    document.getElementById('email-modal').classList.remove('hidden');
}

// Close modal
function closeModal() {
    document.getElementById('email-modal').classList.add('hidden');
    currentContract = null;
}

// Send email
async function sendEmail() {
    if (!currentContract) {
        showToast('No contract selected', 'error');
        return;
    }

    const sendBtn = document.getElementById('send-email-btn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';

    try {
        const formData = new FormData();
        formData.append('contract_id', currentContract.contract_id);

        const response = await fetch('http://127.0.0.1:8000/api/send-email', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to send email');
        }

        showToast('Email sent successfully!', 'success');
        closeModal();
        loadContractsTable();
        loadDashboardStats();
        loadHourlyAnalytics();

    } catch (error) {
        console.error('Error sending email:', error);
        showToast('Failed to send email. Please try again.', 'error');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send Email';
    }
}

// Open campaign selector
async function openCampaignSelector() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/campaigns-list');
        allCampaigns = await response.json();

        renderCampaignList(allCampaigns);
        document.getElementById('campaign-selector-modal').classList.remove('hidden');

        // Setup search
        document.getElementById('campaign-search').addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const filtered = allCampaigns.filter(c =>
                c.company.toLowerCase().includes(searchTerm)
            );
            renderCampaignList(filtered);
        });
    } catch (error) {
        console.error('Error loading campaigns:', error);
        showToast('Failed to load campaigns', 'error');
    }
}

// Render campaign list
function renderCampaignList(campaigns) {
    const list = document.getElementById('campaign-list');
    list.innerHTML = campaigns.map(campaign => `
        <div class="p-4 border-2 border-gray-200 rounded-xl hover:border-purple-400 cursor-pointer transition-all campaign-item" data-campaign-id="${campaign.campaign_id}">
            <div class="flex justify-between items-start">
                <div>
                    <h5 class="font-bold text-gray-900">${campaign.company}</h5>
                    <p class="text-sm text-gray-600">Total: ${campaign.total_contracts} | Sent: ${campaign.sent_count}</p>
                </div>
                <span class="text-xs px-3 py-1 rounded-full bg-purple-100 text-purple-700 font-semibold">${campaign.campaign_id}</span>
            </div>
        </div>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.campaign-item').forEach(item => {
        item.addEventListener('click', async function() {
            const campaignId = parseInt(this.dataset.campaignId);
            await selectCampaign(campaignId);
        });
    });
}

// Select campaign and load contracts
async function selectCampaign(campaignId) {
    selectedCampaign = allCampaigns.find(c => c.campaign_id === campaignId);

    try {
        const response = await fetch(`http://127.0.0.1:8000/api/campaigns/${campaignId}/contracts-with-status`);
        const contracts = await response.json();

        document.getElementById('selected-campaign-name').textContent = selectedCampaign.company;
        renderContractChecklist(contracts);
        document.getElementById('selected-campaign-details').classList.remove('hidden');
        document.getElementById('action-buttons').classList.remove('hidden');
    } catch (error) {
        console.error('Error loading campaign contracts:', error);
        showToast('Failed to load campaign contracts', 'error');
    }
}

// Render contract checklist
function renderContractChecklist(contracts) {
    const checklist = document.getElementById('contract-checklist');
    checklist.innerHTML = `
        <div class="mb-3 p-3 bg-white rounded-lg border-2 border-purple-200">
            <label class="flex items-center cursor-pointer">
                <input type="checkbox" id="select-all-contracts" class="w-5 h-5 text-purple-600 rounded border-gray-300 focus:ring-purple-500">
                <span class="ml-3 font-bold text-gray-900">Select All (${contracts.length} contracts)</span>
            </label>
        </div>
        ${contracts.map(contract => `
            <div class="p-2 hover:bg-gray-50 rounded-lg transition-colors">
                <label class="flex items-center cursor-pointer">
                    <input type="checkbox" class="contract-checkbox w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500" data-contract-id="${contract.contract_id}" data-send-status="${contract.send_status}">
                    <span class="ml-3 text-sm text-gray-700">${contract.name} - ${contract.contract_num_detail} ${contract.send_status ? '<span class="badge-sent ml-2">Sent</span>' : '<span class="badge-unsent ml-2">Unsent</span>'}</span>
                </label>
            </div>
        `).join('')}
    `;

    // Select all handler
    document.getElementById('select-all-contracts').addEventListener('change', function() {
        document.querySelectorAll('.contract-checkbox').forEach(cb => {
            cb.checked = this.checked;
        });
    });
}

// Open bulk confirmation
function openBulkConfirmation(mode) {
    bulkMode = mode;
    const checkboxes = document.querySelectorAll('.contract-checkbox:checked');

    let contractIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.contractId));

    if (mode === 'unsent') {
        contractIds = contractIds.filter((id, index) => {
            const checkbox = checkboxes[index];
            return checkbox.dataset.sendStatus === 'false';
        });
    }

    if (contractIds.length === 0) {
        showToast('No contracts selected', 'error');
        return;
    }

    selectedContracts = contractIds;

    const message = mode === 'all' ?
        'Send emails to all selected contracts?' :
        'Send emails to unsent selected contracts only?';

    document.getElementById('bulk-message').textContent = message;
    document.getElementById('bulk-campaign-name').textContent = selectedCampaign.company;
    document.getElementById('bulk-count').textContent = selectedContracts.length;
    document.getElementById('bulk-modal').classList.remove('hidden');
}

// Close bulk modal
function closeBulkModal() {
    document.getElementById('bulk-modal').classList.add('hidden');
}

// Confirm bulk send
async function confirmBulkSend() {
    const confirmBtn = document.getElementById('confirm-bulk');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Sending...';

    try {
        const response = await fetch('http://127.0.0.1:8000/api/bulk-send-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                contract_ids: selectedContracts,
                mode: bulkMode,
                campaign_id: selectedCampaign.campaign_id
            })
        });

        const result = await response.json();

        closeBulkModal();
        document.getElementById('campaign-selector-modal').classList.add('hidden');
        showResultModal(result);

        // Reload data
        loadContractsTable();
        loadDashboardStats();
        loadHourlyAnalytics();

    } catch (error) {
        console.error('Error sending bulk emails:', error);
        showToast('Failed to send bulk emails. Please try again.', 'error');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Confirm & Send';
    }
}

// Show result modal
function showResultModal(result) {
    const resultContent = document.getElementById('result-content');

    const successCount = result.success.length;
    const failureCount = result.failed.length;

    let html = `
        <div class="mb-4">
            <p class="text-lg font-semibold text-gray-900">Summary</p>
            <p class="text-sm text-green-600">✓ Successfully sent: ${successCount}</p>
            <p class="text-sm text-red-600">✗ Failed: ${failureCount}</p>
        </div>
    `;

    if (failureCount > 0) {
        html += `
            <div>
                <p class="text-md font-semibold text-red-600 mb-2">Failed Emails:</p>
                <div class="bg-red-50 p-4 rounded-lg max-h-64 overflow-y-auto">
                    <ul class="space-y-2">
        `;

        result.failed.forEach(item => {
            html += `
                <li class="text-sm">
                    <span class="font-medium">${item.contract_id}</span>: ${item.error}
                </li>
            `;
        });

        html += `
                    </ul>
                </div>
            </div>
        `;
    }

    resultContent.innerHTML = html;
    document.getElementById('result-modal').classList.remove('hidden');
}

// Close result modal
function closeResultModal() {
    document.getElementById('result-modal').classList.add('hidden');
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';

    const bgColors = {
        success: 'bg-gradient-to-r from-green-500 to-emerald-500',
        error: 'bg-gradient-to-r from-red-500 to-pink-500',
        info: 'bg-gradient-to-r from-blue-500 to-indigo-500'
    };

    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ'
    };

    toast.innerHTML = `
        <div class="${bgColors[type]} text-white px-6 py-4 rounded-xl shadow-2xl flex items-center space-x-3">
            <span class="text-2xl">${icons[type]}</span>
            <span class="font-medium">${message}</span>
        </div>
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}