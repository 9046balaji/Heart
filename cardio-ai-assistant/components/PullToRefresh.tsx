/**
 * PullToRefresh Component
 * 
 * A reusable pull-to-refresh wrapper component with animated indicator.
 * Integrates with the usePullToRefresh hook for gesture handling.
 * 
 * @author Cardio AI Team
 * @version 1.0.0
 */

import React, { ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface PullToRefreshProps {
  /** Child content to wrap */
  children: ReactNode;
  /** Current pull distance from hook */
  pullDistance: number;
  /** Whether refresh is in progress */
  isRefreshing: boolean;
  /** Progress percentage (0-100) */
  progress: number;
  /** Threshold for triggering refresh */
  threshold?: number;
  /** Custom refresh indicator */
  customIndicator?: ReactNode;
  /** Indicator color */
  indicatorColor?: string;
  /** Background color during pull */
  backgroundColor?: string;
  /** Container ref from hook */
  containerRef?: React.RefObject<HTMLDivElement>;
  /** Additional className for container */
  className?: string;
}

export const PullToRefresh: React.FC<PullToRefreshProps> = ({
  children,
  pullDistance,
  isRefreshing,
  progress,
  threshold = 80,
  customIndicator,
  indicatorColor = '#ef4444', // Red-500 for cardio theme
  backgroundColor = '#fef2f2', // Red-50
  containerRef,
  className = '',
}) => {
  const indicatorHeight = Math.max(0, pullDistance);
  const rotation = (progress / 100) * 360;
  const scale = 0.5 + (progress / 100) * 0.5;
  const isReadyToRefresh = progress >= 100;

  return (
    <div 
      ref={containerRef}
      className={`ptr-container relative overflow-hidden ${className}`}
      style={{
        touchAction: 'pan-y',
        overscrollBehaviorY: 'contain',
        WebkitOverflowScrolling: 'touch',
      }}
      role="region"
      aria-label="Pull down to refresh content"
      aria-live="polite"
      aria-busy={isRefreshing}
    >
      {/* Pull indicator area */}
      <AnimatePresence>
        {(pullDistance > 0 || isRefreshing) && (
          <motion.div
            className="ptr-indicator absolute top-0 left-0 right-0 flex items-center justify-center"
            style={{
              backgroundColor,
              willChange: 'transform, height',
              backfaceVisibility: 'hidden',
            }}
            initial={{ height: 0, opacity: 0 }}
            animate={{ 
              height: isRefreshing ? threshold : indicatorHeight,
              opacity: 1,
            }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ 
              type: 'spring', 
              stiffness: 300, 
              damping: 30,
              opacity: { duration: 0.2 }
            }}
          >
            {customIndicator || (
              <div className="flex flex-col items-center justify-center py-2">
                {isRefreshing ? (
                  // Refreshing spinner
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ 
                      repeat: Infinity, 
                      duration: 1, 
                      ease: 'linear' 
                    }}
                  >
                    <RefreshSpinner color={indicatorColor} />
                  </motion.div>
                ) : (
                  // Pull indicator with heart icon
                  <motion.div
                    style={{
                      transform: `rotate(${rotation}deg) scale(${scale})`,
                    }}
                    className={isReadyToRefresh ? 'ptr-heart' : ''}
                  >
                    <HeartIcon 
                      color={indicatorColor} 
                      filled={isReadyToRefresh}
                    />
                  </motion.div>
                )}
                
                {/* Status text */}
                <motion.span
                  className="text-xs mt-1 font-medium"
                  style={{ color: indicatorColor }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: pullDistance > 20 ? 1 : 0 }}
                >
                  {isRefreshing 
                    ? 'Refreshing...' 
                    : isReadyToRefresh 
                      ? 'Release to refresh' 
                      : 'Pull to refresh'
                  }
                </motion.span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Screen reader announcement */}
      <span className="sr-only">
        {isRefreshing
          ? 'Content is refreshing'
          : isReadyToRefresh
            ? 'Release to refresh content'
            : 'Pull down to refresh content'
        }
      </span>

      {/* Main content with transform */}
      <motion.div
        className="ptr-content"
        style={{
          transform: `translate3d(0, ${pullDistance}px, 0)`,
          willChange: pullDistance > 0 ? 'transform' : 'auto',
        }}
        animate={{
          y: isRefreshing ? threshold : pullDistance,
        }}
        transition={{
          type: 'spring',
          stiffness: 300,
          damping: 30,
        }}
      >
        {children}
      </motion.div>
    </div>
  );
};

// Heart icon component for cardio theme
const HeartIcon: React.FC<{ color: string; filled: boolean }> = ({ 
  color, 
  filled 
}) => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill={filled ? color : 'none'}
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
  </svg>
);

// Refresh spinner component
const RefreshSpinner: React.FC<{ color: string }> = ({ color }) => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

export default PullToRefresh;
