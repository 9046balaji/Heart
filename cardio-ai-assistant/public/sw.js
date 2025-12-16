/**
 * Service Worker for Cardio AI Assistant
 * 
 * Provides offline support and caching for the PWA
 * 
 * Features:
 * - Cache-first strategy for static assets
 * - Network-first strategy for API calls
 * - Offline fallback for critical pages
 */

const CACHE_NAME = 'cardio-ai-v1';
const STATIC_CACHE = 'cardio-static-v1';
const DYNAMIC_CACHE = 'cardio-dynamic-v1';

// Assets to pre-cache for offline use
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
];

// API routes to cache with network-first
const API_ROUTES = [
  '/api/health',
  '/api/nlp',
  '/api/memory',
  '/api/rag',
];

// Install event - pre-cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Pre-caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('[SW] Static assets cached');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('[SW] Failed to cache static assets:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => {
              // Remove old cache versions
              return name.startsWith('cardio-') && 
                     name !== STATIC_CACHE && 
                     name !== DYNAMIC_CACHE;
            })
            .map((name) => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        console.log('[SW] Service Worker activated');
        return self.clients.claim();
      })
  );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Skip chrome-extension and other non-http(s) requests
  if (!url.protocol.startsWith('http')) {
    return;
  }
  
  // Handle API requests with network-first strategy
  if (isAPIRequest(url.pathname)) {
    event.respondWith(networkFirstStrategy(event.request));
    return;
  }
  
  // Handle static assets with cache-first strategy
  event.respondWith(cacheFirstStrategy(event.request));
});

// Check if request is an API call
function isAPIRequest(pathname) {
  return API_ROUTES.some(route => pathname.startsWith(route));
}

// Cache-first strategy (for static assets)
async function cacheFirstStrategy(request) {
  try {
    // Try cache first
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // If not in cache, fetch from network
    const networkResponse = await fetch(request);
    
    // Cache the response for future use
    if (networkResponse.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('[SW] Cache-first strategy failed:', error);
    
    // Return offline fallback if available
    return caches.match('/offline.html') || new Response(
      '<h1>Offline</h1><p>Please check your internet connection.</p>',
      { headers: { 'Content-Type': 'text/html' } }
    );
  }
}

// Network-first strategy (for API calls)
async function networkFirstStrategy(request) {
  try {
    // Try network first
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('[SW] Network-first strategy failed:', error);
    
    // Fall back to cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('[SW] Serving cached API response');
      return cachedResponse;
    }
    
    // Return error response if no cache
    return new Response(
      JSON.stringify({ 
        error: 'offline', 
        message: 'You are currently offline. This data is not available.' 
      }),
      { 
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Message handler for cache management from main app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then((names) => {
      names.forEach((name) => caches.delete(name));
    });
  }
  
  if (event.data && event.data.type === 'CACHE_HEALTH_DATA') {
    // Cache health data for offline access
    const cache = caches.open(DYNAMIC_CACHE).then((cache) => {
      cache.put('/api/health/data', new Response(
        JSON.stringify(event.data.payload),
        { headers: { 'Content-Type': 'application/json' } }
      ));
    });
  }
});

// Background sync for deferred actions (when back online)
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync:', event.tag);
  
  if (event.tag === 'sync-health-data') {
    event.waitUntil(syncHealthData());
  }
});

// Sync queued health data when back online
async function syncHealthData() {
  try {
    const cache = await caches.open(DYNAMIC_CACHE);
    const queuedData = await cache.match('/offline-queue');
    
    if (queuedData) {
      const data = await queuedData.json();
      
      // Send queued data to server
      for (const item of data) {
        await fetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: JSON.stringify(item.body),
        });
      }
      
      // Clear the queue
      await cache.delete('/offline-queue');
      console.log('[SW] Synced offline data');
    }
  } catch (error) {
    console.error('[SW] Failed to sync offline data:', error);
  }
}

console.log('[SW] Service Worker script loaded');
