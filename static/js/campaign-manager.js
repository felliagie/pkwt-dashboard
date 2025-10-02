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
const itemsPerPage = 9;
let totalCampaigns = 0;
let campaigns = [];
let progressPollingInterval = null;

function initializeCampaignManager() {
    loadCampaigns();
    setupModal();
    startProgressPolling();
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
        totalCampaigns = campaigns.length;

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
    const pageData = campaigns.slice(startIndex, endIndex);

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
                    <div class="campaign-title">${campaign.company}</div>
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
    const now = new Date();
    const sendDate = new Date(campaign.send_at);
    const dueDate = new Date(campaign.due_date);

    if (campaign.signed_count === campaign.total_contracts && campaign.total_contracts > 0) {
        return 'status-completed';
    } else if (now > dueDate) {
        return 'status-pending';
    } else {
        return 'status-active';
    }
}

// Get status text based on campaign data
function getStatusText(campaign) {
    const now = new Date();
    const sendDate = new Date(campaign.send_at);
    const dueDate = new Date(campaign.due_date);

    if (campaign.signed_count === campaign.total_contracts && campaign.total_contracts > 0) {
        return 'Completed';
    } else if (now > dueDate) {
        return 'Overdue';
    } else {
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

    let paginationHTML = '<div class="pagination">';

    // Previous button
    paginationHTML += `
        <button class="page-btn ${currentPage === 1 ? 'disabled' : ''}"
                onclick="changePage(${currentPage - 1})"
                ${currentPage === 1 ? 'disabled' : ''}>
            Previous
        </button>
    `;

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            paginationHTML += `
                <button class="page-btn ${i === currentPage ? 'active' : ''}"
                        onclick="changePage(${i})">
                    ${i}
                </button>
            `;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            paginationHTML += '<span class="page-btn disabled">...</span>';
        }
    }

    // Next button
    paginationHTML += `
        <button class="page-btn ${currentPage === totalPages ? 'disabled' : ''}"
                onclick="changePage(${currentPage + 1})"
                ${currentPage === totalPages ? 'disabled' : ''}>
            Next
        </button>
    `;

    paginationHTML += '</div>';
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
        modalTitle.textContent = `${campaign.company} - Campaign ${campaign.campaign_id}`;
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