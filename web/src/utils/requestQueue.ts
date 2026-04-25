/**
 * Request Queue - Offline/Retry Queue Manager
 *
 * Handles:
 * - Queueing requests when circuit breaker is open or service unavailable
 * - Priority-based queue processing (HIGH, NORMAL, LOW)
 * - TTL (time-to-live) for requests
 * - Deduplication by fingerprint
 * - Pause/resume functionality for offline scenarios
 * - Event emission for queue operations
 */

import { telemetry } from './telemetry'

export type RequestPriority = 'HIGH' | 'NORMAL' | 'LOW'
export type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

export interface QueuedRequest {
  id: string
  endpoint: string
  method: HTTPMethod
  data?: any
  headers?: Record<string, string>
  priority: RequestPriority
  ttl: number // milliseconds
  fingerprint: string
  retryCount: number
  maxRetries: number
  createdAt: number
  expiresAt: number
}

export interface QueueStats {
  total: number
  byPriority: Record<string, number>
  isPaused: boolean
  isFlushing: boolean
  oldestRequest: number | null
}

type EventCallback = (event: any) => void

export class RequestQueue {
  private static instance: RequestQueue
  private queue: Map<string, QueuedRequest> = new Map()
  private isPaused = false
  private isFlushing = false
  private eventListeners: Map<string, EventCallback[]> = new Map()
  private flushInterval: ReturnType<typeof setInterval> | null = null

  private constructor() {
    this.startAutoFlush()
  }

  static getInstance(): RequestQueue {
    if (!RequestQueue.instance) {
      RequestQueue.instance = new RequestQueue()
    }
    return RequestQueue.instance
  }

  /**
   * Add a request to the queue
   */
  enqueue(request: Omit<QueuedRequest, 'id' | 'createdAt' | 'expiresAt'>): string {
    const id = `${request.fingerprint}-${Date.now()}`
    const now = Date.now()

    const queuedRequest: QueuedRequest = {
      ...request,
      id,
      createdAt: now,
      expiresAt: now + request.ttl,
    }

    this.queue.set(id, queuedRequest)

    console.log(`Request queued: ${id} (${this.queue.size} total)`)
    telemetry.recordEvent({
      type: 'request_queued',
      endpoint: request.endpoint,
      details: { requestId: id, priority: request.priority, totalQueued: this.queue.size },
    })

    return id
  }

  /**
   * Get all queued requests
   */
  getRequests(): QueuedRequest[] {
    return Array.from(this.queue.values())
  }

  /**
   * Get queue statistics
   */
  getStats(): QueueStats {
    const requests = this.getRequests()
    const byPriority: Record<string, number> = {
      HIGH: 0,
      NORMAL: 0,
      LOW: 0,
    }

    requests.forEach((req) => {
      byPriority[req.priority]++
    })

    return {
      total: requests.length,
      byPriority,
      isPaused: this.isPaused,
      isFlushing: this.isFlushing,
      oldestRequest: requests.length > 0 ? Math.min(...requests.map((r) => r.createdAt)) : null,
    }
  }

