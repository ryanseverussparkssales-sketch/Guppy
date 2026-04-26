import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/api/client'
import { toast } from 'sonner'
import DesktopView from './DesktopView'
import InstancesView from './InstancesView'

// ── types ─────────────────────────────────────────────────────────────────────
interface Service {
  name: string
  label: string
  description: string
  state: 'running' | 'stopped'
  pid: number | null
  started_at: string | null
  port: number | null
  type: 'managed' | 'external'
  icon: string
  has_logs: boolean
  health: 'up' | 'down' | 'degraded' | 'unknown'
  latency_ms: number | null
  health_detail: string
}

interface LogData { lines: string[]; total?: number; note?: string }
interface DebugInfo {
  platform: string; python: string; cwd: string
  ports: Record<string, boolean>; env: Record<string, string>
  registry_file: string; recent_errors: string[]
}

type TabId = 'services' | 'instances' | 'health' | 'logs' | 'debug' | 'desktop'

// ── helpers ───────────────────────────────────────────────────────────────────
const reltime = (iso: string) => {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60)   return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  return `${Math.round(diff / 3600)}h ago`
}

const healthColor = (h: string) => ({
  up: 'text-green-400', down: 'text-red-400', degraded: 'text-yellow-400', unknown: 'text-slate-500',
}[h] ?? 'text-slate-500')

const stateDot = (state: string, health: string) => {
  if (state === 'running') return health === 'up' ? 'bg-green-400 shadow-[0_0_6px_#22c55e]' : 'bg-yellow-400'
  return 'bg-slate-600'
}

// ── query keys ────────────────────────────────────────────────────────────────
const QK = {
  services: ['launcher', 'services'] as const,
  logs:     (name: string) => ['launcher', 'logs', name] as const,
  debug:    ['launcher', 'debug'] as const,
}

