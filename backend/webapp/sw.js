/* جان‌کلام service worker — offline-capable PWA.
   App shell: cache-first. API: network-first with cache fallback. */
const VERSION = "jankalam-v1";
const SHELL = [
  "/", "/index.html", "/styles.css", "/app.js",
  "/manifest.webmanifest", "/icons/icon.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return; // never cache writes (follows, ask)

  if (url.pathname.startsWith("/api/")) {
    // network-first so news stays fresh; fall back to last cached response offline
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // app shell: cache-first
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
