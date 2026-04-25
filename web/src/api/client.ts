import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { CircuitBreaker, getCircuitBreaker, getAllCircuitBreakerStates } from '../utils/circuitBreaker'

declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _authRetry?: boolean
  }
}
import { RequestQueue, generateRequestFingerprint } from '../utils/requestQueue'
import { telemetry } from '../utils/telemetry'

/**
 * Enhanced API Client with Circuit Breaker & Request Queue
 *
 * Features:
 * - Circuit breaker per endpoint (prevents cascading failures)
 * - Request queueing for offline/unavailable scenarios
 * - Proper timeout handling with AbortController
 * - Automatic retry logic with exponential backoff
 * - Error classification and telemetry
 * - Complete telemetry instrumentation
 */

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
})

// Get singletons
const requestQueue = RequestQueue.getInstance()

// Track request timings for telemetry
const requestStartTimes = new Map<string, number>()

// Track active requests for timeout handling
const activeRequests = new Map<string, AbortController>()

/**
 * Determine if an error is retryable
 */
function isRetryableError(error: any): boolean {
  // Network errors are retryable
  if (!error.response) {
    return true
  }

  const status = error.response.status
  // Retry on server errors (5xx) and specific client errors
  return (
    status >= 500 || // Server errors
    status === 408 || // Request timeout
    status === 429 || // Too many requests
    status === 503 || // Service unavailable
    status === 504 // Gateway timeout
  )
}

/**
 * Extract endpoint from config for circuit breaker
 */
function getEndpoint(config: InternalAxiosRequestConfig): string {
  const url = config.url || ''
  const method = config.method?.toUpperCase() || 'GET'
  // Use just the path, not full URL (for circuit breaker grouping)
  const path = url.split('?')[0].split('#')[0]
  return `${method} ${path}`
}

/**
 * Request interceptor: Add auth token, setup timeout, check circuit breaker, record telemetry
 */
api.interceptors.request.use((config) => {
  // Add auth token if available
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  const endpoint = getEndpoint(config)
  const breaker = getCircuitBreaker(endpoint)

  // Record request start time
  requestStartTimes.set(endpoint, Date.now())

  // Skip circuit breaker for local API — always true when using relative URLs
  // through the Vite proxy (dev) or served from the same origin (prod).
  const isLocalApi = true

  // Check if circuit is open
  if (!isLocalApi && breaker.isOpen()) {
    // Queue the request instead of sending it
    const fingerprint = generateRequestFingerprint(
      endpoint,
      (config.method?.toUpperCase() || 'GET') as any,
      config.data
    )

    const queuedId = requestQueue.enqueue({
      endpoint,
      method: (config.method?.toUpperCase() || 'GET') as any,
      data: config.data,
      headers: config.headers as Record<string, string>,
      priority: 'HIGH',
      ttl: 24 * 60 * 60 * 1000, // 24 hours
      fingerprint,
      retryCount: 0,
      maxRetries: 3,
    })

    // Record telemetry
    telemetry.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { reason: 'circuit_breaker_open', queuedId },
    })

    // Abort this request
    const error: any = new Error('Circuit breaker is open - request queued')
    error.isCircuitBreakerOpen = true
    error.code = 'CIRCUIT_BREAKER_OPEN'
    throw error
  }

  // Setup AbortController for timeout
  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    controller.abort()
  }, config.timeout || 30000)

  // Store reference for cleanup
  activeRequests.set(endpoint, controller)

  // Store timeout ID for cleanup
  ;(config as any)._timeoutId = timeoutId
  ;(config as any)._controller = controller
  ;(config as any)._endpoint = endpoint

  config.signal = controller.signal

  return config
})

/**
 * Response interceptor: Handle success, errors, circuit breaker updates, record telemetry
 */
