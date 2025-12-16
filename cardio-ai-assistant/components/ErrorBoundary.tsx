import React, { Component, ReactNode, ErrorInfo, createContext, useContext } from 'react';

// ============================================================================
// Types & Interfaces
// ============================================================================

/**
 * Error details passed to error handlers and fallback components
 */
export interface ErrorDetails {
  error: Error;
  errorInfo: ErrorInfo | null;
  componentStack: string | null;
  timestamp: Date;
  retryCount: number;
  errorId: string;
}

/**
 * Props for custom fallback components
 */
export interface FallbackProps {
  error: Error;
  errorDetails: ErrorDetails;
  resetError: () => void;
  retryCount: number;
  maxRetries: number;
  canRetry: boolean;
}

/**
 * Configuration options for ErrorBoundary
 */
export interface ErrorBoundaryConfig {
  /** Maximum number of retry attempts before showing permanent error */
  maxRetries?: number;
  /** Callback when an error is caught */
  onError?: (details: ErrorDetails) => void;
  /** Callback when error is reset/retried */
  onReset?: (details: ErrorDetails) => void;
  /** Custom fallback component */
  fallback?: React.ComponentType<FallbackProps>;
  /** Custom fallback render function */
  fallbackRender?: (props: FallbackProps) => ReactNode;
  /** Whether to report errors to external service */
  reportErrors?: boolean;
  /** Custom error reporter function */
  errorReporter?: (details: ErrorDetails) => Promise<void>;
  /** Reset keys - when these change, the boundary resets */
  resetKeys?: unknown[];
  /** Boundary name for debugging */
  name?: string;
  /** Whether to show detailed error info in development */
  showDevInfo?: boolean;
}

interface Props extends ErrorBoundaryConfig {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  retryCount: number;
  errorId: string;
  timestamp: Date | null;
}

// ============================================================================
// Error Boundary Context
// ============================================================================

interface ErrorBoundaryContextValue {
  resetError: () => void;
  hasError: boolean;
  error: Error | null;
}

const ErrorBoundaryContext = createContext<ErrorBoundaryContextValue | null>(null);

/**
 * Hook to access error boundary context from child components
 */
export function useErrorBoundary(): ErrorBoundaryContextValue {
  const context = useContext(ErrorBoundaryContext);
  if (!context) {
    return {
      resetError: () => {},
      hasError: false,
      error: null,
    };
  }
  return context;
}

// ============================================================================
// Error Reporting Service
// ============================================================================

/**
 * Default error reporter - logs to console and could be extended
 * to send to external services like Sentry, LogRocket, etc.
 */
async function defaultErrorReporter(details: ErrorDetails): Promise<void> {
  const errorReport = {
    errorId: details.errorId,
    message: details.error.message,
    stack: details.error.stack,
    componentStack: details.componentStack,
    timestamp: details.timestamp.toISOString(),
    retryCount: details.retryCount,
    userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
    url: typeof window !== 'undefined' ? window.location.href : 'unknown',
  };

  // Log to console in development
  if (process.env.NODE_ENV === 'development') {
    console.group(`🚨 Error Boundary Report [${details.errorId}]`);
    console.error('Error:', details.error);
    console.info('Component Stack:', details.componentStack);
    console.info('Retry Count:', details.retryCount);
    console.groupEnd();
  }

  // In production, you would send to an error tracking service
  // Example: await fetch('/api/error-reports', { method: 'POST', body: JSON.stringify(errorReport) });
  
  // Store in sessionStorage for debugging
  try {
    const existingErrors = JSON.parse(sessionStorage.getItem('errorBoundaryReports') || '[]');
    existingErrors.push(errorReport);
    // Keep only last 10 errors
    if (existingErrors.length > 10) {
      existingErrors.shift();
    }
    sessionStorage.setItem('errorBoundaryReports', JSON.stringify(existingErrors));
  } catch {
    // Ignore storage errors
  }
}

/**
 * Generate a unique error ID for tracking
 */
