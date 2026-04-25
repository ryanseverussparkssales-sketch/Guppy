/**
 * Diagnostic Dashboard Component
 *
 * Real-time monitoring and visualization of:
 * - Circuit breaker states
 * - Request queue status
 * - Error metrics
 * - System health
 *
 * Useful for debugging, monitoring, and understanding system behavior
 */

import { useState } from 'react'
import {
  useMonitoring,
  useQueueMonitoring,
  useErrorMonitoring,
  useSystemHealth,
} from '../hooks/useMonitoring'
import { telemetry } from '../utils/telemetry'

interface DiagnosticDashboardProps {
  minimal?: boolean // Compact view
  expanded?: boolean // Detailed view
}

export function DiagnosticDashboard({ minimal = false, expanded = false }: DiagnosticDashboardProps) {
  const monitoring = useMonitoring(2000)
  const queueStatus = useQueueMonitoring(1000)
  const errorStatus = useErrorMonitoring(3000)
  const health = useSystemHealth()
  const [showDetails, setShowDetails] = useState(expanded)

  if (minimal) {
    return <MinimalDashboard health={health} />
  }

  return (
    <div className="diagnostic-dashboard p-4 space-y-4">
      {/* Health Summary */}
      <HealthSummary health={health} onToggleDetails={() => setShowDetails(!showDetails)} />

      {/* Critical Issues */}
      {health.criticalIssues.length > 0 && (
        <CriticalIssuesPanel issues={health.criticalIssues} />
      )}

      {showDetails && (
        <>
          {/* Circuit Breaker Status */}
          <CircuitBreakerPanel states={monitoring.circuitBreakerStates} />

          {/* Request Queue Status */}
          <QueuePanel queueStatus={queueStatus} />

          {/* Error Metrics */}
          <ErrorMetricsPanel errorStatus={errorStatus} />

          {/* Detailed Metrics */}
          <DetailedMetricsPanel monitoring={monitoring} />

          {/* Export and Actions */}
          <ActionsPanel />
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────
// Sub-Components
// ─────────────────────────────────────────────────────────

function MinimalDashboard({ health }: { health: ReturnType<typeof useSystemHealth> }) {
  return (
    <div className="diagnostic-minimal flex items-center gap-2 text-sm">
      <div
        className={`w-3 h-3 rounded-full ${health.isHealthy ? 'bg-green-500' : 'bg-red-500'}`}
        title={health.isHealthy ? 'System healthy' : 'System has issues'}
      />
      <span className="text-gray-600">
        {health.isHealthy
          ? '✓ All systems healthy'
          : `⚠ ${health.criticalIssues.length} issue(s)`}
      </span>
      {health.queuedRequests > 0 && (
        <span className="text-amber-600 ml-2">
          📦 {health.queuedRequests} queued
        </span>
      )}
    </div>
  )
}

function HealthSummary({
  health,
  onToggleDetails,
}: {
  health: ReturnType<typeof useSystemHealth>
  onToggleDetails: () => void
}) {
  return (
    <div className="health-summary border rounded-lg p-4 bg-gray-50">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-4 h-4 rounded-full ${
              health.isHealthy ? 'bg-green-500 animate-pulse' : 'bg-red-500 animate-pulse'
            }`}
          />
          <div>
            <h2 className="font-semibold">System Health</h2>
            <p className="text-sm text-gray-600">
              {health.isHealthy ? 'All systems operational' : 'System experiencing issues'}
            </p>
          </div>
        </div>
        <button
          onClick={onToggleDetails}
          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
        >
          Toggle Details
        </button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-4 gap-4 mt-4 text-center">
        <div>
          <div className="text-2xl font-bold text-green-600">{health.successRate}%</div>
          <div className="text-xs text-gray-600">Success Rate</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-red-600">{health.errorRate}%</div>
          <div className="text-xs text-gray-600">Error Rate</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-blue-600">{health.openEndpoints.length}</div>
          <div className="text-xs text-gray-600">Open Circuits</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-amber-600">{health.queuedRequests}</div>
          <div className="text-xs text-gray-600">Queued Requests</div>
        </div>
      </div>
    </div>
  )
}

function CriticalIssuesPanel({ issues }: { issues: string[] }) {
  return (
    <div className="critical-issues border border-red-300 rounded-lg p-4 bg-red-50">
      <h3 className="font-semibold text-red-800 mb-2">⚠️ Critical Issues</h3>
      <ul className="space-y-1">
        {issues.map((issue, i) => (
          <li key={i} className="text-sm text-red-700">
            • {issue}
          </li>
        ))}
      </ul>
    </div>
  )
}

function CircuitBreakerPanel({ states }: { states: Record<string, string> }) {
  const endpoints = Object.entries(states).sort()

  return (
    <div className="circuit-breaker-panel border rounded-lg p-4">
      <h3 className="font-semibold mb-3">🔌 Circuit Breakers</h3>
      <div className="space-y-2">
        {endpoints.length === 0 ? (
          <p className="text-sm text-gray-500">No circuit breakers tracked</p>
        ) : (
          endpoints.map(([endpoint, state]) => (
            <CircuitBreakerRow key={endpoint} endpoint={endpoint} state={state} />
          ))
        )}
      </div>
    </div>
  )
}

function CircuitBreakerRow({ endpoint, state }: { endpoint: string; state: string }) {
  const stateColor =
    state === 'CLOSED'
      ? 'bg-green-100 text-green-800'
      : state === 'OPEN'
        ? 'bg-red-100 text-red-800'
        : 'bg-yellow-100 text-yellow-800'

  const stateIcon = state === 'CLOSED' ? '✓' : state === 'OPEN' ? '✕' : '⟳'

  return (
    <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
      <span className="text-sm font-mono">{endpoint}</span>
      <span className={`px-2 py-1 rounded text-xs font-semibold ${stateColor}`}>
        {stateIcon} {state}
      </span>
    </div>
  )
}

function QueuePanel({
  queueStatus,
}: {
  queueStatus: ReturnType<typeof useQueueMonitoring>
}) {
  return (
    <div className="queue-panel border rounded-lg p-4">
      <h3 className="font-semibold mb-3">📦 Request Queue</h3>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-3xl font-bold text-blue-600">{queueStatus.queuedCount}</div>
          <div className="text-xs text-gray-600">Queued Requests</div>
        </div>
        <div>
          <div className="text-3xl font-bold text-gray-600">
            {queueStatus.oldestAgeSeconds ? `${queueStatus.oldestAgeSeconds}s` : '—'}
          </div>
          <div className="text-xs text-gray-600">Oldest Request Age</div>
        </div>
      </div>

      {queueStatus.queuedCount > 0 && (
        <div className="bg-gray-50 rounded p-3">
          <div className="text-xs font-semibold text-gray-700 mb-2">By Priority</div>
          <div className="space-y-1">
            {Object.entries(queueStatus.byPriority)
              .filter(([_, count]) => count > 0)
              .map(([priority, count]) => (
                <div key={priority} className="flex justify-between text-xs">
                  <span className="text-gray-600">{priority}</span>
                  <span className="font-semibold">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {queueStatus.isPaused && (
        <div className="mt-2 text-xs text-amber-600 font-semibold">⏸ Queue paused (offline)</div>
      )}
      {queueStatus.isFlushing && (
        <div className="mt-2 text-xs text-blue-600 font-semibold">🔄 Queue flushing...</div>
      )}
    </div>
  )
}

function ErrorMetricsPanel({
  errorStatus,
}: {
  errorStatus: ReturnType<typeof useErrorMonitoring>
}) {
  return (
    <div className="error-metrics-panel border rounded-lg p-4">
      <h3 className="font-semibold mb-3">❌ Error Metrics</h3>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-2xl font-bold text-red-600">{errorStatus.totalErrors}</div>
          <div className="text-xs text-gray-600">Total Errors</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-orange-600">
            {errorStatus.uniqueErrorCodes}
          </div>
          <div className="text-xs text-gray-600">Unique Codes</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-green-600">{errorStatus.recoveryRate}%</div>
          <div className="text-xs text-gray-600">Recovery Rate</div>
        </div>
      </div>

      {errorStatus.topErrors.length > 0 && (
        <div className="bg-gray-50 rounded p-3">
          <div className="text-xs font-semibold text-gray-700 mb-2">Top Errors</div>
          <div className="space-y-1">
            {errorStatus.topErrors.map((error) => (
              <div key={error.code} className="flex justify-between text-xs">
                <span className="text-gray-600 font-mono">{error.code}</span>
                <span className="font-semibold text-red-600">{error.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {errorStatus.lastErrorTime && (
        <div className="mt-2 text-xs text-gray-600">
          Last error: {new Date(errorStatus.lastErrorTime).toLocaleTimeString()}
        </div>
      )}
    </div>
  )
}

function DetailedMetricsPanel({
  monitoring,
}: {
  monitoring: ReturnType<typeof useMonitoring>
}) {
  return (
    <div className="detailed-metrics border rounded-lg p-4">
      <h3 className="font-semibold mb-3">📊 Performance Metrics</h3>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-blue-50 rounded p-3">
          <div className="text-xs text-gray-600 mb-1">Avg Response Time</div>
          <div className="text-2xl font-bold text-blue-600">
            {monitoring.averageResponseTime}ms
          </div>
        </div>

        <div className="bg-green-50 rounded p-3">
          <div className="text-xs text-gray-600 mb-1">Success Rate</div>
          <div className="text-2xl font-bold text-green-600">{monitoring.successRate}%</div>
        </div>

        <div className="bg-purple-50 rounded p-3">
          <div className="text-xs text-gray-600 mb-1">System Uptime</div>
          <div className="text-2xl font-bold text-purple-600">—</div>
        </div>
      </div>
    </div>
  )
}

function ActionsPanel() {
  const handleExport = () => {
    const data = telemetry.export()
    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `guppy-telemetry-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClear = () => {
    if (confirm('Clear all telemetry data?')) {
      telemetry.clear()
    }
  }

  return (
    <div className="actions-panel border rounded-lg p-4">
      <h3 className="font-semibold mb-3">⚙️ Actions</h3>
      <div className="flex gap-2">
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
        >
          📥 Export Telemetry
        </button>
        <button
          onClick={handleClear}
          className="px-4 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600"
        >
          🗑️ Clear Data
        </button>
      </div>
    </div>
  )
}

export default DiagnosticDashboard
