/**
 * Hooks Index
 *
 * Central export for all custom React hooks
 */

// Performance Hooks
export {
  useDebounce,
  useDebouncedCallback,
  useThrottledCallback,
  useIntersectionObserver,
  useLazyLoad,
  useDeepMemo,
  useStableCallback,
  useVirtualList,
  useRenderPerformance,
  useAsyncTiming,
  useWindowSize,
  useScrollPosition,
  usePrevious,
  useHasChanged,
  useIdleCallback,
} from './usePerformance';

// Domain Hooks
export { useVitals } from './useVitals';
export { useAppointments } from './useAppointments';
export { useDailyInsight } from './useDailyInsight';
export { useWaterTracking } from './useWaterTracking';

// Offline/PWA Hooks
export {
  useOfflineStatus,
  OfflineBanner,
  OfflineFallback,
} from './useOfflineStatus';

// UX Enhancement Hooks
export {
  useHaptic,
  useHapticButton,
  type HapticStyle,
  type UseHapticReturn,
} from './useHaptic';

// Pull-to-Refresh Hook
export {
  usePullToRefresh,
  type PullToRefreshOptions,
  type PullToRefreshState,
  type PullToRefreshReturn,
} from './usePullToRefresh';

// Error Handling Hook
export { useErrorHandler } from './useErrorHandler';
