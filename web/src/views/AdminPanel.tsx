import { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Activity, Wrench, Server,
  CheckCircle, XCircle, AlertCircle, RefreshCw,
  Play, Eye,
} from 'lucide-react'
import api from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

/**
 * BACKEND INTEGRATION:
 * - GET /metrics - System metrics and request statistics
 * - GET /status - Service health and readiness checks
 * - GET /logs/recent - Recent log events
 * - GET /telemetry/report - Telemetry summary
 * - GET /repair-token/refresh - Get repair authorization token
 * - POST /repair - Execute repair actions (requires X-Repair-Token header)
 */

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

function StateIcon({ state }: { state: string }) {
  const s = (state || '').toUpperCase()
  if (s === 'READY') return <CheckCircle size={16} className="text-success" />
  if (s === 'PARTIAL' || s === 'OPTIONAL' || s === 'SKIPPED') return <AlertCircle size={16} className="text-warning" />
  return <XCircle size={16} className="text-coral" />
}

function relativeTime(ts: string | undefined): string {
  if (!ts) return ''
  const diff = Date.now() - new Date(ts).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

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
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-headline text-3xl text-on-surface">Admin Panel</h1>
        <p className="text-on-surface-variant mt-1">System management and monitoring</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-outline-variant pb-2">
        {tabs.map((t) => (
          <button
            type="button"
            key={t.id}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === t.id 
                ? 'bg-primary text-on-primary' 
                : 'text-on-surface-variant hover:bg-surface-container'
            }`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
        <button 
          type="button" 
          className="ml-auto p-2 rounded-lg text-on-surface-variant hover:bg-surface-container"
          onClick={fetchDashboard} 
          title="Refresh"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {loading ? (
            <div className="text-center py-12 text-on-surface-variant">Loading...</div>
          ) : (
            <>
              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <Card className={status?.status === 'healthy' ? 'border-success' : 'border-warning'}>
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 mb-2">
                      {status?.status === 'healthy' 
                        ? <CheckCircle className="text-success" size={20} />
                        : <AlertCircle className="text-warning" size={20} />
                      }
                    </div>
                    <p className="text-sm text-on-surface-variant">System Status</p>
                    <p className="font-semibold text-on-surface">
                      {(status?.status ?? 'unknown').toUpperCase()}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-primary">
                      {metrics?.started_at ? formatUptime(metrics.started_at) : '—'}
                    </p>
                    <p className="text-sm text-on-surface-variant">Uptime</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-on-surface">
                      {(metrics?.requests_total ?? 0).toLocaleString()}
                    </p>
                    <p className="text-sm text-on-surface-variant">Total Requests</p>
                  </CardContent>
                </Card>

                <Card className={metrics?.errors_total ? 'border-coral' : ''}>
                  <CardContent className="pt-4">
                    <p className={`text-2xl font-bold ${metrics?.errors_total ? 'text-coral' : 'text-on-surface'}`}>
                      {metrics?.errors_total ?? 0}
                    </p>
                    <p className="text-sm text-on-surface-variant">Errors</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-on-surface">
                      {(metrics?.average_latency_ms ?? 0).toFixed(0)}ms
                    </p>
                    <p className="text-sm text-on-surface-variant">Avg Latency</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-primary">
                      {Object.values(checks).filter((c) => c.state === 'READY').length}
                      /{Object.keys(checks).length || '—'}
                    </p>
                    <p className="text-sm text-on-surface-variant">Services Ready</p>
                  </CardContent>
                </Card>
              </div>

              {/* Service Readiness */}
              <Card>
                <CardHeader>
                  <CardTitle>Service Readiness</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(checks).map(([name, check]) => (
                      <div key={name} className="flex items-start gap-3 p-3 rounded-lg bg-surface-container">
                        <StateIcon state={check.state} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-on-surface">{name}</span>
                            <Badge variant={check.state === 'READY' ? 'success' : check.state === 'PARTIAL' ? 'warning' : 'destructive'}>
                              {check.state}
                            </Badge>
                          </div>
                          <p className="text-sm text-on-surface-variant truncate">{check.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Top Endpoints */}
              {metrics && Object.keys(metrics.path_counts ?? {}).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Top Endpoints</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(metrics.path_counts)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 8)
                        .map(([path, count]) => (
                          <div key={path} className="flex items-center justify-between py-2 border-b border-outline-variant last:border-0">
                            <code className="text-sm font-mono text-on-surface">{path}</code>
                            <Badge variant="secondary">{count}</Badge>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="font-headline text-xl text-on-surface">Last 60 Minutes</h3>
            <Button variant="ghost" size="sm" onClick={fetchActivity}>
              <RefreshCw size={16} />
            </Button>
          </div>

          {telemetry && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold text-primary">{telemetry.report.total_events}</p>
                  <p className="text-sm text-on-surface-variant">Events</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold text-on-surface">{telemetry.report.active_sessions}</p>
                  <p className="text-sm text-on-surface-variant">Sessions</p>
                </CardContent>
              </Card>
              {telemetry.report.latency_ms && (
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-on-surface">{telemetry.report.latency_ms.avg.toFixed(0)}ms</p>
                    <p className="text-sm text-on-surface-variant">Avg Latency</p>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Recent Session Events</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {(logs?.session_events ?? []).slice(0, 20).map((ev, i) => (
                  <div 
                    key={i} 
                    className={`flex items-center justify-between p-2 rounded-lg ${
                      ev.level === 'error' ? 'bg-coral/10' : ev.level === 'warning' ? 'bg-warning/10' : 'bg-surface-container'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-on-surface">{ev.stream ?? ev.event ?? '—'}</span>
                      <p className="text-xs text-on-surface-variant truncate">
                        {typeof ev.payload === 'object' && ev.payload
                          ? JSON.stringify(ev.payload).slice(0, 100)
                          : String(ev.event ?? '')}
                      </p>
                    </div>
                    <span className="text-xs text-on-surface-variant ml-2">{relativeTime(ev.ts)}</span>
                  </div>
                ))}
                {!logs?.session_events?.length && (
                  <p className="text-center py-4 text-on-surface-variant">No session events yet</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Recovery Tab */}
      {activeTab === 'recovery' && (
        <div className="space-y-6">
          <div className={`flex items-center gap-2 p-3 rounded-lg ${repairToken ? 'bg-success/10' : 'bg-coral/10'}`}>
            {repairToken 
              ? <><CheckCircle size={16} className="text-success" /> Repair token acquired</>
              : <><XCircle size={16} className="text-coral" /> No repair token (localhost only)</>
            }
          </div>

          <div className="grid gap-4">
            {[
              { action: 'warmup', label: 'Warmup', desc: 'Refresh startup readiness checks and clear status cache' },
              { action: 'restart_daemon', label: 'Restart Daemon', desc: 'Stop then restart the background daemon manager' },
              { action: 'audit_runtime', label: 'Audit Runtime', desc: 'Write a diagnostics bundle JSON to the runtime directory' },
            ].map(({ action, label, desc }) => (
              <Card key={action}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-on-surface">{label}</h4>
                      <p className="text-sm text-on-surface-variant">{desc}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!repairToken || repairRunning}
                        onClick={() => runRepair(action, true)}
                      >
                        <Eye size={14} className="mr-1" />
                        Preview
                      </Button>
                      <Button
                        size="sm"
                        disabled={!repairToken || repairRunning}
                        onClick={() => runRepair(action, false)}
                      >
                        <Play size={14} className="mr-1" />
                        {repairRunning ? 'Running...' : 'Run'}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {repairResults && (
            <Card className={repairResults.ok ? 'border-success' : 'border-coral'}>
              <CardContent className="pt-4">
                <p className={`font-semibold ${repairResults.ok ? 'text-success' : 'text-coral'}`}>
                  {repairResults.ok ? 'Success' : 'Failed'}
                </p>
                <pre className="mt-2 text-xs bg-surface-container p-2 rounded overflow-auto max-h-48">
                  {JSON.stringify(repairResults, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* System Tab */}
      {activeTab === 'system' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Runtime Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Local Backend', value: status?.local_runtime?.backend ?? '—' },
                  { label: 'Runtime State', value: status?.local_runtime?.state ?? '—' },
                  { label: 'Chat Ready', value: status?.local_runtime?.chat_ready ? 'Yes' : 'No' },
                  { label: 'Memory', value: status?.memory_available ? 'Available' : 'Unavailable' },
                  { label: 'Voice', value: status?.voice_available ? 'Available' : 'Unavailable' },
                  { label: 'Daemon', value: status?.daemon_available ? 'Running' : 'Not Running' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between py-2 border-b border-outline-variant">
                    <span className="text-on-surface-variant">{label}</span>
                    <span className="font-medium text-on-surface">{value}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {metrics && Object.keys(metrics.status_counts ?? {}).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Request Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(metrics.status_counts).map(([code, n]) => (
                    <Badge 
                      key={code} 
                      variant={code.startsWith('2') ? 'success' : code.startsWith('4') ? 'warning' : 'destructive'}
                    >
                      {code}: {n}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
