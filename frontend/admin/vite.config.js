import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5174,
    open: false,
    proxy: {
      '/api': {
        target: 'http://backend_container:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1024,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          utils: ['axios', 'dayjs'],
        },
      },
    },
  },
})
