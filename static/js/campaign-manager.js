// Campaign Manager JavaScript functionality
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
    initializeCampaignManager();
});

let currentPage = 1;
const itemsPerPage = 6; // Limit to 6 cards per page (2 rows of 3)
let totalCampaigns = 0;
let campaigns = [];
let filteredCampaigns = [];
let progressPollingInterval = null;

// Filter state
let filters = {
    search: '',
    status: 'all',
    company: ''
};

function initializeCampaignManager() {
    loadCampaigns();
    setupModal();
    setupFilters();
    startProgressPolling();
}

// Setup filter event listeners
function setupFilters() {
    const searchInput = document.getElementById('search-campaign');
    const statusFilter = document.getElementById('status-filter');
    const companyFilter = document.getElementById('company-filter');
    const companySuggestions = document.getElementById('company-suggestions');
    const resetButton = document.getElementById('reset-filters');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            filters.search = e.target.value.toLowerCase();
            applyFilters();
        });
    }

    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            filters.status = e.target.value;
            applyFilters();
        });
    }

    if (companyFilter) {
        // Show suggestions on focus
        companyFilter.addEventListener('focus', () => {
            showCompanySuggestions('');
        });

        // Update suggestions on input
        companyFilter.addEventListener('input', (e) => {
            const value = e.target.value;
            filters.company = value.toLowerCase();
            showCompanySuggestions(value);
            applyFilters();
        });

        // Hide suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!companyFilter.contains(e.target) && !companySuggestions.contains(e.target)) {
                companySuggestions.classList.remove('active');
            }
        });
    }

    if (resetButton) {
        resetButton.addEventListener('click', () => {
            filters = { search: '', status: 'all', company: '' };
            searchInput.value = '';
            statusFilter.value = 'all';
            companyFilter.value = '';
            companySuggestions.classList.remove('active');
            applyFilters();
        });
    }
}

// Show company suggestions dropdown
function showCompanySuggestions(searchValue) {
    const companySuggestions = document.getElementById('company-suggestions');
    const companyFilter = document.getElementById('company-filter');

    // Get unique company names from campaigns
    const uniqueCompanies = [...new Set(campaigns
        .map(c => c.company_name)
        .filter(name => name && name.toLowerCase().includes(searchValue.toLowerCase()))
    )].sort();

    if (uniqueCompanies.length === 0) {
        companySuggestions.innerHTML = '<div class="company-suggestion-empty">No companies found</div>';
        companySuggestions.classList.add('active');
        return;
    }

    // Build suggestions HTML
    const suggestionsHTML = uniqueCompanies.map(company =>
        `<div class="company-suggestion-item" data-company="${company}">${company}</div>`
    ).join('');

    companySuggestions.innerHTML = suggestionsHTML;
    companySuggestions.classList.add('active');

    // Add click handlers to suggestions
    companySuggestions.querySelectorAll('.company-suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            const selectedCompany = item.dataset.company;
            companyFilter.value = selectedCompany;
            filters.company = selectedCompany.toLowerCase();
            companySuggestions.classList.remove('active');
            applyFilters();
        });
    });
}

// Apply filters to campaigns
function applyFilters() {
    filteredCampaigns = campaigns.filter(campaign => {
        // Search filter - searches in company_name, company_detail, and campaign_id
        const searchMatch = filters.search === '' ||
            (campaign.company_name && campaign.company_name.toLowerCase().includes(filters.search)) ||
            (campaign.company_detail && campaign.company_detail.toLowerCase().includes(filters.search)) ||
            campaign.campaign_id.toString().includes(filters.search);

        // Status filter
        const statusMatch = filters.status === 'all' || getCampaignStatus(campaign) === filters.status;

        // Company filter - searches in company_name
        const companyMatch = filters.company === '' ||
            (campaign.company_name && campaign.company_name.toLowerCase().includes(filters.company));

        return searchMatch && statusMatch && companyMatch;
    });

    totalCampaigns = filteredCampaigns.length;
    currentPage = 1;
    displayCampaigns();
    setupPagination();
}