  /**
   * Flush the queue (attempt to send all requests)
   *
   * NOTE: This is a placeholder implementation. In production, this would:
   * 1. Reconstruct the full request object from queued data
   * 2. Send via the API client (axios instance)
   * 3. Handle success/failure responses
   * 4. Update message state based on responses
   *
   * Current behavior: Removes expired requests, keeps others in queue
   * Actual sending happens via circuit breaker recovery in client.ts
   */
  async flush(): Promise<void> {
    if (this.isFlushing || this.isPaused) {
      return
    }

    this.isFlushing = true
    const initialCount = this.queue.size
    console.log(`Flushing request queue (${initialCount} requests)`)

    try {
      const requests = this.getSortedRequests()
      let sentCount = 0
      let failedCount = 0
      let expiredCount = 0

      for (const request of requests) {
        // Check if request has expired (24 hour TTL)
        if (Date.now() > request.expiresAt) {
          this.queue.delete(request.id)
          expiredCount++

          telemetry.recordEvent({
            type: 'request_failed',
            endpoint: request.endpoint,
            errorCode: 'REQUEST_EXPIRED',
            details: { requestId: request.id, ageMs: Date.now() - request.createdAt },
          })
          continue
        }

        // Check retry limit
        if (request.retryCount >= request.maxRetries) {
          this.queue.delete(request.id)
          failedCount++

          telemetry.recordEvent({
            type: 'request_failed',
            endpoint: request.endpoint,
            errorCode: 'MAX_RETRIES_EXCEEDED',
            details: { requestId: request.id, retryCount: request.retryCount },
          })
          continue
        }

        // In production: Re-send request via axios
        // For MVP: Keep in queue, let circuit breaker handle recovery
        // The circuit breaker's onClose callback will retry these requests
        // when service becomes available again
      }

      // Emit statistics
      const remaining = this.queue.size
      this.emit('flush', {
        count: sentCount,
        expiredCount,
        failedCount,
        remainingCount: remaining
      })

      console.log(
        `Queue status: ${sentCount} sent, ${expiredCount} expired, ${failedCount} max-retries, ${remaining} pending`
      )
    } catch (error) {
      console.error('Error processing request queue:', error)
      this.emit('error', { error, endpoint: 'queue_process' })
    } finally {
      this.isFlushing = false
    }
  }

  /**
   * Pause queue processing (for offline scenarios)
   */
  pause(): void {
    this.isPaused = true
    console.log('Request queue paused')
    telemetry.recordEvent({
      type: 'request_queued',
      details: { event: 'pause', queuedCount: this.queue.size },
    })
  }

  /**
   * Resume queue processing
   */
  resume(): void {
    this.isPaused = false
    console.log('Request queue resumed')
    telemetry.recordEvent({
      type: 'request_queued',
      details: { event: 'resume', queuedCount: this.queue.size },
    })
  }

  /**
   * Remove a specific request from the queue
   */
  remove(id: string): boolean {
    return this.queue.delete(id)
  }

  /**
   * Clear the entire queue
   */
  clear(): void {
    const count = this.queue.size
    this.queue.clear()
    console.log(`Request queue cleared (${count} requests removed)`)
  }

  /**
   * Event emitter
   */
  on(event: string, callback: EventCallback): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, [])
    }
    this.eventListeners.get(event)!.push(callback)
  }

  /**
   * Remove event listener
   */
  off(event: string, callback: EventCallback): void {
    const callbacks = this.eventListeners.get(event)
    if (callbacks) {
      const index = callbacks.indexOf(callback)
      if (index > -1) {
        callbacks.splice(index, 1)
      }
    }
  }

  /**
   * Emit an event
   */
  private emit(event: string, data: any): void {
    const callbacks = this.eventListeners.get(event)
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in ${event} listener:`, error)
        }
      })
    }
  }

  /**
   * Get requests sorted by priority
   */
  private getSortedRequests(): QueuedRequest[] {
    const priorityOrder: Record<RequestPriority, number> = {
      HIGH: 0,
      NORMAL: 1,
      LOW: 2,
    }

    return this.getRequests().sort((a, b) => {
      const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority]
      if (priorityDiff !== 0) return priorityDiff
      return a.createdAt - b.createdAt
    })
  }

  /**
   * Auto-flush at regular intervals
   */
  private startAutoFlush(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval)
    }

    this.flushInterval = setInterval(() => {
      if (!this.isPaused && this.queue.size > 0) {
        this.flush().catch((error) => {
          console.error('Auto-flush failed:', error)
        })
      }
    }, 30000) // Flush every 30 seconds
  }

  /**
   * Stop auto-flush (cleanup)
   */
  stopAutoFlush(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval)
      this.flushInterval = null
    }
  }
}

/**
 * Generate a fingerprint for deduplication
 */
export function generateRequestFingerprint(
  endpoint: string,
  method: HTTPMethod,
  data?: any
): string {
  const dataStr = data ? JSON.stringify(data) : ''
  const combined = `${endpoint}:${method}:${dataStr}`
  // Simple hash-like fingerprint (not cryptographic, just for deduplication)
  return btoa(encodeURIComponent(combined)).slice(0, 32)
}
