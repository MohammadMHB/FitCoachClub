// ===== Retire previous offline support =====
// Only update existing FitCoach workers; new visitors need no service worker.
(async () => {
  if ('caches' in window) {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.filter(key => key.startsWith('fitcoach-'))
        .map(key => caches.delete(key)));
    } catch (_) { /* Storage may be disabled by browser policy. */ }
  }
  if ('serviceWorker' in navigator) {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.filter(registration => {
        const worker = registration.active || registration.waiting || registration.installing;
        if (!worker) return false;
        const url = new URL(worker.scriptURL);
        return url.origin === location.origin &&
          ['/sw.js', '/static/sw.js'].includes(url.pathname);
      }).map(async registration => {
        try {
          await registration.update();
        } catch (_) { /* Unregister even if the update request fails. */ }
        await registration.unregister();
      }));
      // A previous worker may have completed a cache write during its update.
      if ('caches' in window) {
        const keys = await caches.keys();
        await Promise.all(keys.filter(key => key.startsWith('fitcoach-'))
          .map(key => caches.delete(key)));
      }
    } catch (_) { /* Retry cleanup on the next online visit. */ }
  }
})();

