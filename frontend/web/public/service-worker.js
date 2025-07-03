// Enhanced service worker for PWA capability
const CACHE_VERSION = '1.0.1';
const CACHE_NAME = `says-cache-v${CACHE_VERSION}`;
const APP_SHELL_CACHE = `says-app-shell-v${CACHE_VERSION}`;

// Assets to cache for offline use (App Shell)
const APP_SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/offline.html',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/assets/index.css'
];

// Install service worker and cache app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE)
      .then((cache) => {
        console.log('App shell cache opened');
        return cache.addAll(APP_SHELL_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Clean up old caches
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [CACHE_NAME, APP_SHELL_CACHE];

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (!cacheWhitelist.includes(cacheName)) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Improved fetch strategy with offline fallback
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests and browser extensions
  if (event.request.method !== 'GET' ||
    !event.request.url.startsWith('http')) {
    return;
  }

  // Handle API requests separately - always try network first
  if (event.request.url.includes('/api/') || event.request.url.includes('localhost:8001')) {
    event.respondWith(
      fetch(event.request)
        .catch((error) => {
          console.error('API request failed:', error);
          return new Response(
            JSON.stringify({
              error: true,
              message: 'API request failed - check network connection'
            }),
            {
              headers: { 'Content-Type': 'application/json' },
              status: 503
            }
          );
        })
    );
    return;
  }

  // For HTML navigation requests, use network first with offline fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match('/offline.html');
        })
    );
    return;
  }

  // For all other requests, use cache first with network fallback
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Cache hit - return the response
        if (response) {
          return response;
        }

        // Clone the request before using it
        const fetchRequest = event.request.clone();

        return fetch(fetchRequest)
          .then((response) => {
            // Check if we received a valid response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clone the response before using it
            const responseToCache = response.clone();

            // Cache the response for future use
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });

            return response;
          })
          .catch(() => {
            // If both network and cache fail for images or assets, return a placeholder
            if (event.request.url.match(/\.(jpg|jpeg|png|gif|svg|webp)$/)) {
              return new Response(
                '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#eee"/><text x="50%" y="50%" font-family="sans-serif" font-size="24" text-anchor="middle" dominant-baseline="middle" fill="#999">Image unavailable</text></svg>',
                { headers: { 'Content-Type': 'image/svg+xml' } }
              );
            }
          });
      })
  );
});

// Listen for push notifications
self.addEventListener('push', (event) => {
  const data = event.data.json();

  const options = {
    body: data.message || '新消息',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-72x72.png',
    data: data.url || '/',
    vibrate: [100, 50, 100],
    actions: [
      {
        action: 'open',
        title: '查看'
      },
      {
        action: 'close',
        title: '关闭'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Says 通知', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  // Open the app and navigate to a specific URL
  event.waitUntil(
    clients.openWindow(event.notification.data || '/')
  );
}); 