// Service worker for Ironman Pipeline PWA
// Strategy: cache-first for static assets, network-first for /api/* routes.

const CACHE = "ironman-v1";

const APP_SHELL = [
  "/",
  "/index.html",
];

// ── Install: cache the app shell ─────────────────────────────────────────────

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// ── Activate: purge old cache versions ───────────────────────────────────────

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch: route requests ─────────────────────────────────────────────────────

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API calls: network-first so the dashboard always shows fresh data.
  // Fall back to a JSON error payload when offline.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: "offline", message: "No network — cached data unavailable for API routes." }),
          { headers: { "Content-Type": "application/json" } }
        )
      )
    );
    return;
  }

  // Static assets: cache-first, network fallback, then cache response.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((response) => {
          // Only cache same-origin successful responses.
          if (
            response.ok &&
            response.type === "basic" &&
            request.method === "GET"
          ) {
            const clone = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        })
    )
  );
});