// Get campaign status
function getCampaignStatus(campaign) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const sendDate = new Date(campaign.send_date);
    sendDate.setHours(0, 0, 0, 0);

    const dueDate = new Date(campaign.due_date);
    dueDate.setHours(0, 0, 0, 0);

    if (today < sendDate) {
        return 'upcoming';
    } else if (today >= sendDate && today <= dueDate) {
        return 'active';
    } else if (today > dueDate) {
        return 'inactive'; // Changed from 'overdue' to 'inactive'
    } else {
        return 'completed';
    }
}

// Poll for PDF generation progress
function startProgressPolling() {
    if (progressPollingInterval) {
        clearInterval(progressPollingInterval);
    }

    progressPollingInterval = setInterval(async () => {
        const hasProcessing = campaigns.some(c => c.pdf_status === 'processing');
        if (hasProcessing) {
            await loadCampaigns(true); // Reload silently
        }
    }, 2000); // Poll every 2 seconds
}

// Load campaigns with pagination
async function loadCampaigns(silent = false) {
    const loadingElement = document.getElementById('loading');
    const campaignsContainer = document.getElementById('campaigns-container');

    try {
        if (!silent) {
            loadingElement.classList.remove('hidden');
            campaignsContainer.innerHTML = '';
        }

        const response = await fetch('/api/campaigns-with-stats');
        campaigns = await response.json();
        filteredCampaigns = campaigns; // Initialize filtered campaigns
        totalCampaigns = filteredCampaigns.length;

        if (!silent) {
            loadingElement.classList.add('hidden');
        }

        if (campaigns.length === 0) {
            showEmptyState();
            return;
        }

        displayCampaigns();
        if (!silent) {
            setupPagination();
        }

    } catch (error) {
        console.error('Error loading campaigns:', error);
        if (!silent) {
            loadingElement.classList.add('hidden');
            showErrorState();
        }
    }
}

// Display campaigns for current page
function displayCampaigns() {
    const campaignsContainer = document.getElementById('campaigns-container');
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageData = filteredCampaigns.slice(startIndex, endIndex);

    if (pageData.length === 0) {
        campaignsContainer.innerHTML = '<div class="col-span-3 text-center py-12 text-gray-500 font-light">No campaigns match your filters.</div>';
        return;
    }

    campaignsContainer.innerHTML = pageData.map(campaign => createCampaignCard(campaign)).join('');

    // Add click handlers to campaign cards
    document.querySelectorAll('.campaign-card').forEach(card => {
        card.addEventListener('click', function() {
            const campaignId = this.dataset.campaignId;
            window.location.href = `/campaign-detail?id=${campaignId}`;
        });
    });
}

// Create campaign card HTML
function createCampaignCard(campaign) {
    const sentPercentage = campaign.total_contracts > 0 ?
        Math.round((campaign.sent_count / campaign.total_contracts) * 100) : 0;

    const signedPercentage = campaign.total_contracts > 0 ?
        Math.round((campaign.signed_count / campaign.total_contracts) * 100) : 0;

    const statusClass = getStatusClass(campaign);

    return `
        <div class="campaign-card" data-campaign-id="${campaign.campaign_id}">
            <div class="campaign-header">
                <div>
                    <div class="campaign-title">${campaign.company_name || 'PT Mandom Indonesia'}</div>
                    ${campaign.company_detail ? `<div class="campaign-subtitle">${campaign.company_detail}</div>` : ''}
                    <div class="campaign-id">ID: ${campaign.campaign_id}</div>
                </div>
                <div class="status-badge ${statusClass}">
                    ${getStatusText(campaign)}
                </div>
            </div>

            <div class="campaign-dates">
                <div class="date-item">
                    <div class="date-label">Created</div>
                    <div class="date-value">${formatDate(campaign.created_at)}</div>
                </div>
                <div class="date-item">
                    <div class="date-label">Send Date</div>
                    <div class="date-value">${formatDate(campaign.send_at)}</div>
                </div>
                <div class="date-item">
                    <div class="date-label">Due Date</div>
                    <div class="date-value">${formatDate(campaign.due_date)}</div>
                </div>
            </div>

            <div class="campaign-stats">
                <div class="stats-row">
                    <span class="stat-label">Total Contracts</span>
                    <span class="stat-value">${campaign.total_contracts}</span>
                </div>
                <div class="stats-row">
                    <span class="stat-label">Sent</span>
                    <span class="stat-value">${campaign.sent_count} (${sentPercentage}%)</span>
                </div>
            </div>

            <div class="progress-section">
                ${getPDFProgressHTML(campaign)}

                <div class="progress-label mt-4">
                    <span class="progress-text">Signed Contracts</span>
                    <span class="progress-percentage">${signedPercentage}%</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${signedPercentage}%"></div>
                </div>
                <div class="mt-2 text-xs text-gray-500 text-center">
                    ${campaign.signed_count} out of ${campaign.total_contracts} contracts signed
                </div>
            </div>
        </div>
    `;
}

