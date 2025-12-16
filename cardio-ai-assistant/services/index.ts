/**
 * Services Index
 * 
 * Central export for all service modules
 */

// API Services
export * from './apiClient';

// Caching
export {
  apiCache,
  healthCache,
  APICache,
  HealthDataCache,
  LRUCache,
  useCachedFetch,
} from './apiCache';

export type {
  CacheEntry,
  CacheOptions,
  RequestConfig,
  UseCachedFetchOptions,
  UseCachedFetchResult,
} from './apiCache';

// Memory / State Persistence
export * from './memory';

// PDF Export
export {
  pdfExportService,
  PDFExportService,
} from './pdfExport';

export type {
  HealthReport,
  BiometricEntry,
  ChatExport,
} from './pdfExport';

// Service Worker / PWA
export {
  serviceWorker,
  registerServiceWorker,
  unregisterServiceWorker,
  clearCaches,
  skipWaiting,
  cacheHealthData,
  queueOfflineRequest,
  triggerSync,
  getOnlineStatus,
  getRegistration,
  isServiceWorkerActive,
  isServiceWorkerSupported,
} from './serviceWorker';
// Firebase
export { db } from './firebase';
