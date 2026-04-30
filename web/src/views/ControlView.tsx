/**
 * Control Panel — model stack + live PC health.
 * Accessible at /control or via tray icon.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { RefreshCw, Zap, FileText, ExternalLink, Cpu } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface ModelStatus {
  key: string; label: string; port: number; alive: boolean
  vram_gb: number; note: string; auto_start: boolean
}

interface PCHealth {
  cpu_pct: number
  ram_used_gb: number; ram_total_gb: number; ram_pct: number
  disk_used_gb: number; disk_total_gb: number; disk_pct: number
  gpu?: {
    vram_used_mb: number; vram_total_mb: number; vram_pct: number
    gpu_use_pct?: number; label: string
  } | null
}

function Gauge({ label, pct, sub, color = 'primary' }: {
  label: string; pct: number; sub: string; color?: string
}) {
  const clamp = Math.min(100, Math.max(0, pct))
  const arc   = (clamp / 100) * 220   // degrees of stroke
  const r = 28
  const circ = 2 * Math.PI * r
  const dash  = (arc / 360) * circ
  const gap   = circ - dash
  const colorMap: Record<string, string> = {
    primary: '#6366f1', green: '#4ade80', cyan: '#22d3ee',
    amber: '#fbbf24', red: '#f87171',
  }
  const strokeColor = pct > 90 ? '#f87171' : pct > 75 ? '#fbbf24' : (colorMap[color] ?? colorMap.primary)

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="72" height="72" viewBox="0 0 72 72" className="-rotate-[110deg]">
        <circle cx="36" cy="36" r={r} fill="none" stroke="currentColor"
          strokeWidth="5" className="text-surface-container" />
        <circle cx="36" cy="36" r={r} fill="none"
          stroke={strokeColor} strokeWidth="5"
          strokeDasharray={`${dash} ${gap}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.4s ease' }} />
      </svg>
      <div className="text-center -mt-1">
        <p className="text-base font-bold text-on-surface leading-none">{Math.round(pct)}%</p>
        <p className="text-[10px] font-semibold text-on-surface-variant/60 uppercase tracking-wide">{label}</p>
        <p className="text-[10px] text-on-surface-variant/40 mt-0.5">{sub}</p>
      </div>
    </div>
  )
}

export default function ControlView() {
  const [models, setModels]         = useState<ModelStatus[]>([])
  const [pc, setPc]                 = useState<PCHealth | null>(null)
  const [loading, setLoading]       = useState(true)
  const [restarting, setRestarting] = useState<string | null>(null)
  const [logKey, setLogKey]         = useState<string | null>(null)
  const [logLines, setLogLines]     = useState<string[]>([])
  const [logLoading, setLogLoading] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  const fetchAll = useCallback(async () => {
    try {
      const [backendsRes, pcRes] = await Promise.all([
        api.get('/api/backends/llamacpp'),
        api.get('/api/control/pc').catch(() => null),
      ])
      // backends API returns array; map name→key for ModelStatus
      const raw: any[] = backendsRes.data ?? []
      setModels(raw.map(b => ({
        key: b.name, label: b.label, port: b.port,
        alive: b.alive, vram_gb: b.vram_gb, note: b.note,
        auto_start: b.auto_start,
      })))
      if (pcRes) setPc(pcRes.data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, 8000)
    return () => clearInterval(id)
  }, [fetchAll])

  const fetchLog = useCallback(async (key: string) => {
    setLogLoading(true); setLogKey(key)
    try {
      const res = await api.get(`/api/control/logs/${key}`, { params: { lines: 100 } })
      setLogLines(res.data.lines ?? ['(no log file)'])
    } catch { setLogLines(['(failed to load)']) }
    finally {
      setLogLoading(false)
      setTimeout(() => logRef.current?.scrollTo(0, logRef.current.scrollHeight), 50)
    }
  }, [])

  const handleWake = async (key: string) => {
    try { await api.post(`/api/backends/llamacpp/${key}/start`) } catch { /* ignore */ }
    setTimeout(fetchAll, 3000)
  }

  const handleRestart = async (key: string) => {
    setRestarting(key)
    try { await api.post(`/api/control/models/${key}/restart`) } catch { /* ignore */ }
    finally { setRestarting(null); setTimeout(fetchAll, 4000) }
  }

  const alive = models.filter(m => m.alive).length

  return (
    <div className="min-h-screen bg-background text-on-surface p-6">
      <div className="max-w-5xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Control Panel</h1>
            <p className="text-sm text-on-surface-variant/60 mt-0.5">
              {loading ? 'Checking…' : `${alive} / ${models.length} models live`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {[
              { label: 'Companion', path: '/companion' },
              { label: 'Workspace', path: '/workspace' },
              { label: 'Codespace', path: '/codespace' },
            ].map(({ label, path }) => (
              <a key={path} href={path}
                className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border border-outline-variant/20 bg-surface-container/40 hover:bg-surface-container transition-all text-on-surface-variant">
                {label} <ExternalLink className="w-3 h-3 opacity-50" />
              </a>
            ))}
            <button onClick={fetchAll}
              className="text-on-surface-variant/40 hover:text-on-surface-variant transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* PC Health */}
        {pc && (
          <div>
            <h2 className="text-xs font-semibold text-on-surface-variant/50 uppercase tracking-wider mb-4">
              System Health
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 p-6 rounded-2xl border border-outline-variant/15 bg-surface-container/30">
              <Gauge
                label="CPU"
                pct={pc.cpu_pct}
                sub={`${pc.cpu_pct.toFixed(0)}%`}
                color="primary"
              />
              <Gauge
                label="RAM"
                pct={pc.ram_pct}
                sub={`${pc.ram_used_gb}/${pc.ram_total_gb} GB`}
                color="green"
              />
              <Gauge
                label="Disk"
                pct={pc.disk_pct}
                sub={`${pc.disk_used_gb.toFixed(0)}/${pc.disk_total_gb.toFixed(0)} GB`}
                color="amber"
              />
              {pc.gpu ? (
                <Gauge
                  label={pc.gpu.label ?? 'GPU VRAM'}
                  pct={pc.gpu.vram_pct ?? 0}
                  sub={`${((pc.gpu.vram_used_mb ?? 0) / 1024).toFixed(1)}/${((pc.gpu.vram_total_mb ?? 0) / 1024).toFixed(1)} GB`}
                  color="cyan"
                />
              ) : (
                <div className="flex flex-col items-center gap-1 opacity-40">
                  <Cpu className="w-8 h-8 text-on-surface-variant/40" />
                  <p className="text-[10px] text-on-surface-variant/40">GPU N/A</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Model stack */}
        <div>
          <h2 className="text-xs font-semibold text-on-surface-variant/50 uppercase tracking-wider mb-3">
            Model Stack
          </h2>
          <div className="space-y-1.5">
            {models.map(m => {
              const isRestarting = restarting === m.key
              const isCpu = m.vram_gb === 0
              return (
                <motion.div key={m.key} layout
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-xl border transition-all',
                    m.alive
                      ? 'border-green-500/20 bg-green-500/5'
                      : 'border-outline-variant/15 bg-surface-container/30',
                  )}>
                  {/* Status dot */}
                  <div className="flex-shrink-0">
                    {isCpu
                      ? <Cpu className={cn('w-3.5 h-3.5', m.alive ? 'text-cyan-400' : 'text-on-surface-variant/30')} />
                      : <span className={cn('block w-2.5 h-2.5 rounded-full',
                          m.alive ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.7)]' : 'bg-on-surface-variant/20'
                        )} />
                    }
                  </div>

                  {/* Label + note */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-on-surface">{m.label}</span>
                      <span className="text-[10px] text-on-surface-variant/30">:{m.port}</span>
                      {m.auto_start && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary/70">always-on</span>
                      )}
                    </div>
                    <p className="text-[11px] text-on-surface-variant/40 truncate">{m.note}</p>
                  </div>

                  <span className="text-[10px] text-on-surface-variant/25 hidden sm:block flex-shrink-0">
                    {m.vram_gb > 0 ? `${m.vram_gb}GB` : 'CPU'}
                  </span>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button onClick={() => fetchLog(m.key)} title="View logs"
                      className="p-1.5 rounded-lg text-on-surface-variant/30 hover:text-on-surface-variant/70 hover:bg-surface-container transition-all">
                      <FileText className="w-3.5 h-3.5" />
                    </button>
                    {!m.alive && (
                      <button onClick={() => handleWake(m.key)} title="Start model"
                        className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border border-primary/30 text-primary/70 hover:bg-primary/10 transition-all">
                        <Zap className="w-3 h-3" /> Wake
                      </button>
                    )}
                    {m.alive && (
                      <button onClick={() => handleRestart(m.key)} disabled={!!isRestarting}
                        className={cn(
                          'flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border transition-all',
                          isRestarting
                            ? 'border-outline-variant/20 text-on-surface-variant/30 cursor-not-allowed'
                            : 'border-outline-variant/20 text-on-surface-variant/40 hover:border-red-400/30 hover:text-red-400/70',
                        )}>
                        <RefreshCw className={cn('w-3 h-3', isRestarting && 'animate-spin')} />
                        {isRestarting ? 'Restarting…' : 'Restart'}
                      </button>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>

        {/* Log viewer */}
        <AnimatePresence>
          {logKey && (
            <motion.div
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
              className="rounded-xl border border-outline-variant/20 bg-surface-container/60 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-outline-variant/15">
                <span className="text-xs font-medium text-on-surface-variant/60">
                  {logLoading ? 'Loading…' : `Logs: ${logKey}`}
                </span>
                <div className="flex gap-2">
                  <button onClick={() => fetchLog(logKey)}
                    className="text-on-surface-variant/40 hover:text-on-surface-variant transition-colors">
                    <RefreshCw className="w-3 h-3" />
                  </button>
                  <button onClick={() => setLogKey(null)}
                    className="text-on-surface-variant/40 hover:text-on-surface-variant transition-colors">
                    ✕
                  </button>
                </div>
              </div>
              <div ref={logRef}
                className="h-64 overflow-y-auto p-4 font-mono text-[11px] text-on-surface-variant/60 leading-5 space-y-0.5">
                {logLines.map((line, i) => (
                  <div key={i} className={cn(
                    line.toLowerCase().includes('error') && 'text-red-400/80',
                    line.toLowerCase().includes('warn')  && 'text-amber-400/70',
                    line.toLowerCase().includes('llm_load') && 'text-green-400/70',
                  )}>
                    {line || ' '}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  )
}
