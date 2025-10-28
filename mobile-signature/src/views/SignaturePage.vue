<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'

// Set up PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker

const route = useRoute()
const contractMd5 = ref(route.params.contractMd5)

// Contract data
const contractData = ref({
  name: '',
  contract_num_detail: '',
  job_description: '',
  location: '',
  signed_status: false
})

// Canvas reference
const canvasRef = ref(null)
let ctx = null
let isDrawing = false
let signaturePath = []

// PDF references
const pdfCanvasRef = ref(null)
const pdfContainerRef = ref(null)
let pdfDoc = null
const currentPage = ref(1)
const totalPages = ref(0)
const pdfScale = ref(1.5)

// Status
const isLoading = ref(true)
const statusMessage = ref('')
const statusType = ref('') // 'success' or 'error'
const showStatus = ref(false)

// API base URL
const API_BASE = 'http://127.0.0.1:8000'

// Load contract data
const loadContractData = async () => {
  try {
    isLoading.value = true

    if (!contractMd5.value || contractMd5.value === 'error') {
      throw new Error('Invalid contract link')
    }

    // Fetch contract details by MD5
    const response = await fetch(`${API_BASE}/api/mobile/contract-by-md5/${contractMd5.value}`)

    if (!response.ok) {
      throw new Error('Contract not found')
    }

    const data = await response.json()
    contractData.value = data

    // Load PDF
    await loadPDF()

  } catch (error) {
    console.error('Error loading contract:', error)
    showStatusMessage('error', error.message || 'Failed to load contract')
  } finally {
    isLoading.value = false
    // Initialize canvas after loading is complete and DOM is updated
    await nextTick()
    initCanvas()
  }
}

// Load PDF using PDF.js
const loadPDF = async () => {
  try {
    const pdfUrl = `${API_BASE}/api/mobile/contract-pdf-by-md5/${contractMd5.value}`

    // Load the PDF document
    const loadingTask = pdfjsLib.getDocument(pdfUrl)
    pdfDoc = await loadingTask.promise
    totalPages.value = pdfDoc.numPages

    // Render first page
    await renderPage(1)

  } catch (error) {
    console.error('Error loading PDF:', error)
    showStatusMessage('error', 'Failed to load PDF document')
  }
}

// Render a specific page
const renderPage = async (pageNum) => {
  if (!pdfDoc || !pdfCanvasRef.value) return

  try {
    const page = await pdfDoc.getPage(pageNum)
    const canvas = pdfCanvasRef.value
    const context = canvas.getContext('2d')

    // Calculate scale to fit container width
    const container = pdfContainerRef.value
    if (container) {
      const containerWidth = container.clientWidth
      const viewport = page.getViewport({ scale: 1 })
      pdfScale.value = containerWidth / viewport.width
    }

    const viewport = page.getViewport({ scale: pdfScale.value })

    // Set canvas dimensions
    canvas.height = viewport.height
    canvas.width = viewport.width

    // Render PDF page
    const renderContext = {
      canvasContext: context,
      viewport: viewport
    }

    await page.render(renderContext).promise
    currentPage.value = pageNum
  } catch (error) {
    console.error('Error rendering page:', error)
  }
}

// Navigate pages
const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    renderPage(currentPage.value + 1)
  }
}

const prevPage = () => {
  if (currentPage.value > 1) {
    renderPage(currentPage.value - 1)
  }
}

// Initialize canvas
const initCanvas = () => {
  if (!canvasRef.value) return

  const canvas = canvasRef.value
  ctx = canvas.getContext('2d')

  // Get device pixel ratio for high-DPI displays
  const dpr = window.devicePixelRatio || 1

  // Set canvas size to match container with high resolution
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width * dpr
  canvas.height = 200 * dpr

  // Scale context to match device pixel ratio
  ctx.scale(dpr, dpr)

  // Set display size (css pixels)
  canvas.style.width = rect.width + 'px'
  canvas.style.height = '200px'

  // Configure drawing style
  ctx.strokeStyle = '#1f2937'
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
}

// Drawing functions
const startDrawing = (e) => {
  if (!ctx || !canvasRef.value) return

  isDrawing = true
  const rect = canvasRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  ctx.beginPath()
  ctx.moveTo(x, y)
  signaturePath.push({ type: 'move', x, y })
}

