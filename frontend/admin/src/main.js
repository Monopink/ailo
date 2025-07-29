// Reset styles
import '@/styles/reset.css'
import '@/styles/global.scss'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// Initialize theme management
import themeManager from '@/utils/theme.js'
// Theme manager is automatically initialized when imported
console.log('Theme manager initialized:', themeManager.getTheme())

// Simplified static routes for admin panel
const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: 'Login' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/layout/index.vue'),
    meta: { title: 'Dashboard - Admin' },
    children: [
      {
        path: '',
        name: 'DashboardHome',
        component: () => import('@/views/workbench/index.vue')
      }
    ]
  },
  // System management routes
  {
    path: '/system',
    name: 'System',
    component: () => import('@/layout/index.vue'),
    children: [
      {
        path: 'users',
        name: 'SystemUsers',
        component: () => import('@/views/admin/users/index.vue'),
        meta: { title: 'Users - Admin' }
      }
    ]
  },
  // Components showcase (IMPORTANT: Development reference page - DO NOT DELETE)
  {
    path: '/components',
    name: 'Components',
    component: () => import('@/layout/index.vue'),
    meta: { title: 'Components - Admin' },
    children: [
      {
        path: '',
        name: 'ComponentsHome',
        component: () => import('@/views/components/index.vue')
      }
    ]
  },
  // Business management routes will be added in future phases
  // Settings
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/layout/index.vue'),
    meta: { title: 'Settings - Admin' },
    children: [
      {
        path: '',
        name: 'SettingsHome',
        component: () => import('@/views/settings/index.vue')
      }
    ]
  },
  // Error pages - minimal design
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error-page/404.vue')
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error-page/403.vue')
  },
  {
    path: '/500',
    name: 'ServerError',
    component: () => import('@/views/error-page/500.vue')
  },
  // Catch all route
  {
    path: '/:pathMatch(.*)*',
    redirect: '/404'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Auth guard and title management
router.beforeEach((to, _from, next) => {
  // Update page title
  if (to.meta && to.meta.title) {
    document.title = to.meta.title
  } else {
    document.title = 'Admin' // Default title
  }

  // Auth guard
  const token = localStorage.getItem('admin_token')

  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && token) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Initialize auth state
async function initApp() {
  const { useAuthStore } = await import('@/store')
  const authStore = useAuthStore()

  const token = localStorage.getItem('admin_token')
  if (token) {
    authStore.setToken(token)

    // Try to get user info
    try {
      const api = (await import('@/api')).default
      const response = await api.getUserInfo()
      if (response.code === 200 && response.data) {
        authStore.setUser(response.data)
      }
    } catch (error) {
      console.warn('Failed to get user info on startup:', error)
      // Token might be invalid, clear it
      authStore.logout()
    }
  }

  app.mount('#app')
}

initApp()
