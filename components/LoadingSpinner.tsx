import React from 'react';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  fullScreen?: boolean;
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'medium',
  fullScreen = false,
  message,
}) => {
  const sizeClasses = {
    small: 'w-8 h-8',
    medium: 'w-12 h-12',
    large: 'w-16 h-16',
  };

  const spinner = (
    <div className="flex flex-col items-center justify-center gap-3">
      <div
        className={`${sizeClasses[size]} rounded-full border-3 border-blue-200 dark:border-blue-900 border-t-blue-600 dark:border-t-blue-400 animate-spin`}
      />
      {message && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{message}</p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-background-light dark:bg-background-dark flex items-center justify-center z-50">
        {spinner}
      </div>
    );
  }

  return spinner;
};
