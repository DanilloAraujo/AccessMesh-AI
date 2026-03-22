import React from 'react';
import { translate } from '../hooks/useTranslation';

interface ErrorBoundaryProps {
    children: React.ReactNode;
    /** Optional fallback UI to render when an error is caught. */
    fallback?: React.ReactNode;
    /** Optional callback invoked when an error is caught. */
    onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

/**
 * React Error Boundary that catches rendering errors in its subtree and
 * displays a graceful fallback UI instead of crashing the entire application.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeRiskyComponent />
 *   </ErrorBoundary>
 *
 *   <ErrorBoundary fallback={<p>Custom fallback</p>}>
 *     <AnotherComponent />
 *   </ErrorBoundary>
 */
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
        console.error('[ErrorBoundary] Caught error:', error, errorInfo);
        this.props.onError?.(error, errorInfo);
    }

    private handleRetry = (): void => {
        this.setState({ hasError: false, error: null });
    };

    render(): React.ReactNode {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div
                    role="alert"
                    style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '12px',
                        padding: '24px',
                        width: '100%',
                        height: '100%',
                        minHeight: '120px',
                        borderRadius: '16px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        color: '#fca5a5',
                        textAlign: 'center',
                    }}
                >
                    <p style={{ fontSize: '14px', fontWeight: 600 }}>
                        {translate('errorBoundary.title')}
                    </p>
                    <p style={{ fontSize: '12px', opacity: 0.7, maxWidth: '300px' }}>
                        {this.state.error?.message || translate('errorBoundary.generic')}
                    </p>
                    <button
                        type="button"
                        onClick={this.handleRetry}
                        style={{
                            marginTop: '4px',
                            padding: '8px 16px',
                            borderRadius: '8px',
                            border: '1px solid rgba(239, 68, 68, 0.4)',
                            background: 'rgba(239, 68, 68, 0.15)',
                            color: '#fca5a5',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: 600,
                            transition: 'background 0.2s',
                        }}
                        onMouseEnter={(e) => {
                            (e.target as HTMLButtonElement).style.background = 'rgba(239, 68, 68, 0.25)';
                        }}
                        onMouseLeave={(e) => {
                            (e.target as HTMLButtonElement).style.background = 'rgba(239, 68, 68, 0.15)';
                        }}
                    >
                        {translate('errorBoundary.retry')}
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
