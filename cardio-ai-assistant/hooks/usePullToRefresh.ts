/**
 * usePullToRefresh Hook
 *
 * Provides pull-to-refresh functionality with haptic feedback integration.
 * Designed for mobile-first healthcare applications.
 *
 * @author Cardio AI Team
 * @version 1.0.0
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { useHaptic } from './useHaptic';

export interface PullToRefreshOptions {
  /** Minimum pull distance to trigger refresh (pixels) */
  threshold?: number;
  /** Maximum pull distance (pixels) */
  maxPull?: number;
  /** Resistance factor (0-1, lower = more resistance) */
  resistance?: number;
  /** Enable haptic feedback on trigger */
  hapticFeedback?: boolean;
  /** Callback when refresh is triggered */
  onRefresh: () => Promise<void>;
  /** Disable pull-to-refresh */
  disabled?: boolean;
}

export interface PullToRefreshState {
  /** Current pull distance */
  pullDistance: number;
  /** Whether refresh is in progress */
  isRefreshing: boolean;
  /** Whether pull threshold has been reached */
  isPulling: boolean;
  /** Progress percentage (0-100) */
  progress: number;
}

export interface PullToRefreshReturn extends PullToRefreshState {
  /** Ref to attach to scrollable container */
  containerRef: React.RefObject<HTMLDivElement>;
  /** Ref to attach to pull indicator */
  indicatorRef: React.RefObject<HTMLDivElement>;
  /** Manual trigger for refresh */
  triggerRefresh: () => Promise<void>;
  /** Reset the pull state */
  reset: () => void;
}

export function usePullToRefresh(options: PullToRefreshOptions): PullToRefreshReturn {
  const {
    threshold = 80,
    maxPull = 150,
    resistance = 0.5,
    hapticFeedback = true,
    onRefresh,
    disabled = false,
  } = options;

  const [state, setState] = useState<PullToRefreshState>({
    pullDistance: 0,
    isRefreshing: false,
    isPulling: false,
    progress: 0,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLDivElement>(null);
  const startY = useRef<number>(0);
  const currentY = useRef<number>(0);
  const isAtTop = useRef<boolean>(true);
  const hasTriggeredHaptic = useRef<boolean>(false);
  const rafId = useRef<number | null>(null);

  const { trigger: hapticTrigger } = useHaptic();

  // Calculate pull distance with resistance
  const calculatePullDistance = useCallback((deltaY: number): number => {
    if (deltaY <= 0) return 0;

    // Apply resistance formula: distance = maxPull * (1 - e^(-resistance * deltaY / maxPull))
    const resistedPull = maxPull * (1 - Math.exp(-resistance * deltaY / maxPull));
    return Math.min(resistedPull, maxPull);
  }, [maxPull, resistance]);

  // Handle touch start
  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (disabled || state.isRefreshing) return;

    const container = containerRef.current;
    if (!container) return;

    // Check if at top of scrollable area
    isAtTop.current = container.scrollTop <= 0;

    if (isAtTop.current) {
      startY.current = e.touches[0].clientY;
      hasTriggeredHaptic.current = false;
    }
  }, [disabled, state.isRefreshing]);

  // Handle touch move with RAF throttling for 60fps
  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (disabled || state.isRefreshing || !isAtTop.current) return;

    // RAF-based throttling for smooth performance
    if (rafId.current) return;

    rafId.current = requestAnimationFrame(() => {
      currentY.current = e.touches[0].clientY;
      const deltaY = currentY.current - startY.current;

      if (deltaY > 0) {
        // Prevent default scroll when pulling down at top
        e.preventDefault();

        const pullDistance = calculatePullDistance(deltaY);
        const progress = Math.min((pullDistance / threshold) * 100, 100);

        // Trigger haptic when threshold is first reached
        if (progress >= 100 && !hasTriggeredHaptic.current && hapticFeedback) {
          hapticTrigger('light');
          hasTriggeredHaptic.current = true;
        }

        setState(prev => ({
          ...prev,
          pullDistance,
          isPulling: true,
          progress,
        }));
      }

      rafId.current = null;
    });
  }, [disabled, state.isRefreshing, calculatePullDistance, threshold, hapticFeedback, hapticTrigger]);

  // Handle touch end
  const handleTouchEnd = useCallback(async () => {
    if (disabled || state.isRefreshing) return;

    // Cancel any pending RAF
    if (rafId.current) {
      cancelAnimationFrame(rafId.current);
      rafId.current = null;
    }

    const { pullDistance } = state;

    if (pullDistance >= threshold) {
      // Trigger refresh
      setState(prev => ({
        ...prev,
        isRefreshing: true,
        pullDistance: threshold, // Hold at threshold during refresh
      }));

      if (hapticFeedback) {
        hapticTrigger('medium');
      }

      try {
        await onRefresh();
      } catch (error) {
        console.error('Pull-to-refresh error:', error);
      } finally {
        // Reset after refresh completes
        setState({
          pullDistance: 0,
          isRefreshing: false,
          isPulling: false,
          progress: 0,
        });
      }
    } else {
      // Reset without refresh (animate back to 0)
      setState({
        pullDistance: 0,
        isRefreshing: false,
        isPulling: false,
        progress: 0,
      });
    }
  }, [disabled, state, threshold, hapticFeedback, hapticTrigger, onRefresh]);

  // Manual trigger for refresh
  const triggerRefresh = useCallback(async () => {
    if (state.isRefreshing) return;

    setState(prev => ({ ...prev, isRefreshing: true }));

    if (hapticFeedback) {
      hapticTrigger('medium');
    }

    try {
      await onRefresh();
    } finally {
      setState({
        pullDistance: 0,
        isRefreshing: false,
        isPulling: false,
        progress: 0,
      });
    }
  }, [state.isRefreshing, hapticFeedback, hapticTrigger, onRefresh]);

  // Reset function
  const reset = useCallback(() => {
    if (rafId.current) {
      cancelAnimationFrame(rafId.current);
      rafId.current = null;
    }
    setState({
      pullDistance: 0,
      isRefreshing: false,
      isPulling: false,
      progress: 0,
    });
  }, []);

  // Attach event listeners
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', handleTouchMove, { passive: false });
    container.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
      container.removeEventListener('touchend', handleTouchEnd);

      // Cleanup RAF on unmount
      if (rafId.current) {
        cancelAnimationFrame(rafId.current);
      }
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);

  return {
    ...state,
    containerRef,
    indicatorRef,
    triggerRefresh,
    reset,
  };
}

export default usePullToRefresh;
