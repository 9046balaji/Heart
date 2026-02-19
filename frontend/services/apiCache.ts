/**
 * API Response Caching Service
 *
 * Provides intelligent caching for API responses:
 * - Time-based cache expiration
 * - Cache invalidation patterns
 * - Stale-while-revalidate support
 * - Memory-efficient LRU eviction
 * - Request deduplication
 */

// ============================================================================
// TYPES
// ============================================================================

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
  staleAt: number;
}

interface CacheOptions {
  /** Time to live in milliseconds */
  ttl?: number;
  /** Time until data is considered stale (for SWR pattern) */
  staleTime?: number;
  /** Cache key prefix */
  prefix?: string;
  /** Maximum number of entries */
  maxEntries?: number;
}

interface RequestConfig {
  /** Cache options for this request */
  cache?: CacheOptions;
  /** Skip cache and fetch fresh data */
  skipCache?: boolean;
  /** Force cache refresh */
  forceRefresh?: boolean;
  /** Signal for aborting requests */
  signal?: AbortSignal;
}

// ============================================================================
// LRU CACHE IMPLEMENTATION
// ============================================================================

class LRUCache<K, V> {
  private cache: Map<K, V>;
  private maxSize: number;

  constructor(maxSize: number) {
    this.cache = new Map();
    this.maxSize = maxSize;
  }

  get(key: K): V | undefined {
    const value = this.cache.get(key);
    if (value !== undefined) {
      // Move to end (most recently used)
      this.cache.delete(key);
      this.cache.set(key, value);
    }
    return value;
  }

  set(key: K, value: V): void {
    // Remove existing to update position
    if (this.cache.has(key)) {
      this.cache.delete(key);
    }
    // Evict oldest if at capacity
    else if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
      }
    }
    this.cache.set(key, value);
  }

  delete(key: K): boolean {
    return this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }

  has(key: K): boolean {
    return this.cache.has(key);
  }

  keys(): IterableIterator<K> {
    return this.cache.keys();
  }

  get size(): number {
    return this.cache.size;
  }
}

// ============================================================================
// API CACHE CLASS
// ============================================================================

const DEFAULT_TTL = 5 * 60 * 1000; // 5 minutes
const DEFAULT_STALE_TIME = 2 * 60 * 1000; // 2 minutes
const DEFAULT_MAX_ENTRIES = 100;

class APICache {
  private cache: LRUCache<string, CacheEntry<unknown>>;
  private pendingRequests: Map<string, Promise<unknown>>;
  private defaultOptions: Required<CacheOptions>;

  constructor(options: CacheOptions = {}) {
    this.defaultOptions = {
      ttl: options.ttl ?? DEFAULT_TTL,
      staleTime: options.staleTime ?? DEFAULT_STALE_TIME,
      prefix: options.prefix ?? 'api',
      maxEntries: options.maxEntries ?? DEFAULT_MAX_ENTRIES,
    };

    this.cache = new LRUCache(this.defaultOptions.maxEntries);
    this.pendingRequests = new Map();
  }

  /**
   * Generate cache key from request parameters
   */
  generateKey(endpoint: string, params?: Record<string, unknown>): string {
    const paramString = params
      ? JSON.stringify(params, Object.keys(params).sort())
      : '';
    return `${this.defaultOptions.prefix}:${endpoint}:${paramString}`;
  }

  /**
   * Get cached data
   */
  get<T>(key: string): CacheEntry<T> | null {
    const entry = this.cache.get(key) as CacheEntry<T> | undefined;

    if (!entry) {
      return null;
    }

    // Check if expired
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return entry;
  }

  /**
   * Set cached data
   */
  set<T>(key: string, data: T, options?: CacheOptions): void {
    const now = Date.now();
    const ttl = options?.ttl ?? this.defaultOptions.ttl;
    const staleTime = options?.staleTime ?? this.defaultOptions.staleTime;

    const entry: CacheEntry<T> = {
      data,
      timestamp: now,
      expiresAt: now + ttl,
      staleAt: now + staleTime,
    };

    this.cache.set(key, entry);
  }

