"use strict";

const CACHE = "shadow-video-engine-shell-v3";
const CACHE_PREFIX = "shadow-video-engine-shell-";

const FILES = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.webmanifest",
  "./assets/icons/icon-192.png",
  "./assets/icons/icon-512.png"
];

const SHELL_URLS = new Set(
  FILES.map(file => new URL(file, self.registration.scope).pathname)
);

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;

  if (request.method !== "GET") return;
  if (request.headers.has("Authorization")) return;
  if (request.headers.has("Range")) return;

  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;
  if (url.search) return;
  if (!SHELL_URLS.has(url.pathname)) return;

  event.respondWith(
    caches.open(CACHE).then(async cache => {
      const cached = await cache.match(request);

      if (cached) return cached;

      const response = await fetch(request);

      if (response.ok && response.type === "basic") {
        await cache.put(request, response.clone());
      }

      return response;
    })
  );
});
