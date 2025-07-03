import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', // Allow external access
    proxy: {
      // Proxy /api/v1 requests to accounts_service (Docker internal network)
      '/api/v1': {
        target: 'http://accounts_service_container:8000',
        changeOrigin: true,
        // Don't rewrite path since accounts_service now expects /api/v1 prefix
      },
      // Proxy /api/contacts requests to contacts_service
      '/api/contacts': {
        target: 'http://contacts_service_container:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/contacts/, '/api/v1/contacts')
      },
    },
    // Add response headers to control caching
    headers: {
      'Cache-Control': 'no-store',
      'Pragma': 'no-cache',
      'Expires': '0'
    }
  },
  // Ensure unique file names are generated for each build
  build: {
    rollupOptions: {
      output: {
        // Add timestamp to file names to avoid caching
        entryFileNames: `assets/[name]-[hash]-${new Date().getTime()}.js`,
        chunkFileNames: `assets/[name]-[hash]-${new Date().getTime()}.js`,
        assetFileNames: `assets/[name]-[hash]-${new Date().getTime()}.[ext]`
      }
    }
  }
}) 