  /**
   * Check if cached data is stale
   */
  isStale(key: string): boolean {
    const entry = this.cache.get(key);
    if (!entry) return true;
    return Date.now() > entry.staleAt;
  }

  /**
   * Invalidate cache entries matching pattern
   */
  invalidate(pattern: string | RegExp): number {
    let count = 0;
    const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;

    for (const key of Array.from(this.cache.keys())) {
      if (regex.test(key)) {
        this.cache.delete(key);
        count++;
      }
    }

    return count;
  }

  /**
   * Invalidate all cache entries with a specific prefix
   */
  invalidateByPrefix(prefix: string): number {
    return this.invalidate(new RegExp(`^${this.defaultOptions.prefix}:${prefix}`));
  }

  /**
   * Clear entire cache
   */
  clear(): void {
    this.cache.clear();
    this.pendingRequests.clear();
  }

  /**
   * Fetch with caching and request deduplication
   */
  async fetch<T>(
    endpoint: string,
    fetcher: () => Promise<T>,
    config: RequestConfig = {}
  ): Promise<T> {
    const key = this.generateKey(endpoint);

    // Skip cache if requested
    if (config.skipCache) {
      return fetcher();
    }

    // Check cache
    if (!config.forceRefresh) {
      const cached = this.get<T>(key);
      if (cached) {
        // Return cached data, optionally revalidate in background
        if (this.isStale(key)) {
          // Stale-while-revalidate: return stale data but refresh in background
          this.revalidateInBackground(key, endpoint, fetcher, config);
        }
        return cached.data;
      }
    }

    // Request deduplication: if same request is pending, wait for it
    const pendingKey = key;
    if (this.pendingRequests.has(pendingKey)) {
      return this.pendingRequests.get(pendingKey) as Promise<T>;
    }

    // Make the request
    const request = this.executeRequest(key, fetcher, config);
    this.pendingRequests.set(pendingKey, request);

    try {
      const data = await request;
      return data;
    } finally {
      this.pendingRequests.delete(pendingKey);
    }
  }

  /**
   * Execute request and cache result
   */
  private async executeRequest<T>(
    key: string,
    fetcher: () => Promise<T>,
    config: RequestConfig
  ): Promise<T> {
    const data = await fetcher();
    this.set(key, data, config.cache);
    return data;
  }

  /**
   * Revalidate cache entry in background
   */
  private async revalidateInBackground<T>(
    key: string,
    endpoint: string,
    fetcher: () => Promise<T>,
    config: RequestConfig
  ): Promise<void> {
    const pendingKey = `revalidate:${key}`;

    // Don't revalidate if already in progress
    if (this.pendingRequests.has(pendingKey)) {
      return;
    }

    const revalidation = (async () => {
      try {
        const data = await fetcher();
        this.set(key, data, config.cache);
      } catch (error) {
        // Silently fail background revalidation
        console.warn(`Background revalidation failed for ${endpoint}:`, error);
      }
    })();

    this.pendingRequests.set(pendingKey, revalidation);

    try {
      await revalidation;
    } finally {
      this.pendingRequests.delete(pendingKey);
    }
  }

  /**
   * Get cache statistics
   */
  getStats(): {
    size: number;
    pendingRequests: number;
  } {
    return {
      size: this.cache.size,
      pendingRequests: this.pendingRequests.size,
    };
  }
}

// ============================================================================
// SPECIALIZED HEALTH DATA CACHE
// ============================================================================

/**
 * Health-specific cache with optimized TTLs
 */
