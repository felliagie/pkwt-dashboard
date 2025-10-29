// Payroll Manager JavaScript
// State Management
let allPayrolls = [];
let filteredPayrolls = [];
let currentPage = 1;
const itemsPerPage = 9;
let progressPollingInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializePayrollManager();
});

function initializePayrollManager() {
    // Setup event listeners
    setupEventListeners();

    // Load initial data
    loadPayrolls();

    // Start progress polling
    startProgressPolling();
}

// Event Listeners Setup
function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById('search-company');
    searchInput.addEventListener('input', handleFilterChange);

    // Status filter
    const statusFilter = document.getElementById('filter-status');
    statusFilter.addEventListener('change', handleFilterChange);

    // Clear filters button
    const clearButton = document.getElementById('clear-filters');
    clearButton.addEventListener('click', clearFilters);

    // Modal close
    const closeModal = document.getElementById('close-payroll-details');
    if (closeModal) {
        closeModal.addEventListener('click', () => {
            document.getElementById('payroll-details-modal').classList.add('hidden');
        });
    }
}

// Load payroll data from API
async function loadPayrolls(silent = false) {
    try {
        if (!silent) {
            showLoading();
        }

        const response = await fetch('/api/payroll-campaigns-with-stats');

        if (!response.ok) {
            throw new Error('Failed to fetch payroll campaigns');
        }

        allPayrolls = await response.json();

        // Apply current filters
        applyFilters();

        // Display results
        displayPayrolls();
        setupPagination();
        updateResultsSummary();

        hideLoading();

    } catch (error) {
        console.error('Error loading payroll campaigns:', error);
        showError('Error loading payroll campaigns. Please try again.');
    }
}

// Apply filters to payrolls
function applyFilters() {
    const searchTerm = document.getElementById('search-company').value.toLowerCase();
    const statusFilter = document.getElementById('filter-status').value;

    filteredPayrolls = allPayrolls.filter(payroll => {
        // Search filter
        const matchesSearch = !searchTerm ||
            (payroll.company && payroll.company.toLowerCase().includes(searchTerm));

        // Status filter
        let matchesStatus = true;
        if (statusFilter !== 'all') {
            if (statusFilter === 'active') {
                matchesStatus = payroll.status === 'active' && payroll.pdf_status !== 'failed';
            } else if (statusFilter === 'inactive') {
                matchesStatus = payroll.status !== 'active' || payroll.pdf_status === 'failed';
            } else if (statusFilter === 'processing') {
                matchesStatus = payroll.pdf_status === 'processing';
            } else if (statusFilter === 'completed') {
                matchesStatus = payroll.pdf_status === 'completed' && payroll.pdf_total === payroll.pdf_generated;
            }
        }

        return matchesSearch && matchesStatus;
    });

    // Reset to first page when filters change
    currentPage = 1;
}

// Handle filter changes
function handleFilterChange() {
    applyFilters();
    displayPayrolls();
    setupPagination();
    updateResultsSummary();
}

// Clear all filters
function clearFilters() {
    document.getElementById('search-company').value = '';
    document.getElementById('filter-status').value = 'all';
    handleFilterChange();
}

