/**
 * Safe LocalStorage Utility
 * 
 * Provides type-safe localStorage access with error handling for:
 * - Private browsing mode (localStorage disabled)
 * - Storage quota exceeded
 * - Corrupted/invalid JSON data
 * - Missing items
 */

// ============================================================================
// Types
// ============================================================================

export interface StorageResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// ============================================================================
// Storage Functions
// ============================================================================

/**
 * Safely get an item from localStorage with JSON parsing
 * Returns the fallback value if item doesn't exist or parsing fails
 */
export function safeGetItem<T>(key: string, fallback: T): T {
  try {
    const item = localStorage.getItem(key);
    if (item === null) {
      return fallback;
    }
    return JSON.parse(item) as T;
  } catch (error) {
    console.warn(`[SafeStorage] Failed to read "${key}":`, error);
    return fallback;
  }
}

/**
 * Safely get an item with full result metadata
 */
export function safeGetItemResult<T>(key: string): StorageResult<T> {
  try {
    const item = localStorage.getItem(key);
    if (item === null) {
      return { success: true, data: undefined };
    }
    const data = JSON.parse(item) as T;
    return { success: true, data };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.warn(`[SafeStorage] Failed to read "${key}":`, error);
    return { success: false, error: errorMessage };
  }
}

/**
 * Safely set an item in localStorage with JSON serialization
 * Returns true if successful, false otherwise
 */
export function safeSetItem<T>(key: string, value: T): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    // Handle quota exceeded
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.error(`[SafeStorage] Storage quota exceeded for "${key}"`);
      // Optionally try to clear old data
      tryCleanupStorage();
    } else {
      console.error(`[SafeStorage] Failed to write "${key}":`, error);
    }
    return false;
  }
}

/**
 * Safely remove an item from localStorage
 * Returns true if successful, false otherwise
 */
export function safeRemoveItem(key: string): boolean {
  try {
    localStorage.removeItem(key);
    return true;
  } catch (error) {
    console.error(`[SafeStorage] Failed to remove "${key}":`, error);
    return false;
  }
}

/**
 * Safely clear all localStorage
 * Returns true if successful, false otherwise
 */
export function safeClear(): boolean {
  try {
    localStorage.clear();
    return true;
  } catch (error) {
    console.error('[SafeStorage] Failed to clear storage:', error);
    return false;
  }
}

/**
 * Check if localStorage is available
 */
export function isStorageAvailable(): boolean {
  try {
    const testKey = '__storage_test__';
    localStorage.setItem(testKey, testKey);
    localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get current storage usage (approximate)
 */
export function getStorageUsage(): { used: number; total: number; percentage: number } {
  try {
    let totalSize = 0;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        const value = localStorage.getItem(key);
        if (value) {
          totalSize += key.length + value.length;
        }
      }
    }
    
    // localStorage typically has 5-10MB limit
    const estimatedLimit = 5 * 1024 * 1024; // 5MB
    
    return {
      used: totalSize,
      total: estimatedLimit,
      percentage: (totalSize / estimatedLimit) * 100,
    };
  } catch {
    return { used: 0, total: 0, percentage: 0 };
  }
}

// ============================================================================
// Internal Helpers
// ============================================================================

/**
 * Try to free up storage space by removing old cached data
 */
function tryCleanupStorage(): void {
  try {
    // Remove old cache entries
    const cacheKeys = [
      'daily_insight_cache',
      'api_cache_',
      'temp_',
    ];
    
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key && cacheKeys.some(prefix => key.startsWith(prefix))) {
        localStorage.removeItem(key);
        console.log(`[SafeStorage] Cleaned up: ${key}`);
      }
    }
  } catch (error) {
    console.error('[SafeStorage] Failed to cleanup storage:', error);
  }
}

// ============================================================================
// Specialized Storage Functions
// ============================================================================

/**
 * Get a stored array, always returns an array (empty if not found)
 */
export function safeGetArray<T>(key: string): T[] {
  return safeGetItem<T[]>(key, []);
}

/**
 * Append item to a stored array
 */
export function safeAppendToArray<T>(key: string, item: T, maxLength?: number): boolean {
  const array = safeGetArray<T>(key);
  array.push(item);
  
  // Trim to max length if specified
  if (maxLength && array.length > maxLength) {
    array.splice(0, array.length - maxLength);
  }
  
  return safeSetItem(key, array);
}

/**
 * Update item in a stored array by predicate
 */
export function safeUpdateArrayItem<T>(
  key: string,
  predicate: (item: T) => boolean,
  updater: (item: T) => T
): boolean {
  const array = safeGetArray<T>(key);
  const index = array.findIndex(predicate);
  
  if (index === -1) {
    return false;
  }
  
  array[index] = updater(array[index]);
  return safeSetItem(key, array);
}

/**
 * Remove item from a stored array by predicate
 */
export function safeRemoveFromArray<T>(
  key: string,
  predicate: (item: T) => boolean
): boolean {
  const array = safeGetArray<T>(key);
  const filtered = array.filter(item => !predicate(item));
  
  if (filtered.length === array.length) {
    return false; // Nothing removed
  }
  
  return safeSetItem(key, filtered);
}

// ============================================================================
// Storage Keys (centralized key management)
// ============================================================================

export const STORAGE_KEYS = {
  // User data
  USER_PROFILE: 'user_profile',
  USER_PREFERENCES: 'user_preferences',
  USER_MEDICATIONS: 'user_medications',
  USER_APPOINTMENTS: 'user_appointments',
  USER_NOTIFICATIONS: 'user_notifications',
  
  // Health data
  LAST_ASSESSMENT: 'last_assessment',
  HEALTH_METRICS: 'health_metrics',
  WATER_INTAKE: 'water_intake',
  
  // Device data
  CONNECTED_DEVICES: 'connected_devices',
  
  // Cache
  DAILY_INSIGHT_CACHE: 'daily_insight_cache',
  API_CACHE_PREFIX: 'api_cache_',
  
  // Auth
  AUTH_TOKEN: 'auth_token',
  REFRESH_TOKEN: 'refresh_token',
  
  // Settings
  LANGUAGE: 'language',
  THEME: 'theme',
  CARETAKER_VIEWING: 'caretaker_viewing_id',
} as const;

export type StorageKey = typeof STORAGE_KEYS[keyof typeof STORAGE_KEYS];
