// Retirement worker: replace older offline workers, clear FitCoach caches,
// and release the registration. Keep this URL available for existing installs.
self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('fitcoach-'))
      .map(key => caches.delete(key)));
    await self.clients.claim();
    await self.registration.unregister();
  })());
});

// Existing tabs may remain controlled until their next navigation.
// Never serve them an offline page or a cached application response.
self.addEventListener('fetch', event => {
  event.respondWith(fetch(event.request, { cache: 'no-store' }));
});