// Display payrolls as cards
function displayPayrolls() {
    const container = document.getElementById('payrolls-container');
    const emptyState = document.getElementById('empty-state');

    if (filteredPayrolls.length === 0) {
        container.innerHTML = '';
        if (allPayrolls.length === 0) {
            emptyState.classList.remove('hidden');
        } else {
            // Show "no results" message for filtered state
            container.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                    <h3 class="mt-2 text-sm font-medium text-gray-900">No results found</h3>
                    <p class="mt-1 text-sm text-gray-500">Try adjusting your filters to find what you're looking for.</p>
                </div>
            `;
        }
        return;
    }

    emptyState.classList.add('hidden');

    // Calculate pagination
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pagePayrolls = filteredPayrolls.slice(startIndex, endIndex);

    // Render cards
    container.innerHTML = pagePayrolls.map(payroll => createPayrollCard(payroll)).join('');

    // Add click handlers
    document.querySelectorAll('.payroll-card').forEach(card => {
        card.addEventListener('click', function() {
            const payrollId = this.dataset.payrollId;
            viewPayrollDetails(payrollId);
        });
    });
}

// Create individual payroll card HTML
function createPayrollCard(payroll) {
    const statusInfo = getStatusInfo(payroll);
    const pdfProgress = payroll.pdf_total > 0 ? (payroll.pdf_generated / payroll.pdf_total * 100) : 0;
    const sendProgress = payroll.total_employees > 0 ? (payroll.sent_count / payroll.total_employees * 100) : 0;

    return `
        <div class="payroll-card" data-payroll-id="${payroll.payroll_campaign_id}">
            <div class="card-header">
                <div>
                    <h3 class="card-title">${escapeHtml(payroll.company || 'Untitled Payroll')}</h3>
                    <p class="card-subtitle">ID: ${payroll.payroll_campaign_id}</p>
                </div>
                <span class="status-badge ${statusInfo.class}">${statusInfo.text}</span>
            </div>

            <div class="card-body">
                <!-- Date Information -->
                <div class="card-info-grid">
                    <div class="card-info-item">
                        <svg class="card-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                        </svg>
                        <div>
                            <div class="card-info-label">Created</div>
                            <div class="card-info-value">${formatDate(payroll.created_at)}</div>
                        </div>
                    </div>

                    ${payroll.send_at ? `
                    <div class="card-info-item">
                        <svg class="card-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <div>
                            <div class="card-info-label">Send Date</div>
                            <div class="card-info-value">${formatDate(payroll.send_at)}</div>
                        </div>
                    </div>
                    ` : ''}
                </div>

                <!-- Statistics -->
                <div class="card-stats">
                    <div class="card-stat">
                        <div class="card-stat-value">${payroll.total_employees || 0}</div>
                        <div class="card-stat-label">Employees</div>
                    </div>
                    <div class="card-stat">
                        <div class="card-stat-value">${payroll.sent_count || 0}</div>
                        <div class="card-stat-label">Sent</div>
                    </div>
                    <div class="card-stat">
                        <div class="card-stat-value">${payroll.pdf_generated || 0}/${payroll.pdf_total || 0}</div>
                        <div class="card-stat-label">PDFs</div>
                    </div>
                </div>

                <!-- Progress Bars -->
                ${payroll.pdf_total > 0 ? `
                <div class="progress-section">
                    <div class="progress-label">
                        <span>PDF Generation</span>
                        <span class="progress-percentage">${Math.round(pdfProgress)}%</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar ${payroll.pdf_status === 'processing' ? 'progress-bar-animated' : ''}"
                             style="width: ${pdfProgress}%"></div>
                    </div>
                </div>
                ` : ''}

                ${payroll.total_employees > 0 ? `
                <div class="progress-section">
                    <div class="progress-label">
                        <span>Send Status</span>
                        <span class="progress-percentage">${Math.round(sendProgress)}%</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar progress-bar-blue" style="width: ${sendProgress}%"></div>
                    </div>
                </div>
                ` : ''}
            </div>

            <div class="card-footer">
                <span class="card-link">View Details →</span>
            </div>
        </div>
    `;
}

// Get status information
function getStatusInfo(payroll) {
    // Determine status based on various fields
    if (payroll.pdf_status === 'failed') {
        return { text: 'Failed', class: 'status-failed' };
    }

    if (payroll.pdf_status === 'processing') {
        return { text: 'Processing', class: 'status-processing' };
    }

    if (payroll.pdf_status === 'completed' && payroll.pdf_total === payroll.pdf_generated) {
        if (payroll.sent_count === payroll.total_employees) {
            return { text: 'Completed', class: 'status-completed' };
        }
        return { text: 'Ready', class: 'status-ready' };
    }

    if (payroll.status === 'active') {
        return { text: 'Active', class: 'status-active' };
    }

    return { text: 'Inactive', class: 'status-inactive' };
}

// Pagination setup
function setupPagination() {
    const paginationContainer = document.getElementById('pagination-container');
    const totalPages = Math.ceil(filteredPayrolls.length / itemsPerPage);

    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }

    let paginationHTML = '<div class="pagination">';

    // Previous button
    paginationHTML += `
        <button
            class="page-btn ${currentPage === 1 ? 'disabled' : ''}"
            onclick="changePage(${currentPage - 1})"
            ${currentPage === 1 ? 'disabled' : ''}
        >
            Previous
        </button>
    `;

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        if (
            i === 1 ||
            i === totalPages ||
            (i >= currentPage - 1 && i <= currentPage + 1)
        ) {
            paginationHTML += `
                <button
                    class="page-btn ${i === currentPage ? 'active' : ''}"
                    onclick="changePage(${i})"
                >
                    ${i}
                </button>
            `;
        } else if (i === currentPage - 2 || i === currentPage + 2) {
            paginationHTML += '<span class="page-ellipsis">...</span>';
        }
    }

    // Next button
    paginationHTML += `
        <button
            class="page-btn ${currentPage === totalPages ? 'disabled' : ''}"
            onclick="changePage(${currentPage + 1})"
            ${currentPage === totalPages ? 'disabled' : ''}
        >
            Next
        </button>
    `;

    paginationHTML += '</div>';
    paginationContainer.innerHTML = paginationHTML;
}

// Change page
function changePage(page) {
    const totalPages = Math.ceil(filteredPayrolls.length / itemsPerPage);
    if (page < 1 || page > totalPages) return;

    currentPage = page;
    displayPayrolls();
    setupPagination();

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Update results summary
function updateResultsSummary() {
    const showingCount = Math.min(filteredPayrolls.length, itemsPerPage * currentPage);
    document.getElementById('showing-count').textContent = showingCount;
    document.getElementById('total-count').textContent = allPayrolls.length;
}

// Start progress polling for PDF generation
function startProgressPolling() {
    if (progressPollingInterval) {
        clearInterval(progressPollingInterval);
    }

    progressPollingInterval = setInterval(async () => {
        // Check if any payroll is processing
        const hasProcessing = allPayrolls.some(p => p.pdf_status === 'processing');

        if (hasProcessing) {
            await loadPayrolls(true); // Silent reload
        }
    }, 2000); // Poll every 2 seconds
}

// View payroll details
function viewPayrollDetails(payrollId) {
    window.location.href = `/payroll-detail?id=${payrollId}`;
}

// Utility Functions
function formatDate(dateString) {
    if (!dateString) return 'N/A';

    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('payrolls-container').innerHTML = '';
    document.getElementById('empty-state').classList.add('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    hideLoading();
    const container = document.getElementById('payrolls-container');
    container.innerHTML = `
        <div class="col-span-full text-center py-12">
            <svg class="mx-auto h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <h3 class="mt-2 text-sm font-medium text-gray-900">Error</h3>
            <p class="mt-1 text-sm text-gray-500">${message}</p>
            <button onclick="loadPayrolls()" class="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                Retry
            </button>
        </div>
    `;
}

// Logout function
function logout() {
    document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    window.location.href = '/login';
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (progressPollingInterval) {
        clearInterval(progressPollingInterval);
    }
});
