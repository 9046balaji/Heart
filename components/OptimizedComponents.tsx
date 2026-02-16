/**
 * Optimized Components
 *
 * Higher-order components and wrappers for performance optimization:
 * - React.memo with custom comparison
 * - Code splitting with React.lazy
 * - Render optimization patterns
 */

import React, {
  memo,
  lazy,
  Suspense,
  ComponentType,
  ReactNode,
  useMemo,
  useCallback,
  useState,
  useEffect
} from 'react';

// ============================================================================
// TYPES
// ============================================================================

interface OptimizedProps {
  children?: ReactNode;
}

type CompareFunction<P> = (prevProps: P, nextProps: P) => boolean;

// ============================================================================
// MEMOIZATION HELPERS
// ============================================================================

/**
 * Deep comparison memo wrapper
 * Use for components with complex prop objects
 */
export function memoDeep<P extends object>(
  Component: ComponentType<P>,
  displayName?: string
): React.MemoExoticComponent<ComponentType<P>> {
  const MemoizedComponent = memo(Component, deepCompare);
  MemoizedComponent.displayName = displayName || `MemoDeep(${Component.displayName || Component.name})`;
  return MemoizedComponent;
}

/**
 * Deep equality comparison for memo
 */
function deepCompare<P extends object>(prevProps: P, nextProps: P): boolean {
  const prevKeys = Object.keys(prevProps) as (keyof P)[];
  const nextKeys = Object.keys(nextProps) as (keyof P)[];

  if (prevKeys.length !== nextKeys.length) {
    return false;
  }

  for (const key of prevKeys) {
    const prevValue = prevProps[key];
    const nextValue = nextProps[key];

    if (typeof prevValue === 'function' && typeof nextValue === 'function') {
      // Skip function comparison (assume stable references via useCallback)
      continue;
    }

    if (typeof prevValue === 'object' && prevValue !== null) {
      if (!deepEqual(prevValue, nextValue)) {
        return false;
      }
    } else if (prevValue !== nextValue) {
      return false;
    }
  }

  return true;
}

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
    return keysA.every(key =>
      deepEqual(
        (a as Record<string, unknown>)[key],
        (b as Record<string, unknown>)[key]
      )
    );
  }
  return false;
}

/**
 * Selective memo - only compare specific props
 */
export function memoSelective<P extends object>(
  Component: ComponentType<P>,
  compareKeys: (keyof P)[],
  displayName?: string
): React.MemoExoticComponent<ComponentType<P>> {
  const compare: CompareFunction<P> = (prev, next) => {
    for (const key of compareKeys) {
      if (prev[key] !== next[key]) {
        return false;
      }
    }
    return true;
  };

  const MemoizedComponent = memo(Component, compare);
  MemoizedComponent.displayName = displayName || `MemoSelective(${Component.displayName || Component.name})`;
  return MemoizedComponent;
}

// ============================================================================
// CODE SPLITTING HELPERS
// ============================================================================

interface LazyLoadOptions {
  fallback?: ReactNode;
  preload?: boolean;
}

/**
 * Create a lazy-loaded component with custom fallback
 */
export function lazyWithFallback<P extends object>(
  factory: () => Promise<{ default: ComponentType<P> }>,
  options: LazyLoadOptions = {}
): React.FC<P> {
  const LazyComponent = lazy(factory);
  const { fallback = <DefaultLoadingFallback /> } = options;

  // Store the factory for preloading
  const preloadPromise = options.preload ? factory() : null;

  const WrappedComponent: React.FC<P> = (props) => (
    <Suspense fallback={fallback}>
      <LazyComponent {...props} />
    </Suspense>
  );

  // Add preload method
  (WrappedComponent as unknown as { preload: () => Promise<{ default: ComponentType<P> }> }).preload = factory;

  return WrappedComponent;
}

/**
 * Default loading fallback component
 */
