/**
 * Performance Optimization Hooks
 * 
 * Custom hooks for performance optimization in the Cardio AI Assistant:
 * - Debouncing and throttling
 * - Memoization helpers
 * - Intersection observer for lazy loading
 * - Virtual scrolling support
 * - Performance monitoring
 */

import { 
  useState, 
  useEffect, 
  useCallback, 
  useRef, 
  useMemo,
  DependencyList
} from 'react';

// ============================================================================
// DEBOUNCE & THROTTLE HOOKS
// ============================================================================

/**
 * Debounce a value - only update after delay of inactivity
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Debounced callback - delays function execution
 */
export function useDebouncedCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number,
  deps: DependencyList = []
): T {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedCallback = useCallback(
    ((...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    }) as T,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [callback, delay, ...deps]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return debouncedCallback;
}

/**
 * Throttled callback - limits function execution rate
 */
export function useThrottledCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  limit: number,
  deps: DependencyList = []
): T {
  const lastRan = useRef<number>(Date.now());
  const lastArgs = useRef<Parameters<T> | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const throttledCallback = useCallback(
    ((...args: Parameters<T>) => {
      const now = Date.now();
      lastArgs.current = args;

      if (now - lastRan.current >= limit) {
        callback(...args);
        lastRan.current = now;
      } else {
        // Schedule a trailing call
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }

        timeoutRef.current = setTimeout(() => {
          if (lastArgs.current) {
            callback(...lastArgs.current);
            lastRan.current = Date.now();
          }
        }, limit - (now - lastRan.current));
      }
    }) as T,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [callback, limit, ...deps]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return throttledCallback;
}

// ============================================================================
// INTERSECTION OBSERVER HOOKS
// ============================================================================

interface IntersectionOptions {
  root?: Element | null;
  rootMargin?: string;
  threshold?: number | number[];
  freezeOnceVisible?: boolean;
}

/**
 * Intersection observer hook for lazy loading and visibility detection
 */
export function useIntersectionObserver(
  options: IntersectionOptions = {}
): [React.RefCallback<Element>, boolean, IntersectionObserverEntry | null] {
  const {
    root = null,
    rootMargin = '0px',
    threshold = 0,
    freezeOnceVisible = false,
  } = options;

  const [entry, setEntry] = useState<IntersectionObserverEntry | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const frozen = useRef(false);
  const nodeRef = useRef<Element | null>(null);

  const setRef = useCallback((node: Element | null) => {
    nodeRef.current = node;
  }, []);

  useEffect(() => {
    const node = nodeRef.current;

    if (!node || (freezeOnceVisible && frozen.current)) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setEntry(entry);
        setIsVisible(entry.isIntersecting);

        if (entry.isIntersecting && freezeOnceVisible) {
          frozen.current = true;
          observer.disconnect();
        }
      },
      { root, rootMargin, threshold }
    );

    observer.observe(node);

    return () => {
      observer.disconnect();
    };
  }, [root, rootMargin, threshold, freezeOnceVisible]);

  return [setRef, isVisible, entry];
}

/**
 * Lazy load content when it becomes visible
 */
