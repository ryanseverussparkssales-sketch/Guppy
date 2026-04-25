/**
 * Error Toast Notification Component
 *
 * Displays error messages to users with:
 * - Severity-based styling (warning, error, critical)
 * - Auto-dismiss after configurable timeout
 * - Retry button for retryable errors
 * - Dismiss button for manual closing
 * - Smooth fade-in/out animations
 *
 * Usage:
 *   <ErrorToast
 *     code="CHAT_FAILED_TO_SEND"
 *     message="Failed to send message. Try again?"
 *     onDismiss={() => setShowToast(false)}
 *     onRetry={() => handleRetry()}
 *     autoDismiss={true}
 *     duration={5000}
 *   />
 */

import React, { useEffect, useState } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle, X, RotateCcw } from 'lucide-react'
import { parseApiError, FormattedError } from '@/utils/errorMessages'
import { isRetryable } from '@/utils/errorCodes'

interface ErrorToastProps {
  /**
   * Error code string or complete error object
   * If string, message should be provided separately
   */
  error?: string | Error | FormattedError

  /**
   * User-friendly error message (required if error is a string code)
   */
  message?: string

  /**
   * Called when user dismisses the toast
   */
  onDismiss: () => void

  /**
   * Called when user clicks retry button
   * Only shown for retryable errors
   */
  onRetry?: () => void

  /**
   * Auto-dismiss after duration (ms)
   * Set to 0 to disable auto-dismiss
   */
  autoDismiss?: boolean
  duration?: number

  /**
   * Position on screen (default: top-right)
   */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

  /**
   * Custom CSS class for styling
   */
  className?: string
}

