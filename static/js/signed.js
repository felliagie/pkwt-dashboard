// Signed contracts page functionality
let currentUid = null;
let contracts = [];

document.addEventListener('DOMContentLoaded', function() {
    loadSignedContracts();
});

// Load all signed contracts
async function loadSignedContracts() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/signed-contracts');
        if (!response.ok) {
            throw new Error('Failed to load signed contracts');
        }

        contracts = await response.json();

        // Display contracts list
        displayContractsList(contracts);

        // Auto-load first contract if available
        if (contracts.length > 0) {
            loadContract(contracts[0].uid);
        }

    } catch (error) {
        console.error('Error loading signed contracts:', error);
        document.getElementById('contracts-list').innerHTML =
            '<p class="text-red-500 text-center py-4">Failed to load contracts</p>';
    }
}

// Display contracts list
function displayContractsList(contracts) {
    const listContainer = document.getElementById('contracts-list');

    if (contracts.length === 0) {
        listContainer.innerHTML = '<p style="color: #6B6B6B;" class="text-center py-4">No signed contracts found</p>';
        return;
    }

    listContainer.innerHTML = contracts.map(contract => {
        const signedDate = new Date(contract.signed_at).toLocaleDateString('id-ID', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        return `
            <button
                onclick="loadContract('${contract.uid}')"
                class="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors border border-gray-200"
                id="contract-${contract.uid}"
            >
                <div class="font-semibold text-gray-900">${contract.signer_name}</div>
                <div class="text-sm text-gray-600">${contract.contract_num_detail}</div>
                <div class="text-xs text-gray-500 mt-1">${signedDate}</div>
            </button>
        `;
    }).join('');
}

// Load specific contract
async function loadContract(uid) {
    try {
        currentUid = uid;

        // Find contract in list
        const contract = contracts.find(c => c.uid === uid);
        if (!contract) {
            throw new Error('Contract not found');
        }

        // Update UI with contract info
        document.getElementById('signer-name').textContent = contract.signer_name || '-';
        document.getElementById('contract-number').textContent = contract.contract_num_detail || '-';

        const signedDate = new Date(contract.signed_at).toLocaleString('id-ID', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('signed-at').textContent = signedDate;

        // Highlight selected contract
        contracts.forEach(c => {
            const element = document.getElementById(`contract-${c.uid}`);
            if (element) {
                if (c.uid === uid) {
                    element.classList.add('bg-purple-50', 'border-purple-600');
                } else {
                    element.classList.remove('bg-purple-50', 'border-purple-600');
                }
            }
        });

        // Load PDF
        await loadPDF(uid);

    } catch (error) {
        console.error('Error loading contract:', error);
        showError('Failed to load contract information');
    }
}

// Load PDF document
async function loadPDF(uid) {
    try {
        const response = await fetch(`http://127.0.0.1:8000/api/signed-contracts/${uid}/pdf`);
        if (!response.ok) {
            throw new Error('Failed to load PDF');
        }

        const blob = await response.blob();
        const pdfUrl = URL.createObjectURL(blob);

        // Display PDF
        const pdfContainer = document.getElementById('pdf-container');
        pdfContainer.innerHTML = `
            <embed src="${pdfUrl}" type="application/pdf" width="100%" height="600px" />
        `;

    } catch (error) {
        console.error('Error loading PDF:', error);
        document.getElementById('pdf-container').innerHTML =
            '<p class="text-red-500 text-center py-8">Failed to load PDF document</p>';
    }
}

// Show error message
function showError(message) {
    const pdfContainer = document.getElementById('pdf-container');
    pdfContainer.innerHTML = `<p class="text-red-500 text-center py-8">${message}</p>`;
}
