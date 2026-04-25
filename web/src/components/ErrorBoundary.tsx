/**
 * Error Boundary - Catches React component errors
 *
 * Wraps the entire app to catch unhandled errors in any child component.
 * Displays error UI instead of white screen of death.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 */

import React, { ReactNode, ReactElement } from 'react'
import { AlertCircle, RefreshCw, Home } from 'lucide-react'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
  errorCount: number
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private resetTimeout: ReturnType<typeof setTimeout> | null = null

  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    }
  }

  static getDerivedStateFromError(_error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error for debugging
    console.error('Error caught by boundary:', error, errorInfo)

    // Log to telemetry (if available)
    this.logErrorTelemetry(error, errorInfo)

    this.setState((prevState) => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1,
    }))
  }

  componentWillUnmount() {
    if (this.resetTimeout) {
      clearTimeout(this.resetTimeout)
    }
  }

  private logErrorTelemetry(error: Error, errorInfo: React.ErrorInfo) {
    try {
      // In production, send to error tracking service
      const errorData = {
        timestamp: new Date().toISOString(),
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        url: window.location.href,
      }

      // Could send to: Sentry, LogRocket, etc.
      console.group('Frontend Error Telemetry')
      console.error(errorData)
      console.groupEnd()
    } catch (e) {
      console.error('Failed to log error telemetry:', e)
    }
  }

  private handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleNavigateHome = () => {
    // Navigate to home page
    window.location.href = '/'
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return this.props.fallback ?? this.renderErrorFallback()
    }

    return <>{this.props.children}</>
  }

  private renderErrorFallback(): ReactElement {
    const isDevelopment = import.meta.env.DEV

    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-50 to-orange-50">
        <div className="max-w-md w-full mx-4">
          {/* Error Icon */}
          <div className="flex justify-center mb-4">
            <div className="bg-red-100 rounded-full p-4">
              <AlertCircle className="w-12 h-12 text-red-600" />
            </div>
          </div>

          {/* Error Message */}
          <h1 className="text-2xl font-bold text-center text-gray-900 mb-2">
            Oops! Something went wrong
          </h1>

          <p className="text-center text-gray-600 mb-6">
            We encountered an unexpected error. Try refreshing the page or navigate back to the home screen.
          </p>

          {/* Error Details (Development Only) */}
          {isDevelopment && this.state.error && (
            <div className="mb-6 p-4 bg-red-100 rounded-lg border border-red-200">
              <p className="text-sm font-mono text-red-700 mb-2 font-bold">
                {this.state.error.message}
              </p>
              <details className="text-xs text-red-600">
                <summary className="cursor-pointer font-semibold mb-2 hover:text-red-700">
                  Component Stack
                </summary>
                <pre className="whitespace-pre-wrap break-words overflow-auto max-h-40 text-red-600">
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
              <details className="text-xs text-red-600 mt-2">
                <summary className="cursor-pointer font-semibold mb-2 hover:text-red-700">
                  Stack Trace
                </summary>
                <pre className="whitespace-pre-wrap break-words overflow-auto max-h-40 text-red-600">
                  {this.state.error.stack}
                </pre>
              </details>
            </div>
          )}

          {/* Error Count Warning */}
          {this.state.errorCount > 2 && (
            <div className="mb-4 p-3 bg-yellow-100 rounded-lg border border-yellow-200">
              <p className="text-sm text-yellow-800">
                Multiple errors detected ({this.state.errorCount}). A page reload is recommended.
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-col gap-3">
            {/* Try Again (Reset) */}
            <button
              onClick={this.handleReset}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>

            {/* Reload Page */}
            <button
              onClick={this.handleReload}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Reload Page
            </button>

            {/* Go Home */}
            <button
              onClick={this.handleNavigateHome}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors"
            >
              <Home className="w-4 h-4" />
              Go Home
            </button>
          </div>

          {/* Support Text */}
          <p className="text-center text-xs text-gray-500 mt-6">
            If the problem persists, please try clearing your browser cache or contact support.
          </p>
        </div>
      </div>
    )
  }
}

/**
 * Hook to use error boundary from functional components
 * Note: Error boundaries can only be class components
 * Use this to trigger error boundary errors:
 *
 * Example:
 *   const throwError = useErrorBoundary()
 *   if (criticalError) {
 *     throwError(new Error('Critical error occurred'))
 *   }
 */
export function useErrorBoundary() {
  return (error: Error) => {
    throw error
  }
}