const draw = (e) => {
  if (!isDrawing || !ctx || !canvasRef.value) return

  const rect = canvasRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  ctx.lineTo(x, y)
  ctx.stroke()
  signaturePath.push({ type: 'line', x, y })
}

const stopDrawing = () => {
  if (isDrawing) {
    signaturePath.push({ type: 'end' })
  }
  isDrawing = false
}

// Touch event handlers
const handleTouchStart = (e) => {
  e.preventDefault()
  if (!ctx || !canvasRef.value) return

  const touch = e.touches[0]
  const rect = canvasRef.value.getBoundingClientRect()
  // Use pageX/pageY and subtract scroll offset for accurate positioning
  const x = touch.clientX - rect.left
  const y = touch.clientY - rect.top

  isDrawing = true
  ctx.beginPath()
  ctx.moveTo(x, y)
  signaturePath.push({ type: 'move', x, y })
}

const handleTouchMove = (e) => {
  e.preventDefault()
  if (!isDrawing || !ctx || !canvasRef.value) return

  const touch = e.touches[0]
  const rect = canvasRef.value.getBoundingClientRect()
  // Use pageX/pageY and subtract scroll offset for accurate positioning
  const x = touch.clientX - rect.left
  const y = touch.clientY - rect.top

  ctx.lineTo(x, y)
  ctx.stroke()
  signaturePath.push({ type: 'line', x, y })
}

// Clear canvas
const clearSignature = () => {
  if (!ctx || !canvasRef.value) return

  ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  signaturePath = []
}

