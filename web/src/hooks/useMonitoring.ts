/**
 * useMonitoring Hook
 *
 * Provides real-time access to:
 * - Circuit breaker state and metrics
 * - Request queue status
 * - Error telemetry
 * - Performance metrics
 * - System health indicators
 *
 * Updates automatically when metrics change
 */

import { useState, useEffect, useCallback } from 'react'
import { telemetry } from '../utils/telemetry'
import { getCircuitBreaker, getAllCircuitBreakerStates } from '../utils/circuitBreaker'
import { RequestQueue } from '../utils/requestQueue'

export interface MonitoringData {
  // Circuit Breaker
  circuitBreakerStates: Record<string, string>
  openEndpoints: string[]

  // Request Queue
  queuedRequestCount: number
  queuedByPriority: Record<string, number>

  // Errors
  totalErrors: number
  errorRate: number // percentage
  lastErrorTime: number | null
  topErrors: Array<{ code: string; count: number }>

  // Performance
  averageResponseTime: number
  successRate: number

  // Health
  isHealthy: boolean
  criticalIssues: string[]
}

export function useMonitoring(refreshInterval: number = 2000): MonitoringData {
  const [monitoring, setMonitoring] = useState<MonitoringData>({
    circuitBreakerStates: {},
    openEndpoints: [],
    queuedRequestCount: 0,
    queuedByPriority: {},
    totalErrors: 0,
    errorRate: 0,
    lastErrorTime: null,
    topErrors: [],
    averageResponseTime: 0,
    successRate: 100,
    isHealthy: true,
    criticalIssues: [],
  })

  const updateMonitoring = useCallback(() => {
    const queue = RequestQueue.getInstance()
    const snapshot = telemetry.getSnapshot()
    const errors = telemetry.getErrorMetrics()
    const successRate = telemetry.getSuccessRate(60)

    // Get circuit breaker states
    const circuitStates = getAllCircuitBreakerStates()
    const openEndpoints = Object.entries(circuitStates)
      .filter(([_, state]) => state === 'OPEN')
      .map(([endpoint, _]) => endpoint)

    // Get queue stats
    const queueStats = queue.getStats()

    // Get top errors
    const topErrors = Object.entries(errors.errorsByCode)
      .map(([code, count]) => ({ code, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)

    // Calculate error rate
    const totalRequests = telemetry.getEvents({ since: Date.now() - 3600000 }).length // Last hour
    const errorRate = totalRequests > 0 ? Math.round((errors.totalErrors / totalRequests) * 100) : 0

    // Determine critical issues
    const criticalIssues: string[] = []
    if (openEndpoints.length > 0) {
      criticalIssues.push(`${openEndpoints.length} service(s) unhealthy`)
    }
    if (queueStats.total > 100) {
      criticalIssues.push(`${queueStats.total} requests queued`)
    }
    if (errorRate > 10) {
      criticalIssues.push(`High error rate: ${errorRate}%`)
    }

    const isHealthy = criticalIssues.length === 0 && successRate >= 95

    setMonitoring({
      circuitBreakerStates: circuitStates,
      openEndpoints,
      queuedRequestCount: queueStats.total,
      queuedByPriority: queueStats.byPriority,
      totalErrors: errors.totalErrors,
      errorRate,
      lastErrorTime: errors.lastErrorTime,
      topErrors,
      averageResponseTime: snapshot.averageResponseTime,
      successRate,
      isHealthy,
      criticalIssues,
    })
  }, [])

  useEffect(() => {
    updateMonitoring()
    const interval = setInterval(updateMonitoring, refreshInterval)
    return () => clearInterval(interval)
  }, [updateMonitoring, refreshInterval])

  return monitoring
}

/**
 * Hook for monitoring a specific endpoint
 */
export function useEndpointMonitoring(endpoint: string, refreshInterval: number = 2000) {
  const [metrics, setMetrics] = useState({
    state: 'CLOSED' as 'CLOSED' | 'OPEN' | 'HALF_OPEN',
    failureCount: 0,
    successCount: 0,
    totalStateChanges: 0,
    openTime: 0, // milliseconds
    isOpen: false,
  })

  const updateMetrics = useCallback(() => {
    const breaker = getCircuitBreaker(endpoint)
    const cbMetrics = breaker.getDiagnostics()
    const openTime = telemetry.getCircuitBreakerOpenTime(endpoint, 60)

    setMetrics({
      state: cbMetrics.state,
      failureCount: cbMetrics.failureCount,
      successCount: cbMetrics.successCount,
      totalStateChanges: telemetry
        .getAllCircuitBreakerMetrics()
        .find((m) => m.endpoint === endpoint)?.totalStateChanges || 0,
      openTime,
      isOpen: cbMetrics.state === 'OPEN',
    })
  }, [endpoint])

  useEffect(() => {
    updateMetrics()
    const interval = setInterval(updateMetrics, refreshInterval)
    return () => clearInterval(interval)
  }, [updateMetrics, refreshInterval])

  return metrics
}

/**
 * Hook for monitoring request queue
 */
export function useQueueMonitoring(refreshInterval: number = 1000) {
  const [queueStatus, setQueueStatus] = useState({
    queuedCount: 0,
    byPriority: {} as Record<string, number>,
    isPaused: false,
    isFlushing: false,
    oldestAgeSeconds: null as number | null,
    averageAgeSeconds: 0,
  })

  const updateQueueStatus = useCallback(() => {
    const queue = RequestQueue.getInstance()
    const stats = queue.getStats()

    const oldestAge = stats.oldestRequest
      ? Math.round((Date.now() - stats.oldestRequest) / 1000)
      : null

    setQueueStatus({
      queuedCount: stats.total,
      byPriority: stats.byPriority,
      isPaused: stats.isPaused,
      isFlushing: stats.isFlushing,
      oldestAgeSeconds: oldestAge,
      averageAgeSeconds: oldestAge ? Math.round(oldestAge / Math.max(stats.total, 1)) : 0,
    })
  }, [])

  useEffect(() => {
    updateQueueStatus()
    const interval = setInterval(updateQueueStatus, refreshInterval)
    return () => clearInterval(interval)
  }, [updateQueueStatus, refreshInterval])

  return queueStatus
}

/**
 * Hook for monitoring error metrics
 */
export function useErrorMonitoring(refreshInterval: number = 3000) {
  const [errorStatus, setErrorStatus] = useState({
    totalErrors: 0,
    uniqueErrorCodes: 0,
    errorRate: 0, // percentage
    lastErrorTime: null as number | null,
    topErrors: [] as Array<{ code: string; count: number }>,
    recoveryRate: 0, // percentage
  })

  const updateErrorStatus = useCallback(() => {
    const errors = telemetry.getErrorMetrics()
    const successRate = telemetry.getSuccessRate(60)
    const errorRate = 100 - successRate

    const topErrors = Object.entries(errors.errorsByCode)
      .map(([code, count]) => ({ code, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)

    setErrorStatus({
      totalErrors: errors.totalErrors,
      uniqueErrorCodes: errors.uniqueErrorCodes,
      errorRate,
      lastErrorTime: errors.lastErrorTime,
      topErrors,
      recoveryRate: errors.recoveryRate,
    })
  }, [])

  useEffect(() => {
    updateErrorStatus()
    const interval = setInterval(updateErrorStatus, refreshInterval)
    return () => clearInterval(interval)
  }, [updateErrorStatus, refreshInterval])

  return errorStatus
}

/**
 * Hook for getting system health status
 */
export function useSystemHealth() {
  const monitoring = useMonitoring(3000)

  return {
    isHealthy: monitoring.isHealthy,
    criticalIssues: monitoring.criticalIssues,
    openEndpoints: monitoring.openEndpoints,
    successRate: monitoring.successRate,
    errorRate: monitoring.errorRate,
    queuedRequests: monitoring.queuedRequestCount,
  }
}