export function useLazyLoad<T>(
  loader: () => Promise<T>,
  options: IntersectionOptions = {}
): [React.RefCallback<Element>, T | null, boolean, Error | null] {
  const [ref, isVisible] = useIntersectionObserver({
    ...options,
    freezeOnceVisible: true,
  });
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const hasLoaded = useRef(false);

  useEffect(() => {
    if (isVisible && !hasLoaded.current) {
      hasLoaded.current = true;
      setLoading(true);

      loader()
        .then((result) => {
          setData(result);
          setError(null);
        })
        .catch((err) => {
          setError(err instanceof Error ? err : new Error(String(err)));
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isVisible, loader]);

  return [ref, data, loading, error];
}

// ============================================================================
// MEMOIZATION HELPERS
// ============================================================================

/**
 * Deep comparison memoization hook
 */
export function useDeepMemo<T>(factory: () => T, deps: DependencyList): T {
  const ref = useRef<{ deps: DependencyList; value: T } | null>(null);

  if (!ref.current || !deepEqual(deps, ref.current.deps)) {
    ref.current = { deps, value: factory() };
  }

  return ref.current.value;
}

/**
 * Simple deep equality check
 */
function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((item, i) => deepEqual(item, b[i]));
  }
  if (typeof a === 'object' && typeof b === 'object') {
    const keysA = Object.keys(a as object);
    const keysB = Object.keys(b as object);
    if (keysA.length !== keysB.length) return false;
    return keysA.every((key) =>
      deepEqual(
        (a as Record<string, unknown>)[key],
        (b as Record<string, unknown>)[key]
      )
    );
  }
  return false;
}

/**
 * Stable callback reference that always calls the latest function
 */
export function useStableCallback<T extends (...args: unknown[]) => unknown>(
  callback: T
): T {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  return useCallback(
    ((...args: Parameters<T>) => callbackRef.current(...args)) as T,
    []
  );
}

// ============================================================================
// VIRTUAL SCROLLING SUPPORT
// ============================================================================

interface VirtualListConfig {
  itemCount: number;
  itemHeight: number;
  overscan?: number;
}

interface VirtualListResult {
  virtualItems: Array<{ index: number; start: number }>;
  totalHeight: number;
  containerRef: React.RefCallback<HTMLElement>;
  scrollToIndex: (index: number) => void;
}

/**
 * Virtual scrolling hook for large lists
 */
export function useVirtualList(config: VirtualListConfig): VirtualListResult {
  const { itemCount, itemHeight, overscan = 3 } = config;

  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(0);
  const containerRef = useRef<HTMLElement | null>(null);

  const setRef = useCallback((node: HTMLElement | null) => {
    containerRef.current = node;

    if (node) {
      setContainerHeight(node.clientHeight);

      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setContainerHeight(entry.contentRect.height);
        }
      });

      resizeObserver.observe(node);

      const handleScroll = () => {
        setScrollTop(node.scrollTop);
      };

      node.addEventListener('scroll', handleScroll, { passive: true });

      return () => {
        resizeObserver.disconnect();
        node.removeEventListener('scroll', handleScroll);
      };
    }
  }, []);

  const virtualItems = useMemo(() => {
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(
      itemCount - 1,
      Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
    );

    const items: Array<{ index: number; start: number }> = [];
    for (let i = startIndex; i <= endIndex; i++) {
      items.push({
        index: i,
        start: i * itemHeight,
      });
    }

    return items;
  }, [scrollTop, containerHeight, itemCount, itemHeight, overscan]);

  const scrollToIndex = useCallback(
    (index: number) => {
      if (containerRef.current) {
        containerRef.current.scrollTop = index * itemHeight;
      }
    },
    [itemHeight]
  );

  const totalHeight = itemCount * itemHeight;

  return {
    virtualItems,
    totalHeight,
    containerRef: setRef,
    scrollToIndex,
  };
}

// ============================================================================
// PERFORMANCE MONITORING
// ============================================================================

interface PerformanceMetrics {
  renderCount: number;
  lastRenderTime: number;
  averageRenderTime: number;
  peakRenderTime: number;
}

/**
 * Track component render performance
 */
