// Get campaign ID from URL
const urlParams = new URLSearchParams(window.location.search);
const campaignId = urlParams.get('id');

let payrollData = [];
let campaignInfo = null;

// Load campaign and payroll data on page load
document.addEventListener('DOMContentLoaded', function() {
    if (!campaignId) {
        alert('No campaign ID provided');
        window.location.href = '/payroll-manager';
        return;
    }

    loadCampaignInfo();
    loadPayrollList();
    setupEventListeners();
});

// Load campaign information
async function loadCampaignInfo() {
    try {
        const response = await fetch(`/api/payroll-campaigns/${campaignId}`);

        if (!response.ok) {
            throw new Error('Failed to load campaign info');
        }

        campaignInfo = await response.json();

        // Update page title
        document.getElementById('payroll-title').textContent = `${campaignInfo.company}`;

        // Format dates
        const sendDate = new Date(campaignInfo.send_at);
        const formattedDate = sendDate.toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric'
        });

        document.getElementById('payroll-subtitle').textContent =
            `Payroll Period: ${formattedDate} | Status: ${campaignInfo.status || 'Active'}`;

    } catch (error) {
        console.error('Error loading campaign info:', error);
        document.getElementById('payroll-subtitle').textContent = 'Error loading campaign information';
    }
}

// Load payroll list
async function loadPayrollList() {
    try {
        const response = await fetch(`/api/payroll-campaigns/${campaignId}/payrolls`);

        if (!response.ok) {
            throw new Error('Failed to load payroll list');
        }

        payrollData = await response.json();

        // Hide loading state
        document.getElementById('loading').classList.add('hidden');

        // Populate table
        populateTable();

    } catch (error) {
        console.error('Error loading payroll list:', error);
        document.getElementById('loading').innerHTML =
            '<p class="text-red-600">Error loading payroll data. Please try again.</p>';
    }
}

