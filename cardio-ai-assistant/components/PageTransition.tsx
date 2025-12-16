/**
 * Page Transition Components
 * 
 * Provides smooth page transitions using Framer Motion
 * Addresses: FINAL_ACTION_PLAN.md "Add page transitions with Framer Motion"
 */

import React from 'react';
import { motion, AnimatePresence, Variants, TargetAndTransition } from 'framer-motion';

// ============================================================================
// Transition Variants
// ============================================================================

export const pageVariants: Variants = {
  initial: {
    opacity: 0,
    x: 20,
  },
  animate: {
    opacity: 1,
    x: 0,
  },
  exit: {
    opacity: 0,
    x: -20,
  },
};

export const fadeVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

export const slideUpVariants: Variants = {
  initial: {
    opacity: 0,
    y: 30,
  },
  animate: {
    opacity: 1,
    y: 0,
  },
  exit: {
    opacity: 0,
    y: -30,
  },
};

export const scaleVariants: Variants = {
  initial: {
    opacity: 0,
    scale: 0.95,
  },
  animate: {
    opacity: 1,
    scale: 1,
  },
  exit: {
    opacity: 0,
    scale: 1.05,
  },
};

// ============================================================================
// Transition Configs
// ============================================================================

export const pageTransition = {
  type: 'tween',
  ease: 'anticipate',
  duration: 0.25,
};

export const quickTransition = {
  type: 'tween',
  ease: 'easeOut',
  duration: 0.15,
};

export const springTransition = {
  type: 'spring',
  stiffness: 300,
  damping: 30,
};

// ============================================================================
// PageWrapper Component
// ============================================================================

interface PageWrapperProps {
  children: React.ReactNode;
  className?: string;
  variants?: Variants;
  transition?: object;
}

/**
 * Wraps a page/screen with animated transitions
 * 
 * Usage:
 * ```tsx
 * <PageWrapper>
 *   <DashboardScreen />
 * </PageWrapper>
 * ```
 */
export const PageWrapper: React.FC<PageWrapperProps> = ({
  children,
  className = '',
  variants = pageVariants,
  transition = pageTransition,
}) => (
  <motion.div
    initial="initial"
    animate="animate"
    exit="exit"
    variants={variants}
    transition={transition}
    className={`w-full h-full ${className}`}
  >
    {children}
  </motion.div>
);

// ============================================================================
// FadeIn Component
// ============================================================================

interface FadeInProps {
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  className?: string;
}

/**
 * Fades in content with optional delay
 * Good for staggered content loading
 */
export const FadeIn: React.FC<FadeInProps> = ({
  children,
  delay = 0,
  duration = 0.3,
  className = '',
}) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration, ease: 'easeOut' }}
    className={className}
  >
    {children}
  </motion.div>
);

// ============================================================================
// SlideIn Component
// ============================================================================

type Direction = 'left' | 'right' | 'up' | 'down';

interface SlideInProps {
  children: React.ReactNode;
  direction?: Direction;
  delay?: number;
  duration?: number;
  className?: string;
}

const getSlideOffset = (direction: Direction) => {
  switch (direction) {
    case 'left': return { x: -30, y: 0 };
    case 'right': return { x: 30, y: 0 };
    case 'up': return { x: 0, y: -30 };
    case 'down': return { x: 0, y: 30 };
    default: return { x: 0, y: 30 };
  }
};

/**
 * Slides in content from specified direction
 */
export const SlideIn: React.FC<SlideInProps> = ({
  children,
  direction = 'down',
  delay = 0,
  duration = 0.3,
  className = '',
}) => {
  const offset = getSlideOffset(direction);
  
  return (
    <motion.div
      initial={{ opacity: 0, ...offset }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ delay, duration, ease: 'easeOut' }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

// ============================================================================
// StaggerContainer and StaggerItem
// ============================================================================

interface StaggerContainerProps {
  children: React.ReactNode;
  staggerDelay?: number;
  className?: string;
}

/**
 * Container for staggered children animations
 * 
 * Usage:
 * ```tsx
 * <StaggerContainer>
 *   <StaggerItem>Item 1</StaggerItem>
 *   <StaggerItem>Item 2</StaggerItem>
 * </StaggerContainer>
 * ```
 */
export const StaggerContainer: React.FC<StaggerContainerProps> = ({
  children,
  staggerDelay = 0.1,
  className = '',
}) => (
  <motion.div
    initial="initial"
    animate="animate"
    variants={{
      initial: {},
      animate: {
        transition: {
          staggerChildren: staggerDelay,
        },
      },
    }}
    className={className}
  >
    {children}
  </motion.div>
);

interface StaggerItemProps {
  children: React.ReactNode;
  className?: string;
}

export const StaggerItem: React.FC<StaggerItemProps> = ({
  children,
  className = '',
}) => (
  <motion.div
    variants={{
      initial: { opacity: 0, y: 20 },
      animate: { opacity: 1, y: 0 },
    }}
    transition={{ duration: 0.3, ease: 'easeOut' }}
    className={className}
  >
    {children}
  </motion.div>
);

// ============================================================================
// AnimatedCard
// ============================================================================

interface AnimatedCardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  whileHover?: TargetAndTransition;
  whileTap?: TargetAndTransition;
}

/**
 * Card with hover and tap animations
 */
export const AnimatedCard: React.FC<AnimatedCardProps> = ({
  children,
  className = '',
  onClick,
  whileHover = { scale: 1.02, y: -2 },
  whileTap = { scale: 0.98 },
}) => (
  <motion.div
    whileHover={whileHover}
    whileTap={onClick ? whileTap : undefined}
    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
    onClick={onClick}
    className={`cursor-pointer ${className}`}
  >
    {children}
  </motion.div>
);

// ============================================================================
// AnimatedButton
// ============================================================================

interface AnimatedButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  variant?: 'default' | 'subtle' | 'bounce';
}

/**
 * Button with micro-animations
 */
export const AnimatedButton: React.FC<AnimatedButtonProps> = ({
  children,
  onClick,
  disabled = false,
  className = '',
  variant = 'default',
}) => {
  const variants = {
    default: {
      whileHover: { scale: 1.02 },
      whileTap: { scale: 0.98 },
    },
    subtle: {
      whileHover: { scale: 1.01 },
      whileTap: { scale: 0.99 },
    },
    bounce: {
      whileHover: { scale: 1.05, y: -2 },
      whileTap: { scale: 0.95 },
    },
  };

  return (
    <motion.button
      {...variants[variant]}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      onClick={onClick}
      disabled={disabled}
      className={`${className} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </motion.button>
  );
};

// ============================================================================
// PresenceWrapper for AnimatePresence
// ============================================================================

interface PresenceWrapperProps {
  children: React.ReactNode;
  mode?: 'sync' | 'wait' | 'popLayout';
}

/**
 * Wrapper for AnimatePresence to handle exit animations
 * 
 * Use with React Router or conditional rendering
 */
export const PresenceWrapper: React.FC<PresenceWrapperProps> = ({
  children,
  mode = 'wait',
}) => (
  <AnimatePresence mode={mode}>
    {children}
  </AnimatePresence>
);

// ============================================================================
// Export everything
// ============================================================================

export default {
  PageWrapper,
  FadeIn,
  SlideIn,
  StaggerContainer,
  StaggerItem,
  AnimatedCard,
  AnimatedButton,
  PresenceWrapper,
  pageVariants,
  fadeVariants,
  slideUpVariants,
  scaleVariants,
  pageTransition,
  quickTransition,
  springTransition,
};
