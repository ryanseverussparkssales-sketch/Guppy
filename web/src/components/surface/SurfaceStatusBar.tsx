/**
 * SurfaceStatusBar — compact chip showing another surface's live status.
 * Subscribes to /api/surface/events SSE for real-time updates.
 * Used in headers to provide cross-surface awareness.
 */
import { useState, useEffect } from 'react'
import { Loader2, CheckCircle2, Radio } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface SurfaceState {
  surface: string
  status: 'idle' | 'active' | 'agent_running'
  current_task?: string
  agent_count: number
  last_context?: string
  updated_at: string
}

interface SurfaceStatusBarProps {
  surface: 'companion' | 'workspace' | 'codespace'
  label?: string
  compact?: boolean
}

const STATUS_COLORS = {
  idle:          'text-on-surface-variant/40',
  active:        'text-primary',
  agent_running: 'text-secondary',
}

export function SurfaceStatusBar({ surface, label, compact = false }: SurfaceStatusBarProps) {
  const [state, setState] = useState<SurfaceState | null>(null)

  // Initial fetch
  useEffect(() => {
    api.get(`/api/surface/state/${surface}`)
      .then((r) => setState(r.data))
      .catch(() => {})
  }, [surface])

  // SSE for live updates
  useEffect(() => {
    let cancelled = false
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    async function connect() {
      if (cancelled) return
      try {
        // Read token fresh each attempt — avoids stale token after refresh.
        const token = localStorage.getItem('accessToken') || ''
        const res = await fetch('/api/surface/events', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = ''
        let evType = ''
        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('event: ')) evType = line.slice(7).trim()
            else if (line.startsWith('data: ')) {
              try {
                const payload = JSON.parse(line.slice(6))
                if (evType === 'state_update' && payload?.data?.surface === surface) {
                  setState(payload.data)
                } else if (evType === 'snapshot' && payload?.[surface]) {
                  setState(payload[surface])
                }
              } catch { /* ignore */ }
              evType = ''
            }
          }
        }
      } catch { /* reconnect */ }
      if (!cancelled) retryTimeout = setTimeout(connect, 5000)
    }

    connect()
    return () => {
      cancelled = true
      if (retryTimeout) clearTimeout(retryTimeout)
    }
  }, [surface])

  if (!state) return null

  const isActive = state.status !== 'idle'
  const displayLabel = label ?? surface

  if (compact) {
    return (
      <div
        className={cn(
          "flex items-center gap-1 text-xs px-2 py-1 rounded-full border transition-colors",
          isActive
            ? "border-primary/30 bg-primary/5 text-primary"
            : "border-outline-variant/20 text-on-surface-variant/40"
        )}
        title={state.current_task ?? `${displayLabel}: ${state.status}`}
      >
        {state.status === 'agent_running' ? (
          <Loader2 className="w-2.5 h-2.5 animate-spin" />
        ) : state.status === 'active' ? (
          <Radio className="w-2.5 h-2.5" />
        ) : (
          <div className="w-2 h-2 rounded-full bg-current opacity-40" />
        )}
        <span className="capitalize">{displayLabel}</span>
        {state.agent_count > 0 && (
          <span className="bg-primary text-on-primary text-[10px] rounded-full px-1 leading-none py-0.5">
            {state.agent_count}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className={cn("flex items-center gap-2 text-sm", STATUS_COLORS[state.status])}>
      {state.status === 'agent_running' ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : state.status === 'active' ? (
        <Radio className="w-3.5 h-3.5" />
      ) : (
        <CheckCircle2 className="w-3.5 h-3.5 opacity-40" />
      )}
      <span className="capitalize font-medium">{displayLabel}</span>
      {state.current_task && (
        <span className="text-xs text-on-surface-variant/60 truncate max-w-[160px]">
          {state.current_task}
        </span>
      )}
    </div>
  )
}
