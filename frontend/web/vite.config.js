import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { writeFileSync } from 'fs'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  // Generate service worker with version from environment
  const version = process.env.VITE_APP_VERSION
  if (!version) {
    throw new Error('VITE_APP_VERSION environment variable is required but not set')
  }

  // Generate service worker content with injected version
  const serviceWorkerContent = `// Enhanced service worker for PWA capability
const CACHE_VERSION = '${version}';
const CACHE_NAME = \`says-cache-v\${CACHE_VERSION}\`;
const APP_SHELL_CACHE = \`says-app-shell-v\${CACHE_VERSION}\`;

// Files to cache for offline functionality
const STATIC_CACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json'
];

// Install event - cache static resources
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Install event');
  event.waitUntil(
    caches.open(APP_SHELL_CACHE)
      .then((cache) => {
        console.log('[ServiceWorker] Caching app shell');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => {
        console.log('[ServiceWorker] Skip waiting');
        return self.skipWaiting();
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activate event');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== APP_SHELL_CACHE) {
            console.log('[ServiceWorker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[ServiceWorker] Claiming clients');
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip API requests
  if (event.request.url.includes('/api/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version or fetch from network
        return response || fetch(event.request).then((fetchResponse) => {
          // Don't cache if not a valid response
          if (!fetchResponse || fetchResponse.status !== 200 || fetchResponse.type !== 'basic') {
            return fetchResponse;
          }

          // Clone the response
          const responseToCache = fetchResponse.clone();

          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });

          return fetchResponse;
        });
      })
      .catch(() => {
        // Fallback for navigation requests
        if (event.request.mode === 'navigate') {
          return caches.match('/index.html');
        }
      })
  );
});

// Message event - handle version check
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_VERSION });
  }
});
`

  // Write the service worker file
  writeFileSync(resolve(__dirname, 'public/service-worker.js'), serviceWorkerContent)

  return {
    plugins: [vue()],
    envDir: resolve(__dirname, '../../'),
    server: {
      host: '0.0.0.0', // Allow external access
      proxy: {
        // Proxy /api/v1/system requests to bot_message_service
        '/api/v1/system': {
          target: 'http://bot_message_service_container:8000',
          changeOrigin: true,
        },
        // Proxy /api/v1/contacts requests to contacts_service
        '/api/v1/contacts': {
          target: 'http://contacts_service_container:8000',
          changeOrigin: true,
        },
        // Proxy other /api/v1 requests to accounts_service (Docker internal network)
        '/api/v1': {
          target: 'http://accounts_service_container:8000',
          changeOrigin: true,
          // Don't rewrite path since accounts_service now expects /api/v1 prefix
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
  }
})