api.interceptors.response.use(
  (response) => {
    const endpoint = getEndpoint(response.config)
    const breaker = getCircuitBreaker(endpoint)
    const startTime = requestStartTimes.get(endpoint)
    const duration = startTime ? Date.now() - startTime : 0

    // Record success in circuit breaker
    breaker.recordSuccess()

    // Record telemetry success
    telemetry.recordRequestSuccess(endpoint, duration)
    telemetry.recordEvent({
      type: 'request_success',
      endpoint,
      duration,
      details: { statusCode: response.status },
    })

    // Cleanup timeout
    const timeoutId = (response.config as any)._timeoutId
    if (timeoutId) {
      clearTimeout(timeoutId)
    }

    activeRequests.delete(endpoint)
    requestStartTimes.delete(endpoint)

    return response
  },
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig
    if (!config) {
      return Promise.reject(error)
    }

    const endpoint = (config as any)._endpoint || getEndpoint(config)
    const breaker = getCircuitBreaker(endpoint)
    const startTime = requestStartTimes.get(endpoint)
    const duration = startTime ? Date.now() - startTime : 0

    // Cleanup timeout
    const timeoutId = (config as any)._timeoutId
    if (timeoutId) {
      clearTimeout(timeoutId)
    }

    activeRequests.delete(endpoint)
    requestStartTimes.delete(endpoint)

    // Determine error code
    let errorCode = 'UNKNOWN_ERROR'
    if (error.response?.status === 401) {
      errorCode = 'AUTH_UNAUTHORIZED'
    } else if (error.response?.status === 403) {
      errorCode = 'AUTH_FORBIDDEN'
    } else if (error.response?.status === 429) {
      errorCode = 'RATE_LIMIT_EXCEEDED'
    } else if (error.response?.status && error.response.status >= 500) {
      errorCode = 'SERVICE_UNAVAILABLE'
    } else if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
      errorCode = 'CONNECTION_FAILED'
    } else if (error.code === 'ECONNABORTED') {
      errorCode = 'REQUEST_TIMEOUT'
    }

    // Record telemetry error
    telemetry.recordRequestError(
      endpoint,
      errorCode,
      error.response?.status,
      duration
    )
    telemetry.recordEvent({
      type: 'request_failed',
      endpoint,
      errorCode,
      duration,
      details: { statusCode: error.response?.status, message: error.message },
    })

    // Handle auth errors: try silent re-auth before forcing login
    if (error.response?.status === 401) {
      const originalRequest = error.config
      // Don't retry auth endpoints themselves — that would loop
      if (originalRequest && !originalRequest._authRetry && !originalRequest.url?.includes('/auth/')) {
        originalRequest._authRetry = true
        try {
          const refreshResp = await api.post('/auth/local')
          const newToken = refreshResp.data?.access_token
          if (newToken) {
            localStorage.setItem('accessToken', newToken)
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            return api(originalRequest)
          }
        } catch {
          // refresh failed — fall through to login redirect
        }
      }
      localStorage.removeItem('accessToken')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // Record failure in circuit breaker
    if (!error.message?.includes('Circuit breaker is open')) {
      breaker.recordFailure()
    }

    // For retryable errors, attempt to queue the request
    if (isRetryableError(error)) {
      const fingerprint = generateRequestFingerprint(
        endpoint,
        (config.method?.toUpperCase() || 'GET') as any,
        config.data
      )

      const queued = requestQueue.enqueue({
        endpoint,
        method: (config.method?.toUpperCase() || 'GET') as any,
        data: config.data,
        headers: config.headers as Record<string, string>,
        priority: 'NORMAL',
        ttl: 24 * 60 * 60 * 1000,
        fingerprint,
        retryCount: 0,
        maxRetries: 3,
      })

      // Mark error as queued
      ;(error as any).queued = true
      ;(error as any).queuedRequestId = queued

      // Record that request was queued for retry
      telemetry.recordEvent({
        type: 'request_queued',
        endpoint,
        details: { reason: 'retryable_error', queuedId: queued },
      })
    }

    return Promise.reject(error)
  }
)

/**
 * Monitor circuit breaker state changes
 */
const monitoredEndpoints = new Set<string>()

