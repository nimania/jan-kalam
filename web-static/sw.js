/* جان‌کلام static PWA — network-first so new deploys always show; cache is the
   offline fallback only. Bump V on any shell change to evict old caches. */
const V = "jankalam-static-v3";
const SHELL = ["./", "./index.html", "./styles.css", "./app.js",
  "./manifest.webmanifest", "./icons/icon.svg"];

self.addEventListener("install", e =>
  e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));

self.addEventListener("activate", e =>
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  ));

// Network-first for everything: always try the freshest copy online, fall back
// to cache only when offline. This keeps a frequently-updated news app current.
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request)
      .then(r => {
        const copy = r.clone();
        caches.open(V).then(c => c.put(e.request, copy)).catch(() => {});
        return r;
      })
      .catch(() => caches.match(e.request).then(h => h || caches.match("./index.html")))
  );
});
