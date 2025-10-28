<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { signOut, supabase } from '../lib/supabase'

const router = useRouter()
const isLoggingOut = ref(false)

// Check if user actually has a contract on mount
onMounted(async () => {
  const { data: { user } } = await supabase.auth.getUser()
  const contractMd5 = user?.user_metadata?.contract_md5

  // If they actually have a contract, redirect them
  if (contractMd5) {
    router.push(`/sign/${contractMd5}`)
  }
})

// Handle logout
const handleLogout = async () => {
  try {
    isLoggingOut.value = true
    await signOut()
    router.push('/login')
  } catch (error) {
    console.error('Logout error:', error)
  } finally {
    isLoggingOut.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-red-50 via-orange-50 to-red-100 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <!-- Error Card -->
      <div class="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">
        <!-- Card Header -->
        <div class="bg-gradient-to-r from-red-600 to-orange-600 px-6 py-5">
          <div class="flex items-center justify-center">
            <svg class="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
        </div>

        <!-- Card Body -->
        <div class="p-8 text-center space-y-4">
          <!-- Error Message -->
          <h2 class="text-2xl font-bold text-gray-900 mt-4">No Contract Found</h2>
          <p class="text-gray-600 leading-relaxed">
            We couldn't find any contract associated with your account. Please contact your administrator or HR department for assistance.
          </p>

          <!-- Info Box -->
          <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left">
            <div class="flex items-start">
              <svg class="w-5 h-5 text-blue-600 mr-2 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
              </svg>
              <div class="text-sm text-blue-800">
                <p class="font-medium mb-1">What should I do?</p>
                <ul class="list-disc list-inside space-y-1 ml-2">
                  <li>Contact your HR department</li>
                  <li>Verify your email address is correct</li>
                  <li>Wait for your contract to be assigned</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="pt-4 space-y-3">
            <button
              @click="handleLogout"
              :disabled="isLoggingOut"
              class="w-full bg-gradient-to-r from-blue-600 to-cyan-600 text-white py-3 px-4 rounded-lg font-semibold shadow-lg hover:from-blue-700 hover:to-cyan-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              <svg v-if="isLoggingOut" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span v-if="isLoggingOut">Signing Out...</span>
              <span v-else>Sign Out</span>
            </button>

            <p class="text-xs text-gray-500">
              Sign out and try again with a different account
            </p>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions for all interactive elements */
button {
  transition: all 0.2s ease-in-out;
}
</style>