const DefaultLoadingFallback: React.FC = () => (
  <div className="flex items-center justify-center p-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500"></div>
  </div>
);

/**
 * Lazy load screens with route-based code splitting
 *
 * NOTE: These lazy imports are configured for screens that will be implemented.
 * As screens are added, uncomment the corresponding lazy loader.
 *
 * Usage:
 * ```tsx
 * import { LazyScreens } from './components/OptimizedComponents';
 * ```
 */

// Placeholder for future screens - implement as screens are created
// Example pattern for when screens are added:
// const DashboardScreen = lazyWithFallback(() => import('../screens/Dashboard'), { preload: true });

export const LazyScreens = {

  // Future screens (add as implemented):
  // Dashboard: DashboardScreen,
  // Chat: ChatScreen,
  // Vitals: VitalsScreen,
  // Medications: MedicationsScreen,
  // Appointments: AppointmentsScreen,
  // Settings: SettingsScreen,
};

/**
 * Preload screens that user is likely to navigate to
 */
export function preloadScreens(screens: (keyof typeof LazyScreens)[]): void {
  screens.forEach(screen => {
    const component = LazyScreens[screen] as unknown as { preload?: () => Promise<unknown> };
    component.preload?.();
  });
}

// ============================================================================
// RENDER OPTIMIZATION COMPONENTS
// ============================================================================

/**
 * Prevents re-renders of children when parent updates
 */
export const RenderGuard: React.FC<OptimizedProps & { shouldUpdate?: boolean }> = memo(
  ({ children, shouldUpdate = false }) => {
    return <>{children}</>;
  },
  (prev, next) => !next.shouldUpdate
);

RenderGuard.displayName = 'RenderGuard';

/**
 * Only renders children after specified delay
 * Useful for content that's expensive to render but not immediately visible
 */
export const DeferredRender: React.FC<OptimizedProps & { delay?: number }> = ({
  children,
  delay = 0,
}) => {
  const [shouldRender, setShouldRender] = useState(delay === 0);

  useEffect(() => {
    if (delay > 0) {
      const timer = setTimeout(() => setShouldRender(true), delay);
      return () => clearTimeout(timer);
    }
  }, [delay]);

  if (!shouldRender) {
    return null;
  }

  return <>{children}</>;
};

/**
 * Renders children only when visible in viewport
 */
export const ViewportRender: React.FC<OptimizedProps & {
  rootMargin?: string;
  placeholder?: ReactNode;
}> = ({
  children,
  rootMargin = '100px',
  placeholder = <div className="h-32 animate-pulse bg-gray-100 rounded" />,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [hasRendered, setHasRendered] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasRendered) {
          setIsVisible(true);
          setHasRendered(true);
          observer.disconnect();
        }
      },
      { rootMargin }
    );

    observer.observe(element);

    return () => observer.disconnect();
  }, [rootMargin, hasRendered]);

  return (
    <div ref={ref}>
      {isVisible ? children : placeholder}
    </div>
  );
};

// ============================================================================
// OPTIMIZED LIST COMPONENTS
// ============================================================================

interface ListItemProps<T> {
  item: T;
  index: number;
}

interface OptimizedListProps<T> {
  items: T[];
  renderItem: (props: ListItemProps<T>) => ReactNode;
  keyExtractor: (item: T, index: number) => string;
  className?: string;
  itemClassName?: string;
}

/**
 * Optimized list with memoized items
 */
export function OptimizedList<T>({
  items,
  renderItem,
  keyExtractor,
  className = '',
  itemClassName = '',
}: OptimizedListProps<T>): React.ReactElement {
  const memoizedRender = useCallback(renderItem, [renderItem]);

  const listItems = useMemo(() =>
    items.map((item, index) => (
      <MemoizedListItem
        key={keyExtractor(item, index)}
        item={item}
        index={index}
        render={memoizedRender}
        className={itemClassName}
      />
    )),
    [items, keyExtractor, memoizedRender, itemClassName]
  );

  return (
    <div className={className}>
      {listItems}
    </div>
  );
}

