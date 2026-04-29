/**
 * WorkspaceView — Operations Hub
 *
 * Two-panel layout: left = full chat (current AssistantView), right = agent task panel.
 * The right panel shows tasks spawned from any surface, with live status.
 * Backend selector in header. Full tool access.
 */
import { useState, useEffect, lazy, Suspense } from 'react'
import {
  Zap, X, CheckCircle2, Clock, AlertCircle, Loader2,
  ChevronRight, ChevronDown, LayoutList,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { BackendSelector } from '@/components/surface/BackendSelector'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'

// Lazy-load the full chat so it doesn't block this view's render
const AssistantChat = lazy(() => import('./AssistantView'))

// ── Task types ─────────────────────────────────────────────────────────────────

interface SurfaceTask {
  id: string
  surface: string
  source: string
  title: string
  description: string
  status: 'queued' | 'running' | 'complete' | 'failed' | 'cancelled'
  result?: string
  created_at: string
  updated_at: string
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  queued:    <Clock className="w-3.5 h-3.5 text-on-surface-variant/60" />,
  running:   <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />,
  complete:  <CheckCircle2 className="w-3.5 h-3.5 text-success" />,
  failed:    <AlertCircle className="w-3.5 h-3.5 text-error" />,
  cancelled: <X className="w-3.5 h-3.5 text-on-surface-variant/40" />,
}

// ── Task item ──────────────────────────────────────────────────────────────────

function TaskItem({ task, onCancel }: { task: SurfaceTask; onCancel: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={cn(
      "rounded-xl border text-sm transition-colors",
      task.status === 'running' && "border-primary/30 bg-primary/5",
      task.status === 'complete' && "border-success/20 bg-success/5",
      task.status === 'failed' && "border-error/20 bg-error/5",
      task.status === 'queued' && "border-outline-variant/30 bg-surface-variant/30",
      task.status === 'cancelled' && "border-outline-variant/10 bg-surface opacity-50",
    )}>
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {STATUS_ICONS[task.status]}
        <span className="flex-1 font-medium text-on-surface truncate">{task.title}</span>
        <span className="text-xs text-on-surface-variant/50 flex-shrink-0">{task.source}</span>
        {(task.status === 'queued' || task.status === 'running') && (
          <button
            onClick={(e) => { e.stopPropagation(); onCancel(task.id) }}
            className="p-0.5 rounded hover:bg-surface-variant text-on-surface-variant/40 hover:text-error transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        )}
        {(task.description || task.result) && (
          expanded
            ? <ChevronDown className="w-3.5 h-3.5 text-on-surface-variant/40 flex-shrink-0" />
            : <ChevronRight className="w-3.5 h-3.5 text-on-surface-variant/40 flex-shrink-0" />
        )}
      </div>
      <AnimatePresence>
        {expanded && (task.description || task.result) && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-2 space-y-1">
              {task.description && (
                <p className="text-xs text-on-surface-variant">{task.description}</p>
              )}
              {task.result && (
                <p className="text-xs text-on-surface bg-surface/60 rounded-lg px-2 py-1.5 font-mono">
                  {task.result}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Agent task panel ───────────────────────────────────────────────────────────

function AgentTaskPanel() {
  const [tasks, setTasks]         = useState<SurfaceTask[]>([])
  const [loading, setLoading]     = useState(true)
  const [filter, setFilter]       = useState<'all' | 'active' | 'done'>('all')

  const loadTasks = async () => {
    try {
      const res = await api.get('/api/surface/tasks?surface=workspace')
      setTasks(res.data || [])
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  // SSE subscription for real-time updates
  useEffect(() => {
    loadTasks()
    const token = localStorage.getItem('accessToken') || ''
    // Use fetch-based SSE so we can send auth header
    let cancelled = false
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    async function connectSSE() {
      if (cancelled) return
      try {
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
                JSON.parse(line.slice(6))  // parse to validate; re-fetch on any task event
                if (['task_spawned', 'task_updated', 'task_cancelled'].includes(evType)) {
                  loadTasks()
                }
              } catch { /* ignore */ }
              evType = ''
            }
          }
        }
      } catch { /* reconnect */ }
      if (!cancelled) retryTimeout = setTimeout(connectSSE, 5000)
    }

    connectSSE()
    return () => {
      cancelled = true
      if (retryTimeout) clearTimeout(retryTimeout)
    }
  }, [])

  const cancelTask = async (id: string) => {
    try {
      await api.delete(`/api/surface/tasks/${id}`)
      setTasks((t) => t.map((x) => x.id === id ? { ...x, status: 'cancelled' } : x))
    } catch { /* ignore */ }
  }

  const filtered = tasks.filter((t) => {
    if (filter === 'active') return ['queued', 'running'].includes(t.status)
    if (filter === 'done')   return ['complete', 'failed', 'cancelled'].includes(t.status)
    return true
  })

  const activeCount = tasks.filter((t) => ['queued', 'running'].includes(t.status)).length

  return (
    <div className="flex flex-col h-full bg-surface-container-low border-l border-outline-variant/20">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/20 flex-shrink-0">
        <div className="flex items-center gap-2">
          <LayoutList className="w-4 h-4 text-on-surface-variant" />
          <span className="text-sm font-semibold text-on-surface">Agent Tasks</span>
          {activeCount > 0 && (
            <span className="px-1.5 py-0.5 text-xs font-medium bg-primary text-on-primary rounded-full">
              {activeCount}
            </span>
          )}
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 px-3 pt-2 pb-1 flex-shrink-0">
        {(['all', 'active', 'done'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "text-xs px-2.5 py-1 rounded-lg capitalize transition-colors",
              filter === f
                ? "bg-primary/10 text-primary font-medium"
                : "text-on-surface-variant/60 hover:text-on-surface"
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Task list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-2 space-y-2">
        {loading ? (
          <div className="flex items-center justify-center pt-8">
            <Loader2 className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center pt-10">
            <Zap className="w-8 h-8 text-on-surface-variant/20 mx-auto mb-2" />
            <p className="text-xs text-on-surface-variant/40">
              {filter === 'active' ? 'No active tasks' : 'No tasks yet'}
            </p>
            <p className="text-xs text-on-surface-variant/30 mt-1">
              Escalate from Companion to queue tasks here
            </p>
          </div>
        ) : (
          <AnimatePresence>
            {filtered.map((task) => (
              <motion.div
                key={task.id}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
              >
                <TaskItem task={task} onCancel={cancelTask} />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}

// ── Main view ──────────────────────────────────────────────────────────────────

export default function WorkspaceView() {
  const [taskPanelOpen, setTaskPanelOpen] = useState(true)

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">
      {/* Workspace header bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-outline-variant/20 flex-shrink-0 bg-surface-container-low/50">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-secondary/20 flex items-center justify-center">
            <Zap className="w-3.5 h-3.5 text-secondary" />
          </div>
          <h1 className="text-sm font-semibold text-on-surface">Workspace</h1>
        </div>
        <div className="flex items-center gap-2">
          <SurfaceStatusBar surface="companion" compact label="Companion" />
          <SurfaceStatusBar surface="codespace" compact label="Codespace" />
          <BackendSelector surface="workspace" compact />
          <button
            onClick={() => setTaskPanelOpen(!taskPanelOpen)}
            className={cn(
              "text-xs px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1.5",
              taskPanelOpen
                ? "bg-primary/10 text-primary"
                : "text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-variant"
            )}
          >
            <LayoutList className="w-3.5 h-3.5" />
            Tasks
          </button>
        </div>
      </div>

      {/* Content: chat + optional task panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Main chat — full AssistantView */}
        <div className={cn("flex-1 overflow-hidden", taskPanelOpen && "border-r border-outline-variant/20")}>
          <Suspense fallback={
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-on-surface-variant/40" />
            </div>
          }>
            <AssistantChat />
          </Suspense>
        </div>

        {/* Agent task panel */}
        <AnimatePresence>
          {taskPanelOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 300, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className="flex-shrink-0 overflow-hidden"
              style={{ width: 300 }}
            >
              <AgentTaskPanel />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