function generateErrorId(): string {
  return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// ============================================================================
// Main Error Boundary Component
// ============================================================================

export class ErrorBoundary extends Component<Props, State> {
  static defaultProps: Partial<Props> = {
    maxRetries: 3,
    reportErrors: true,
    showDevInfo: process.env.NODE_ENV === 'development',
  };

  private previousResetKeys: unknown[] = [];

  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0,
      errorId: '',
      timestamp: null,
    };
    this.previousResetKeys = props.resetKeys || [];
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error,
      errorId: generateErrorId(),
      timestamp: new Date(),
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const { onError, reportErrors, errorReporter, name } = this.props;
    
    // Update state with error info
    this.setState({ errorInfo });

    const details: ErrorDetails = {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack || null,
      timestamp: new Date(),
      retryCount: this.state.retryCount,
      errorId: this.state.errorId || generateErrorId(),
    };

    // Log with boundary name for easier debugging
    console.error(`ErrorBoundary${name ? ` [${name}]` : ''} caught:`, error, errorInfo);

    // Call custom error handler
    onError?.(details);

    // Report error
    if (reportErrors) {
      const reporter = errorReporter || defaultErrorReporter;
      reporter(details).catch(console.error);
    }
  }

  componentDidUpdate(prevProps: Props): void {
    const { resetKeys } = this.props;
    const { hasError } = this.state;

    // Reset error state if resetKeys have changed
    if (hasError && resetKeys && this.previousResetKeys) {
      const hasResetKeyChanged = resetKeys.some(
        (key, index) => key !== this.previousResetKeys[index]
      );
      if (hasResetKeyChanged) {
        this.resetError();
      }
    }
    this.previousResetKeys = resetKeys || [];
  }

  /**
   * Reset the error boundary state, allowing retry
   */
  resetError = (): void => {
    const { onReset } = this.props;
    const { error, errorInfo, retryCount, errorId, timestamp } = this.state;

    if (error && onReset) {
      onReset({
        error,
        errorInfo,
        componentStack: errorInfo?.componentStack || null,
        timestamp: timestamp || new Date(),
        retryCount,
        errorId,
      });
    }

    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: retryCount + 1,
      errorId: '',
      timestamp: null,
    });
  };

  /**
   * Check if retry is allowed based on maxRetries
   */
  canRetry = (): boolean => {
    const { maxRetries = 3 } = this.props;
    return this.state.retryCount < maxRetries;
  };

  /**
   * Get error details object
   */
  getErrorDetails = (): ErrorDetails => {
    const { error, errorInfo, retryCount, errorId, timestamp } = this.state;
    return {
      error: error || new Error('Unknown error'),
      errorInfo,
      componentStack: errorInfo?.componentStack || null,
      timestamp: timestamp || new Date(),
      retryCount,
      errorId,
    };
  };

  render(): ReactNode {
    const { hasError, error, retryCount } = this.state;
    const { 
      children, 
      fallback: FallbackComponent, 
      fallbackRender,
      maxRetries = 3,
      showDevInfo,
    } = this.props;

    if (hasError && error) {
      const fallbackProps: FallbackProps = {
        error,
        errorDetails: this.getErrorDetails(),
        resetError: this.resetError,
        retryCount,
        maxRetries,
        canRetry: this.canRetry(),
      };

      // Custom fallback render function
      if (fallbackRender) {
        return fallbackRender(fallbackProps);
      }

      // Custom fallback component
      if (FallbackComponent) {
        return <FallbackComponent {...fallbackProps} />;
      }

      // Default fallback UI
      return (
        <ErrorBoundaryContext.Provider
          value={{
            resetError: this.resetError,
            hasError,
            error,
          }}
        >
          <DefaultErrorFallback
            {...fallbackProps}
            showDevInfo={showDevInfo}
          />
        </ErrorBoundaryContext.Provider>
      );
    }

    return (
      <ErrorBoundaryContext.Provider
        value={{
          resetError: this.resetError,
          hasError,
          error,
        }}
      >
        {children}
      </ErrorBoundaryContext.Provider>
    );
  }
}

// ============================================================================
// Default Fallback Component
// ============================================================================

interface DefaultErrorFallbackProps extends FallbackProps {
  showDevInfo?: boolean;
}

