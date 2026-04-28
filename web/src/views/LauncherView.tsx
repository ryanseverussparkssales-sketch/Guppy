import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/api/client'
import { toast } from 'sonner'
import { RefreshCw } from 'lucide-react'
import DesktopView from './DesktopView'
import InstancesView from './InstancesView'
import AgentsView from './AgentsView'
import ModelsView from './ModelsView'
import { useProviders, QK as PQKK } from '@/api/queries'

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

type TabId = 'services' | 'instances' | 'health' | 'logs' | 'debug' | 'desktop' | 'models' | 'agents' | 'backends'

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
    { id: 'backends',  label: 'Backends' },
    { id: 'agents',    label: 'Agents' },
    { id: 'instances', label: 'Instances' },
    { id: 'models',    label: 'Models' },
    { id: 'health',    label: 'Health' },
    { id: 'logs',      label: 'Logs' },
    { id: 'debug',     label: 'Debug' },
    { id: 'desktop',   label: 'Desktop' },
  ]

  return (
    <div className="flex flex-col h-full bg-[#0a0a10] text-slate-200">
      {/* header */}
      <div className="flex items-center gap-3 px-5 h-13 bg-[#12121a] border-b border-[#252535] shrink-0">
        <h1 className="font-bold text-sm tracking-tight text-slate-300">Launch Control</h1>
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

        {/* AGENTS */}
        {tab === 'agents' && <div className="-m-5"><AgentsView /></div>}

        {/* MODELS */}
        {tab === 'models' && <div className="-m-5"><ModelsView /></div>}

        {/* BACKENDS */}
        {tab === 'backends' && <BackendsTab onRefresh={() => qc.invalidateQueries({ queryKey: PQKK.providers })} />}

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

// ── VRAM bar ──────────────────────────────────────────────────────────────────

const VRAM_COLORS = [
  '#6366f1', // indigo  — pepe
  '#10b981', // emerald — gemma
  '#f59e0b', // amber   — qwen3
  '#ec4899', // pink    — minicpm
  '#06b6d4', // cyan    — dispatch
]

function VramBar({ backends, totalGb }: { backends: LlamacppBackend[]; totalGb: number }) {
  const alive   = backends.filter(b => b.alive)
  const usedGb  = alive.reduce((s, b) => s + (b.vram_gb ?? 0), 0)
  const pct     = Math.min(100, (usedGb / totalGb) * 100)
  const warn    = pct >= 80
  const danger  = pct >= 100

  // Build stacked segments — one per alive backend in config order
  const segments: { name: string; label: string; pct: number; color: string }[] = []
  let colorIdx = 0
  for (const b of backends) {
    if (!b.alive) { colorIdx++; continue }
    segments.push({
      name:  b.name,
      label: b.label,
      pct:   Math.min(100, (b.vram_gb / totalGb) * 100),
      color: VRAM_COLORS[colorIdx % VRAM_COLORS.length],
    })
    colorIdx++
  }

  return (
    <div className="bg-[#0e0e18] border border-[#252535] rounded-xl p-4 flex flex-col gap-3">
      {/* header row */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-300">VRAM Allocation</span>
          <span className="text-slate-500">RX 7900 XTX · {totalGb} GB total</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`font-bold tabular-nums ${danger ? 'text-red-400' : warn ? 'text-yellow-400' : 'text-slate-200'}`}>
            {usedGb.toFixed(1)} / {totalGb} GB
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
            danger ? 'bg-red-500/20 text-red-400' :
            warn   ? 'bg-yellow-500/20 text-yellow-400' :
                     'bg-indigo-500/15 text-indigo-400'
          }`}>
            {pct.toFixed(0)}%
          </span>
        </div>
      </div>

      {/* stacked bar */}
      <div className="relative h-4 bg-[#1a1a28] rounded-full overflow-hidden">
        {segments.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-600">
            no models running
          </div>
        ) : (
          segments.map((seg, i) => {
            const left = segments.slice(0, i).reduce((s, x) => s + x.pct, 0)
            return (
              <div
                key={seg.name}
                title={`${seg.label} · ${backends.find(b => b.name === seg.name)?.vram_gb ?? 0} GB`}
                className="absolute top-0 h-full transition-all duration-500"
                style={{ left: `${left}%`, width: `${seg.pct}%`, background: seg.color }}
              />
            )
          })
        )}
        {/* 80% warning line */}
        <div className="absolute top-0 h-full border-r border-yellow-500/40" style={{ left: '80%' }} title="80% threshold" />
      </div>

      {/* legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {backends.map((b, i) => (
          <div key={b.name} className="flex items-center gap-1.5 text-[11px]">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
              style={{ background: b.alive ? VRAM_COLORS[i % VRAM_COLORS.length] : '#2d2d45' }}
            />
            <span className={b.alive ? 'text-slate-300' : 'text-slate-600'}>
              {b.label}
            </span>
            <span className={b.alive ? 'text-slate-500' : 'text-slate-700'}>
              {b.vram_gb} GB
            </span>
            {b.auto_start && !b.alive && (
              <span className="text-cyan-700 text-[9px] font-bold">AUTO</span>
            )}
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-[11px] ml-auto">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-[#1a1a28] border border-[#252535]" />
          <span className="text-slate-600">free {(totalGb - usedGb).toFixed(1)} GB</span>
        </div>
      </div>

      {/* mode legend */}
      <div className="flex items-center gap-3 text-[11px] text-slate-600 border-t border-[#1e1e2a] pt-2">
        <span className="px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-500 font-semibold">MODE A</span>
        <span>models share GPU — can run together</span>
        <span className="mx-1">·</span>
        <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 font-semibold">MODE B</span>
        <span>needs full GPU — run alone</span>
      </div>
    </div>
  )
}

// ── backends tab ──────────────────────────────────────────────────────────────

interface LlamacppBackend {
  name:       string
  label:      string
  port:       number
  mode:       'A' | 'B'
  note:       string
  vram_gb:    number
  auto_start: boolean
  alive:      boolean
  tracked:    boolean
  pid:        number | null
}

const OTHER_BACKEND_PORTS: Record<string, number> = {
  ollama:        11434,
  lmstudio:      1234,
  lemonade:      8000,
  local_harness: 8001,
}

// How long (ms) to keep a backend in "starting" state before giving up
const STARTING_TIMEOUT_MS = 150_000

function BackendsTab({ onRefresh }: { onRefresh: () => void }) {
  const qc = useQueryClient()

  // ── providers probe (for Ollama/LMStudio/etc. status in the other-backends list)
  const { data: providers, isFetching: provFetching } = useProviders({ refetchInterval: 8_000 })

  // ── dedicated llamacpp status endpoint (faster probe, start/stop aware)
  const { data: llamacppData = [], isLoading: llcLoading, isFetching: llcFetching } = useQuery<LlamacppBackend[]>({
    queryKey: ['backends', 'llamacpp'],
    queryFn:  () => apiClient.get('/api/backends/llamacpp').then((r: { data: LlamacppBackend[] }) => r.data),
    refetchInterval: 4_000,
  })

  // Local "starting" state: name → timestamp when Start was pressed
  const [startingAt, setStartingAt] = useState<Record<string, number>>({})

  // Clear starting state when backend becomes alive, or after timeout
  const prevAlive = useRef<Record<string, boolean>>({})
  useEffect(() => {
    const now = Date.now()
    setStartingAt(prev => {
      const next = { ...prev }
      let changed = false
      for (const name of Object.keys(next)) {
        const b = llamacppData.find(x => x.name === name)
        const wasAlive = prevAlive.current[name]
        const isAlive = b?.alive ?? false
        if (isAlive && !wasAlive) { delete next[name]; changed = true }
        else if (now - next[name] > STARTING_TIMEOUT_MS) { delete next[name]; changed = true }
      }
      return changed ? next : prev
    })
    for (const b of llamacppData) prevAlive.current[b.name] = b.alive
  }, [llamacppData])

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['backends', 'llamacpp'] })
    qc.invalidateQueries({ queryKey: PQKK.providers })
  }

  // ── mutations
  const startMut = useMutation({
    mutationFn: (name: string) => apiClient.post(`/api/backends/llamacpp/${name}/start`),
    onMutate: (name) => setStartingAt(prev => ({ ...prev, [name]: Date.now() })),
    onSuccess: (_d, name) => {
      toast.success(`Starting ${name.replace('llamacpp-', '')} — loading model…`)
      // Poll more frequently while starting
      qc.invalidateQueries({ queryKey: ['backends', 'llamacpp'] })
    },
    onError: (e: { response?: { data?: { detail?: string } }; message: string }, name) => {
      setStartingAt(prev => { const n = { ...prev }; delete n[name]; return n })
      toast.error(e.response?.data?.detail ?? e.message)
    },
  })

  const stopMut = useMutation({
    mutationFn: (name: string) => apiClient.post(`/api/backends/llamacpp/${name}/stop`),
    onSuccess: (_d, name) => {
      toast.success(`Stopped ${name.replace('llamacpp-', '')}`)
      invalidateAll()
    },
    onError: (e: { response?: { data?: { detail?: string } }; message: string }) =>
      toast.error(e.response?.data?.detail ?? e.message),
  })

  const isFetching = provFetching || llcFetching
  const isLoading  = llcLoading

  // Other (non-llamacpp) backends from providers — guard against unexpected API shapes
  const rawBackends = providers?.local?.backends ?? {}
  const otherList = Object.entries(rawBackends)
    .filter(([name]) => !name.startsWith('llamacpp'))
    .map(([name, info]) => {
      const safeInfo = info && typeof info === 'object' ? info as { alive?: boolean; label?: string } : {}
      return { name, alive: Boolean(safeInfo.alive), label: safeInfo.label ?? name }
    })

  return (
    <div className="flex flex-col gap-6">
      {/* header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-200">Backend Connections</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            llama.cpp servers probed every 4 s · other backends every 8 s
          </p>
        </div>
        <button
          onClick={() => { invalidateAll(); onRefresh() }}
          disabled={isFetching}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-[#1e1e2a] border border-[#252535] text-slate-300 hover:bg-[#252535] transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          Check All
        </button>
      </div>

      {isLoading && <div className="text-slate-500 text-sm">Probing backends…</div>}

      {/* ── llama.cpp servers ─────────────────────────────────────────────── */}
      {llamacppData.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            llama.cpp Servers
            <span className="text-slate-600 normal-case font-normal ml-1">— local GPU inference (ROCm · RX 7900 XTX)</span>
          </h3>

          {/* VRAM allocation bar */}
          <VramBar backends={llamacppData} totalGb={24} />

          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))' }}>
            {llamacppData.map(b => {
              const isStarting  = b.name in startingAt && !b.alive
              const modeOrange  = b.mode === 'A'
              const isStopping  = stopMut.isPending && stopMut.variables === b.name
              const isLaunching = startMut.isPending && startMut.variables === b.name

              // VRAM conflict detection: Mode B needs all other backends stopped
              const otherAlive = llamacppData.filter(x => x.name !== b.name && x.alive)
              const modeConflict = b.mode === 'B' && otherAlive.length > 0
              const conflictNames = modeConflict ? otherAlive.map(x => x.label).join(', ') : ''

              const statusLabel = b.alive
                ? '● connected'
                : isStarting
                  ? '◌ loading model…'
                  : '○ offline'
              const statusColor = b.alive
                ? 'text-green-400'
                : isStarting
                  ? 'text-yellow-400'
                  : 'text-slate-500'

              return (
                <div
                  key={b.name}
                  className={`bg-[#12121a] border rounded-xl p-4 flex flex-col gap-3 transition-all ${
                    b.alive
                      ? 'border-l-[3px] border-l-green-500 border-[#252535]'
                      : isStarting
                        ? 'border-l-[3px] border-l-yellow-500 border-[#252535]'
                        : modeConflict
                          ? 'border-l-[3px] border-l-orange-500/60 border-[#252535]'
                          : 'border-[#252535]'
                  }`}
                >
                  {/* name + port */}
                  <div className="flex items-center gap-2">
                    {isStarting
                      ? <RefreshCw className="w-2 h-2 text-yellow-400 animate-spin flex-shrink-0" />
                      : <span className={`w-2 h-2 rounded-full flex-shrink-0 ${b.alive ? 'bg-green-400 shadow-[0_0_6px_#22c55e]' : 'bg-slate-600'}`} />
                    }
                    <span className="font-semibold text-sm flex-1">{b.label}</span>
                    <span className="text-xs text-cyan-400 font-mono">:{b.port}</span>
                  </div>

                  {/* mode badge + note */}
                  <div className="flex items-center gap-2 text-xs">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      modeOrange ? 'bg-orange-500/15 text-orange-400' : 'bg-purple-500/15 text-purple-400'
                    }`}>
                      MODE {b.mode}
                    </span>
                    <span className="text-slate-500">{b.note}</span>
                  </div>

                  {/* VRAM conflict warning */}
                  {modeConflict && !b.alive && (
                    <div className="flex items-start gap-1.5 text-xs text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded-md px-2.5 py-2">
                      <span className="mt-0.5 flex-shrink-0">⚠</span>
                      <span>Stop first: <span className="font-semibold">{conflictNames}</span></span>
                    </div>
                  )}

                  {/* status + pid */}
                  <div className="flex items-center gap-3 text-xs">
                    <span className={`font-semibold ${statusColor}`}>{statusLabel}</span>
                    {b.pid && <span className="text-slate-600">pid {b.pid}</span>}
                    {isStarting && (
                      <span className="text-slate-600 ml-auto">
                        {Math.round((STARTING_TIMEOUT_MS - (Date.now() - startingAt[b.name])) / 1000)}s max
                      </span>
                    )}
                  </div>

                  {/* start / stop buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => startMut.mutate(b.name)}
                      disabled={b.alive || isStarting || isLaunching || isStopping}
                      className="flex-1 text-xs py-1.5 rounded-md font-semibold transition-colors bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:cursor-default"
                    >
                      {isLaunching ? '▶ Starting…' : '▶ Start'}
                    </button>
                    <button
                      onClick={() => stopMut.mutate(b.name)}
                      disabled={!b.alive && !isStarting && !b.tracked}
                      className="flex-1 text-xs py-1.5 rounded-md font-semibold transition-colors bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/30 disabled:opacity-40 disabled:cursor-default"
                    >
                      {isStopping ? '■ Stopping…' : '■ Stop'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── other backends ─────────────────────────────────────────────────── */}
      {otherList.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Other Backends</h3>
          <div className="bg-[#12121a] border border-[#252535] rounded-xl overflow-hidden">
            {otherList.map((b, i) => (
              <div
                key={b.name}
                className={`flex items-center px-4 py-3 gap-3 ${i < otherList.length - 1 ? 'border-b border-[#252535]' : ''}`}
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${b.alive ? 'bg-green-400 shadow-[0_0_6px_#22c55e]' : 'bg-slate-600'}`} />
                <span className="text-sm flex-1">{b.label}</span>
                {OTHER_BACKEND_PORTS[b.name] && (
                  <span className="text-xs text-slate-500 font-mono">:{OTHER_BACKEND_PORTS[b.name]}</span>
                )}
                <span className={`text-xs font-semibold ${b.alive ? 'text-green-400' : 'text-slate-500'}`}>
                  {b.alive ? 'up' : 'offline'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!isLoading && llamacppData.length === 0 && (
        <div className="bg-[#12121a] border border-[#252535] rounded-xl p-5 text-center">
          <p className="text-slate-400 text-sm font-medium">No llama.cpp backends configured</p>
          <p className="text-slate-600 text-xs mt-1">
            Add backend configs to <code className="text-slate-500">routes_backends.py</code> or click Check All to re-probe
          </p>
        </div>
      )}
      {!isLoading && llamacppData.length === 0 && otherList.length === 0 && (
        <div className="text-slate-500 text-sm text-center py-4">No backend data — click Check All to probe.</div>
      )}
    </div>
  )
}
