/* ============================================================
   Safar-e-Taleem — Service Worker (Offline-First Shell)
   Caches the core design-system CSS + landing page so the app
   loads instantly on repeat visits, even on flaky 3G networks.
   OpenStreetMap tiles get their own cache-first store so the
   live safety map still renders when the network drops.
   ============================================================ */

// Bumped to v5 because the precache list grew (principal-map.js) and
// static/js/app.js changed. /static/* is served stale-while-revalidate, so
// without a version bump every returning user would be handed the OLD files on
// their first load after deploy and only get the fix on the second. Renaming the
// cache makes the activate handler drop it outright.
const CACHE_NAME = 'safar-e-taleem-v5';
const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/principal-map.js',
  '/static/images/logo.svg',
  '/static/images/favicon.svg',
  '/static/manifest.json',
];

// OpenStreetMap tiles live in their OWN cache: they are immutable per z/x/y,
// so they can be served cache-first and survive app-shell version bumps.
const TILE_CACHE_NAME = 'safar-e-taleem-tiles-v1';
const TILE_HOSTS = [
  'tile.openstreetmap.org',
  'a.tile.openstreetmap.org',
  'b.tile.openstreetmap.org',
  'c.tile.openstreetmap.org',
];
// Panning across a city can pull thousands of tiles; cap the cache so quota
// pressure never evicts the app shell along with it.
const MAX_TILES = 250;

// cache.keys() is insertion-ordered, so the front of the list is the oldest.
function trimTileCache(cache) {
  return cache.keys().then((keys) => {
    if (keys.length <= MAX_TILES) return undefined;
    return keys
      .slice(0, keys.length - MAX_TILES)
      .reduce((chain, key) => chain.then(() => cache.delete(key)), Promise.resolve());
  });
}

// INSTALL — pre-cache static shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        // Silently skip assets that fail (e.g. CDN unreachable during SW install)
      });
    })
  );
  self.skipWaiting();
});

// ACTIVATE — purge old caches on update
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME && key !== TILE_CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// FETCH — network-first for HTML (fresh data), cache-first for static assets
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Static assets: stale-while-revalidate — instant loads from cache, with a
  // background refresh so asset updates (JS/CSS edits) land on the next
  // reload instead of requiring a manual cache-version bump. Offline users
  // still get the last cached copy.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetchPromise = fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        }).catch(() => cached); // offline fallback to stale cache
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Map tiles: cache-first. A tile for a given z/x/y never changes, so the
  // cached copy is always correct — and it is what keeps the safety map
  // readable offline instead of rendering grey squares.
  if (request.method === 'GET' && TILE_HOSTS.includes(url.hostname)) {
    event.respondWith(
      caches.open(TILE_CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          if (cached) return cached;
          return fetch(request).then((response) => {
            if (response.ok) {
              cache.put(request, response.clone()).then(() => trimTileCache(cache));
            }
            return response;
          });
        })
      )
    );
    return;
  }

  // CDN assets (Chart.js, Font Awesome, Leaflet): stale-while-revalidate
  // so the app stays fully functional offline after the first online visit
  const CDN_HOSTS = ['cdn.jsdelivr.net', 'cdnjs.cloudflare.com', 'unpkg.com'];
  if (url.origin !== self.location.origin && CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetchPromise = fetch(request).then((response) => {
          if (response.ok || response.type === 'opaque') {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // HTML pages: network-first (always show fresh dashboard data)
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // API calls: network-only (never cache live fuel prices or auth)
  if (url.pathname.startsWith('/api/')) {
    return; // let the browser handle it normally
  }

  // Everything else: stale-while-revalidate
  event.respondWith(
    caches.match(request).then((cached) => {
      const fetchPromise = fetch(request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      });
      return cached || fetchPromise;
    })
  );
});
