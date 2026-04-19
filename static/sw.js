const CACHE_NAME = "stockiepilot-v4";
const APP_SHELL = [
  "/",
  "/dashboard/",
  "/sales/create/",
  "/offline/",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/js/pwa-install.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const request = event.request;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/offline/") || caches.match("/"))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;

      return fetch(request)
        .then((response) => {
          if (!response || response.status !== 200) return response;

          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned));
          return response;
        })
        .catch(() => caches.match("/"));
    })
  );
});