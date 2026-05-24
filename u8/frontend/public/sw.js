const CACHE_NAME = 'ars-u8-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // API requests: network only
  if (request.url.includes('/api/')) {
    event.respondWith(fetch(request));
    return;
  }
  // Static assets: cache first
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});

// Push notification skeleton (activated in U8-C)
self.addEventListener('push', (event) => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'ふれまーるちゃん', {
      body: data.body || '',
      icon: '/icon-192.png',
    })
  );
});