class HealthDataCache extends APICache {
  // Different TTLs for different data types
  private static readonly CACHE_CONFIGS: Record<string, CacheOptions> = {
    // Real-time data: short TTL
    vitals: { ttl: 30 * 1000, staleTime: 15 * 1000 }, // 30s / 15s
    heartRate: { ttl: 30 * 1000, staleTime: 15 * 1000 },

    // Semi-static data: medium TTL
    medications: { ttl: 5 * 60 * 1000, staleTime: 2 * 60 * 1000 }, // 5m / 2m
    appointments: { ttl: 5 * 60 * 1000, staleTime: 2 * 60 * 1000 },
    chatHistory: { ttl: 5 * 60 * 1000, staleTime: 2 * 60 * 1000 },

    // Static data: long TTL
    userProfile: { ttl: 30 * 60 * 1000, staleTime: 15 * 60 * 1000 }, // 30m / 15m
    medicalHistory: { ttl: 30 * 60 * 1000, staleTime: 15 * 60 * 1000 },
    drugInfo: { ttl: 60 * 60 * 1000, staleTime: 30 * 60 * 1000 }, // 1h / 30m

    // Analytics: long TTL
    analytics: { ttl: 15 * 60 * 1000, staleTime: 10 * 60 * 1000 }, // 15m / 10m
  };

  constructor() {
    super({ prefix: 'health', maxEntries: 200 });
  }

  /**
   * Get cache config for data type
   */
  getConfigForType(dataType: string): CacheOptions {
    return HealthDataCache.CACHE_CONFIGS[dataType] || {};
  }

  /**
   * Fetch health data with appropriate caching
   */
  async fetchHealthData<T>(
    dataType: string,
    endpoint: string,
    fetcher: () => Promise<T>,
    config?: RequestConfig
  ): Promise<T> {
    const cacheConfig = this.getConfigForType(dataType);
    return this.fetch(endpoint, fetcher, {
      ...config,
      cache: { ...cacheConfig, ...config?.cache },
    });
  }

  /**
   * Invalidate all vitals-related cache
   */
  invalidateVitals(): void {
    this.invalidateByPrefix('vitals');
    this.invalidateByPrefix('heartRate');
  }

  /**
   * Invalidate medication-related cache
   */
  invalidateMedications(): void {
    this.invalidateByPrefix('medications');
  }

  /**
   * Invalidate appointments cache
   */
  invalidateAppointments(): void {
    this.invalidateByPrefix('appointments');
  }
}

// ============================================================================
// SINGLETON INSTANCES
// ============================================================================

// Global API cache instance
export const apiCache = new APICache();

// Health-specific cache instance
export const healthCache = new HealthDataCache();

// ============================================================================
// REACT HOOK
// ============================================================================

import { useState, useEffect, useCallback, useRef } from 'react';

interface UseCachedFetchOptions<T> extends RequestConfig {
  /** Fetch on mount */
  fetchOnMount?: boolean;
  /** Polling interval in ms */
  pollingInterval?: number;
  /** Enable/disable polling */
  enablePolling?: boolean;
  /** Initial data */
  initialData?: T;
  /** Callback on success */
  onSuccess?: (data: T) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

interface UseCachedFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  invalidate: () => void;
}

/**
 * React hook for cached API fetching
 */
export function useCachedFetch<T>(
  endpoint: string,
  fetcher: () => Promise<T>,
  options: UseCachedFetchOptions<T> = {}
): UseCachedFetchResult<T> {
  const {
    fetchOnMount = true,
    pollingInterval,
    enablePolling = false,
    initialData = null,
    onSuccess,
    onError,
    ...requestConfig
  } = options;

  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const mountedRef = useRef(true);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiCache.fetch(endpoint, fetcher, requestConfig);
      if (mountedRef.current) {
        setData(result);
        onSuccess?.(result);
      }
    } catch (err) {
      if (mountedRef.current) {
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        onError?.(error);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [endpoint, fetcher, requestConfig, onSuccess, onError]);

  const invalidate = useCallback(() => {
    const key = apiCache.generateKey(endpoint);
    apiCache.invalidate(key);
  }, [endpoint]);

  // Fetch on mount
  useEffect(() => {
    if (fetchOnMount) {
      fetchData();
    }
  }, [fetchOnMount, fetchData]);

  // Polling
  useEffect(() => {
    if (enablePolling && pollingInterval && pollingInterval > 0) {
      pollingRef.current = setInterval(() => {
        fetchData();
      }, pollingInterval);
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [enablePolling, pollingInterval, fetchData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
    invalidate,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export { APICache, HealthDataCache, LRUCache };
export type { CacheEntry, CacheOptions, RequestConfig, UseCachedFetchOptions, UseCachedFetchResult };
