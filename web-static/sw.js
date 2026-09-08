/* جان‌کلام static PWA — cache shell + last-seen data for offline. */
const V = "jankalam-static-v1";
const SHELL = ["./", "./index.html", "./styles.css", "./app.js",
  "./manifest.webmanifest", "./icons/icon.svg"];

self.addEventListener("install", e =>
  e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e =>
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.pathname.includes("/data/")) {
    // network-first for news data, fall back to cache offline
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(V).then(x => x.put(e.request, c)); return r; }).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then(h => h || fetch(e.request)));
});
