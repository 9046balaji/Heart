/**
 * useHaptic Hook - Haptic Feedback for Mobile Devices
 *
 * Uses @capacitor/haptics for native Android haptic feedback when available.
 * Falls back to the Web Vibration API, then silently fails on unsupported devices.
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
 */

import { useCallback, useMemo, useRef, useEffect } from 'react';

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
// Vibration Patterns (in milliseconds) — web fallback only
// ============================================================================

const HAPTIC_DURATIONS: Record<HapticStyle, number | number[]> = {
  light: 10,
  medium: 20,
  heavy: 30,
  success: [10, 50, 20],
  warning: [30, 50, 30],
  error: [50, 30, 50, 30, 50],
  selection: 5,
};

const PATTERNS = {
  tap: [10],
  doubleTap: [10, 50, 10],
  longPress: [5, 10, 5, 10, 30],
  notification: [20, 100, 20, 100, 50],
  heartbeat: [50, 100, 50, 300],
};

// ============================================================================
// Capacitor Haptics bridge (lazy-loaded)
// ============================================================================

let capacitorHaptics: any = null;
let capacitorHapticsLoaded = false;

async function loadCapacitorHaptics() {
  if (capacitorHapticsLoaded) return capacitorHaptics;
  capacitorHapticsLoaded = true;
  try {
    const mod = await import('@capacitor/haptics');
    capacitorHaptics = mod.Haptics;
    return capacitorHaptics;
  } catch {
    capacitorHaptics = null;
    return null;
  }
}

/** Map our HapticStyle → Capacitor ImpactStyle / NotificationType */
const CAPACITOR_IMPACT_MAP: Record<string, string> = {
  light: 'Light',
  medium: 'Medium',
  heavy: 'Heavy',
  selection: 'selection', // special case
};

const CAPACITOR_NOTIFICATION_MAP: Record<string, string> = {
  success: 'Success',
  warning: 'Warning',
  error: 'Error',
};

async function triggerCapacitor(style: HapticStyle): Promise<boolean> {
  const h = capacitorHaptics ?? (await loadCapacitorHaptics());
  if (!h) return false;

  try {
    if (style === 'selection') {
      await h.selectionStart();
      await h.selectionChanged();
      await h.selectionEnd();
      return true;
    }
    const notification = CAPACITOR_NOTIFICATION_MAP[style];
    if (notification) {
      await h.notification({ type: notification });
      return true;
    }
    const impact = CAPACITOR_IMPACT_MAP[style];
    if (impact) {
      await h.impact({ style: impact });
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

// ============================================================================
// Hook Implementation
// ============================================================================

export const useHaptic = (options: HapticOptions = {}): UseHapticReturn => {
  const { enabled = true } = options;
  const hapticModuleRef = useRef<boolean>(false);

  // Eagerly load Capacitor haptics on mount
  useEffect(() => {
    if (!hapticModuleRef.current) {
      hapticModuleRef.current = true;
      loadCapacitorHaptics();
    }
  }, []);

  const isSupported = useMemo(() => {
    // Capacitor is always "supported" on Android; also check web vibration
    return true;
  }, []);

  // Main trigger function — tries Capacitor first, then Web Vibration API
  const trigger = useCallback((style: HapticStyle = 'light') => {
    if (!enabled) return;

    // Fire-and-forget: try Capacitor, fall back to web vibration
    triggerCapacitor(style).then((handled) => {
      if (handled) return;
      // Web Vibration API fallback
      try {
        if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
          const duration = HAPTIC_DURATIONS[style];
          navigator.vibrate(Array.isArray(duration) ? duration : duration);
        }
      } catch {
        // Silently fail
      }
    });
  }, [enabled]);

  // Custom pattern function — web vibration only (Capacitor doesn't support arbitrary patterns)
  const pattern = useCallback((durations: number[]) => {
    if (!enabled) return;
    try {
      if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
        navigator.vibrate(durations);
      }
    } catch {
      // Silently fail
    }
  }, [enabled]);

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

export const useHapticButton = (style: HapticStyle = 'light') => {
  const { trigger } = useHaptic();

  return useMemo(() => ({
    onClick: () => { trigger(style); },
    onTouchStart: () => { trigger('selection'); },
  }), [trigger, style]);
};

// ============================================================================
// Default Export
// ============================================================================

export default useHaptic;