export function useRenderPerformance(componentName: string): PerformanceMetrics {
  const renderCount = useRef(0);
  const renderTimes = useRef<number[]>([]);
  const lastRenderStart = useRef(performance.now());

  // Track render start
  lastRenderStart.current = performance.now();

  useEffect(() => {
    // Calculate render time after paint
    const renderTime = performance.now() - lastRenderStart.current;
    renderCount.current += 1;
    renderTimes.current.push(renderTime);

    // Keep only last 100 renders
    if (renderTimes.current.length > 100) {
      renderTimes.current.shift();
    }

    // Log slow renders in development
    if (process.env.NODE_ENV === 'development' && renderTime > 16) {
      console.warn(
        `[Performance] ${componentName} slow render: ${renderTime.toFixed(2)}ms`
      );
    }
  });

  return useMemo(() => {
    const times = renderTimes.current;
    const lastRenderTime = times[times.length - 1] || 0;
    const averageRenderTime =
      times.length > 0 ? times.reduce((a, b) => a + b, 0) / times.length : 0;
    const peakRenderTime = times.length > 0 ? Math.max(...times) : 0;

    return {
      renderCount: renderCount.current,
      lastRenderTime,
      averageRenderTime,
      peakRenderTime,
    };
  }, []);
}

/**
 * Measure execution time of async operations
 */
export function useAsyncTiming<T extends (...args: unknown[]) => Promise<unknown>>(
  asyncFn: T,
  onTiming?: (duration: number) => void
): [T, number | null] {
  const [lastDuration, setLastDuration] = useState<number | null>(null);

  const wrappedFn = useCallback(
    (async (...args: Parameters<T>) => {
      const start = performance.now();
      try {
        const result = await asyncFn(...args);
        return result;
      } finally {
        const duration = performance.now() - start;
        setLastDuration(duration);
        onTiming?.(duration);
      }
    }) as T,
    [asyncFn, onTiming]
  );

  return [wrappedFn, lastDuration];
}

// ============================================================================
// WINDOW EVENT OPTIMIZATION
// ============================================================================

/**
 * Optimized window resize hook with debouncing
 */
export function useWindowSize(debounceMs = 100): { width: number; height: number } {
  const [size, setSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0,
  });

  const debouncedSetSize = useDebouncedCallback(
    (width: number, height: number) => {
      setSize({ width, height });
    },
    debounceMs
  );

  useEffect(() => {
    const handleResize = () => {
      debouncedSetSize(window.innerWidth, window.innerHeight);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [debouncedSetSize]);

  return size;
}

/**
 * Optimized scroll position hook with throttling
 */
export function useScrollPosition(throttleMs = 100): { x: number; y: number } {
  const [position, setPosition] = useState({
    x: typeof window !== 'undefined' ? window.scrollX : 0,
    y: typeof window !== 'undefined' ? window.scrollY : 0,
  });

  const throttledSetPosition = useThrottledCallback(
    (x: number, y: number) => {
      setPosition({ x, y });
    },
    throttleMs
  );

  useEffect(() => {
    const handleScroll = () => {
      throttledSetPosition(window.scrollX, window.scrollY);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [throttledSetPosition]);

  return position;
}

// ============================================================================
// PREVIOUS VALUE HOOK
// ============================================================================

/**
 * Track previous value for comparison optimization
 */
export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);

  useEffect(() => {
    ref.current = value;
  }, [value]);

  return ref.current;
}

/**
 * Check if value has changed from previous render
 */
export function useHasChanged<T>(value: T): boolean {
  const prevValue = usePrevious(value);
  return prevValue !== value;
}

// ============================================================================
// REQUEST IDLE CALLBACK
// ============================================================================

/**
 * Schedule low-priority work during browser idle time
 */
export function useIdleCallback(
  callback: () => void,
  options?: { timeout?: number }
): void {
  useEffect(() => {
    if ('requestIdleCallback' in window) {
      const id = (window as unknown as { requestIdleCallback: (cb: () => void, opts?: { timeout?: number }) => number }).requestIdleCallback(callback, options);
      return () => {
        (window as unknown as { cancelIdleCallback: (id: number) => void }).cancelIdleCallback(id);
      };
    } else {
      // Fallback for browsers without requestIdleCallback
      const id = setTimeout(callback, 1);
      return () => clearTimeout(id);
    }
  }, [callback, options]);
}

export default {
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
};