export function ErrorToast({
  error,
  message,
  onDismiss,
  onRetry,
  autoDismiss = true,
  duration = 5000,
  position = 'top-right',
  className = '',
}: ErrorToastProps) {
  const [isVisible, setIsVisible] = useState(true)
  const [isExiting, setIsExiting] = useState(false)

  // Parse error if needed
  let formattedError: FormattedError | null = null
  let displayMessage = message

  if (error) {
    if (typeof error === 'string') {
      formattedError = parseApiError(error)
      displayMessage = displayMessage || formattedError.message
    } else if (error instanceof Error) {
      formattedError = parseApiError(error)
      displayMessage = displayMessage || formattedError.message
    } else if ('code' in error) {
      formattedError = error as FormattedError
      displayMessage = displayMessage || formattedError.message
    }
  }

  const severity = formattedError?.severity || 'warning'
  const code = formattedError?.code || 'UNKNOWN_ERROR'
  const canRetry = formattedError ? isRetryable(formattedError.code) : false

  // Auto-dismiss timer
  useEffect(() => {
    if (!autoDismiss || duration === 0 || !isVisible) return

    const timer = setTimeout(() => {
      handleDismiss()
    }, duration)

    return () => clearTimeout(timer)
  }, [autoDismiss, duration, isVisible])

  const handleDismiss = () => {
    setIsExiting(true)
    // Wait for animation to complete before calling onDismiss
    setTimeout(() => {
      setIsVisible(false)
      onDismiss()
    }, 300) // Match animation duration
  }

  const handleRetry = () => {
    if (onRetry) {
      setIsExiting(true)
      setTimeout(() => {
        setIsVisible(false)
        onRetry()
      }, 300)
    }
  }

  if (!isVisible) return null

  // Severity styles
  const severityStyles = {
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      icon: 'text-blue-600',
      text: 'text-blue-900',
      button: 'hover:bg-blue-100',
    },
    warning: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      icon: 'text-yellow-600',
      text: 'text-yellow-900',
      button: 'hover:bg-yellow-100',
    },
    critical: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      icon: 'text-red-600',
      text: 'text-red-900',
      button: 'hover:bg-red-100',
    },
  }

  const styles = severityStyles[severity as keyof typeof severityStyles]

  // Position classes
  const positionClasses = {
    'top-left': 'top-4 left-4',
    'top-right': 'top-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'bottom-right': 'bottom-4 right-4',
  }

  // Icon based on severity
  const IconComponent = {
    info: CheckCircle,
    warning: AlertTriangle,
    critical: AlertCircle,
  }[severity as keyof typeof IconComponent]

  return (
    <div
      className={`fixed ${positionClasses[position]} z-50 transition-all duration-300 ${
        isExiting ? 'opacity-0 scale-95' : 'opacity-100 scale-100'
      } ${className}`}
    >
      <div
        className={`${styles.bg} ${styles.border} border rounded-lg shadow-lg p-4 max-w-md`}
      >
        {/* Header with icon and message */}
        <div className="flex items-start gap-3">
          <IconComponent className={`${styles.icon} w-5 h-5 flex-shrink-0 mt-0.5`} />

          <div className="flex-1 min-w-0">
            {/* Error code (small) */}
            <p className={`${styles.text} text-xs font-mono opacity-75 mb-0.5`}>{code}</p>

            {/* Main message */}
            <p className={`${styles.text} text-sm font-medium`}>{displayMessage}</p>
          </div>

          {/* Close button */}
          <button
            onClick={handleDismiss}
            className={`${styles.button} flex-shrink-0 ml-2 p-1 rounded-md transition-colors`}
            aria-label="Dismiss notification"
          >
            <X className={`${styles.icon} w-4 h-4`} />
          </button>
        </div>

        {/* Action buttons (retry if applicable) */}
        {canRetry && onRetry && (
          <div className="mt-3 flex gap-2">
            <button
              onClick={handleRetry}
              className={`${styles.button} flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium ${styles.text} transition-colors`}
            >
              <RotateCcw className="w-4 h-4" />
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Hook to manage toast notifications
 *
 * Usage:
 *   const { showError, toast } = useErrorToast()
 *
 *   // Show error from API response
 *   catch (error) {
 *     showError(error)
 *   }
 *
 *   // Or show custom error
 *   showError('CHAT_FAILED_TO_SEND', 'Could not send message')
 *
 *   // Render all toasts
 *   return (
 *     <div>
 *       {toast.map((t) => (
 *         <ErrorToast key={t.id} {...t} onDismiss={() => dismissToast(t.id)} />
 *       ))}
 *     </div>
 *   )
 */

export interface Toast {
  id: string
  error?: string | Error | FormattedError
  message?: string
  onRetry?: () => void
  severity?: 'info' | 'warning' | 'critical'
}

export function useErrorToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const showError = (error?: string | Error | FormattedError, message?: string) => {
    const id = `${Date.now()}-${Math.random()}`
    const newToast: Toast = {
      id,
      error,
      message,
    }
    setToasts((prev) => [...prev, newToast])
  }

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  const showWithRetry = (
    error: string | Error | FormattedError,
    message: string,
    onRetry: () => void
  ) => {
    const id = `${Date.now()}-${Math.random()}`
    const newToast: Toast = {
      id,
      error,
      message,
      onRetry,
    }
    setToasts((prev) => [...prev, newToast])
  }

  return {
    toasts,
    showError,
    showWithRetry,
    dismissToast,
  }
}

/**
 * Container component for displaying multiple error toasts
 *
 * Usage:
 *   const { toasts, showError, dismissToast } = useErrorToast()
 *
 *   return (
 *     <>
 *       <ErrorToastContainer
 *         toasts={toasts}
 *         onDismiss={dismissToast}
 *       />
 *       ... rest of app ...
 *     </>
 *   )
 */

interface ErrorToastContainerProps {
  toasts: Toast[]
  onDismiss: (id: string) => void
  maxToasts?: number
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
}

export function ErrorToastContainer({
  toasts,
  onDismiss,
  maxToasts = 3,
  position = 'top-right',
}: ErrorToastContainerProps) {
  // Show only the most recent toasts up to maxToasts
  const visibleToasts = toasts.slice(-maxToasts)

  return (
    <>
      {visibleToasts.map((toast) => (
        <ErrorToast
          key={toast.id}
          error={toast.error}
          message={toast.message}
          onDismiss={() => onDismiss(toast.id)}
          onRetry={toast.onRetry}
          autoDismiss={true}
          duration={5000}
          position={position}
        />
      ))}
    </>
  )
}
