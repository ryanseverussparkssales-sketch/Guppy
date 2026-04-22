import { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Activity, Wrench, Server,
  CheckCircle, XCircle, AlertCircle, RefreshCw,
  Play, Eye,
} from 'lucide-react'
import api from '../api/client'
import './AdminPanel.css'

// ── types ─────────────────────────────────────────────────────────────────────

interface Metrics {
  started_at: string
  requests_total: number
  errors_total: number
  slow_requests: number
  average_latency_ms: number
  path_counts: Record<string, number>
  status_counts: Record<string, number>
}

interface ReadinessCheck {
  state: string
  detail: string
  [key: string]: unknown
}

interface StatusPayload {
  status: string
  memory_available: boolean
  voice_available: boolean
  daemon_available: boolean
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
  resource_envelope?: Record<string, unknown>
}

interface LogEvent {
  ts?: string
  stream?: string
  event?: string
  level?: string
  payload?: Record<string, unknown>
  [key: string]: unknown
}

interface LogsPayload {
  session_events: LogEvent[]
  agent_performance: LogEvent[]
  integration_events: LogEvent[]
}

interface TelemetryReport {
  report: {
    total_events: number
    streams: Record<string, number>
    levels: Record<string, number>
    top_events: { event: string; count: number }[]
    active_sessions: number
    latency_ms?: { avg: number; p95: number; max: number }
  }
}

type Tab = 'dashboard' | 'activity' | 'recovery' | 'system'

// ── helpers ───────────────────────────────────────────────────────────────────

function formatUptime(startedAt: string): string {
  const diffMs = Date.now() - new Date(startedAt).getTime()
  const s = Math.floor(diffMs / 1000)
  const m = Math.floor(s / 60)
  const h = Math.floor(m / 60)
  const d = Math.floor(h / 24)
  if (d > 0) return `${d}d ${h % 24}h`
  if (h > 0) return `${h}h ${m % 60}m`
  return `${m}m ${s % 60}s`
}

function stateColor(state: string): string {
  const s = (state || '').toUpperCase()
  if (s === 'READY') return 'check-ok'
  if (s === 'PARTIAL' || s === 'OPTIONAL') return 'check-warn'
  return 'check-err'
}

function StateIcon({ state }: { state: string }) {
  const s = (state || '').toUpperCase()
  if (s === 'READY') return <CheckCircle size={16} className="check-ok" />
  if (s === 'PARTIAL' || s === 'OPTIONAL' || s === 'SKIPPED') return <AlertCircle size={16} className="check-warn" />
  return <XCircle size={16} className="check-err" />
}

