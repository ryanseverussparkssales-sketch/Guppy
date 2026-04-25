/**
 * Error Telemetry System
 *
 * Tracks and aggregates metrics about:
 * - Circuit breaker state changes
 * - Request queue statistics
 * - API error rates and types
 * - Response times and timeouts
 * - Recovery events
 *
 * Data is stored in memory with optional persistence to localStorage
 */


export interface MetricsSnapshot {
  timestamp: number
  circuitBreakerStates: Record<string, 'CLOSED' | 'OPEN' | 'HALF_OPEN'>
  queuedRequestCount: number
  totalErrorCount: number
  errorsByCode: Record<string, number>
  averageResponseTime: number
  uptime: number // milliseconds
}

export interface TelemetryEvent {
  type: 'circuit_breaker_open' | 'circuit_breaker_close' | 'request_queued' | 'request_failed' | 'request_success' | 'queue_flushed'
  timestamp: number
  endpoint?: string
  errorCode?: string
  duration?: number
  details?: any
}

export interface CircuitBreakerMetrics {
  endpoint: string
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN'
  failureCount: number
  successCount: number
  totalStateChanges: number
  lastStateChange: number
  timeSinceStateChange: number
}

export interface RequestQueueMetrics {
  queuedCount: number
  byPriority: Record<string, number>
  avgAgeSeconds: number
  oldestRequestAgeSeconds: number | null
  totalProcessed: number
  totalFailed: number
  flushCount: number
}

export interface ErrorMetrics {
  totalErrors: number
  uniqueErrorCodes: number
  errorsByCode: Record<string, number>
  errorsByStatus: Record<number, number>
  lastErrorTime: number | null
  recoveryRate: number // errors resolved / total errors
}

/**
 * Singleton telemetry collector
 */
export class Telemetry {
  private static instance: Telemetry

  private events: TelemetryEvent[] = []
  private circuitBreakerMetrics = new Map<string, CircuitBreakerMetrics>()
  private errorMetrics: ErrorMetrics = {
    totalErrors: 0,
    uniqueErrorCodes: 0,
    errorsByCode: {},
    errorsByStatus: {},
    lastErrorTime: null,
    recoveryRate: 0,
  }
  private startTime = Date.now()
  private storageKey = 'guppy_telemetry'
  private maxEvents = 1000 // Keep last 1000 events

  private constructor() {
    this.loadFromStorage()
    this.setupCleanup()
  }

  static getInstance(): Telemetry {
    if (!Telemetry.instance) {
      Telemetry.instance = new Telemetry()
    }
    return Telemetry.instance
  }

  /**
   * Record a telemetry event
   */
  recordEvent(event: Omit<TelemetryEvent, 'timestamp'>): void {
    const telemetryEvent: TelemetryEvent = {
      ...event,
      timestamp: Date.now(),
    }

    this.events.push(telemetryEvent)

    // Keep only last N events
    if (this.events.length > this.maxEvents) {
      this.events = this.events.slice(-this.maxEvents)
    }

    this.saveToStorage()
  }

  /**
   * Record circuit breaker state change
   */
  recordCircuitBreakerStateChange(
    endpoint: string,
    state: 'CLOSED' | 'OPEN' | 'HALF_OPEN',
    failureCount: number = 0,
    successCount: number = 0
  ): void {
    const metrics = this.circuitBreakerMetrics.get(endpoint) || {
      endpoint,
      state: 'CLOSED',
      failureCount: 0,
      successCount: 0,
      totalStateChanges: 0,
      lastStateChange: Date.now(),
      timeSinceStateChange: 0,
    }

    const oldState = metrics.state
    metrics.state = state
    metrics.failureCount = failureCount
    metrics.successCount = successCount
    metrics.totalStateChanges++
    metrics.lastStateChange = Date.now()
    metrics.timeSinceStateChange = 0

    this.circuitBreakerMetrics.set(endpoint, metrics)

    this.recordEvent({
      type: 'circuit_breaker_open',
      endpoint,
      details: { oldState, newState: state },
    })
  }