// ── main view ─────────────────────────────────────────────────────────────────
export default function LauncherView() {
  const [tab, setTab]         = useState<TabId>('services')
  const [logService, setLogService] = useState<string>('')
  const qc = useQueryClient()

  const { data: services = [], isLoading } = useQuery<Service[]>({
    queryKey: QK.services,
    queryFn:  () => apiClient.get('/api/launcher/services').then((r: { data: Service[] }) => r.data),
    refetchInterval: 5000,
  })

  const { data: debugData } = useQuery<DebugInfo>({
    queryKey: QK.debug,
    queryFn:  () => apiClient.get('/api/launcher/debug').then((r: { data: DebugInfo }) => r.data),
    enabled:  tab === 'debug',
    refetchInterval: tab === 'debug' ? 10000 : false,
  })

  const { data: logData } = useQuery<LogData>({
    queryKey: QK.logs(logService),
    queryFn:  () => apiClient.get(`/api/launcher/services/${logService}/logs?lines=200`).then((r: { data: LogData }) => r.data),
    enabled:  tab === 'logs' && !!logService,
    refetchInterval: tab === 'logs' ? 4000 : false,
  })

  const startMut   = useMutation({ mutationFn: (n: string) => apiClient.post(`/api/launcher/services/${n}/start`),   onSuccess: () => qc.invalidateQueries({ queryKey: QK.services }), onError: (e: { response?: { data?: { detail?: string } }; message: string }) => toast.error(`Start failed: ${e.response?.data?.detail ?? e.message}`) })
  const stopMut    = useMutation({ mutationFn: (n: string) => apiClient.post(`/api/launcher/services/${n}/stop`),    onSuccess: () => qc.invalidateQueries({ queryKey: QK.services }), onError: (e: { response?: { data?: { detail?: string } }; message: string }) => toast.error(`Stop failed: ${e.response?.data?.detail ?? e.message}`) })
  const restartMut = useMutation({ mutationFn: (n: string) => apiClient.post(`/api/launcher/services/${n}/restart`), onSuccess: () => { qc.invalidateQueries({ queryKey: QK.services }); toast.success('Service restarted') }, onError: (e: { response?: { data?: { detail?: string } }; message: string }) => toast.error(`Restart failed: ${e.response?.data?.detail ?? e.message}`) })
  const resetMut   = useMutation({ mutationFn: (n: string) => apiClient.post(`/api/launcher/services/${n}/reset`),   onSuccess: () => { qc.invalidateQueries({ queryKey: QK.services }); toast.success('Service reset') }, onError: (e: { response?: { data?: { detail?: string } }; message: string }) => toast.error(`Reset failed: ${e.response?.data?.detail ?? e.message}`) })
  const startAllMut = useMutation({ mutationFn: () => apiClient.post('/api/launcher/start-all'), onSuccess: () => { qc.invalidateQueries({ queryKey: QK.services }); toast.success('All managed services started') } })
  const stopAllMut  = useMutation({ mutationFn: () => apiClient.post('/api/launcher/stop-all'),  onSuccess: () => { qc.invalidateQueries({ queryKey: QK.services }); toast.success('All services stopped') } })

  const up = services.filter(s => s.health === 'up').length
  const total = services.length
  const overallHealth = up === total ? 'healthy' : up > 0 ? 'degraded' : 'down'
  const overallColor = { healthy: 'text-green-400', degraded: 'text-yellow-400', down: 'text-red-400' }[overallHealth]

  const showLogs = (name: string) => { setLogService(name); setTab('logs') }

  const TABS: { id: TabId; label: string }[] = [
    { id: 'services',  label: 'Services' },
    { id: 'instances', label: 'Instances' },
    { id: 'health',    label: 'Health' },
    { id: 'logs',      label: 'Logs' },
    { id: 'debug',     label: 'Debug' },
    { id: 'desktop',   label: 'Desktop' },
  ]

  return (
    <div className="flex flex-col h-full bg-[#0a0a10] text-slate-200">
      {/* header */}
      <div className="flex items-center gap-3 px-5 h-13 bg-[#12121a] border-b border-[#252535] shrink-0">
        <h1 className="font-bold text-sm tracking-tight">
          Guppy <span className="text-indigo-400">Platform</span>
        </h1>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${overallColor} border-current`}>
          ● {up}/{total} up
        </span>
        <div className="flex-1" />
        <button onClick={() => startAllMut.mutate()} className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-md font-semibold transition-colors">
          ▶ Start All
        </button>
        <button onClick={() => stopAllMut.mutate()} className="text-xs bg-[#1e1e2a] hover:bg-[#252535] border border-[#252535] text-slate-300 px-3 py-1 rounded-md transition-colors">
          ■ Stop All
        </button>
        <button onClick={() => qc.invalidateQueries({ queryKey: QK.services })} className="text-xs bg-transparent border border-[#252535] text-slate-400 px-2 py-1 rounded-md hover:bg-[#1e1e2a] transition-colors">
          ↻
        </button>
      </div>

      {/* tabs */}
      <div className="flex gap-0.5 px-5 bg-[#12121a] border-b border-[#252535] shrink-0">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3.5 py-2.5 text-xs font-medium border-b-2 transition-colors ${
              tab === t.id ? 'border-indigo-400 text-indigo-300' : 'border-transparent text-slate-500 hover:text-slate-400'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-5">
        {/* SERVICES */}
        {tab === 'services' && (
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))' }}>
            {isLoading && <div className="text-slate-500 text-sm">Loading services...</div>}
            {services.map(s => <ServiceCard key={s.name} s={s} onStart={() => startMut.mutate(s.name)} onStop={() => stopMut.mutate(s.name)} onRestart={() => restartMut.mutate(s.name)} onReset={() => resetMut.mutate(s.name)} onLogs={() => showLogs(s.name)} />)}
          </div>
        )}

        {/* HEALTH */}
        {tab === 'health' && <HealthTab services={services} />}

        {/* LOGS */}
        {tab === 'logs' && (
          <div className="flex flex-col gap-3 h-full">
            <div className="flex items-center gap-2">
              <select
                value={logService}
                onChange={e => setLogService(e.target.value)}
                className="bg-[#1e1e2a] border border-[#252535] text-slate-200 rounded-md px-3 py-1.5 text-sm"
              >
                <option value="">— select service —</option>
                {services.filter(s => s.has_logs).map(s => <option key={s.name} value={s.name}>{s.label}</option>)}
              </select>
              <button onClick={() => qc.invalidateQueries({ queryKey: QK.logs(logService) })} className="text-xs border border-[#252535] text-slate-400 px-3 py-1.5 rounded-md hover:bg-[#1e1e2a]">Refresh</button>
              <span className="text-xs text-slate-500 ml-auto">{logData?.total ?? 0} total lines</span>
            </div>
            <pre className="flex-1 bg-[#12121a] border border-[#252535] rounded-lg p-4 font-mono text-xs leading-relaxed overflow-auto whitespace-pre-wrap break-all text-slate-400 min-h-0" style={{ maxHeight: 'calc(100vh - 240px)' }}>
              {logData ? (
                logData.lines.length ? logData.lines.map((l, i) => (
                  <span key={i} className={/ERROR|CRITICAL/i.test(l) ? 'text-red-400' : /WARN/i.test(l) ? 'text-yellow-400' : /INFO/i.test(l) ? 'text-cyan-400' : ''}>
                    {l}{'\n'}
                  </span>
                )) : <span className="text-slate-600">{logData.note ?? 'No log entries.'}</span>
              ) : (logService ? 'Loading...' : 'Select a service to view its logs.')}
            </pre>
          </div>
        )}

        {/* INSTANCES */}
        {tab === 'instances' && <InstancesView />}

        {/* DEBUG */}
        {tab === 'debug' && debugData && <DebugTab d={debugData} />}
        {tab === 'debug' && !debugData && <div className="text-slate-500 text-sm">Loading debug info...</div>}

        {/* DESKTOP */}
        {tab === 'desktop' && <div className="-m-5"><DesktopView /></div>}
      </div>
    </div>
  )
}

// ── service card ──────────────────────────────────────────────────────────────
function ServiceCard({ s, onStart, onStop, onRestart, onReset, onLogs }: {
  s: Service
  onStart: () => void; onStop: () => void; onRestart: () => void; onReset: () => void; onLogs: () => void
}) {
  const running = s.state === 'running'
  const ext = s.type === 'external'
  return (
    <div className={`bg-[#12121a] border rounded-xl p-4 flex flex-col gap-2.5 transition-all ${running ? 'border-l-[3px] border-l-green-500 border-[#252535]' : ext ? 'border-l-[3px] border-l-cyan-500 border-[#252535]' : 'border-[#252535]'}`}>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${stateDot(s.state, s.health)}`} />
        <span className="font-semibold text-sm flex-1 truncate">{s.label}</span>
        {s.port && <span className="text-xs text-cyan-400 font-mono">:{s.port}</span>}
      </div>
      <p className="text-xs text-slate-500 leading-snug">{s.description}</p>
      <div className="flex items-center gap-3 text-xs">
        {running && s.pid && <span className="text-slate-500">PID {s.pid}</span>}
        {running && s.started_at && <span className="text-slate-500">{reltime(s.started_at)}</span>}
        <span className={`${healthColor(s.health)} ml-auto`}>
          {s.latency_ms ? `${s.health} · ${s.latency_ms}ms` : s.health}
        </span>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {ext ? (
          <>
            <span className="text-xs text-slate-600 px-2 py-1">external</span>
            {s.has_logs && <Btn onClick={onLogs} ghost>Logs →</Btn>}
          </>
        ) : (
          <>
            <Btn onClick={onStart} primary disabled={running}>Start</Btn>
            <Btn onClick={onStop}  danger disabled={!running}>Stop</Btn>
            <Btn onClick={onRestart} disabled={!running}>↺</Btn>
            <Btn onClick={onReset}>⟳ Reset</Btn>
            {s.has_logs && <Btn onClick={onLogs} ghost>Logs →</Btn>}
          </>
        )}
      </div>
    </div>
  )
}

function Btn({ onClick, children, primary, danger, ghost, disabled }: {
  onClick: () => void; children: React.ReactNode
  primary?: boolean; danger?: boolean; ghost?: boolean; disabled?: boolean
}) {
  const base = 'text-xs px-2.5 py-1 rounded-md font-medium transition-colors disabled:opacity-40 disabled:cursor-default'
  const variant = primary ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
    : danger   ? 'bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/30'
    : ghost    ? 'bg-transparent border border-[#252535] text-slate-400 hover:bg-[#1e1e2a]'
    :            'bg-[#1e1e2a] hover:bg-[#252535] text-slate-300 border border-[#252535]'
  return <button onClick={onClick} disabled={disabled} className={`${base} ${variant}`}>{children}</button>
}

// ── health tab ────────────────────────────────────────────────────────────────
function HealthTab({ services }: { services: Service[] }) {
  const up = services.filter(s => s.health === 'up').length
  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-4">
        {[
          { num: up, label: 'Up', color: 'text-green-400' },
          { num: services.length, label: 'Total', color: 'text-slate-300' },
          { num: services.length - up, label: 'Down', color: 'text-red-400' },
        ].map(s => (
          <div key={s.label} className="bg-[#12121a] border border-[#252535] rounded-xl p-4 text-center min-w-24">
            <div className={`text-3xl font-bold leading-none ${s.color}`}>{s.num}</div>
            <div className="text-xs text-slate-500 mt-1">{s.label}</div>
          </div>
        ))}
      </div>
      <div className="bg-[#12121a] border border-[#252535] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#252535]">
              {['Service', 'Status', 'Latency', 'Detail'].map(h => (
                <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {services.map(s => (
              <tr key={s.name} className="border-b border-[#252535] last:border-0">
                <td className="px-4 py-3 font-medium text-sm">{s.label}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
                    s.health === 'up' ? 'bg-green-500/15 text-green-400' :
                    s.health === 'down' ? 'bg-red-500/15 text-red-400' :
                    s.health === 'degraded' ? 'bg-yellow-500/15 text-yellow-400' :
                    'bg-slate-600/20 text-slate-500'
                  }`}>{s.health}</span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">{s.latency_ms ? `${s.latency_ms}ms` : '—'}</td>
                <td className="px-4 py-3 text-xs text-slate-500">{s.health_detail || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── debug tab ─────────────────────────────────────────────────────────────────
function DebugTab({ d }: { d: DebugInfo }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <DebugCard title="System">
        {[['Platform', d.platform], ['Python', d.python], ['CWD', d.cwd]].map(([k, v]) => (
          <KVRow key={k} k={k} v={v} />
        ))}
      </DebugCard>
      <DebugCard title="Port Status">
        {Object.entries(d.ports).map(([p, open]) => (
          <div key={p} className="flex justify-between py-1.5 text-xs border-b border-[#252535] last:border-0">
            <span className="text-slate-400">:{p}</span>
            <span className={open ? 'text-green-400' : 'text-slate-600'}>
              {open ? '● open' : '○ closed'}
            </span>
          </div>
        ))}
      </DebugCard>
      <DebugCard title="Environment">
        {Object.entries(d.env).map(([k, v]) => <KVRow key={k} k={k} v={v} mono />)}
      </DebugCard>
      <DebugCard title="Recent API Errors">
        {d.recent_errors.length ? (
          <pre className="text-xs text-red-400 font-mono leading-relaxed max-h-48 overflow-auto whitespace-pre-wrap">
            {d.recent_errors.slice(-10).join('\n')}
          </pre>
        ) : <span className="text-xs text-slate-500">No recent errors ✓</span>}
      </DebugCard>
    </div>
  )
}

function DebugCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#12121a] border border-[#252535] rounded-xl p-4">
      <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

function KVRow({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between py-1.5 text-xs border-b border-[#252535] last:border-0 gap-3">
      <span className="text-slate-400 truncate">{k}</span>
      <span className={`text-slate-200 text-right truncate max-w-48 ${mono ? 'font-mono text-[11px]' : ''}`}>{v}</span>
    </div>
  )
}