// Get status class based on campaign data
function getStatusClass(campaign) {
    const status = getCampaignStatus(campaign);
    return `status-${status}`;
}

// Get status text based on campaign data
function getStatusText(campaign) {
    const status = getCampaignStatus(campaign);
    switch (status) {
        case 'active':
            return 'Active';
        case 'upcoming':
            return 'Upcoming';
        case 'completed':
            return 'Completed';
        case 'inactive':
            return 'Inactive'; // Changed from 'Overdue' to 'Inactive'
        default:
            return 'Active';
    }
}

// Get PDF progress HTML
function getPDFProgressHTML(campaign) {
    const pdfStatus = campaign.pdf_status || 'pending';
    const pdfTotal = campaign.pdf_total || 0;
    const pdfGenerated = campaign.pdf_generated || 0;
    const pdfPercentage = pdfTotal > 0 ? Math.round((pdfGenerated / pdfTotal) * 100) : 0;

    let statusText = '';
    let statusColor = '';
    let showProgress = false;

    switch(pdfStatus) {
        case 'processing':
            statusText = 'Generating PDFs...';
            statusColor = 'text-blue-600';
            showProgress = true;
            break;
        case 'completed':
            statusText = 'PDFs Ready';
            statusColor = 'text-green-600';
            showProgress = true;
            break;
        case 'failed':
            statusText = 'PDF Generation Failed';
            statusColor = 'text-red-600';
            showProgress = false;
            break;
        case 'pending':
        default:
            statusText = 'Pending PDF Generation';
            statusColor = 'text-gray-500';
            showProgress = false;
            break;
    }

    if (!showProgress) {
        return `
            <div class="mb-3">
                <div class="text-xs ${statusColor} font-medium">${statusText}</div>
            </div>
        `;
    }

    return `
        <div class="mb-3">
            <div class="progress-label">
                <span class="progress-text ${statusColor}">${statusText}</span>
                <span class="progress-percentage">${pdfPercentage}%</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar ${pdfStatus === 'processing' ? 'bg-blue-500' : 'bg-green-500'}" style="width: ${pdfPercentage}%"></div>
            </div>
            <div class="mt-1 text-xs text-gray-500 text-center">
                ${pdfGenerated} out of ${pdfTotal} PDFs generated
            </div>
        </div>
    `;
}

