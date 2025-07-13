import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'
import './assets/main.css' // Import our global CSS

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { generatePWAIcons } from './utils/generateIcons'
import { initErrorHandler } from './utils/errorHandler.js'
import { logger } from './utils/logger.js'
import { UI_CONFIG } from './config/constants.js'


// Initialize the PWA features when in browser environment
if (typeof window !== 'undefined') {
  // Set dynamic page title
  const brandName = import.meta.env.VITE_BRAND_NAME
  if (brandName) {
    document.title = `${brandName} - 网页版`
  }

  // Check for dark mode preference
  const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches
  document.documentElement.setAttribute('data-theme', prefersDarkMode ? 'dark' : 'light')

  // Listen for changes in color scheme preference
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light')
  })

  // Log environment variables in development using new logger
  logger.debug('Environment variables', {
    VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
    VITE_LEANCLOUD_APP_ID: import.meta.env.VITE_LEANCLOUD_APP_ID,
    VITE_LEANCLOUD_APP_KEY: import.meta.env.VITE_LEANCLOUD_APP_KEY ? '[HIDDEN]' : 'undefined',
  });
}

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(Toast, {
  transition: "Vue-Toastification__fade",
  maxToasts: 3,
  newestOnTop: true,
  position: "top-center",
  timeout: 3000,
  closeOnClick: true,
  pauseOnFocusLoss: false,
  pauseOnHover: true,
  draggable: false,
  showCloseButtonOnHover: false,
  hideProgressBar: false,
  closeButton: false,
  icon: false,
  rtl: false,
  toastClassName: "custom-toast"
})

// Initialize error handler after toast is configured
initErrorHandler();

// Add global styles for selectable toast
const style = document.createElement('style');
style.textContent = `
  .selectable-toast {
    user-select: text !important;
    cursor: default !important;
  }
  .selectable-toast * {
    user-select: text !important;
  }
`;
document.head.appendChild(style);

// Make PWA icon generator available globally for development
if (process.env.NODE_ENV === 'development') {
  window.generatePWAIcons = generatePWAIcons
}

// Get the auth store instance
const authStore = useAuthStore()

// Check authentication status when the app initializes
authStore.checkAuth().then(() => {
  app.use(router)
  app.mount('#app')
})