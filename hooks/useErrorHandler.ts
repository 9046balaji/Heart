import { useState, useCallback } from 'react';
import { AppError, handleError } from '../utils/errorHandling';

/**
 * Custom hook for handling errors in functional components
 * Provides consistent error state management and logging
 */
export const useErrorHandler = () => {
  const [error, setError] = useState<AppError | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Handle an error with context
   */
  const handleCaughtError = useCallback((error: any, context?: any) => {
    const appError = handleError(error, context);
    setError(appError);
    return appError;
  }, []);

  /**
   * Clear the current error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Wrapper for async operations that handles loading states and errors
   */
  const executeAsyncOperation = useCallback(async <T>(
    operation: () => Promise<T>,
    context?: any
  ): Promise<T | undefined> => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await operation();
      return result;
    } catch (err) {
      handleCaughtError(err, context);
      return undefined;
    } finally {
      setIsLoading(false);
    }
  }, [handleCaughtError]);

  return {
    error,
    isLoading,
    setError: handleCaughtError,
    clearError,
    executeAsyncOperation,
  };
};
