/**
 * SystemMetricsPanel — live CPU, RAM, disk, network gauges
 * Polls /api/system/info + /api/system/processes every 4 seconds.
 */
import { useState, useEffect, useRef } from 'react'
import { Cpu, MemoryStick, HardDrive, Wifi, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface SystemInfo {
  cpu_percent: number
  ram_total_gb: number
  ram_used_gb: number
  ram_percent: number
  swap_used_gb: number
  swap_total_gb: number
  uptime_human: string
  disks: Array<{ path: string; total_gb: number; used_gb: number; percent: number }>
  net_sent_mb: number
  net_recv_mb: number
}

interface Process {
  pid: number
  name: string
  cpu_percent: number
  ram_mb: number
  status: string
}

function n(v: number | null | undefined, digits = 0) {
  return (v ?? 0).toFixed(digits)
}

function MiniGauge({ value, label, color }: { value: number | null | undefined; label: string; color: string }) {
  const pct = value ?? 0
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-on-surface-variant/70">{label}</span>
        <span className="font-medium text-on-surface">{n(pct)}%</span>
      </div>
      <div className="h-1.5 bg-surface-variant rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color)}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  )
}

export function SystemMetricsPanel() {
  const [info, setInfo]         = useState<SystemInfo | null>(null)
  const [procs, setProcs]       = useState<Process[]>([])
  const [showProcs, setShowProcs] = useState(false)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const intervalRef             = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchAll = async () => {
    try {
      const [sysRes, procRes] = await Promise.all([
        api.get('/api/system/info'),
        api.get('/api/system/processes?limit=15&sort_by=cpu'),
      ])
      setInfo(sysRes.data)
      setProcs(procRes.data?.processes ?? [])
      setError(null)
    } catch (e: any) {
      setError('System metrics unavailable')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    intervalRef.current = setInterval(fetchAll, 4000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-40">
      <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
    </div>
  )

  if (error || !info) return (
    <div className="text-center py-10 text-sm text-on-surface-variant/50">{error ?? 'No data'}</div>
  )

  return (
    <div className="space-y-5">
      {/* Core metrics */}
      <div className="grid grid-cols-2 gap-3">
        {/* CPU */}
        <div className="bg-surface-container rounded-xl p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-on-surface-variant">
            <Cpu className="w-3.5 h-3.5" /> CPU
          </div>
          <MiniGauge
            value={info.cpu_percent}
            label="Usage"
            color={info.cpu_percent > 80 ? 'bg-error' : info.cpu_percent > 60 ? 'bg-warning' : 'bg-primary'}
          />
        </div>

        {/* RAM */}
        <div className="bg-surface-container rounded-xl p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-on-surface-variant">
            <MemoryStick className="w-3.5 h-3.5" /> RAM
          </div>
          <MiniGauge
            value={info.ram_percent}
            label={`${n(info.ram_used_gb, 1)} / ${n(info.ram_total_gb, 1)} GB`}
            color={info.ram_percent > 90 ? 'bg-error' : info.ram_percent > 75 ? 'bg-warning' : 'bg-secondary'}
          />
        </div>
      </div>

      {/* Network */}
      <div className="bg-surface-container rounded-xl p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-on-surface-variant mb-2">
          <Wifi className="w-3.5 h-3.5" /> Network
        </div>
        <div className="flex gap-4 text-xs">
          <span className="text-on-surface-variant/70">↑ {n(info.net_sent_mb, 1)} MB sent</span>
          <span className="text-on-surface-variant/70">↓ {n(info.net_recv_mb, 1)} MB recv</span>
          <span className="text-on-surface-variant/40 ml-auto">Up {info.uptime_human}</span>
        </div>
      </div>

      {/* Disks */}
      {info.disks.length > 0 && (
        <div className="bg-surface-container rounded-xl p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-on-surface-variant mb-1">
            <HardDrive className="w-3.5 h-3.5" /> Disks
          </div>
          {info.disks.map((d, i) => (
            <MiniGauge
              key={i}
              value={d.percent}
              label={`${d.path}  ${n(d.used_gb)}/${n(d.total_gb)} GB`}
              color={d.percent > 90 ? 'bg-error' : d.percent > 75 ? 'bg-warning' : 'bg-tertiary'}
            />
          ))}
        </div>
      )}

      {/* Processes toggle */}
      <button
        onClick={() => setShowProcs(!showProcs)}
        className="w-full flex items-center justify-between text-xs text-on-surface-variant/60 hover:text-on-surface transition-colors px-1"
      >
        <span>Top processes by CPU</span>
        {showProcs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {showProcs && procs.length > 0 && (
        <div className="bg-surface-container rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-on-surface-variant/50 border-b border-outline-variant/10">
                <th className="text-left px-3 py-2">Name</th>
                <th className="text-right px-3 py-2">CPU%</th>
                <th className="text-right px-3 py-2">RAM MB</th>
              </tr>
            </thead>
            <tbody>
              {procs.slice(0, 10).map((p) => (
                <tr key={p.pid} className="border-b border-outline-variant/5 hover:bg-surface-variant/30">
                  <td className="px-3 py-1.5 font-medium text-on-surface truncate max-w-[120px]">{p.name}</td>
                  <td className={cn("px-3 py-1.5 text-right font-mono",
                    p.cpu_percent > 50 ? "text-error" : p.cpu_percent > 20 ? "text-warning" : "text-on-surface-variant"
                  )}>
                    {n(p.cpu_percent, 1)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-on-surface-variant">{n(p.ram_mb)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