function DefaultErrorFallback({
  error,
  errorDetails,
  resetError,
  retryCount,
  maxRetries,
  canRetry,
  showDevInfo,
}: DefaultErrorFallbackProps): React.ReactElement {
  const [showDetails, setShowDetails] = React.useState(false);

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center p-4">
      <div className="max-w-lg w-full bg-white dark:bg-card-dark rounded-2xl p-6 shadow-lg">
        {/* Error Icon */}
        <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 dark:bg-red-900/30">
          <span className="material-symbols-outlined text-3xl text-red-600 dark:text-red-400">
            {canRetry ? 'refresh_auto' : 'error_outline'}
          </span>
        </div>

        {/* Title */}
        <h2 className="text-xl font-bold text-center text-slate-900 dark:text-white mb-2">
          {canRetry ? 'Something went wrong' : 'Unable to recover'}
        </h2>

        {/* Error Message */}
        <p className="text-sm text-slate-600 dark:text-slate-400 text-center mb-4">
          {error.message || 'An unexpected error occurred.'}
        </p>

        {/* Retry Counter */}
        {retryCount > 0 && (
          <div className="flex items-center justify-center gap-2 mb-4">
            <span className="text-xs text-slate-500 dark:text-slate-500">
              Retry attempts: {retryCount} / {maxRetries}
            </span>
            <div className="flex gap-1">
              {Array.from({ length: maxRetries }).map((_, i) => (
                <div
                  key={i}
                  className={`w-2 h-2 rounded-full ${
                    i < retryCount
                      ? 'bg-orange-500'
                      : 'bg-slate-200 dark:bg-slate-700'
                  }`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col gap-3">
          {canRetry ? (
            <button
              onClick={resetError}
              className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              <span className="material-symbols-outlined text-lg">refresh</span>
              Try Again
            </button>
          ) : (
            <button
              onClick={() => window.location.reload()}
              className="w-full py-3 px-4 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              <span className="material-symbols-outlined text-lg">restart_alt</span>
              Reload Page
            </button>
          )}

          {canRetry && (
            <button
              onClick={() => window.location.reload()}
              className="w-full py-2 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-colors text-sm"
            >
              Reload Page Instead
            </button>
          )}

          {/* Go Home Button */}
          <button
            onClick={() => {
              window.location.href = '/';
            }}
            className="w-full py-2 px-4 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-sm transition-colors"
          >
            Return to Home
          </button>
        </div>

        {/* Development Info Toggle */}
        {showDevInfo && (
          <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="w-full flex items-center justify-between text-xs text-slate-500 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            >
              <span>Developer Details</span>
              <span className="material-symbols-outlined text-sm">
                {showDetails ? 'expand_less' : 'expand_more'}
              </span>
            </button>

            {showDetails && (
              <div className="mt-3 space-y-3">
                {/* Error ID */}
                <div className="text-xs">
                  <span className="text-slate-500 dark:text-slate-500">Error ID:</span>
                  <code className="ml-2 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-slate-700 dark:text-slate-300">
                    {errorDetails.errorId}
                  </code>
                </div>

                {/* Timestamp */}
                <div className="text-xs">
                  <span className="text-slate-500 dark:text-slate-500">Time:</span>
                  <span className="ml-2 text-slate-700 dark:text-slate-300">
                    {errorDetails.timestamp.toLocaleString()}
                  </span>
                </div>

                {/* Stack Trace */}
                {error.stack && (
                  <div className="text-xs">
                    <span className="text-slate-500 dark:text-slate-500 block mb-1">
                      Stack Trace:
                    </span>
                    <pre className="p-2 bg-slate-100 dark:bg-slate-800 rounded text-slate-600 dark:text-slate-400 overflow-x-auto text-[10px] leading-relaxed max-h-32 overflow-y-auto">
                      {error.stack}
                    </pre>
                  </div>
                )}

                {/* Component Stack */}
                {errorDetails.componentStack && (
                  <div className="text-xs">
                    <span className="text-slate-500 dark:text-slate-500 block mb-1">
                      Component Stack:
                    </span>
                    <pre className="p-2 bg-slate-100 dark:bg-slate-800 rounded text-slate-600 dark:text-slate-400 overflow-x-auto text-[10px] leading-relaxed max-h-32 overflow-y-auto">
                      {errorDetails.componentStack}
                    </pre>
                  </div>
                )}

                {/* Copy Error Button */}
                <button
                  onClick={() => {
                    const errorText = JSON.stringify(
                      {
                        errorId: errorDetails.errorId,
                        message: error.message,
                        stack: error.stack,
                        componentStack: errorDetails.componentStack,
                        timestamp: errorDetails.timestamp.toISOString(),
                        retryCount: errorDetails.retryCount,
                      },
                      null,
                      2
                    );
                    navigator.clipboard.writeText(errorText);
                  }}
                  className="w-full py-2 px-3 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 rounded text-xs flex items-center justify-center gap-2 transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">content_copy</span>
                  Copy Error Details
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Specialized Error Boundaries
// ============================================================================

/**
 * Compact error boundary for inline components
 */
export function InlineErrorBoundary({
  children,
  fallbackMessage = 'Failed to load',
  ...props
}: Props & { fallbackMessage?: string }): React.ReactElement {
  return (
    <ErrorBoundary
      {...props}
      fallbackRender={({ error, resetError, canRetry }) => (
        <div className="inline-flex items-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
          <span className="material-symbols-outlined text-red-500 text-sm">
            warning
          </span>
          <span className="text-sm text-red-700 dark:text-red-300">
            {fallbackMessage}
          </span>
          {canRetry && (
            <button
              onClick={resetError}
              className="ml-2 text-xs text-red-600 dark:text-red-400 hover:underline"
            >
              Retry
            </button>
          )}
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
}

/**
 * Card-level error boundary for dashboard widgets
 */
export function CardErrorBoundary({
  children,
  title = 'Widget Error',
  ...props
}: Props & { title?: string }): React.ReactElement {
  return (
    <ErrorBoundary
      {...props}
      fallbackRender={({ error, resetError, canRetry }) => (
        <div className="bg-white dark:bg-card-dark rounded-xl p-4 shadow-sm border border-red-200 dark:border-red-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <span className="material-symbols-outlined text-red-500 text-sm">
                error
              </span>
            </div>
            <span className="font-medium text-slate-900 dark:text-white">
              {title}
            </span>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
            {error.message || 'Unable to display this content'}
          </p>
          {canRetry && (
            <button
              onClick={resetError}
              className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">refresh</span>
              Try again
            </button>
          )}
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
}

/**
 * Async boundary for components that fetch data
 * Automatically resets when key changes
 */
export function AsyncErrorBoundary({
  children,
  queryKey,
  ...props
}: Props & { queryKey?: unknown }): React.ReactElement {
  return (
    <ErrorBoundary
      {...props}
      resetKeys={queryKey ? [queryKey] : undefined}
      maxRetries={5}
    >
      {children}
    </ErrorBoundary>
  );
}
