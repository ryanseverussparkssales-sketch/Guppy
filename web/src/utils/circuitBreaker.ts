/**
 * Circuit Breaker Pattern Implementation
 *
 * Prevents cascading failures by monitoring for failures and temporarily
 * blocking requests when a service is detected as unhealthy.
 *
 * States:
 * - CLOSED: Normal operation, all requests pass through
 * - OPEN: Too many failures, requests fail immediately
 * - HALF_OPEN: Testing if service recovered, limited requests allowed
 *
 * Usage:
 *   const breaker = new CircuitBreaker({
 *     failureThreshold: 5,      // Open after 5 failures
 *     resetTimeout: 30000,       // Try recovery after 30s
 *     successThreshold: 2,       // Close after 2 successes in HALF_OPEN
 *   })
 *
 *   if (breaker.isOpen()) {
 *     throw new Error('Service unavailable - circuit breaker open')
 *   }
 *
 *   try {
 *     const result = await api.call()
 *     breaker.recordSuccess()
 *     return result
 *   } catch (error) {
 *     breaker.recordFailure()
 *     throw error
 *   }
 */

export type CircuitBreakerState = 'CLOSED' | 'OPEN' | 'HALF_OPEN'

interface CircuitBreakerConfig {
  /**
   * Number of failures before opening circuit (default: 5)
   */
  failureThreshold?: number

  /**
   * Time in milliseconds before attempting recovery (default: 30000)
   */
  resetTimeout?: number

  /**
   * Number of successes needed to close circuit from HALF_OPEN (default: 2)
   */
  successThreshold?: number

  /**
   * Maximum time a request can take in HALF_OPEN state before failure (default: 5000)
   */
  halfOpenTimeout?: number

  /**
   * Callback when state changes
   */
  onStateChange?: (from: CircuitBreakerState, to: CircuitBreakerState) => void
}

export class CircuitBreaker {
  private state: CircuitBreakerState = 'CLOSED'
  private failureCount = 0
  private successCount = 0
  private lastFailureTime: number | null = null
  private resetTimer: ReturnType<typeof setTimeout> | null = null

  private readonly failureThreshold: number
  private readonly resetTimeout: number
  private readonly successThreshold: number
  private readonly onStateChange?: (from: CircuitBreakerState, to: CircuitBreakerState) => void

  constructor(config: CircuitBreakerConfig = {}) {
    this.failureThreshold = config.failureThreshold ?? 5
    this.resetTimeout = config.resetTimeout ?? 30000
    this.successThreshold = config.successThreshold ?? 2
    this.onStateChange = config.onStateChange
  }

  /**
   * Check if circuit is open (should reject requests)
   */
  isOpen(): boolean {
    if (this.state === 'OPEN') {
      // Check if reset timeout has passed
      if (this.lastFailureTime && Date.now() - this.lastFailureTime > this.resetTimeout) {
        this.transitionTo('HALF_OPEN')
        return false // Allow HALF_OPEN requests through
      }
      return true
    }
    return false
  }

  /**
   * Check if circuit allows requests (CLOSED or HALF_OPEN)
   */
  canRequest(): boolean {
    return !this.isOpen()
  }

  /**
   * Record a successful request
   */
  recordSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.successCount++
      if (this.successCount >= this.successThreshold) {
        this.reset()
      }
    } else if (this.state === 'CLOSED') {
      // In CLOSED state, just reset failure count on success
      this.failureCount = 0
    }
  }

  /**
   * Record a failed request
   */
  recordFailure(): void {
    this.lastFailureTime = Date.now()

    if (this.state === 'HALF_OPEN') {
      // Failure in HALF_OPEN state opens circuit again
      this.transitionTo('OPEN')
      this.scheduleReset()
    } else if (this.state === 'CLOSED') {
      this.failureCount++
      if (this.failureCount >= this.failureThreshold) {
        this.transitionTo('OPEN')
        this.scheduleReset()
      }
    }
  }

  /**
   * Manually reset circuit to CLOSED state
   */
  reset(): void {
    this.transitionTo('CLOSED')
    this.failureCount = 0
    this.successCount = 0
    this.lastFailureTime = null
    if (this.resetTimer) {
      clearTimeout(this.resetTimer)
      this.resetTimer = null
    }
  }

  /**
   * Get current state
   */
  getState(): CircuitBreakerState {
    return this.state
  }

  /**
   * Get diagnostics
   */
  getDiagnostics(): {
    state: CircuitBreakerState
    failureCount: number
    successCount: number
    lastFailureTime: number | null
    timeSinceLastFailure: number | null
  } {
    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime,
      timeSinceLastFailure: this.lastFailureTime ? Date.now() - this.lastFailureTime : null,
    }
  }

  private transitionTo(newState: CircuitBreakerState): void {
    if (this.state !== newState) {
      const oldState = this.state
      this.state = newState
      this.onStateChange?.(oldState, newState)
    }
  }

  private scheduleReset(): void {
    if (this.resetTimer) {
      clearTimeout(this.resetTimer)
    }
    this.resetTimer = setTimeout(() => {
      this.transitionTo('HALF_OPEN')
      this.successCount = 0
      this.resetTimer = null
    }, this.resetTimeout)
  }
}

/**
 * Global circuit breaker instances by endpoint
 */
const breakers = new Map<string, CircuitBreaker>()

/**
 * Get or create circuit breaker for an endpoint
 */
export function getCircuitBreaker(endpoint: string, config?: CircuitBreakerConfig): CircuitBreaker {
  if (!breakers.has(endpoint)) {
    breakers.set(endpoint, new CircuitBreaker(config))
  }
  return breakers.get(endpoint)!
}

/**
 * Reset all circuit breakers
 */
export function resetAllCircuitBreakers(): void {
  breakers.forEach((breaker) => breaker.reset())
}

/**
 * Get all circuit breaker states
 */
export function getAllCircuitBreakerStates(): Record<string, CircuitBreakerState> {
  const states: Record<string, CircuitBreakerState> = {}
  breakers.forEach((breaker, endpoint) => {
    states[endpoint] = breaker.getState()
  })
  return states
}