  /**
   * Record request failure with error details
   */
  recordRequestError(
    endpoint: string,
    errorCode: string,
    statusCode?: number,
    duration?: number
  ): void {
    this.errorMetrics.totalErrors++
    this.errorMetrics.lastErrorTime = Date.now()

    // Track by error code
    if (!this.errorMetrics.errorsByCode[errorCode]) {
      this.errorMetrics.uniqueErrorCodes++
      this.errorMetrics.errorsByCode[errorCode] = 0
    }
    this.errorMetrics.errorsByCode[errorCode]++

    // Track by HTTP status
    if (statusCode) {
      if (!this.errorMetrics.errorsByStatus[statusCode]) {
        this.errorMetrics.errorsByStatus[statusCode] = 0
      }
      this.errorMetrics.errorsByStatus[statusCode]++
    }

    this.recordEvent({
      type: 'request_failed',
      endpoint,
      errorCode,
      duration,
    })
  }

  /**
   * Record successful request
   */
  recordRequestSuccess(endpoint: string, duration: number): void {
    this.recordEvent({
      type: 'request_success',
      endpoint,
      duration,
    })
  }

  /**
   * Record request queued
   */
  recordRequestQueued(endpoint: string, priority: string): void {
    this.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { priority },
    })
  }

  /**
   * Record queue flush
   */
  recordQueueFlushed(flushedCount: number): void {
    this.recordEvent({
      type: 'queue_flushed',
      details: { count: flushedCount },
    })
  }

  /**
   * Get current metrics snapshot
   */
  getSnapshot(): MetricsSnapshot {
    const circuitStates: Record<string, 'CLOSED' | 'OPEN' | 'HALF_OPEN'> = {}
    for (const [endpoint, metrics] of this.circuitBreakerMetrics) {
      circuitStates[endpoint] = metrics.state
      metrics.timeSinceStateChange = Date.now() - metrics.lastStateChange
    }

    // Calculate average response time
    const successEvents = this.events.filter((e) => e.type === 'request_success' && e.duration)
    const avgResponseTime =
      successEvents.length > 0
        ? successEvents.reduce((sum, e) => sum + (e.duration || 0), 0) / successEvents.length
        : 0

    return {
      timestamp: Date.now(),
      circuitBreakerStates: circuitStates,
      queuedRequestCount: 0, // Updated from request queue
      totalErrorCount: this.errorMetrics.totalErrors,
      errorsByCode: { ...this.errorMetrics.errorsByCode },
      averageResponseTime: Math.round(avgResponseTime),
      uptime: Date.now() - this.startTime,
    }
  }

  /**
   * Get circuit breaker metrics for an endpoint
   */
  getCircuitBreakerMetrics(endpoint: string): CircuitBreakerMetrics | null {
    const metrics = this.circuitBreakerMetrics.get(endpoint)
    if (metrics) {
      metrics.timeSinceStateChange = Date.now() - metrics.lastStateChange
    }
    return metrics || null
  }

  /**
   * Get all circuit breaker metrics
   */
  getAllCircuitBreakerMetrics(): CircuitBreakerMetrics[] {
    return Array.from(this.circuitBreakerMetrics.values()).map((m) => ({
      ...m,
      timeSinceStateChange: Date.now() - m.lastStateChange,
    }))
  }

  /**
   * Get error metrics
   */
  getErrorMetrics(): ErrorMetrics {
    return {
      ...this.errorMetrics,
      recoveryRate: this.calculateRecoveryRate(),
    }
  }

  /**
   * Get events filtered by type and time range
   */
  getEvents(options?: {
    type?: string
    endpoint?: string
    since?: number
    limit?: number
  }): TelemetryEvent[] {
    let filtered = [...this.events]

    if (options?.type) {
      filtered = filtered.filter((e) => e.type === options.type)
    }

    if (options?.endpoint) {
      filtered = filtered.filter((e) => e.endpoint === options.endpoint)
    }

    if (options?.since) {
      filtered = filtered.filter((e) => e.timestamp >= options.since!)
    }

    if (options?.limit) {
      filtered = filtered.slice(-options.limit)
    }

    return filtered
  }

  /**
   * Get error timeline (errors per 5-minute bucket)
   */
  getErrorTimeline(minutes: number = 60): Array<{
    bucketStart: number
    errorCount: number
    errorCodes: Set<string>
  }> {
    const bucketSize = 5 * 60 * 1000 // 5 minutes
    const buckets = new Map<number, { count: number; codes: Set<string> }>()

    const cutoff = Date.now() - minutes * 60 * 1000

    for (const event of this.events) {
      if (event.type === 'request_failed' && event.timestamp >= cutoff) {
        const bucketStart = Math.floor(event.timestamp / bucketSize) * bucketSize
        if (!buckets.has(bucketStart)) {
          buckets.set(bucketStart, { count: 0, codes: new Set() })
        }

        const bucket = buckets.get(bucketStart)!
        bucket.count++
        if (event.errorCode) {
          bucket.codes.add(event.errorCode)
        }
      }
    }

    return Array.from(buckets.entries())
      .map(([bucketStart, data]) => ({
        bucketStart,
        errorCount: data.count,
        errorCodes: data.codes,
      }))
      .sort((a, b) => a.bucketStart - b.bucketStart)
  }

  /**
   * Get success rate over time period
   */
  getSuccessRate(minutes: number = 60): number {
    const cutoff = Date.now() - minutes * 60 * 1000

    const totalRequests = this.events.filter(
      (e) => (e.type === 'request_success' || e.type === 'request_failed') && e.timestamp >= cutoff
    ).length

    if (totalRequests === 0) return 100

    const successCount = this.events.filter(
      (e) => e.type === 'request_success' && e.timestamp >= cutoff
    ).length

    return Math.round((successCount / totalRequests) * 100)
  }

  /**
   * Get circuit breaker open time
   */
  getCircuitBreakerOpenTime(endpoint: string, minutes: number = 60): number {
    const cutoff = Date.now() - minutes * 60 * 1000
    let openTime = 0
    let lastOpenTime = 0

    const events = this.events.filter((e) => e.endpoint === endpoint && e.timestamp >= cutoff)

    for (const event of events) {
      if (event.details?.newState === 'OPEN') {
        lastOpenTime = event.timestamp
      } else if (event.details?.newState === 'CLOSED' && lastOpenTime > 0) {
        openTime += event.timestamp - lastOpenTime
        lastOpenTime = 0
      }
    }

    // If still open, count time until now
    if (lastOpenTime > 0) {
      openTime += Date.now() - lastOpenTime
    }

    return openTime
  }

  /**
   * Clear all telemetry data
   */
  clear(): void {
    this.events = []
    this.circuitBreakerMetrics.clear()
    this.errorMetrics = {
      totalErrors: 0,
      uniqueErrorCodes: 0,
      errorsByCode: {},
      errorsByStatus: {},
      lastErrorTime: null,
      recoveryRate: 0,
    }
    this.startTime = Date.now()
    this.saveToStorage()
  }

  /**
   * Export telemetry data as JSON
   */
  export(): {
    events: TelemetryEvent[]
    circuitBreakers: Record<string, any>
    errors: ErrorMetrics
    exportTime: number
  } {
    return {
      events: this.events,
      circuitBreakers: Object.fromEntries(this.circuitBreakerMetrics),
      errors: this.getErrorMetrics(),
      exportTime: Date.now(),
    }
  }

  // ─────────────────────────────────────────────────────────
  // Private Methods
  // ─────────────────────────────────────────────────────────

  private calculateRecoveryRate(): number {
    // Calculate percentage of errors that were resolved
    // (e.g., circuit breaker closed after opening)
    const opens = this.events.filter((e) => e.details?.newState === 'OPEN').length
    const closes = this.events.filter((e) => e.details?.newState === 'CLOSED').length

    if (opens === 0) return 100

    return Math.round((closes / opens) * 100)
  }

  private saveToStorage(): void {
    try {
      const data = {
        events: this.events.slice(-500), // Keep last 500 events
        circuitBreakers: Object.fromEntries(this.circuitBreakerMetrics),
        errors: this.errorMetrics,
      }
      localStorage.setItem(this.storageKey, JSON.stringify(data))
    } catch (error) {
      console.warn('Failed to save telemetry:', error)
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(this.storageKey)
      if (stored) {
        const data = JSON.parse(stored)
        this.events = data.events || []
        this.errorMetrics = data.errors || this.errorMetrics

        if (data.circuitBreakers) {
          for (const [endpoint, metrics] of Object.entries(data.circuitBreakers)) {
            this.circuitBreakerMetrics.set(endpoint, metrics as CircuitBreakerMetrics)
          }
        }
      }
    } catch (error) {
      console.warn('Failed to load telemetry:', error)
    }
  }

  private setupCleanup(): void {
    // Cleanup old data periodically (every 5 minutes)
    setInterval(() => {
      const fiveMinutesAgo = Date.now() - 5 * 60 * 1000
      this.events = this.events.filter((e) => e.timestamp >= fiveMinutesAgo)
    }, 5 * 60 * 1000)
  }
}

/**
 * Global telemetry instance
 */
export const telemetry = Telemetry.getInstance()