interface MemoizedListItemProps<T> {
  item: T;
  index: number;
  render: (props: ListItemProps<T>) => ReactNode;
  className?: string;
}

const MemoizedListItem = memo(function MemoizedListItem<T>({
  item,
  index,
  render,
  className = '',
}: MemoizedListItemProps<T>) {
  return (
    <div className={className}>
      {render({ item, index })}
    </div>
  );
}) as <T>(props: MemoizedListItemProps<T>) => React.ReactElement;

// ============================================================================
// WINDOWED LIST FOR LARGE DATASETS
// ============================================================================

interface WindowedListProps<T> {
  items: T[];
  itemHeight: number;
  overscan?: number;
  renderItem: (props: ListItemProps<T>) => ReactNode;
  keyExtractor: (item: T, index: number) => string;
  className?: string;
  containerHeight?: number;
}

/**
 * Virtualized list for large datasets
 */
export function WindowedList<T>({
  items,
  itemHeight,
  overscan = 3,
  renderItem,
  keyExtractor,
  className = '',
  containerHeight = 400,
}: WindowedListProps<T>): React.ReactElement {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const { startIndex, endIndex, visibleItems } = useMemo(() => {
    const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const end = Math.min(
      items.length - 1,
      Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
    );

    return {
      startIndex: start,
      endIndex: end,
      visibleItems: items.slice(start, end + 1).map((item, i) => ({
        item,
        index: start + i,
        offset: (start + i) * itemHeight,
      })),
    };
  }, [scrollTop, itemHeight, containerHeight, overscan, items]);

  const totalHeight = items.length * itemHeight;

  return (
    <div
      ref={containerRef}
      className={`overflow-auto ${className}`}
      style={{ height: containerHeight }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        {visibleItems.map(({ item, index, offset }) => (
          <div
            key={keyExtractor(item, index)}
            style={{
              position: 'absolute',
              top: offset,
              left: 0,
              right: 0,
              height: itemHeight,
            }}
          >
            {renderItem({ item, index })}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// STABLE CHILDREN WRAPPER
// ============================================================================

/**
 * Wraps children to prevent re-renders from parent state changes
 * Use when children don't depend on frequently changing parent state
 */
export const StableChildren: React.FC<{ children: ReactNode }> = memo(
  ({ children }) => <>{children}</>,
  () => true // Never re-render based on props
);

StableChildren.displayName = 'StableChildren';

// ============================================================================
// PERFORMANCE BOUNDARY
// ============================================================================

interface PerformanceBoundaryProps extends OptimizedProps {
  /** Maximum render time before logging warning (ms) */
  warnThreshold?: number;
  /** Component name for logging */
  componentName?: string;
}

/**
 * Monitors render performance of children
 */
export const PerformanceBoundary: React.FC<PerformanceBoundaryProps> = ({
  children,
  warnThreshold = 16, // 60fps frame budget
  componentName = 'Unknown',
}) => {
  const renderStart = React.useRef(performance.now());

  // Update render start time
  renderStart.current = performance.now();

  useEffect(() => {
    const renderTime = performance.now() - renderStart.current;

    if (process.env.NODE_ENV === 'development' && renderTime > warnThreshold) {
      console.warn(
        `[Performance] ${componentName} render took ${renderTime.toFixed(2)}ms ` +
        `(threshold: ${warnThreshold}ms)`
      );
    }
  });

  return <>{children}</>;
};

// ============================================================================
// EXPORTS
// ============================================================================

export {
  DefaultLoadingFallback,
};

export default {
  memoDeep,
  memoSelective,
  lazyWithFallback,
  LazyScreens,
  preloadScreens,
  RenderGuard,
  DeferredRender,
  ViewportRender,
  OptimizedList,
  WindowedList,
  StableChildren,
  PerformanceBoundary,
};
