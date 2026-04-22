/**
 * Error Recovery Hook
 *
 * Provides retry logic with exponential backoff, timeout handling,
 * and circuit breaker pattern for frontend requests.
 *
 * Usage:
 *   const { retry, isRetrying, error, reset } = useErrorRecovery({
 *     onRetry: async () => {
 *       await sendMessage('Hello')
 *     },
 *     maxAttempts: 3,
 *     initialBackoff: 500,
 *   })
 *
 *   return (
 *     <>
 *       {error && <ErrorToast error={error} onRetry={retry} />}
 *       <button onClick={retry} disabled={isRetrying}>
 *         {isRetrying ? 'Retrying...' : 'Try Again'}
 *       </button>
 *     </>
 *   )
 */

import { useCallback, useRef, useState } from 'react'
import { FormattedError, parseApiError } from '@/utils/errorMessages'
import { isRetryable, shouldTriggerCircuitBreaker } from '@/utils/errorCodes'
import { ErrorCode } from '@/utils/errorCodes'

interface UseErrorRecoveryOptions {
  /**
   * Async function to retry
   */
  onRetry: () => Promise<void>

  /**
   * Maximum retry attempts (default: 3)
   */
  maxAttempts?: number

  /**
   * Initial backoff time in ms (default: 500)
   */
  initialBackoff?: number

  /**
   * Backoff multiplier (default: 2, i.e., exponential)
   */
  backoffMultiplier?: number

  /**
   * Maximum backoff time in ms (default: 30000 = 30s)
   */
  maxBackoff?: number

  /**
   * Request timeout in ms (default: 30000 = 30s)
   */
  timeout?: number

  /**
   * Called when all retries exhausted
   */
  onExhausted?: (error: FormattedError) => void

  /**
   * Called on successful retry
   */
  onSuccess?: () => void
}

interface UseErrorRecoveryState {
  /**
   * Current retry attempt (0-indexed)
   */
  attempt: number

  /**
   * Current error
   */
  error: FormattedError | null

  /**
   * Whether currently retrying
   */
  isRetrying: boolean

  /**
   * Whether circuit breaker is open (too many failures)
   */
  circuitBreakerOpen: boolean
}

