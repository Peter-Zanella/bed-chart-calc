// Keeps the app shell available offline; chart calculations always go to the server.
const CACHE = "jyotisa-v9";
const SHELL = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "icon.svg", "icon-192.png"];
// a new version takes over at once instead of waiting until every tab of the
// installed app is closed (which on a phone may never happen)
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE)
  .then(c => c.addAll(SHELL.map(u => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.includes("/api/")) return;
  // network first so updates show up right away; cache as the offline fallback
  // no-cache: always ask the server (a cheap 304 when unchanged), never the HTTP cache
  e.respondWith(fetch(e.request.url, { cache: "no-cache" }).then(r => {
    const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r;
  }).catch(() => caches.match(e.request)));
});
