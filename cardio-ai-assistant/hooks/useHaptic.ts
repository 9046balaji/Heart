/**
 * useHaptic Hook - Haptic Feedback for Mobile Devices
 * 
 * Provides tactile feedback using the Vibration API for enhanced mobile UX.
 * Falls back silently on unsupported devices.
 * 
 * Usage:
 * ```tsx
 * const { trigger, isSupported } = useHaptic();
 * 
 * const handleButtonClick = () => {
 *   trigger('light');
 *   // ... rest of your logic
 * };
 * ```
 * 
 * @see https://developer.mozilla.org/en-US/docs/Web/API/Vibration_API
 */

import { useCallback, useMemo } from 'react';

// ============================================================================
// Types
// ============================================================================

export type HapticStyle = 'light' | 'medium' | 'heavy' | 'success' | 'warning' | 'error' | 'selection';

export interface HapticOptions {
  /** Whether haptics are enabled (can be controlled by user preference) */
  enabled?: boolean;
}

export interface UseHapticReturn {
  /** Trigger haptic feedback */
  trigger: (style?: HapticStyle) => void;
  /** Whether the Vibration API is supported */
  isSupported: boolean;
  /** Trigger a custom vibration pattern */
  pattern: (durations: number[]) => void;
  /** Predefined patterns for common interactions */
  patterns: {
    tap: () => void;
    doubleTap: () => void;
    longPress: () => void;
    notification: () => void;
    heartbeat: () => void;
  };
}

// ============================================================================
// Vibration Patterns (in milliseconds)
// ============================================================================

const HAPTIC_DURATIONS: Record<HapticStyle, number | number[]> = {
  light: 10,
  medium: 20,
  heavy: 30,
  success: [10, 50, 20],      // Two quick taps
  warning: [30, 50, 30],      // Two medium taps
  error: [50, 30, 50, 30, 50], // Three strong taps
  selection: 5,               // Very light tap
};

// Pre-defined patterns for common interactions
const PATTERNS = {
  tap: [10],
  doubleTap: [10, 50, 10],
  longPress: [5, 10, 5, 10, 30],
  notification: [20, 100, 20, 100, 50],
  heartbeat: [50, 100, 50, 300],
};

// ============================================================================
// Hook Implementation
// ============================================================================

export const useHaptic = (options: HapticOptions = {}): UseHapticReturn => {
  const { enabled = true } = options;

  // Check if Vibration API is supported
  const isSupported = useMemo(() => {
    return typeof navigator !== 'undefined' && 'vibrate' in navigator;
  }, []);

  // Main trigger function
  const trigger = useCallback((style: HapticStyle = 'light') => {
    if (!enabled || !isSupported) return;

    try {
      const duration = HAPTIC_DURATIONS[style];
      if (Array.isArray(duration)) {
        navigator.vibrate(duration);
      } else {
        navigator.vibrate(duration);
      }
    } catch (error) {
      // Silently fail - haptics are non-critical
      console.debug('Haptic feedback failed:', error);
    }
  }, [enabled, isSupported]);

  // Custom pattern function
  const pattern = useCallback((durations: number[]) => {
    if (!enabled || !isSupported) return;

    try {
      navigator.vibrate(durations);
    } catch (error) {
      console.debug('Haptic pattern failed:', error);
    }
  }, [enabled, isSupported]);

  // Predefined pattern triggers
  const patterns = useMemo(() => ({
    tap: () => pattern(PATTERNS.tap),
    doubleTap: () => pattern(PATTERNS.doubleTap),
    longPress: () => pattern(PATTERNS.longPress),
    notification: () => pattern(PATTERNS.notification),
    heartbeat: () => pattern(PATTERNS.heartbeat),
  }), [pattern]);

  return {
    trigger,
    isSupported,
    pattern,
    patterns,
  };
};

// ============================================================================
// Utility Hook - useHapticButton
// ============================================================================

/**
 * Hook for adding haptic feedback to button interactions
 * 
 * Usage:
 * ```tsx
 * const buttonProps = useHapticButton('medium');
 * return <button {...buttonProps}>Click me</button>;
 * ```
 */
export const useHapticButton = (style: HapticStyle = 'light') => {
  const { trigger } = useHaptic();

  return useMemo(() => ({
    onClick: (e: React.MouseEvent) => {
      trigger(style);
    },
    onTouchStart: () => {
      trigger('selection');
    },
  }), [trigger, style]);
};

// ============================================================================
// Default Export
// ============================================================================

export default useHaptic;
