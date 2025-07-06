import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'
import './assets/main.css' // Import our global CSS

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { generatePWAIcons } from './utils/generateIcons'


// Initialize the PWA features when in browser environment
if (typeof window !== 'undefined') {
  // Check for dark mode preference
  const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches
  document.documentElement.setAttribute('data-theme', prefersDarkMode ? 'dark' : 'light')

  // Listen for changes in color scheme preference
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light')
  })

  // Only log environment variables in development
  if (import.meta.env.DEV) {
    console.log('Environment variables:');
    console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
    console.log('VITE_LEANCLOUD_APP_ID:', import.meta.env.VITE_LEANCLOUD_APP_ID);
    console.log('VITE_LEANCLOUD_APP_KEY:', import.meta.env.VITE_LEANCLOUD_APP_KEY ? '[HIDDEN]' : 'undefined');
  }
}

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(Toast, {
  transition: "Vue-Toastification__fade",
  maxToasts: 5,
  newestOnTop: true,
  position: "top-center",
  timeout: 5000,
  closeOnClick: false,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: false,
  showCloseButtonOnHover: true,
  hideProgressBar: false,
  closeButton: "button",
  icon: true,
  rtl: false,
  toastClassName: "selectable-toast"
})

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