import { useEffect, useState, useCallback } from 'react'
import { Activity, Zap, Mic, Database, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react'
import api from '../api/client'
import './StatusView.css'

interface ReadinessCheck {
  state: string
  detail: string
}

interface StatusData {
  status?: string
  message?: string
  memory_available?: boolean
  voice_available?: boolean
  daemon_available?: boolean
  guppy_core_available?: boolean
  startup_readiness?: {
    overall: string
    checks: Record<string, ReadinessCheck>
  }
  local_runtime?: {
    state: string
    backend: string
    chat_ready: boolean
    models?: string[]
  }
}

function StateIcon({ state }: { state: string }) {
  const s = (state || '').toUpperCase()
  if (s === 'READY')    return <CheckCircle size={16} className="status-ok-icon" />
  if (s === 'PARTIAL' || s === 'OPTIONAL' || s === 'SKIPPED')
                         return <AlertCircle size={16} className="status-warn-icon" />
  return <XCircle size={16} className="status-err-icon" />
}

export default function StatusView() {
  const [statusData, setStatusData] = useState<StatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true)
      const response = await api.get('/status')
      setStatusData(response.data)
      setLastFetch(new Date())
    } catch (error) {
      console.error('Failed to fetch status:', error)
      setStatusData({ status: 'error', message: 'Failed to fetch system status' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const isHealthy = statusData?.status === 'healthy'
  const checks = statusData?.startup_readiness?.checks ?? {}

  const serviceCards = [
    {
      key: 'api',
      icon: <Activity size={28} />,
      title: 'API Status',
      available: isHealthy,
      label: isHealthy ? 'Healthy' : 'Unhealthy',
      detail: statusData?.message || 'Checking...',
    },
    {
      key: 'core',
      icon: <Zap size={28} />,
      title: 'Guppy Core',
      available: statusData?.guppy_core_available ?? false,
      label: statusData?.guppy_core_available ? 'Available' : 'Unavailable',
      detail: statusData?.guppy_core_available ? 'Core services ready' : 'Limited functionality',
    },
    {
      key: 'memory',
      icon: <Database size={28} />,
      title: 'Memory',
      available: statusData?.memory_available ?? false,
      label: statusData?.memory_available ? 'Available' : 'Unavailable',
      detail: statusData?.memory_available ? 'Memory backend operational' : 'Memory features disabled',
    },
    {
      key: 'voice',
      icon: <Mic size={28} />,
      title: 'Voice System',
      available: statusData?.voice_available ?? false,
      label: statusData?.voice_available ? 'Available' : 'Not Available',
      detail: statusData?.voice_available ? 'Voice features enabled' : 'Voice features disabled',
    },
  ]

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>System Status</h2>
        <div className="status-header-actions">
          {lastFetch && (
            <span className="status-last-fetch">
              Updated {lastFetch.toLocaleTimeString()}
            </span>
          )}
          <button type="button" className="btn btn-secondary" onClick={fetchStatus} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {loading && !statusData ? (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <p>Loading system status...</p>
        </div>
      ) : (
        <>
          <div className="status-grid">
            {serviceCards.map((card) => (
              <div key={card.key} className={`status-card ${card.available ? 'healthy' : 'warning'}`}>
                <div className="status-icon">
                  {card.icon}
                </div>
                <h3>{card.title}</h3>
                <p>{card.label}</p>
                <small>{card.detail}</small>
              </div>
            ))}
          </div>

          {Object.keys(checks).length > 0 && (
            <div className="status-checks">
              <h3>Startup Readiness — {statusData?.startup_readiness?.overall ?? '…'}</h3>
              <div className="status-checks-grid">
                {Object.entries(checks).map(([name, check]) => (
                  <div key={name} className={`status-check-row ${check.state === 'READY' ? 'ok' : check.state === 'PARTIAL' || check.state === 'SKIPPED' ? 'warn' : 'err'}`}>
                    <StateIcon state={check.state} />
                    <span className="status-check-name">{name}</span>
                    <span className="status-check-state">{check.state}</span>
                    <span className="status-check-detail">{check.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {statusData?.local_runtime && (
            <div className="status-runtime">
              <h3>Local Runtime</h3>
              <div className="status-runtime-row">
                <span>Backend</span>
                <strong>{statusData.local_runtime.backend}</strong>
              </div>
              <div className="status-runtime-row">
                <span>State</span>
                <strong>{statusData.local_runtime.state}</strong>
              </div>
              <div className="status-runtime-row">
                <span>Chat Ready</span>
                <strong>{statusData.local_runtime.chat_ready ? 'Yes' : 'No'}</strong>
              </div>
              {statusData.local_runtime.models && statusData.local_runtime.models.length > 0 && (
                <div className="status-runtime-row">
                  <span>Models</span>
                  <strong>{statusData.local_runtime.models.join(', ')}</strong>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
