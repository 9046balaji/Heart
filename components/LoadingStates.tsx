/**
 * Loading States Components
 *
 * Higher-order components and utilities for managing loading states
 * with better UX patterns:
 *
 * - Suspense boundaries with fallbacks
 * - Loading overlays
 * - Progress indicators
 * - Retry mechanisms
 */

import React, { Suspense, useState, useEffect, useCallback, ReactNode } from 'react';
import { LoadingSpinner } from './LoadingSpinner';
import {
  Skeleton,
  CardSkeleton,
  ListSkeleton,
  PageSkeleton,
  ChatListSkeleton,
} from './Skeleton';

// ============================================================================
// Loading Overlay
// ============================================================================

interface LoadingOverlayProps {
  isLoading: boolean;
  message?: string;
  blur?: boolean;
  children: ReactNode;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  isLoading,
  message,
  blur = true,
  children,
}) => {
  return (
    <div className="relative">
      {children}
      {isLoading && (
        <div
          className={`
            absolute inset-0
            flex items-center justify-center
            bg-white/80 dark:bg-slate-900/80
            z-10
            ${blur ? 'backdrop-blur-sm' : ''}
          `}
        >
          <LoadingSpinner message={message} />
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Async Boundary (Suspense wrapper with error handling)
// ============================================================================

interface AsyncBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  errorFallback?: ReactNode | ((error: Error, retry: () => void) => ReactNode);
}

interface AsyncBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class AsyncBoundary extends React.Component<AsyncBoundaryProps, AsyncBoundaryState> {
  state: AsyncBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): AsyncBoundaryState {
    return { hasError: true, error };
  }

  retry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (typeof this.props.errorFallback === 'function') {
        return this.props.errorFallback(this.state.error, this.retry);
      }
      return this.props.errorFallback || (
        <ErrorState error={this.state.error} onRetry={this.retry} />
      );
    }

    return (
      <Suspense fallback={this.props.fallback || <LoadingSpinner />}>
        {this.props.children}
      </Suspense>
    );
  }
}

// ============================================================================
// Error State Component
// ============================================================================

