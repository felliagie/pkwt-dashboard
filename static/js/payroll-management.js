// Payroll Management JavaScript

let currentStep = 1;
let payrollCampaignId = null;
let uploadedData = [];

// Logout function
function logout() {
    fetch('/api/logout', {
        method: 'POST',
        credentials: 'include'
    }).then(() => {
        window.location.href = '/login';
    });
}

// Navigate between steps
function goToStep(step) {
    // Hide all steps
    document.querySelectorAll('.process-step').forEach(el => {
        el.classList.add('hidden');
    });

    // Show target step
    document.getElementById(`step-${step}`).classList.remove('hidden');

    // Update timeline
    document.querySelectorAll('.timeline-step').forEach((el, index) => {
        const stepNum = index + 1;

        if (stepNum < step) {
            // Completed steps
            el.classList.remove('active');
            el.classList.add('completed');
        } else if (stepNum === step) {
            // Current step
            el.classList.remove('completed');
            el.classList.add('active');
        } else {
            // Future steps
            el.classList.remove('active', 'completed');
        }
    });

    // Update connectors
    document.querySelectorAll('.timeline-connector').forEach((connector, index) => {
        if (index < step - 1) {
            connector.classList.add('completed');
        } else {
            connector.classList.remove('completed');
        }
    });

    currentStep = step;
}

// Step 1: Create Payroll Campaign
document.getElementById('payroll-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = document.getElementById('create-campaign-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Creating...';

    const formData = {
        company: document.getElementById('company').value,
        period: document.getElementById('period').value,
        send_at: document.getElementById('send_at').value
    };

    try {
        const response = await fetch('/api/payroll-campaigns', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            const result = await response.json();
            payrollCampaignId = result.payroll_campaign_id;
            goToStep(2);
        } else {
            const error = await response.json();
            alert('Error: ' + (error.detail || 'Failed to create payroll campaign'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating payroll campaign. Please try again.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
});

// Step 2: File Upload
const fileUploadContainer = document.getElementById('file-upload-container');
const fileInput = document.getElementById('payroll-file');
const fileNameDisplay = document.getElementById('file-name');

fileUploadContainer.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        fileNameDisplay.textContent = `Selected: ${file.name}`;
        fileNameDisplay.classList.remove('hidden');
    }
});

// Drag and drop
fileUploadContainer.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUploadContainer.classList.add('border-purple-400', 'bg-purple-50');
});

fileUploadContainer.addEventListener('dragleave', () => {
    fileUploadContainer.classList.remove('border-purple-400', 'bg-purple-50');
});

fileUploadContainer.addEventListener('drop', (e) => {
    e.preventDefault();
    fileUploadContainer.classList.remove('border-purple-400', 'bg-purple-50');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        fileNameDisplay.textContent = `Selected: ${files[0].name}`;
        fileNameDisplay.classList.remove('hidden');
    }
});

