import { useState } from 'react'
import {
  BarChart, Activity, Wrench, Server,
  CheckCircle, XCircle, AlertCircle, RefreshCw,
  Play, Eye,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  useMetrics, useStatus, useLogs, useTelemetry,
  useRepairToken, useRunRepair,
} from '@/api/queries'
import type { Status } from '@/api/schemas'

type ReadinessCheck = NonNullable<Status['startup_readiness']>['checks'][string]

type Tab = 'dashboard' | 'activity' | 'recovery' | 'system'

function formatUptime(startedAt: string): string {
  const s = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
  const m = Math.floor(s / 60), h = Math.floor(m / 60), d = Math.floor(h / 24)
  if (d > 0) return `${d}d ${h % 24}h`
  if (h > 0) return `${h}h ${m % 60}m`
  return `${m}m ${s % 60}s`
}

function relativeTime(ts: string | undefined): string {
  if (!ts) return ''
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function StateIcon({ state }: { state: string }) {
  const s = state.toUpperCase()
  if (s === 'READY') return <CheckCircle size={16} className="text-success" />
  if (['PARTIAL', 'OPTIONAL', 'SKIPPED'].includes(s)) return <AlertCircle size={16} className="text-warning" />
  return <XCircle size={16} className="text-coral" />
}

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [repairResults, setRepairResults] = useState<Record<string, unknown> | null>(null)

  const metrics    = useMetrics()
  const status     = useStatus()
  const logs       = useLogs()
  const telemetry  = useTelemetry()
  const repairQ    = useRepairToken()
  const runRepair  = useRunRepair()

  const repairToken   = repairQ.data ?? null
  const repairRunning = runRepair.isPending

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab)
    if (tab === 'activity') {
      logs.refetch()
      telemetry.refetch()
    }
    if (tab === 'recovery') {
      repairQ.refetch()
    }
  }

  const doRepair = async (action: string, dryRun: boolean) => {
    if (!repairToken) return
    setRepairResults(null)
    try {
      const r = await runRepair.mutateAsync({ action, dryRun, token: repairToken })
      setRepairResults(r.data)
    } catch (e: unknown) {
      const err = e as { response?: { data?: unknown } }
      setRepairResults({ ok: false, error: err.response?.data || String(e) })
    }
  }

  const checks: Record<string, ReadinessCheck> = status.data?.startup_readiness?.checks ?? {}
  const isLoading = metrics.isPending || status.isPending

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <BarChart size={16} /> },
    { id: 'activity',  label: 'Activity',  icon: <Activity size={16} /> },
    { id: 'recovery',  label: 'Recovery',  icon: <Wrench size={16} /> },
    { id: 'system',    label: 'System',    icon: <Server size={16} /> },
  ]

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-headline text-3xl text-on-surface">Admin Panel</h1>
        <p className="text-on-surface-variant mt-1">System management and monitoring</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-outline-variant pb-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === t.id
                ? 'bg-primary text-on-primary'
                : 'text-on-surface-variant hover:bg-surface-container'
            }`}
            onClick={() => handleTabChange(t.id)}
          >
            {t.icon}{t.label}
          </button>
        ))}
        <button
          type="button"
          className="ml-auto p-2 rounded-lg text-on-surface-variant hover:bg-surface-container"
          onClick={() => { metrics.refetch(); status.refetch() }}
          title="Refresh"
        >
          <RefreshCw size={16} className={metrics.isFetching ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {isLoading ? (
            <div className="text-center py-12 text-on-surface-variant">Loading…</div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <Card className={status.data?.status === 'healthy' ? 'border-success' : 'border-warning'}>
                  <CardContent className="pt-4">
                    <div className="mb-2">
                      {status.data?.status === 'healthy'
                        ? <CheckCircle className="text-success" size={20} />
                        : <AlertCircle className="text-warning" size={20} />}
                    </div>
                    <p className="text-sm text-on-surface-variant">Status</p>
                    <p className="font-semibold text-on-surface">{(status.data?.status ?? 'unknown').toUpperCase()}</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-primary">
                      {metrics.data?.started_at ? formatUptime(metrics.data.started_at) : '—'}
                    </p>
                    <p className="text-sm text-on-surface-variant">Uptime</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-on-surface">
                      {(metrics.data?.requests_total ?? 0).toLocaleString()}
                    </p>
                    <p className="text-sm text-on-surface-variant">Requests</p>
                  </CardContent>
                </Card>

                <Card className={metrics.data?.errors_total ? 'border-coral' : ''}>
                  <CardContent className="pt-4">
                    <p className={`text-2xl font-bold ${metrics.data?.errors_total ? 'text-coral' : 'text-on-surface'}`}>
                      {metrics.data?.errors_total ?? 0}
                    </p>
                    <p className="text-sm text-on-surface-variant">Errors</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-on-surface">
                      {(metrics.data?.average_latency_ms ?? 0).toFixed(0)}ms
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
                    <p className="text-sm text-on-surface-variant">Ready</p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader><CardTitle>Service Readiness</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(checks).map(([name, check]) => (
                      <div key={name} className="flex items-start gap-3 p-3 rounded-lg bg-surface-container">
                        <StateIcon state={check.state} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-on-surface text-sm">{name}</span>
                            <Badge variant={check.state === 'READY' ? 'success' : check.state === 'PARTIAL' ? 'warning' : 'destructive'}>
                              {check.state}
                            </Badge>
                          </div>
                          <p className="text-xs text-on-surface-variant truncate mt-0.5">{check.detail}</p>
                        </div>
                      </div>
                    ))}
                    {!Object.keys(checks).length && (
                      <p className="text-sm text-on-surface-variant col-span-full">No readiness checks reported</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {metrics.data && Object.keys(metrics.data.path_counts ?? {}).length > 0 && (
                <Card>
                  <CardHeader><CardTitle>Top Endpoints</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-1">
                      {Object.entries(metrics.data.path_counts)
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
            <Button variant="ghost" size="sm" onClick={() => { logs.refetch(); telemetry.refetch() }}>
              <RefreshCw size={16} className={logs.isFetching ? 'animate-spin' : ''} />
            </Button>
          </div>

          {telemetry.data && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold text-primary">{telemetry.data.report.total_events}</p>
                  <p className="text-sm text-on-surface-variant">Events</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold text-on-surface">{telemetry.data.report.active_sessions}</p>
                  <p className="text-sm text-on-surface-variant">Sessions</p>
                </CardContent>
              </Card>
              {telemetry.data.report.latency_ms && (
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-2xl font-bold text-on-surface">{telemetry.data.report.latency_ms.avg.toFixed(0)}ms</p>
                    <p className="text-sm text-on-surface-variant">Avg Latency</p>
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold text-on-surface">
                    {Object.entries(telemetry.data.report.levels).find(([k]) => k === 'error')?.[1] ?? 0}
                  </p>
                  <p className="text-sm text-on-surface-variant">Errors</p>
                </CardContent>
              </Card>
            </div>
          )}

          {logs.isPending && logs.isFetching && (
            <div className="text-center py-8 text-on-surface-variant">Loading logs…</div>
          )}

          <Card>
            <CardHeader><CardTitle>Recent Session Events</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {(logs.data?.session_events ?? []).slice(0, 20).map((ev, i) => (
                  <div
                    key={i}
                    className={`flex items-center justify-between p-2 rounded-lg ${
                      ev.level === 'error' ? 'bg-coral/10' : ev.level === 'warning' ? 'bg-warning/10' : 'bg-surface-container'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-on-surface">{ev.stream ?? ev.event ?? '—'}</span>
                      <p className="text-xs text-on-surface-variant truncate">
                        {ev.payload ? JSON.stringify(ev.payload).slice(0, 100) : String(ev.event ?? '')}
                      </p>
                    </div>
                    <span className="text-xs text-on-surface-variant ml-2 shrink-0">{relativeTime(ev.ts)}</span>
                  </div>
                ))}
                {!logs.data?.session_events?.length && !logs.isFetching && (
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
              ? <><CheckCircle size={16} className="text-success" /> Repair token acquired — localhost session authorized</>
              : <><XCircle size={16} className="text-coral" /> No repair token (localhost only)</>}
          </div>

          <div className="grid gap-4">
            {[
              { action: 'warmup',         label: 'Warmup',         desc: 'Refresh startup readiness checks and clear status cache' },
              { action: 'restart_daemon', label: 'Restart Daemon', desc: 'Stop then restart the background daemon manager' },
              { action: 'audit_runtime',  label: 'Audit Runtime',  desc: 'Write a diagnostics bundle JSON to the runtime directory' },
            ].map(({ action, label, desc }) => (
              <Card key={action}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-on-surface">{label}</h4>
                      <p className="text-sm text-on-surface-variant">{desc}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" disabled={!repairToken || repairRunning} onClick={() => doRepair(action, true)}>
                        <Eye size={14} className="mr-1" /> Preview
                      </Button>
                      <Button size="sm" disabled={!repairToken || repairRunning} onClick={() => doRepair(action, false)}>
                        <Play size={14} className="mr-1" />
                        {repairRunning ? 'Running…' : 'Run'}
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
            <CardHeader><CardTitle>Runtime Configuration</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Local Backend', value: status.data?.local_runtime?.backend ?? '—' },
                  { label: 'Runtime State', value: status.data?.local_runtime?.state ?? '—' },
                  { label: 'Chat Ready',    value: status.data?.local_runtime?.chat_ready ? 'Yes' : 'No' },
                  { label: 'Memory',        value: status.data?.memory_available ? 'Available' : 'Unavailable' },
                  { label: 'Voice',         value: status.data?.voice_available  ? 'Available' : 'Unavailable' },
                  { label: 'Daemon',        value: status.data?.daemon_available ? 'Running'   : 'Not Running' },
                ].map(({ label, value }) => (
                  <div key={label} className="p-3 rounded-lg bg-surface-container">
                    <p className="text-xs text-on-surface-variant">{label}</p>
                    <p className="font-medium text-on-surface">{value}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {status.data?.local_runtime?.models && (
            <Card>
              <CardHeader><CardTitle>Loaded Models</CardTitle></CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {status.data.local_runtime.models.map((m) => (
                    <Badge key={m} variant="secondary" className="font-mono">{m}</Badge>
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
