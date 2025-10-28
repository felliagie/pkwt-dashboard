import { createRouter, createWebHistory } from 'vue-router'
import SignaturePage from './views/SignaturePage.vue'
import LoginPage from './views/LoginPage.vue'
import NoContractPage from './views/NoContractPage.vue'
import { isAuthenticated } from './lib/supabase'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { requiresGuest: true }
  },
  {
    path: '/no-contract',
    name: 'no-contract',
    component: NoContractPage,
    meta: { requiresAuth: true }
  },
  {
    path: '/sign/:contractMd5',
    name: 'signature',
    component: SignaturePage,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard to protect routes
router.beforeEach(async (to, from, next) => {
  const userIsAuthenticated = await isAuthenticated()

  // Check if route requires authentication
  if (to.meta.requiresAuth && !userIsAuthenticated) {
    // Redirect to login if not authenticated
    next({ name: 'login' })
  }
  // Check if route is for guests only (login page)
  else if (to.meta.requiresGuest && userIsAuthenticated) {
    // Redirect to no-contract page if already authenticated
    // The user will be properly redirected from there if they have a contract
    next({ name: 'no-contract' })
  }
  // Allow navigation
  else {
    next()
  }
})

export default router
