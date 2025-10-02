// Signature page functionality
let canvas, ctx;
let isDrawing = false;
let contractId = null;
let signaturePath = [];

document.addEventListener('DOMContentLoaded', function() {
    initializeCanvas();
    loadContractData();
    setupEventListeners();
});

// Initialize signature canvas
function initializeCanvas() {
    canvas = document.getElementById('signature-canvas');
    ctx = canvas.getContext('2d');

    // Set canvas size
    canvas.width = canvas.offsetWidth;
    canvas.height = 200;

    // Set canvas style
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
}

// Setup event listeners for canvas
function setupEventListeners() {
    // Mouse events
    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseout', stopDrawing);

    // Touch events for mobile
    canvas.addEventListener('touchstart', handleTouchStart);
    canvas.addEventListener('touchmove', handleTouchMove);
    canvas.addEventListener('touchend', stopDrawing);

    // Button events
    document.getElementById('clear-btn').addEventListener('click', clearCanvas);
    document.getElementById('submit-btn').addEventListener('click', submitSignature);

    // Window resize
    window.addEventListener('resize', () => {
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        canvas.width = canvas.offsetWidth;
        ctx.putImageData(imageData, 0, 0);
    });
}

// Drawing functions
function startDrawing(e) {
    isDrawing = true;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    ctx.beginPath();
    ctx.moveTo(x, y);

    // Start new path segment
    signaturePath.push({ type: 'move', x, y });
}

function draw(e) {
    if (!isDrawing) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.stroke();

    // Store path point
    signaturePath.push({ type: 'line', x, y });
}

function stopDrawing() {
    if (isDrawing) {
        signaturePath.push({ type: 'end' });
    }
    isDrawing = false;
}

// Touch event handlers
function handleTouchStart(e) {
    e.preventDefault();
    const touch = e.touches[0];
    const rect = canvas.getBoundingClientRect();
    const x = touch.clientX - rect.left;
    const y = touch.clientY - rect.top;

    isDrawing = true;
    ctx.beginPath();
    ctx.moveTo(x, y);

    // Start new path segment
    signaturePath.push({ type: 'move', x, y });
}

function handleTouchMove(e) {
    e.preventDefault();
    if (!isDrawing) return;

    const touch = e.touches[0];
    const rect = canvas.getBoundingClientRect();
    const x = touch.clientX - rect.left;
    const y = touch.clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.stroke();

    // Store path point
    signaturePath.push({ type: 'line', x, y });
}

// Clear canvas
function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    signaturePath = [];
}

// Check if canvas is empty
function isCanvasEmpty() {
    return signaturePath.length === 0;
}

// Convert signature path to SVG
function signatureToSVG() {
    if (signaturePath.length === 0) return null;

    let pathData = '';

    for (let i = 0; i < signaturePath.length; i++) {
        const point = signaturePath[i];

        if (point.type === 'move') {
            pathData += `M ${point.x} ${point.y} `;
        } else if (point.type === 'line') {
            pathData += `L ${point.x} ${point.y} `;
        }
    }

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}">
  <path d="${pathData.trim()}" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>`;

    return svg;
}

// Load contract data
async function loadContractData() {
    try {
        // Get contract ID from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        contractId = urlParams.get('contract_id');

        if (!contractId) {
            showStatus('error', 'No contract ID provided');
            return;
        }

        // Fetch contract details
        const response = await fetch(`http://127.0.0.1:8000/api/contract/${contractId}`);
        if (!response.ok) {
            throw new Error('Failed to load contract');
        }

        const contract = await response.json();

        // Update UI with contract info
        document.getElementById('employee-name').textContent = contract.name || '-';
        document.getElementById('contract-number').textContent = contract.contract_num_detail || '-';
        document.getElementById('contract-status').textContent = contract.signed_status ? 'Signed' : 'Pending';

        // Load PDF
        await loadPDF(contractId);

    } catch (error) {
        console.error('Error loading contract data:', error);
        showStatus('error', 'Failed to load contract information');
    }
}

// Load PDF document
async function loadPDF(contractId) {
    try {
        const response = await fetch(`http://127.0.0.1:8000/api/contracts/${contractId}/pdf`);
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

// Submit signature
async function submitSignature() {
    try {
        // Validate signature
        if (isCanvasEmpty()) {
            showStatus('error', 'Please provide a signature');
            return;
        }

        if (!contractId) {
            showStatus('error', 'No contract ID available');
            return;
        }

        // Convert signature to SVG
        const svgData = signatureToSVG();
        if (!svgData) {
            showStatus('error', 'Failed to generate signature');
            return;
        }

        // Create blob from SVG
        const blob = new Blob([svgData], { type: 'image/svg+xml' });

        // Create form data
        const formData = new FormData();
        formData.append('signature', blob, 'signature.svg');
        formData.append('contract_id', contractId);

        // Submit to backend
        const response = await fetch('http://127.0.0.1:8000/api/sign-contract', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to submit signature');
        }

        const result = await response.json();

        showStatus('success', 'Signature submitted successfully!');

        // Disable submit button
        document.getElementById('submit-btn').disabled = true;
        document.getElementById('submit-btn').classList.add('opacity-50', 'cursor-not-allowed');

        // Update status
        document.getElementById('contract-status').textContent = 'Signed';

        // Clear canvas
        clearCanvas();

        // Refresh PDF to show the signed version
        await loadPDF(contractId);

    } catch (error) {
        console.error('Error:', error);
        showStatus('error', 'An error occurred. Please try again.');
    }
}

// Show status message
function showStatus(type, message) {
    const statusDiv = document.getElementById('status-message');
    const statusText = document.getElementById('status-text');

    statusDiv.classList.remove('hidden', 'bg-green-100', 'bg-red-100', 'text-green-800', 'text-red-800');

    if (type === 'success') {
        statusDiv.classList.add('bg-green-100');
        statusText.classList.add('text-green-800');
    } else {
        statusDiv.classList.add('bg-red-100');
        statusText.classList.add('text-red-800');
    }

    statusText.textContent = message;

    // Auto-hide after 5 seconds
    setTimeout(() => {
        statusDiv.classList.add('hidden');
    }, 5000);
}