/**
 * Components Index
 *
 * Central export for all reusable UI components
 */

// Loading & State Components
export { LoadingSpinner } from './LoadingSpinner';
export {
  Skeleton,
  TextSkeleton,
  AvatarSkeleton,
  CardSkeleton,
  ListItemSkeleton,
  ListSkeleton,
  ChatMessageSkeleton,
  ChatListSkeleton,
  StatsCardSkeleton,
  ChartSkeleton,
  VitalCardSkeleton,
  AppointmentCardSkeleton,
  MedicationCardSkeleton,
  FormSkeleton,
  PageSkeleton,
  ShimmerEffect,
  DashboardSkeleton,
  ChatScreenSkeleton,
  MedicationScreenSkeleton,
  ProfileScreenSkeleton,
} from './Skeleton';

export {
  LoadingOverlay,
  AsyncBoundary,
  ErrorState,
  EmptyState,
  ContentLoader,
  ProgressBar,
  IndeterminateProgress,
  withSkeleton,
  useLoadingState,
  useAsyncData,
} from './LoadingStates';

// Optimized Components
export {
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
  DefaultLoadingFallback,
} from './OptimizedComponents';

// Navigation
export { default as BottomNav } from './BottomNav';

// Error Handling
export { default as ErrorBoundary } from './ErrorBoundary';
export { default as ErrorDisplay } from './ErrorDisplay';

// Voice
export { default as VoiceControl } from './VoiceControl';

// Page Transitions (Framer Motion)
export {
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
} from './PageTransition';

// Markdown Rendering
export {
  MarkdownRenderer,
  ChatMessageMarkdown,
  HealthAlertMarkdown,
} from './MarkdownRenderer';

// Pull-to-Refresh
export { PullToRefresh } from './PullToRefresh';