interface ErrorStateProps {
  error?: Error | string;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  title = 'Something went wrong',
  onRetry,
  className = '',
}) => {
  const errorMessage = error instanceof Error ? error.message : error;

  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center ${className}`}>
      <div className="w-16 h-16 mb-4 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
        <svg
          className="w-8 h-8 text-red-600 dark:text-red-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
        {title}
      </h3>
      {errorMessage && (
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 max-w-md">
          {errorMessage}
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
};

// ============================================================================
// Empty State Component
// ============================================================================

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center ${className}`}>
      {icon && (
        <div className="w-16 h-16 mb-4 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 max-w-md">
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
};

// ============================================================================
// Content Loader (with automatic skeleton selection)
// ============================================================================

type ContentType = 'card' | 'list' | 'chat' | 'page' | 'custom';

interface ContentLoaderProps {
  isLoading: boolean;
  isEmpty?: boolean;
  error?: Error | string | null;
  type?: ContentType;
  skeletonCount?: number;
  emptyState?: ReactNode;
  children: ReactNode;
  onRetry?: () => void;
  className?: string;
}

export const ContentLoader: React.FC<ContentLoaderProps> = ({
  isLoading,
  isEmpty = false,
  error,
  type = 'card',
  skeletonCount = 3,
  emptyState,
  children,
  onRetry,
  className = '',
}) => {
  // Error state
  if (error) {
    return <ErrorState error={error} onRetry={onRetry} className={className} />;
  }

  // Loading state
  if (isLoading) {
    switch (type) {
      case 'card':
        return (
          <div className={`space-y-4 ${className}`}>
            {Array.from({ length: skeletonCount }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        );
      case 'list':
        return <ListSkeleton items={skeletonCount} className={className} />;
      case 'chat':
        return <ChatListSkeleton messages={skeletonCount} className={className} />;
      case 'page':
        return <PageSkeleton type="dashboard" className={className} />;
      default:
        return <LoadingSpinner />;
    }
  }

  // Empty state
  if (isEmpty) {
    return emptyState || (
      <EmptyState
        title="No data yet"
        description="There's nothing here yet. Get started by adding some data."
        className={className}
      />
    );
  }

  // Content
  return <>{children}</>;
};

// ============================================================================
// Progress Bar
// ============================================================================

interface ProgressBarProps {
  progress: number; // 0-100
  showLabel?: boolean;
  color?: 'blue' | 'green' | 'red' | 'yellow';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  showLabel = false,
  color = 'blue',
  size = 'md',
  className = '',
}) => {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  const colorClasses = {
    blue: 'bg-blue-600',
    green: 'bg-green-600',
    red: 'bg-red-600',
    yellow: 'bg-yellow-500',
  };

  const sizeClasses = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  };

  return (
    <div className={className}>
      <div className={`w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`${colorClasses[color]} ${sizeClasses[size]} rounded-full transition-all duration-300`}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-slate-600 dark:text-slate-400 mt-1">
          {clampedProgress}%
        </span>
      )}
    </div>
  );
};

// ============================================================================
// Indeterminate Progress
// ============================================================================

interface IndeterminateProgressProps {
  className?: string;
}

export const IndeterminateProgress: React.FC<IndeterminateProgressProps> = ({
  className = '',
}) => {
  return (
    <div className={`w-full h-1 bg-slate-200 dark:bg-slate-700 overflow-hidden ${className}`}>
      <div className="h-full bg-blue-600 animate-[indeterminate_1.5s_ease-in-out_infinite] origin-left" />
    </div>
  );
};

// Add to tailwind config:
// keyframes: { indeterminate: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(100%)' } } }

// ============================================================================
// Skeleton Wrapper (HOC)
// ============================================================================

interface WithSkeletonOptions {
  type?: ContentType;
  count?: number;
}

export function withSkeleton<P extends object>(
  Component: React.ComponentType<P>,
  options: WithSkeletonOptions = {}
) {
  const { type = 'card', count = 1 } = options;

  return function SkeletonWrapped(props: P & { isLoading?: boolean }) {
    const { isLoading, ...rest } = props;

    if (isLoading) {
      switch (type) {
        case 'card':
          return (
            <>
              {Array.from({ length: count }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </>
          );
        case 'list':
          return <ListSkeleton items={count} />;
        default:
          return <Skeleton height={100} />;
      }
    }

    return <Component {...(rest as P)} />;
  };
}

// ============================================================================
// useLoadingState Hook
// ============================================================================

interface UseLoadingStateOptions {
  minimumLoadingTime?: number; // Prevent flash of loading state
  initialLoading?: boolean;
}

export function useLoadingState(options: UseLoadingStateOptions = {}) {
  const { minimumLoadingTime = 0, initialLoading = false } = options;
  const [isLoading, setIsLoading] = useState(initialLoading);
  const [startTime, setStartTime] = useState<number | null>(null);

  const startLoading = useCallback(() => {
    setIsLoading(true);
    setStartTime(Date.now());
  }, []);

  const stopLoading = useCallback(() => {
    if (minimumLoadingTime > 0 && startTime) {
      const elapsed = Date.now() - startTime;
      const remaining = minimumLoadingTime - elapsed;

      if (remaining > 0) {
        setTimeout(() => setIsLoading(false), remaining);
        return;
      }
    }
    setIsLoading(false);
    setStartTime(null);
  }, [minimumLoadingTime, startTime]);

  return {
    isLoading,
    startLoading,
    stopLoading,
  };
}

// ============================================================================
// useAsyncData Hook (with loading/error states)
// ============================================================================

interface UseAsyncDataOptions<T> {
  initialData?: T;
  fetchOnMount?: boolean;
}

interface UseAsyncDataResult<T> {
  data: T | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useAsyncData<T>(
  fetchFn: () => Promise<T>,
  options: UseAsyncDataOptions<T> = {}
): UseAsyncDataResult<T> {
  const { initialData, fetchOnMount = true } = options;
  const [data, setData] = useState<T | undefined>(initialData);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e : new Error('Unknown error'));
    } finally {
      setIsLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    if (fetchOnMount) {
      fetchData();
    }
  }, [fetchOnMount]); // eslint-disable-line

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}

// ============================================================================
// Exports
// ============================================================================

export {
  // Re-export skeletons
  Skeleton,
  CardSkeleton,
  ListSkeleton,
  PageSkeleton,
  ChatListSkeleton,
} from './Skeleton';