// Populate table with payroll data
function populateTable() {
    const tableBody = document.getElementById('payroll-table-body');
    tableBody.innerHTML = '';

    payrollData.forEach(payroll => {
        const row = document.createElement('tr');
        row.classList.add('hover:bg-gray-50');

        // Format THP with thousand separator
        const thpFormatted = new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR',
            minimumFractionDigits: 0
        }).format(payroll.thp);

        // Status badge
        const statusBadge = payroll.send_status
            ? '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Sent</span>'
            : '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">Pending</span>';

        // Send date
        const sendDate = payroll.send_at
            ? new Date(payroll.send_at).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              })
            : '-';

        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <input type="checkbox" class="payroll-checkbox rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    data-payroll-id="${payroll.list_payroll_id}"
                    data-email="${payroll.email}"
                    data-name="${payroll.employee_name}"
                    data-sent="${payroll.send_status}">
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${payroll.employee_id || '-'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${payroll.employee_name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${payroll.nik || '-'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${payroll.email || '-'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${thpFormatted}</td>
            <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${sendDate}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <button onclick="viewPayslip(${payroll.list_payroll_id})"
                    class="text-purple-600 hover:text-purple-900 font-medium mr-3">
                    👁️ View
                </button>
            </td>
        `;

        tableBody.appendChild(row);
    });
}

// Setup event listeners
function setupEventListeners() {
    // Select all checkbox
    document.getElementById('select-all').addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('.payroll-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = this.checked;
        });
    });

    // Open send modal
    document.getElementById('open-send-modal').addEventListener('click', openSendModal);

    // Close send modal
    document.getElementById('close-send-modal').addEventListener('click', () => {
        document.getElementById('send-modal').classList.add('hidden');
    });

    // Send selected button
    document.getElementById('send-selected').addEventListener('click', () => {
        const selected = getSelectedPayrolls();
        if (selected.length === 0) {
            alert('Please select at least one employee');
            return;
        }
        showConfirmation(selected, 'selected');
    });

    // Send unsent button
    document.getElementById('send-unsent').addEventListener('click', () => {
        const unsent = payrollData.filter(p => !p.send_status);
        if (unsent.length === 0) {
            alert('All payroll emails have been sent');
            return;
        }
        showConfirmation(unsent.map(p => p.list_payroll_id), 'unsent');
    });

    // Close confirm modal
    document.getElementById('close-confirm-modal').addEventListener('click', closeConfirmModal);
    document.getElementById('cancel-send').addEventListener('click', closeConfirmModal);

    // Confirm send
    document.getElementById('confirm-send').addEventListener('click', executeSend);

    // Close result modal
    document.getElementById('close-result-modal').addEventListener('click', closeResultModal);
    document.getElementById('close-result-btn').addEventListener('click', closeResultModal);

    // Close payslip modal
    document.getElementById('close-payslip-modal').addEventListener('click', () => {
        document.getElementById('payslip-preview-modal').classList.add('hidden');
    });
}

// Open send modal
function openSendModal() {
    const modal = document.getElementById('send-modal');
    modal.classList.remove('hidden');
    updateSelectedRecipients();
}

// Get selected payrolls
function getSelectedPayrolls() {
    const checkboxes = document.querySelectorAll('.payroll-checkbox:checked');
    return Array.from(checkboxes).map(cb => parseInt(cb.dataset.payrollId));
}

// Update selected recipients display
function updateSelectedRecipients() {
    const checkboxes = document.querySelectorAll('.payroll-checkbox:checked');
    const recipientsDiv = document.getElementById('selected-recipients');

    if (checkboxes.length === 0) {
        recipientsDiv.innerHTML = '<p class="text-gray-500 text-sm">No recipients selected</p>';
    } else {
        const recipientsList = Array.from(checkboxes).map(cb => {
            const sent = cb.dataset.sent === 'true';
            const statusIcon = sent ? '✅' : '⏳';
            return `<div class="flex justify-between items-center py-2 border-b border-gray-200">
                <span class="text-sm">${cb.dataset.name} (${cb.dataset.email})</span>
                <span class="text-xs text-gray-500">${statusIcon} ${sent ? 'Sent' : 'Pending'}</span>
            </div>`;
        }).join('');

        recipientsDiv.innerHTML = recipientsList;
    }
}

// Show confirmation modal
let pendingSend = null;

function showConfirmation(payrollIds, mode) {
    const count = payrollIds.length;

    pendingSend = { payrollIds, mode };

    document.getElementById('confirm-message').textContent =
        `Are you sure you want to send ${count} payroll email${count > 1 ? 's' : ''}?`;

    document.getElementById('send-modal').classList.add('hidden');
    document.getElementById('confirm-modal').classList.remove('hidden');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.add('hidden');
    document.getElementById('send-modal').classList.remove('hidden');
    pendingSend = null;
}

// Execute send
async function executeSend() {
    if (!pendingSend) return;

    const { payrollIds } = pendingSend;

    // Close confirm modal
    document.getElementById('confirm-modal').classList.add('hidden');

    // Show loading state
    const confirmBtn = document.getElementById('confirm-send');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Sending...';

    try {
        const response = await fetch('/api/bulk-send-payroll-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                list_payroll_ids: payrollIds,
                test_mode: false,
                campaign_id: parseInt(campaignId)
            })
        });

        if (!response.ok) {
            throw new Error('Failed to send emails');
        }

        const result = await response.json();

        // Show results
        showResults(result);

        // Reload payroll list to update status
        await loadPayrollList();

    } catch (error) {
        console.error('Error sending emails:', error);
        alert('Failed to send emails. Please try again.');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Confirm & Send';
        pendingSend = null;
    }
}

// Show results modal
function showResults(result) {
    const resultContent = document.getElementById('result-content');

    const successCount = result.success_count || 0;
    const failedCount = result.failed_count || 0;

    resultContent.innerHTML = `
        <div class="bg-gray-50 rounded-lg p-4">
            <div class="grid grid-cols-2 gap-4">
                <div class="text-center">
                    <div class="text-3xl font-bold text-green-600">${successCount}</div>
                    <div class="text-sm text-gray-600 mt-1">Successful</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl font-bold text-red-600">${failedCount}</div>
                    <div class="text-sm text-gray-600 mt-1">Failed</div>
                </div>
            </div>
        </div>
    `;

    if (failedCount > 0 && result.failed) {
        const failedList = result.failed.map(f =>
            `<li class="text-sm text-red-600">Payroll ID ${f.list_payroll_id}: ${f.error}</li>`
        ).join('');

        resultContent.innerHTML += `
            <div class="mt-4">
                <h4 class="font-semibold text-gray-900 mb-2">Failed Emails:</h4>
                <ul class="list-disc list-inside bg-red-50 rounded-lg p-4">
                    ${failedList}
                </ul>
            </div>
        `;
    }

    document.getElementById('result-modal').classList.remove('hidden');
}

function closeResultModal() {
    document.getElementById('result-modal').classList.add('hidden');
}

// View payslip
function viewPayslip(listPayrollId) {
    const iframe = document.getElementById('payslip-iframe');
    iframe.src = `/api/payroll/${listPayrollId}/pdf`;
    document.getElementById('payslip-preview-modal').classList.remove('hidden');
}