// Upload and preview
document.getElementById('upload-btn').addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) {
        alert('Please select a file first');
        return;
    }

    const btn = document.getElementById('upload-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Uploading...';

    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    progressContainer.classList.remove('hidden');
    progressBar.style.width = '0%';
    progressText.textContent = 'Uploading...';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('payroll_campaign_id', payrollCampaignId);

    try {
        progressBar.style.width = '30%';

        const response = await fetch('/api/payroll-campaigns/upload-payroll', {
            method: 'POST',
            body: formData
        });

        progressBar.style.width = '70%';

        if (response.ok) {
            const result = await response.json();
            uploadedData = result.data;

            progressBar.style.width = '100%';
            progressText.textContent = 'Upload complete!';

            setTimeout(() => {
                displayEmployeeData(uploadedData);
                goToStep(3);
                progressContainer.classList.add('hidden');
            }, 500);
        } else {
            const error = await response.json();
            alert('Error: ' + (error.detail || 'Failed to upload file'));
            progressContainer.classList.add('hidden');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error uploading file. Please try again.');
        progressContainer.classList.add('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
});

// Display employee data in table
function displayEmployeeData(data) {
    const tableBody = document.getElementById('employee-table-body');
    const employeeCount = document.getElementById('employee-count');

    employeeCount.textContent = data.length;
    tableBody.innerHTML = '';

    data.forEach((employee, index) => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50';
        row.innerHTML = `
            <td class="px-4 py-3 text-sm text-gray-900">${displayValue(employee.employee_id)}</td>
            <td class="px-4 py-3 text-sm text-gray-900">${displayValue(employee.employee_name)}</td>
            <td class="px-4 py-3 text-sm text-gray-600">${displayValue(employee.job_titles)}</td>
            <td class="px-4 py-3 text-sm text-right font-semibold text-gray-900">${formatCurrency(employee.thp)}</td>
            <td class="px-4 py-3 text-center">
                <button onclick="previewPayrollSlip(${index})" class="inline-flex items-center px-3 py-1 bg-purple-100 hover:bg-purple-200 text-purple-700 text-sm font-medium rounded-lg transition-colors">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                    </svg>
                    Preview
                </button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// Format number with thousand separators
function formatNumber(num) {
    // Round the number first
    const rounded = Math.round(num);
    return new Intl.NumberFormat('id-ID').format(rounded);
}

// Format currency - show "-" for 0 or null values
function formatCurrency(value) {
    if (value === null || value === undefined || value === 0 || value === '0') {
        return '-';
    }
    // Round the value first
    const rounded = Math.round(value);
    return 'Rp ' + new Intl.NumberFormat('id-ID').format(rounded);
}

// Convert null/undefined values to "-"
function displayValue(value) {
    if (value === null || value === undefined || value === '') {
        return '-';
    }
    return value;
}

// Preview payroll slip in modal
async function previewPayrollSlip(index) {
    const employee = uploadedData[index];
    const modal = document.getElementById('preview-modal');
    const modalContent = document.getElementById('modal-content');

    // Get payment date from campaign
    const sendDate = document.getElementById('send_at').value;
    const formattedDate = new Date(sendDate).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: '2-digit'
    });

    // Build payroll slip HTML
    const slipHTML = `
        <div id="payroll-slip-preview" class="bg-white p-6">
            <!-- Header Section -->
            <div class="border-b-2 border-gray-200 pb-3 mb-3">
                <div class="flex items-start justify-start">
                    <img src="/static/images/top-logo.png" alt="JMax Indonesia Logo" class="h-16 w-auto">
                </div>
            </div>

            <!-- Employee and Payment Information -->
            <div class="grid grid-cols-2 gap-8 mb-4">
                <!-- Left Column - Employee Info -->
                <div class="space-y-1">
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Name</span>
                        <span class="text-sm text-gray-600">: ${displayValue(employee.employee_name)}</span>
                    </div>
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">ID</span>
                        <span class="text-sm text-gray-600">: ${displayValue(employee.employee_id)}</span>
                    </div>
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Position</span>
                        <span class="text-sm text-gray-600">: ${displayValue(employee.job_titles)}</span>
                    </div>
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Client</span>
                        <span class="text-sm text-gray-600">: ${document.getElementById('company').value}</span>
                    </div>
                </div>

                <!-- Right Column - Payment Info -->
                <div class="space-y-1">
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Payment Date</span>
                        <span class="text-sm text-gray-600">: ${formattedDate}</span>
                    </div>
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Tax Code</span>
                        <span class="text-sm text-gray-600">: ${displayValue(employee.tax_code)}</span>
                    </div>
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Work Days</span>
                        <span class="text-sm text-gray-600">: ${displayValue(employee.working_days)}</span>
                    </div>
                    <div class="flex">
                        <span class="text-sm font-semibold text-gray-700 w-32">Bank Account</span>
                        <span class="text-sm text-gray-600">: ${displayValue(employee.beneficiary_bank)} (${displayValue(employee.bank_account_no)})</span>
                    </div>
                </div>
            </div>

            <!-- Earnings and Deductions Tables -->
            <div class="grid grid-cols-2 gap-6 mb-8">
                <!-- Earnings Table -->
                <div>
                    <h3 class="text-sm font-bold text-gray-900 mb-3 bg-gray-100 px-4 py-2 rounded-t-lg">EARNINGS</h3>
                    <div class="border border-gray-200 rounded-b-lg overflow-hidden">
                        <table class="w-full text-sm">
                            <tbody class="divide-y divide-gray-200">
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">Basic Salary</td>
                                    <td class="px-4 py-2 text-right ${employee.basic_pay ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.basic_pay)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">KSD</td>
                                    <td class="px-4 py-2 text-right ${employee.ksd ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.ksd)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">Incentive</td>
                                    <td class="px-4 py-2 text-right ${employee.incentive ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.incentive)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">TDK</td>
                                    <td class="px-4 py-2 text-right ${employee.tdk ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.tdk)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">Potongan Absensi</td>
                                    <td class="px-4 py-2 text-right ${employee.potongan ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.potongan)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">Tunjangan Pajak</td>
                                    <td class="px-4 py-2 text-right ${employee.tunjangan ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.tunjangan)}</td>
                                </tr>
                                <tr class="bg-gray-50">
                                    <td class="px-4 py-3 font-bold text-gray-900">TOTAL EARNINGS</td>
                                    <td class="px-4 py-3 text-right font-bold text-gray-900">${formatCurrency(employee.total_salary)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Deductions Table -->
                <div>
                    <h3 class="text-sm font-bold text-gray-900 mb-3 bg-gray-100 px-4 py-2 rounded-t-lg">DEDUCTIONS</h3>
                    <div class="border border-gray-200 rounded-b-lg overflow-hidden">
                        <table class="w-full text-sm">
                            <tbody class="divide-y divide-gray-200">
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">JHT 2%</td>
                                    <td class="px-4 py-2 text-right ${employee.jht_2_percent_deduction ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.jht_2_percent_deduction)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">JP 1%</td>
                                    <td class="px-4 py-2 text-right ${employee.jp_1_percent_deduction ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.jp_1_percent_deduction)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">BPJS Kesehatan 1%</td>
                                    <td class="px-4 py-2 text-right ${employee.bpjs_kesehatan_1_percent_deduction ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.bpjs_kesehatan_1_percent_deduction)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">PPH21</td>
                                    <td class="px-4 py-2 text-right ${employee.pph21 ? 'text-gray-900 font-medium' : 'text-gray-400'}">${formatCurrency(employee.pph21)}</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">&nbsp;</td>
                                    <td class="px-4 py-2 text-right text-gray-400">-</td>
                                </tr>
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-2 text-gray-700">&nbsp;</td>
                                    <td class="px-4 py-2 text-right text-gray-400">-</td>
                                </tr>
                                <tr class="bg-gray-50">
                                    <td class="px-4 py-3 font-bold text-gray-900">TOTAL DEDUCTIONS</td>
                                    <td class="px-4 py-3 text-right font-bold text-gray-900">${formatCurrency(employee.total_deduction)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Take Home Pay -->
            <div class="mb-6">
                <div class="bg-gray-50 border-2 border-gray-300 rounded-lg p-3">
                    <div class="flex items-center justify-between">
                        <span class="text-base font-bold text-gray-900">TAKE HOME PAY</span>
                        <span class="text-xl font-bold text-gray-900">${formatCurrency(employee.thp)}</span>
                    </div>
                </div>
            </div>

            <!-- Signature Section -->
            <div class="border-t-2 border-gray-200 pt-6 mb-6">
                <div class="flex justify-start">
                    <div class="relative">
                        <p class="text-sm text-gray-600 mb-4">Jakarta, ${formattedDate}</p>
                        <div class="relative w-48 h-24 mb-2">
                            <img src="/static/images/sign_logo.png" alt="JMax Logo" class="absolute top-0 left-0 h-16 w-auto opacity-50">
                            <img src="/static/images/sign.png" alt="Signature" class="absolute top-0 left-0 h-20 w-auto">
                        </div>
                        <p class="text-sm font-semibold text-gray-900">Fitria Nurhafsyah</p>
                        <p class="text-xs text-gray-600">HR Payroll & Operation</p>
                    </div>
                </div>
            </div>

            <!-- Footer Info -->
            <div class="text-center text-xs text-gray-500 border-t border-gray-200 pt-4">
                <p class="font-semibold">PT JMAX INDONESIA</p>
                <p class="leading-relaxed mt-1">
                    Kantorkuu Office Citywalk Sudirman, Jl. K.H. Mas Mansyur No.121 Level 5, RT.10/RW.11,<br>
                    Karet Tengsin, Kecamatan Tanah Abang, Jakarta Pusat, 10220
                </p>
                <p class="mt-1">e-mail: info@jmaxindo.com | URL: www.jmaxindonesia.com</p>
            </div>
        </div>
    `;

    modalContent.innerHTML = slipHTML;
    modal.classList.remove('hidden');
}

// Close modal
document.getElementById('close-modal').addEventListener('click', () => {
    document.getElementById('preview-modal').classList.add('hidden');
});

document.getElementById('preview-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        e.currentTarget.classList.add('hidden');
    }
});

// Step 3: Confirm and save to database
document.getElementById('confirm-btn').addEventListener('click', async () => {
    const btn = document.getElementById('confirm-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Saving & Generating PDFs...';

    try {
        const response = await fetch(`/api/payroll-campaigns/${payrollCampaignId}/finalize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data: uploadedData
            })
        });

        if (response.ok) {
            const result = await response.json();
            const pdfStatus = result.pdf_generated_count === result.inserted_count
                ? 'All PDFs generated successfully!'
                : `${result.pdf_generated_count}/${result.inserted_count} PDFs generated.`;

            alert(`Success!\n\n${result.message}\n\nPayroll records: ${result.inserted_count}\nPDFs generated: ${result.pdf_generated_count}`);
            window.location.href = '/';
        } else {
            const error = await response.json();
            alert('Error: ' + (error.detail || 'Failed to save data'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error saving data. Please try again.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('send_at').value = today;

    // Set default period to current month
    const currentMonth = new Date().toISOString().slice(0, 7);
    document.getElementById('period').value = currentMonth;
});
