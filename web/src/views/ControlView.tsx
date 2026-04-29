/**
 * Control Panel — model stack health, wake/kill/restart, log viewer, API status.
 * Accessible at /control from browser or tray icon → Control Panel.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { RefreshCw, Play, Square, FileText, ExternalLink, Cpu, Zap, ZapOff } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface ModelStatus {
  key: string
  label: string
  port: number
  alive: boolean
  vram_gb: number
  note: string
  auto_start: boolean
}

export default function ControlView() {
  const [models, setModels]         = useState<ModelStatus[]>([])
  const [loading, setLoading]       = useState(true)
  const [restarting, setRestarting] = useState<string | null>(null)
  const [logKey, setLogKey]         = useState<string | null>(null)
  const [logLines, setLogLines]     = useState<string[]>([])
  const [logLoading, setLogLoading] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get('/api/control/status')
      setModels(res.data.models ?? [])
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchStatus()
    const id = setInterval(fetchStatus, 8000)
    return () => clearInterval(id)
  }, [fetchStatus])

  const fetchLog = useCallback(async (key: string) => {
    setLogLoading(true)
    setLogKey(key)
    try {
      const res = await api.get(`/api/control/logs/${key}`, { params: { lines: 100 } })
      setLogLines(res.data.lines ?? ['(no log file found)'])
    } catch {
      setLogLines(['(failed to load log)'])
    } finally {
      setLogLoading(false)
      setTimeout(() => logRef.current?.scrollTo(0, logRef.current.scrollHeight), 50)
    }
  }, [])

  const handleWake = async (key: string) => {
    try { await api.post(`/api/backends/llamacpp/${key}/start`) } catch { /* ignore */ }
    setTimeout(fetchStatus, 3000)
  }

  const handleRestart = async (key: string) => {
    setRestarting(key)
    try { await api.post(`/api/control/models/${key}/restart`) } catch { /* ignore */ }
    finally {
      setRestarting(null)
      setTimeout(fetchStatus, 4000)
    }
  }

  const alive  = models.filter(m => m.alive).length
  const total  = models.length

  return (
    <div className="min-h-screen bg-background text-on-surface p-6">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-on-surface">Control Panel</h1>
            <p className="text-sm text-on-surface-variant/60 mt-0.5">
              {loading ? 'Checking…' : `${alive} / ${total} models live`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchStatus}
              className="flex items-center gap-1.5 text-sm text-on-surface-variant/50 hover:text-on-surface-variant transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
          </div>
        </div>

        {/* Quick nav */}
        <div className="flex gap-2 flex-wrap">
          {[
            { label: 'Companion', path: '/companion' },
            { label: 'Workspace', path: '/workspace' },
            { label: 'Codespace', path: '/codespace' },
          ].map(({ label, path }) => (
            <a
              key={path}
              href={path}
              className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border border-outline-variant/20 bg-surface-container/40 hover:bg-surface-container hover:border-outline-variant/40 transition-all text-on-surface-variant"
            >
              {label} <ExternalLink className="w-3 h-3 opacity-50" />
            </a>
          ))}
        </div>

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
                <motion.div
                  key={m.key}
                  layout
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-xl border transition-all',
                    m.alive
                      ? 'border-green-500/20 bg-green-500/5'
                      : 'border-outline-variant/15 bg-surface-container/30',
                  )}
                >
                  {/* Status dot */}
                  <div className="flex-shrink-0">
                    {isCpu ? (
                      <Cpu className={cn('w-3.5 h-3.5', m.alive ? 'text-cyan-400' : 'text-on-surface-variant/30')} />
                    ) : (
                      <span className={cn(
                        'block w-2.5 h-2.5 rounded-full',
                        m.alive
                          ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.7)]'
                          : 'bg-on-surface-variant/20',
                      )} />
                    )}
                  </div>

                  {/* Label + note */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-on-surface">{m.label}</span>
                      <span className="text-[10px] text-on-surface-variant/40">:{m.port}</span>
                      {m.auto_start && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary/70">
                          always-on
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-on-surface-variant/40 truncate">{m.note}</p>
                  </div>

                  {/* VRAM badge */}
                  <span className="text-[10px] text-on-surface-variant/30 hidden sm:block flex-shrink-0">
                    {m.vram_gb > 0 ? `${m.vram_gb}GB` : 'CPU'}
                  </span>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {/* Log viewer */}
                    <button
                      onClick={() => fetchLog(m.key)}
                      title="View logs"
                      className="p-1.5 rounded-lg text-on-surface-variant/30 hover:text-on-surface-variant/70 hover:bg-surface-container transition-all"
                    >
                      <FileText className="w-3.5 h-3.5" />
                    </button>

                    {/* Wake (if cold) */}
                    {!m.alive && (
                      <button
                        onClick={() => handleWake(m.key)}
                        title="Start model"
                        className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border border-primary/30 text-primary/70 hover:bg-primary/10 transition-all"
                      >
                        <Zap className="w-3 h-3" /> Wake
                      </button>
                    )}

                    {/* Restart (if alive) */}
                    {m.alive && (
                      <button
                        onClick={() => handleRestart(m.key)}
                        disabled={!!isRestarting}
                        title="Kill + relaunch"
                        className={cn(
                          'flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border transition-all',
                          isRestarting
                            ? 'border-outline-variant/20 text-on-surface-variant/30 cursor-not-allowed'
                            : 'border-outline-variant/20 text-on-surface-variant/40 hover:border-red-400/30 hover:text-red-400/70',
                        )}
                      >
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
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="rounded-xl border border-outline-variant/20 bg-surface-container/60 overflow-hidden"
            >
              <div className="flex items-center justify-between px-4 py-2 border-b border-outline-variant/15">
                <span className="text-xs font-medium text-on-surface-variant/60">
                  {logLoading ? 'Loading…' : `Logs: ${logKey}`}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => fetchLog(logKey)}
                    className="text-[11px] text-on-surface-variant/40 hover:text-on-surface-variant transition-colors"
                  >
                    <RefreshCw className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => setLogKey(null)}
                    className="text-[11px] text-on-surface-variant/40 hover:text-on-surface-variant transition-colors"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div
                ref={logRef}
                className="h-64 overflow-y-auto p-4 font-mono text-[11px] text-on-surface-variant/60 leading-5 space-y-0.5"
              >
                {logLines.map((line, i) => (
                  <div
                    key={i}
                    className={cn(
                      line.toLowerCase().includes('error') && 'text-red-400/80',
                      line.toLowerCase().includes('warn')  && 'text-amber-400/70',
                      line.toLowerCase().includes('llm_load') && 'text-green-400/70',
                    )}
                  >
                    {line || ' '}
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
