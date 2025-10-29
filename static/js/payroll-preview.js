// Payroll Preview JavaScript

let currentPayrollId = null;
let currentCampaignId = null;
let employeeList = [];
let currentIndex = -1;

// Get payroll ID from URL
function getPayrollIdFromURL() {
    const pathParts = window.location.pathname.split('/');
    const payrollId = pathParts[pathParts.length - 1];
    return parseInt(payrollId);
}

// Format currency
function formatCurrency(value) {
    if (value === null || value === undefined || value === 0) {
        return '-';
    }
    return 'Rp ' + new Intl.NumberFormat('id-ID').format(Math.round(value));
}

// Display value (handle null/empty)
function displayValue(value) {
    if (value === null || value === undefined || value === '') {
        return '-';
    }
    return value;
}

// Format date
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('id-ID', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Show/hide loading state
function showLoading() {
    document.getElementById('loading-state').classList.remove('hidden');
    document.getElementById('main-content').classList.add('hidden');
    document.getElementById('error-state').classList.add('hidden');
}

function hideLoading() {
    document.getElementById('loading-state').classList.add('hidden');
}

// Show error state
function showError(message) {
    hideLoading();
    document.getElementById('error-state').classList.remove('hidden');
    document.getElementById('error-message').textContent = message;
    document.getElementById('main-content').classList.add('hidden');
}

// Show main content
function showContent() {
    hideLoading();
    document.getElementById('error-state').classList.add('hidden');
    document.getElementById('main-content').classList.remove('hidden');
}

// Load payroll data
async function loadPayrollData(payrollId) {
    try {
        showLoading();
        currentPayrollId = payrollId;

        const response = await fetch(`/api/payroll/${payrollId}`);

        if (!response.ok) {
            if (response.status === 404) {
                showError('Payroll not found.');
            } else if (response.status === 401) {
                window.location.href = '/login';
            } else {
                showError('Failed to load payroll data.');
            }
            return;
        }

        const data = await response.json();
        currentCampaignId = data.payroll_campaign_id;

        // Populate employee information
        document.getElementById('employee-name').textContent = displayValue(data.employee_name);
        document.getElementById('employee-id').textContent = displayValue(data.employee_id);
        document.getElementById('nik').textContent = displayValue(data.nik);
        document.getElementById('job-title').textContent = displayValue(data.job_titles);
        document.getElementById('bank').textContent = displayValue(data.beneficiary_bank);
        document.getElementById('bank-account').textContent = displayValue(data.bank_account_no);

        // Populate campaign information
        document.getElementById('company').textContent = displayValue(data.company);
        document.getElementById('payment-date').textContent = formatDate(data.send_at);
        document.getElementById('salary-period').textContent = formatDate(data.salary_period);
        document.getElementById('thp').textContent = formatCurrency(data.thp);

        // Update page title
        document.title = `Payroll - ${data.employee_name || 'Employee'} - PKWT Dashboard`;

        // Load PDF
        loadPDF(payrollId);

        // Load employee list for navigation
        loadEmployeeList(currentCampaignId);

        showContent();
    } catch (error) {
        console.error('Error loading payroll data:', error);
        showError('An error occurred while loading payroll data.');
    }
}

// Load PDF
function loadPDF(payrollId) {
    const pdfContainer = document.getElementById('pdf-container');
    const pdfUrl = `/api/payroll/${payrollId}/pdf`;

    // Create object element for PDF
    const objectElement = document.createElement('object');
    objectElement.setAttribute('data', pdfUrl);
    objectElement.setAttribute('type', 'application/pdf');
    objectElement.style.width = '100%';
    objectElement.style.height = '100%';

    // Fallback content
    objectElement.innerHTML = `
        <div class="text-center py-8">
            <p class="text-gray-600 mb-4">Unable to display PDF.</p>
            <a href="${pdfUrl}" target="_blank" class="text-purple-600 hover:text-purple-700 font-semibold">
                Open PDF in new tab
            </a>
        </div>
    `;

    pdfContainer.innerHTML = '';
    pdfContainer.appendChild(objectElement);
}

// Download PDF
async function downloadPDF() {
    try {
        const btn = document.getElementById('download-btn');
        const originalHTML = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = `
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Downloading...
        `;

        const response = await fetch(`/api/payroll/${currentPayrollId}/pdf`);

        if (!response.ok) {
            throw new Error('Failed to download PDF');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // Get filename from Content-Disposition header or use default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'Payslip.pdf';
        if (contentDisposition) {
            const matches = /filename="?(.+)"?/i.exec(contentDisposition);
            if (matches && matches[1]) {
                filename = matches[1];
            }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        btn.disabled = false;
        btn.innerHTML = originalHTML;
    } catch (error) {
        console.error('Error downloading PDF:', error);
        alert('Failed to download PDF. Please try again.');

        const btn = document.getElementById('download-btn');
        btn.disabled = false;
        btn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            Download PDF
        `;
    }
}

// Load employee list for navigation
async function loadEmployeeList(campaignId) {
    try {
        const response = await fetch(`/api/payroll/campaign/${campaignId}/employees`);

        if (!response.ok) {
            console.error('Failed to load employee list');
            return;
        }

        const data = await response.json();
        employeeList = data.employees || [];

        // Find current index
        currentIndex = employeeList.findIndex(emp => emp.list_payroll_id === currentPayrollId);

        updateNavigationButtons();
    } catch (error) {
        console.error('Error loading employee list:', error);
    }
}

// Update navigation buttons
function updateNavigationButtons() {
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const navInfo = document.getElementById('nav-info');

    if (employeeList.length === 0) {
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        navInfo.textContent = '';
        return;
    }

    // Update buttons state
    prevBtn.disabled = currentIndex <= 0;
    nextBtn.disabled = currentIndex >= employeeList.length - 1;

    // Update info text
    navInfo.textContent = `Employee ${currentIndex + 1} of ${employeeList.length}`;
}

// Navigate to previous employee
function navigatePrevious() {
    if (currentIndex > 0) {
        const prevEmployee = employeeList[currentIndex - 1];
        window.location.href = `/payroll-preview/${prevEmployee.list_payroll_id}`;
    }
}

// Navigate to next employee
function navigateNext() {
    if (currentIndex < employeeList.length - 1) {
        const nextEmployee = employeeList[currentIndex + 1];
        window.location.href = `/payroll-preview/${nextEmployee.list_payroll_id}`;
    }
}

// Logout function
function logout() {
    fetch('/logout', { method: 'POST' })
        .then(() => {
            window.location.href = '/login';
        })
        .catch(() => {
            window.location.href = '/login';
        });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    const payrollId = getPayrollIdFromURL();

    if (!payrollId || isNaN(payrollId)) {
        showError('Invalid payroll ID.');
        return;
    }

    // Load payroll data
    loadPayrollData(payrollId);

    // Setup event listeners
    document.getElementById('download-btn').addEventListener('click', downloadPDF);
    document.getElementById('prev-btn').addEventListener('click', navigatePrevious);
    document.getElementById('next-btn').addEventListener('click', navigateNext);

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            navigatePrevious();
        } else if (e.key === 'ArrowRight') {
            navigateNext();
        }
    });
});