// Setup pagination
function setupPagination() {
    const paginationContainer = document.getElementById('pagination-container');
    const totalPages = Math.ceil(totalCampaigns / itemsPerPage);

    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }

    const startItem = (currentPage - 1) * itemsPerPage + 1;
    const endItem = Math.min(currentPage * itemsPerPage, totalCampaigns);

    let paginationHTML = '<div class="pagination-wrapper"><div class="pagination">';

    // Previous button with icon
    paginationHTML += `
        <button class="page-btn"
                onclick="changePage(${currentPage - 1})"
                ${currentPage === 1 ? 'disabled' : ''}>
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
        </button>
    `;

    // Always show first page
    paginationHTML += `
        <button class="page-btn ${1 === currentPage ? 'active' : ''}"
                onclick="changePage(1)">
            1
        </button>
    `;

    // Show ellipsis if needed
    if (currentPage > 3) {
        paginationHTML += '<span class="page-btn ellipsis">...</span>';
    }

    // Show pages around current page
    for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) {
        paginationHTML += `
            <button class="page-btn ${i === currentPage ? 'active' : ''}"
                    onclick="changePage(${i})">
                ${i}
            </button>
        `;
    }

    // Show ellipsis if needed
    if (currentPage < totalPages - 2) {
        paginationHTML += '<span class="page-btn ellipsis">...</span>';
    }

    // Always show last page if there's more than one page
    if (totalPages > 1) {
        paginationHTML += `
            <button class="page-btn ${totalPages === currentPage ? 'active' : ''}"
                    onclick="changePage(${totalPages})">
                ${totalPages}
            </button>
        `;
    }

    // Next button with icon
    paginationHTML += `
        <button class="page-btn"
                onclick="changePage(${currentPage + 1})"
                ${currentPage === totalPages ? 'disabled' : ''}>
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
        </button>
    `;

    paginationHTML += '</div>';

    // Add pagination info below
    paginationHTML += `
        <div class="pagination-info">
            Showing ${startItem} to ${endItem} of ${totalCampaigns} campaigns
        </div>
    </div>`;

    paginationContainer.innerHTML = paginationHTML;
}

// Change page
function changePage(page) {
    const totalPages = Math.ceil(totalCampaigns / itemsPerPage);
    if (page >= 1 && page <= totalPages && page !== currentPage) {
        currentPage = page;
        displayCampaigns();
        setupPagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// Setup modal functionality
function setupModal() {
    // Close modal handler
    document.getElementById('close-campaign-details').addEventListener('click', function() {
        document.getElementById('campaign-details-modal').classList.add('hidden');
    });

    // Close modal when clicking outside
    document.getElementById('campaign-details-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.add('hidden');
        }
    });
}

// Open campaign details modal
async function openCampaignDetails(campaignId) {
    const modal = document.getElementById('campaign-details-modal');
    const modalTitle = document.getElementById('modal-campaign-title');

    // Find campaign data
    const campaign = campaigns.find(c => c.campaign_id == campaignId);
    if (campaign) {
        const companyDisplay = campaign.company_detail
            ? `${campaign.company_name || 'PT Mandom Indonesia'} - ${campaign.company_detail}`
            : (campaign.company_name || 'PT Mandom Indonesia');
        modalTitle.textContent = `${companyDisplay} - Campaign ${campaign.campaign_id}`;
    }

    // Load campaign data
    await loadModalCampaignData(campaignId);

    modal.classList.remove('hidden');
}

// Load campaign data for modal
async function loadModalCampaignData(campaignId) {
    await loadModalContractsTable(campaignId);
    await loadModalContractTemplate(campaignId);
}

// Load contracts table for modal
async function loadModalContractsTable(campaignId) {
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
async function loadModalContractTemplate(campaignId) {
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

// Show empty state
function showEmptyState() {
    const campaignsContainer = document.getElementById('campaigns-container');
    campaignsContainer.innerHTML = `
        <div class="col-span-full empty-state">
            <div class="empty-state-icon">📋</div>
            <div class="empty-state-title">No Campaigns Found</div>
            <div class="empty-state-text">Create your first campaign to get started</div>
        </div>
    `;
}

// Show error state
function showErrorState() {
    const campaignsContainer = document.getElementById('campaigns-container');
    campaignsContainer.innerHTML = `
        <div class="col-span-full empty-state">
            <div class="empty-state-icon">⚠️</div>
            <div class="empty-state-title">Error Loading Campaigns</div>
            <div class="empty-state-text">Please try refreshing the page</div>
        </div>
    `;
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