// Convert signature to SVG
const signatureToSVG = () => {
  if (signaturePath.length === 0) return null

  let pathData = ''

  for (let i = 0; i < signaturePath.length; i++) {
    const point = signaturePath[i]

    if (point.type === 'move') {
      pathData += `M ${point.x} ${point.y} `
    } else if (point.type === 'line') {
      pathData += `L ${point.x} ${point.y} `
    }
  }

  // Use CSS dimensions for SVG, not internal canvas dimensions
  const rect = canvasRef.value.getBoundingClientRect()
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${rect.width}" height="200" viewBox="0 0 ${rect.width} 200">
  <path d="${pathData.trim()}" stroke="#1f2937" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>`

  return svg
}

// Submit signature
const submitSignature = async () => {
  try {
    // Validate
    if (signaturePath.length === 0) {
      showStatusMessage('error', 'Please provide a signature')
      return
    }

    if (contractData.value.signed_status) {
      showStatusMessage('error', 'This contract is already signed')
      return
    }

    // Convert to SVG
    const svgData = signatureToSVG()
    if (!svgData) {
      showStatusMessage('error', 'Failed to generate signature')
      return
    }

    // Create form data
    const blob = new Blob([svgData], { type: 'image/svg+xml' })
    const formData = new FormData()
    formData.append('signature', blob, 'signature.svg')
    formData.append('contract_md5', contractMd5.value)
    formData.append('signer_name', contractData.value.name)

    // Submit
    const response = await fetch(`${API_BASE}/api/sign-contract`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error('Failed to submit signature')
    }

    showStatusMessage('success', 'Signature submitted successfully!')
    contractData.value.signed_status = true
    clearSignature()

    // Reload PDF to show signed version
    await loadPDF()

  } catch (error) {
    console.error('Error submitting signature:', error)
    showStatusMessage('error', 'Failed to submit signature. Please try again.')
  }
}

// Show status message
const showStatusMessage = (type, message) => {
  statusType.value = type
  statusMessage.value = message
  showStatus.value = true

  setTimeout(() => {
    showStatus.value = false
  }, 5000)
}

// Lifecycle hooks
onMounted(() => {
  loadContractData()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
      <div class="px-4 py-4">
        <h1 class="text-xl font-bold text-gray-900">JMax Contract</h1>
        <p class="text-sm text-gray-500 mt-1">Digital Signature</p>
      </div>
    </header>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center min-h-[calc(100vh-80px)]">
      <div class="text-center">
        <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
        <p class="mt-4 text-gray-600">Loading contract...</p>
      </div>
    </div>

    <!-- Main Content -->
    <main v-else class="pb-6">
      <!-- Status Message -->
      <div v-if="showStatus"
           :class="[
             'mx-4 mt-4 p-4 rounded-lg border',
             statusType === 'success' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'
           ]">
        <p class="font-medium">{{ statusMessage }}</p>
      </div>

      <!-- Contract Info Card -->
      <div class="mx-4 mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div class="bg-gradient-to-r from-blue-600 to-cyan-600 px-5 py-4">
          <h2 class="text-lg font-semibold text-white">Contract Information</h2>
        </div>
        <div class="p-5 space-y-4">
          <div>
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Employee Name</label>
            <p class="mt-1 text-base font-semibold text-gray-900">{{ contractData.name || '-' }}</p>
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Contract Number</label>
            <p class="mt-1 text-sm font-medium text-gray-700">{{ contractData.contract_num_detail || '-' }}</p>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Position</label>
              <p class="mt-1 text-sm font-medium text-gray-700">{{ contractData.job_description || '-' }}</p>
            </div>
            <div>
              <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Location</label>
              <p class="mt-1 text-sm font-medium text-gray-700">{{ contractData.location || '-' }}</p>
            </div>
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Status</label>
            <div class="mt-1">
              <span v-if="contractData.signed_status"
                    class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                ✓ Signed
              </span>
              <span v-else
                    class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                ⏳ Pending Signature
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- PDF Viewer Card -->
      <div class="mx-4 mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div class="bg-gradient-to-r from-blue-600 to-cyan-600 px-5 py-4 flex justify-between items-center">
          <h2 class="text-lg font-semibold text-white">Contract Document</h2>
          <div v-if="totalPages > 0" class="text-sm text-white">
            Page {{ currentPage }} / {{ totalPages }}
          </div>
        </div>
        <div class="p-4">
          <div v-if="pdfDoc">
            <div ref="pdfContainerRef" class="border border-gray-200 rounded-lg overflow-auto bg-gray-100 mb-3" style="max-height: 500px;">
              <canvas ref="pdfCanvasRef" class="w-full"></canvas>
            </div>
            <!-- Page navigation -->
            <div v-if="totalPages > 1" class="flex gap-2 mb-3">
              <button
                @click="prevPage"
                :disabled="currentPage === 1"
                class="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
              >
                ← Previous
              </button>
              <button
                @click="nextPage"
                :disabled="currentPage === totalPages"
                class="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
              >
                Next →
              </button>
            </div>
            <!-- Download button -->
            <a
              :href="`${API_BASE}/api/mobile/contract-pdf-by-md5/${contractMd5}`"
              download="contract.pdf"
              class="flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              <span class="mr-2">📥</span>
              Download Contract
            </a>
          </div>
          <div v-else class="py-12 text-center text-gray-500">
            <p>Loading PDF document...</p>
          </div>
        </div>
      </div>

      <!-- Signature Card -->
      <div class="mx-4 mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div class="bg-gradient-to-r from-blue-600 to-cyan-600 px-5 py-4">
          <h2 class="text-lg font-semibold text-white">Your Signature</h2>
          <p class="text-xs text-blue-100 mt-1">Sign with your finger or stylus</p>
        </div>
        <div class="p-5">
          <!-- Canvas -->
          <div class="border-2 border-dashed border-gray-300 rounded-xl bg-white overflow-hidden touch-none">
            <canvas
              ref="canvasRef"
              class="w-full cursor-crosshair touch-none"
              @mousedown="startDrawing"
              @mousemove="draw"
              @mouseup="stopDrawing"
              @mouseout="stopDrawing"
              @touchstart="handleTouchStart"
              @touchmove="handleTouchMove"
              @touchend="stopDrawing"
            ></canvas>
          </div>

          <!-- Action Buttons -->
          <div class="mt-5 grid grid-cols-2 gap-3">
            <button
              @click="clearSignature"
              class="flex items-center justify-center px-5 py-3 border border-gray-300 rounded-lg font-semibold text-gray-700 bg-white hover:bg-gray-50 active:bg-gray-100 transition-colors shadow-sm"
            >
              <span class="mr-2">🗑️</span>
              Clear
            </button>
            <button
              @click="submitSignature"
              :disabled="contractData.signed_status"
              :class="[
                'flex items-center justify-center px-5 py-3 rounded-lg font-semibold text-white transition-colors shadow-md',
                contractData.signed_status
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 active:from-blue-800 active:to-cyan-800'
              ]"
            >
              <span class="mr-2">✓</span>
              {{ contractData.signed_status ? 'Signed' : 'Submit' }}
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
canvas {
  touch-action: none;
}
</style>