function monitorCircuitBreaker(endpoint: string): CircuitBreaker {
  if (monitoredEndpoints.has(endpoint)) {
    return getCircuitBreaker(endpoint)
  }

  monitoredEndpoints.add(endpoint)

  const breaker = getCircuitBreaker(endpoint, {
    failureThreshold: 5,
    resetTimeout: 30000,
    successThreshold: 2,
    onStateChange: (from, to) => {
      console.log(`Circuit breaker state change: ${endpoint}`, { from, to })

      // Record telemetry for state change
      telemetry.recordCircuitBreakerStateChange(
        endpoint,
        to,
        breaker.getDiagnostics().failureCount,
        breaker.getDiagnostics().successCount
      )

      // When circuit closes, attempt to flush queued requests
      if (to === 'CLOSED') {
        telemetry.recordEvent({
          type: 'circuit_breaker_close',
          endpoint,
          details: { actionTaken: 'queue_flush_triggered' },
        })

        requestQueue.flush().catch((err) => {
          console.error('Error flushing request queue:', err)
          telemetry.recordEvent({
            type: 'queue_flushed',
            endpoint,
            details: { error: err.message },
          })
        })
      }

      // Record open state
      if (to === 'OPEN') {
        telemetry.recordEvent({
          type: 'circuit_breaker_open',
          endpoint,
          details: { reason: 'failure_threshold_exceeded' },
        })
      }

      // Emit custom event for UI monitoring
      window.dispatchEvent(
        new CustomEvent('circuitBreakerStateChange', {
          detail: { endpoint, from, to },
        })
      )
    },
  })

  return breaker
}

/**
 * Setup automatic flush when online
 */
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    requestQueue.resume()
    telemetry.recordEvent({
      type: 'request_queued',
      details: { event: 'online', action: 'queue_flush_triggered' },
    })
    requestQueue.flush().catch((err) => {
      console.error('Error flushing queue on online:', err)
      telemetry.recordEvent({
        type: 'request_failed',
        details: { event: 'queue_flush_on_online', error: err.message },
      })
    })
  })

  window.addEventListener('offline', () => {
    requestQueue.pause()
    telemetry.recordEvent({
      type: 'request_queued',
      details: { event: 'offline', action: 'queue_paused' },
    })
  })

  // Setup request queue event monitoring
  requestQueue.on('flush', (event) => {
    console.log('Request queue flushed:', event.count, 'remaining')
    telemetry.recordQueueFlushed(event.count)
    telemetry.recordEvent({
      type: 'queue_flushed',
      details: { count: event.count, remainingCount: event.remainingCount },
    })
  })

  requestQueue.on('error', (event) => {
    console.error('Request queue error:', event.error)
    telemetry.recordEvent({
      type: 'request_failed',
      endpoint: event.endpoint,
      errorCode: event.error.code || 'QUEUE_ERROR',
      details: { message: event.error.message },
    })
  })
}

/**
 * Public API for monitoring circuit breaker
 */
export function setupCircuitBreakerMonitoring(endpoint: string): CircuitBreaker {
  return monitorCircuitBreaker(endpoint)
}

/**
 * Public API to get circuit breaker diagnostics
 */
export function getCircuitBreakerDiagnostics(): Record<string, any> {
  const states = getAllCircuitBreakerStates()
  const queueStats = requestQueue.getStats()

  return {
    circuitBreakers: states,
    requestQueue: queueStats,
    activeRequests: activeRequests.size,
  }
}

/**
 * Public API to manually trigger queue flush
 */
export async function flushRequestQueue(): Promise<void> {
  return requestQueue.flush()
}

/**
 * Public API to get queue statistics
 */
export function getQueueStats() {
  return requestQueue.getStats()
}

const _BASE_URL = (import.meta.env.VITE_API_URL || '') as string

/**
 * SSE streaming chat. Calls /api/chat/stream and invokes onToken for each token.
 * Throws on HTTP error or if the server sends {"error": "..."}.
 */
export async function streamChat(
  params: { message: string; session_id?: string; workspace_id?: string | null; mode?: string },
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const token = localStorage.getItem('accessToken')
  const response = await fetch(`${_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(params),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Stream request failed: ${response.status}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (payload === '[DONE]') return
      try {
        const parsed = JSON.parse(payload)
        if (parsed.error) throw new Error(parsed.error)
        if (parsed.token) onToken(parsed.token)
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }
}

// Named export for hooks, default for backwards compatibility
export { api, requestQueue }
export default api
