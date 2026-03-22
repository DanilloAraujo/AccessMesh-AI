// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';

import { describe, it, expect, vi } from 'vitest';
import ErrorBoundary from '../ErrorBoundary';

// Mock translation hook
vi.mock('../../hooks/useTranslation', () => ({
  translate: (key: string) => {
    const dict: Record<string, string> = {
      'errorBoundary.title': 'Something went wrong',
      'errorBoundary.generic': 'An unexpected error occurred.',
      'errorBoundary.retry': 'Try Again'
    };
    return dict[key] || key;
  }
}));

const ThrowError = ({ shouldThrow }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test Error');
  }
  return <div>Everything is fine</div>;
};

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );
    expect(screen.getByText('Everything is fine')).not.toBeNull();
  });

  it('renders fallback UI when an error is thrown', () => {
    // Prevent vitest from failing the test on the expected error log
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).not.toBeNull();
    expect(screen.getByText('Test Error')).not.toBeNull();
    expect(screen.getByText('Try Again')).not.toBeNull();

    consoleError.mockRestore();
  });

  it('renders custom fallback when provided', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom Error</div>}>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );

    expect(screen.queryByText('Something went wrong')).toBeNull();
    expect(screen.getByTestId('custom-fallback')).not.toBeNull();

    consoleError.mockRestore();
  });

  it('calls onError callback when an error is thrown', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0].message).toBe('Test Error');

    consoleError.mockRestore();
  });
});