export function useErrorRecovery(options: UseErrorRecoveryOptions) {
  const {
    onRetry,
    maxAttempts = 3,
    initialBackoff = 500,
    backoffMultiplier = 2,
    maxBackoff = 30000,
    timeout = 30000,
    onExhausted,
    onSuccess,
  } = options

  const [state, setState] = useState<UseErrorRecoveryState>({
    attempt: 0,
    error: null,
    isRetrying: false,
    circuitBreakerOpen: false,
  })

  const abortControllerRef = useRef<AbortController | null>(null)
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  /**
   * Calculate exponential backoff time
   */
  const calculateBackoff = (attempt: number): number => {
    const backoff = initialBackoff * Math.pow(backoffMultiplier, attempt)
    return Math.min(backoff, maxBackoff)
  }

  /**
   * Add jitter to prevent thundering herd
   */
  const addJitter = (ms: number): number => {
    const jitter = Math.random() * 0.1 * ms // 0-10% jitter
    return ms + jitter
  }

  /**
   * Reset retry state
   */
  const reset = useCallback(() => {
    setState({
      attempt: 0,
      error: null,
      isRetrying: false,
      circuitBreakerOpen: false,
    })

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }

    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
  }, [])

  /**
   * Open circuit breaker
   */
  const openCircuitBreaker = useCallback(() => {
    setState((prev) => ({ ...prev, circuitBreakerOpen: true }))
  }, [])

  /**
   * Attempt to execute the retry function with timeout
   */
  const executeWithTimeout = useCallback(
    async (signal: AbortSignal): Promise<void> => {
      return Promise.race([
        onRetry(),
        new Promise<void>((_, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error('Request timeout'))
          }, timeout)

          signal.addEventListener('abort', () => {
            clearTimeout(timeoutId)
          })
        }),
      ])
    },
    [onRetry, timeout]
  )

  /**
   * Main retry function
   */
  const retry = useCallback(async () => {
    // Don't retry if circuit breaker is open
    if (state.circuitBreakerOpen) {
      setState((prev) => ({
        ...prev,
        error: parseApiError(ErrorCode.SYSTEM_SERVICE_UNAVAILABLE),
      }))
      return
    }

    // Don't retry if already at max attempts
    if (state.attempt >= maxAttempts) {
      if (onExhausted && state.error) {
        onExhausted(state.error)
      }
      return
    }

    setState((prev) => ({ ...prev, isRetrying: true }))

    try {
      // Create abort controller for this attempt
      abortControllerRef.current = new AbortController()

      // Execute with timeout
      await executeWithTimeout(abortControllerRef.current.signal)

      // Success
      setState({
        attempt: 0,
        error: null,
        isRetrying: false,
        circuitBreakerOpen: false,
      })

      if (onSuccess) {
        onSuccess()
      }
    } catch (error) {
      const formattedError = parseApiError(error)

      // Check if should open circuit breaker
      if (shouldTriggerCircuitBreaker(formattedError.code)) {
        openCircuitBreaker()
      }

      // Check if error is retryable
      if (!isRetryable(formattedError.code)) {
        setState({
          attempt: state.attempt + 1,
          error: formattedError,
          isRetrying: false,
          circuitBreakerOpen: state.circuitBreakerOpen,
        })
        return
      }

      const nextAttempt = state.attempt + 1

      // Check if exhausted attempts
      if (nextAttempt >= maxAttempts) {
        setState({
          attempt: nextAttempt,
          error: formattedError,
          isRetrying: false,
          circuitBreakerOpen: state.circuitBreakerOpen,
        })

        if (onExhausted) {
          onExhausted(formattedError)
        }
        return
      }

      // Schedule next retry
      const backoffTime = calculateBackoff(state.attempt)
      const jitteredBackoff = addJitter(backoffTime)

      setState({
        attempt: nextAttempt,
        error: formattedError,
        isRetrying: false,
        circuitBreakerOpen: state.circuitBreakerOpen,
      })

      // Schedule automatic retry
      retryTimeoutRef.current = setTimeout(() => {
        retry()
      }, jitteredBackoff)
    }
  }, [
    state.attempt,
    state.error,
    state.circuitBreakerOpen,
    maxAttempts,
    executeWithTimeout,
    onExhausted,
    onSuccess,
    openCircuitBreaker,
  ])

  /**
   * Cancel ongoing retry
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }

    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }

    setState((prev) => ({ ...prev, isRetrying: false }))
  }, [])

  return {
    /**
     * Attempt to retry the function
     */
    retry,

    /**
     * Cancel ongoing retry
     */
    cancel,

    /**
     * Reset to initial state
     */
    reset,

    /**
     * Current attempt number (0-indexed)
     */
    attempt: state.attempt,

    /**
     * Total attempts (for progress display)
     */
    totalAttempts: maxAttempts,

    /**
     * Current error (null if none)
     */
    error: state.error,

    /**
     * Whether currently retrying
     */
    isRetrying: state.isRetrying,

    /**
     * Whether circuit breaker is open
     */
    circuitBreakerOpen: state.circuitBreakerOpen,

    /**
     * Whether can retry (has attempts remaining and not circuit breaker open)
     */
    canRetry: state.attempt < maxAttempts && !state.circuitBreakerOpen,

    /**
     * Backoff time until next attempt (ms)
     */
    nextRetryIn: state.isRetrying
      ? calculateBackoff(state.attempt)
      : null,
  }
}

/**
 * Hook for handling request timeout with recovery
 *
 * Usage:
 *   const { executeWithTimeout } = useRequestTimeout({
 *     timeout: 30000,
 *   })
 *
 *   try {
 *     await executeWithTimeout(async () => {
 *       await api.post('/chat', { message })
 *     })
 *   } catch (error) {
 *     if (error.code === 'CLIENT_REQUEST_TIMEOUT') {
 *       // Handle timeout
 *     }
 *   }
 */

interface UseRequestTimeoutOptions {
  /**
   * Request timeout in ms (default: 30000)
   */
  timeout?: number
}

export function useRequestTimeout(options: UseRequestTimeoutOptions = {}) {
  const { timeout = 30000 } = options

  const executeWithTimeout = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T> => {
      return Promise.race([
        fn(),
        new Promise<T>((_, reject) => {
          const timeoutId = setTimeout(() => {
            reject(
              parseApiError(
                new Error(
                  JSON.stringify({
                    code: ErrorCode.CLIENT_REQUEST_TIMEOUT,
                    message: 'Request timed out',
                  })
                )
              )
            )
          }, timeout)
        }),
      ])
    },
    [timeout]
  )

  return {
    executeWithTimeout,
    timeout,
  }
}

/**
 * Hook for offline detection and recovery
 *
 * Usage:
 *   const { isOnline, goOffline, goOnline } = useOfflineDetection()
 *
 *   return (
 *     <div>
 *       {!isOnline && <OfflineBanner />}
 *     </div>
 *   )
 */

export function useOfflineDetection() {
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  )

  const handleOnline = useCallback(() => {
    setIsOnline(true)
  }, [])

  const handleOffline = useCallback(() => {
    setIsOnline(false)
  }, [])

  // Set up event listeners
  useState(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  })

  return {
    /**
     * Whether device is online
     */
    isOnline,

    /**
     * Manually mark as offline
     */
    goOffline: () => setIsOnline(false),

    /**
     * Manually mark as online
     */
    goOnline: () => setIsOnline(true),
  }
}