function relativeTime(ts: string | undefined): string {
  if (!ts) return ''
  const diff = Date.now() - new Date(ts).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

// ── component ─────────────────────────────────────────────────────────────────

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [status, setStatus] = useState<StatusPayload | null>(null)
  const [logs, setLogs] = useState<LogsPayload | null>(null)
  const [telemetry, setTelemetry] = useState<TelemetryReport | null>(null)
  const [repairToken, setRepairToken] = useState<string | null>(null)
  const [repairResults, setRepairResults] = useState<Record<string, unknown> | null>(null)
  const [repairRunning, setRepairRunning] = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchDashboard = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([api.get('/metrics'), api.get('/status')])
      setMetrics(m.data)
      setStatus(s.data)
    } catch (e) {
      console.error('dashboard fetch failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchActivity = useCallback(async () => {
    try {
      const [l, t] = await Promise.all([
        api.get('/logs/recent?limit=50'),
        api.get('/telemetry/report?since_minutes=60'),
      ])
      setLogs(l.data)
      setTelemetry(t.data)
    } catch (e) {
      console.error('activity fetch failed', e)
    }
  }, [])

  const fetchRepairToken = useCallback(async () => {
    try {
      const r = await api.get('/repair-token/refresh')
      setRepairToken(r.data.repair_token)
    } catch {
      setRepairToken(null)
    }
  }, [])

  useEffect(() => {
    fetchDashboard()
    const t = setInterval(fetchDashboard, 30000)
    return () => clearInterval(t)
  }, [fetchDashboard])

  useEffect(() => {
    if (activeTab === 'activity') fetchActivity()
    if (activeTab === 'recovery') fetchRepairToken()
  }, [activeTab, fetchActivity, fetchRepairToken])

  const runRepair = async (action: string, dryRun: boolean) => {
    if (!repairToken) return
    setRepairRunning(true)
    setRepairResults(null)
    try {
      const r = await api.post(
        '/repair',
        { action, dry_run: dryRun },
        { headers: { 'X-Repair-Token': repairToken } },
      )
      setRepairResults(r.data)
    } catch (e: unknown) {
      const err = e as { response?: { data?: unknown } }
      setRepairResults({ ok: false, error: err.response?.data || String(e) })
    } finally {
      setRepairRunning(false)
    }
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <BarChart size={16} /> },
    { id: 'activity',  label: 'Activity',  icon: <Activity size={16} /> },
    { id: 'recovery',  label: 'Recovery',  icon: <Wrench size={16} /> },
    { id: 'system',    label: 'System',    icon: <Server size={16} /> },
  ]

  const checks = status?.startup_readiness?.checks ?? {}

  return (
    <div className="admin-container">
      <div className="admin-header">
        <h2>Admin Panel</h2>
        <p>System management and monitoring</p>
      </div>

      <div className="admin-tabs">
        {tabs.map((t) => (
          <button
            type="button"
            key={t.id}
            className={`tab-btn ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
        <button type="button" className="tab-btn refresh-btn" onClick={fetchDashboard} title="Refresh">
          <RefreshCw size={16} />
        </button>
      </div>

      {/* ── DASHBOARD ── */}
      {activeTab === 'dashboard' && (
        <div className="admin-dashboard">
          {loading ? (
            <div className="loading">Loading...</div>
          ) : (
            <>
              <div className="stats-grid">
                <div className={`stat-card ${status?.status === 'healthy' ? 'healthy' : 'warn'}`}>
                  <div className="stat-icon">
                    {status?.status === 'healthy'
                      ? <CheckCircle size={28} />
                      : <AlertCircle size={28} />}
                  </div>
                  <h3>System Status</h3>
                  <p className={status?.status === 'healthy' ? '' : 'warning'}>
                    {(status?.status ?? 'unknown').toUpperCase()}
                  </p>
                </div>

                <div className="stat-card">
                  <div className="stat-value">
                    {metrics?.started_at ? formatUptime(metrics.started_at) : '—'}
                  </div>
                  <h3>Uptime</h3>
                  <p>Since {metrics?.started_at ? new Date(metrics.started_at).toLocaleTimeString() : '—'}</p>
                </div>

                <div className="stat-card">
                  <div className="stat-value">{(metrics?.requests_total ?? 0).toLocaleString()}</div>
                  <h3>Total Requests</h3>
                  <p>{metrics?.slow_requests ?? 0} slow</p>
                </div>

                <div className="stat-card">
                  <div className={`stat-value ${(metrics?.errors_total ?? 0) > 0 ? 'err' : ''}`}>
                    {metrics?.errors_total ?? 0}
                  </div>
                  <h3>Errors</h3>
                  <p className={(metrics?.errors_total ?? 0) > 0 ? 'warning' : ''}>
                    {(metrics?.errors_total ?? 0) > 0 ? 'Detected' : 'None'}
                  </p>
                </div>

                <div className="stat-card">
                  <div className="stat-value">{(metrics?.average_latency_ms ?? 0).toFixed(0)}ms</div>
                  <h3>Avg Latency</h3>
                  <p>API response time</p>
                </div>

                <div className="stat-card">
                  <div className="stat-value">
                    {Object.values(checks).filter((c) => c.state === 'READY').length}
                    /{Object.keys(checks).length || '—'}
                  </div>
                  <h3>Services Ready</h3>
                  <p>{status?.startup_readiness?.overall ?? '—'}</p>
                </div>
              </div>

              <div className="checks-section">
                <h3>Service Readiness</h3>
                <div className="checks-grid">
                  {Object.entries(checks).map(([name, check]) => (
                    <div key={name} className={`check-card ${stateColor(check.state)}-border`}>
                      <div className="check-header">
                        <StateIcon state={check.state} />
                        <span className="check-name">{name}</span>
                        <span className={`check-state ${stateColor(check.state)}`}>{check.state}</span>
                      </div>
                      <p className="check-detail">{check.detail}</p>
                    </div>
                  ))}
                </div>
              </div>

              {metrics && Object.keys(metrics.path_counts ?? {}).length > 0 && (
                <div className="top-paths">
                  <h3>Top Endpoints</h3>
                  <div className="path-list">
                    {Object.entries(metrics.path_counts)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 8)
                      .map(([path, count]) => (
                        <div key={path} className="path-row">
                          <code className="path-name">{path}</code>
                          <span className="path-count">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── ACTIVITY ── */}
      {activeTab === 'activity' && (
        <div className="admin-activity">
          <div className="activity-header">
            <h3>Last 60 Minutes</h3>
            <button type="button" className="btn-icon" onClick={fetchActivity} title="Refresh">
              <RefreshCw size={16} />
            </button>
          </div>

          {telemetry && (
            <div className="telemetry-summary">
              <div className="tel-stat">
                <span className="tel-value">{telemetry.report.total_events}</span>
                <span className="tel-label">Events</span>
              </div>
              <div className="tel-stat">
                <span className="tel-value">{telemetry.report.active_sessions}</span>
                <span className="tel-label">Sessions</span>
              </div>
              {telemetry.report.latency_ms && (
                <div className="tel-stat">
                  <span className="tel-value">{telemetry.report.latency_ms.avg.toFixed(0)}ms</span>
                  <span className="tel-label">Avg Latency</span>
                </div>
              )}
              {Object.entries(telemetry.report.levels).map(([lvl, n]) => (
                <div key={lvl} className="tel-stat">
                  <span className={`tel-value tel-${lvl}`}>{n}</span>
                  <span className="tel-label">{lvl}</span>
                </div>
              ))}
            </div>
          )}

          {telemetry && telemetry.report.top_events.length > 0 && (
            <div className="top-events">
              <h4>Top Events</h4>
              {telemetry.report.top_events.slice(0, 6).map((e) => (
                <div key={e.event} className="event-row">
                  <span className="event-name">{e.event}</span>
                  <span className="event-count">{e.count}</span>
                </div>
              ))}
            </div>
          )}

          <div className="log-section">
            <h4>Recent Session Events</h4>
            <div className="log-list">
              {(logs?.session_events ?? []).slice(0, 20).map((ev, i) => (
                <div key={i} className={`log-item ${ev.level === 'warning' ? 'warn' : ev.level === 'error' ? 'err' : ''}`}>
                  <span className="log-stream">{ev.stream ?? ev.event ?? '—'}</span>
                  <span className="log-msg">
                    {typeof ev.payload === 'object' && ev.payload
                      ? JSON.stringify(ev.payload).slice(0, 100)
                      : String(ev.event ?? '')}
                  </span>
                  <small className="log-time">{relativeTime(ev.ts)}</small>
                </div>
              ))}
              {!logs?.session_events?.length && (
                <div className="log-empty">No session events yet</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── RECOVERY ── */}
      {activeTab === 'recovery' && (
        <div className="admin-recovery">
          <div className="recovery-token-bar">
            {repairToken
              ? <><CheckCircle size={14} className="check-ok" /> Repair token acquired</>
              : <><XCircle size={14} className="check-err" /> No repair token (localhost only)</>}
          </div>

          <div className="repair-actions">
            {[
              {
                action: 'warmup',
                label: 'Warmup',
                desc: 'Refresh startup readiness checks and clear status cache',
              },
              {
                action: 'restart_daemon',
                label: 'Restart Daemon',
                desc: 'Stop then restart the background daemon manager',
              },
              {
                action: 'audit_runtime',
                label: 'Audit Runtime',
                desc: 'Write a diagnostics bundle JSON to the runtime directory',
              },
            ].map(({ action, label, desc }) => (
              <div key={action} className="repair-card">
                <div className="repair-info">
                  <strong>{label}</strong>
                  <p>{desc}</p>
                </div>
                <div className="repair-btns">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={!repairToken || repairRunning}
                    onClick={() => runRepair(action, true)}
                    title="Dry run — preview only"
                  >
                    <Eye size={14} />
                    Preview
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!repairToken || repairRunning}
                    onClick={() => runRepair(action, false)}
                  >
                    <Play size={14} />
                    {repairRunning ? 'Running…' : 'Run'}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {repairResults && (
            <div className={`repair-result ${repairResults.ok ? 'ok' : 'fail'}`}>
              <strong>{repairResults.ok ? '✓ Success' : '✗ Failed'}</strong>
              <pre>{JSON.stringify(repairResults, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* ── SYSTEM ── */}
      {activeTab === 'system' && (
        <div className="admin-system">
          <div className="system-section">
            <h3>Runtime Configuration</h3>
            <div className="info-grid">
              <div className="info-row">
                <span className="info-key">Local Backend</span>
                <span className="info-val">{status?.local_runtime?.backend ?? '—'}</span>
              </div>
              <div className="info-row">
                <span className="info-key">Local Runtime State</span>
                <span className={`info-val ${stateColor(status?.local_runtime?.state ?? '')}`}>
                  {status?.local_runtime?.state ?? '—'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-key">Chat Ready</span>
                <span className="info-val">
                  {status?.local_runtime?.chat_ready ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-key">Memory</span>
                <span className="info-val">
                  {status?.memory_available ? 'Available' : 'Unavailable'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-key">Voice</span>
                <span className="info-val">
                  {status?.voice_available ? 'Available' : 'Unavailable'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-key">Daemon</span>
                <span className="info-val">
                  {status?.daemon_available ? 'Running' : 'Not Running'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-key">API Started</span>
                <span className="info-val">
                  {metrics?.started_at ? new Date(metrics.started_at).toLocaleString() : '—'}
                </span>
              </div>
            </div>
          </div>

          {status?.resource_envelope && Object.keys(status.resource_envelope).length > 0 && (
            <div className="system-section">
              <h3>Resource Envelope</h3>
              <pre className="system-json">
                {JSON.stringify(status.resource_envelope, null, 2)}
              </pre>
            </div>
          )}

          <div className="system-section">
            <h3>Request Distribution</h3>
            <div className="status-codes">
              {Object.entries(metrics?.status_counts ?? {}).map(([code, n]) => (
                <div key={code} className={`code-pill code-${code[0]}xx`}>
                  <span>{code}</span>
                  <span>{n}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
