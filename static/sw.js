// نسخه رو هر بار که این فایل عوض میشه بالا ببر تا مرورگر کش قدیمی رو دور بریزه
const CACHE_NAME = 'fitcoach-v2';
const OFFLINE_URL = '/static/offline.html';

const STATIC_ASSETS = [
  OFFLINE_URL,
  '/static/css/main.css',
  '/static/js/main.js',
  '/static/icons/fontawesome/css/all.min.css',
  '/static/manifest.json',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .catch(err => console.error('[SW] cache install failed:', err))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  // درخواست‌های ناوبری (باز کردن یک صفحه‌ی کامل HTML، مثل رفتن به داشبورد):
  // اول شبکه، اگه موفق شد نسخه‌ش رو کش کن تا دفعه‌ی بعد که آفلاین بود در
  // دسترس باشه؛ اگه شبکه نبود، از کش همون صفحه استفاده کن، و اگه اون صفحه
  // هیچ‌وقت قبلاً باز نشده بود، صفحه‌ی «بدون اینترنت» رو نشون بده.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(res => {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, resClone));
          return res;
        })
        .catch(() =>
          caches.match(req).then(cached => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // فایل‌های استاتیک (css/js/فونت/آیکون): اول کش (سریع‌تر)، بعد شبکه برای
  // به‌روزرسانی در پس‌زمینه.
  event.respondWith(
    caches.match(req).then(cached => {
      const networkFetch = fetch(req).then(res => {
        const resClone = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(req, resClone));
        return res;
      }).catch(() => cached);
      return cached || networkFetch;
    })
  );
});
