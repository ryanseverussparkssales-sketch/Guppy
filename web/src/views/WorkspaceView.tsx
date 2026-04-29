/**
 * WorkspaceView — Operations Hub
 *
 * Icon tab strip (11 tabs):
 *   Chat | Agents | CRM | Screen | Files | PC | Tasks | Calls | Calendar | Email | Media
 * Each tab mounts its panel in a consistent scrollable container.
 * Chat tab keeps the full AssistantView + collapsible AgentTaskPanel sidebar.
 */
import { useState, useEffect } from 'react'
import {
  MessageSquare, LayoutList, Users, Monitor, FolderOpen,
  Cpu, Phone, Zap, X, CheckCircle2, Clock, AlertCircle,
  Loader2, ChevronRight, ChevronDown, Calendar, Mail, Library,
  CheckSquare, RefreshCw, FileText, Wrench,
} from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { BackendSelector } from '@/components/surface/BackendSelector'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'
import { CRMPanel } from '@/components/workspace/CRMPanel'
import { ScreenPanel } from '@/components/workspace/ScreenPanel'
import { FilesPanel } from '@/components/workspace/FilesPanel'
import { SystemMetricsPanel } from '@/components/workspace/SystemMetricsPanel'
import { VoIPPanel } from '@/components/workspace/VoIPPanel'
import { CalendarPanel } from '@/components/workspace/CalendarPanel'
import { EmailPanel } from '@/components/workspace/EmailPanel'
import { MediaLibraryPanel } from '@/components/workspace/MediaLibraryPanel'
import { TaskManagerPanel } from '@/components/workspace/TaskManagerPanel'
import { AutomationPanel } from '@/components/workspace/AutomationPanel'
import { DocumentDropZone } from '@/components/shared/DocumentDropZone'
import { DocumentsPanel } from '@/components/workspace/DocumentsPanel'
import { ToolsPanel } from '@/components/workspace/ToolsPanel'
import AssistantChat from './AssistantView'

// ── Tab config ─────────────────────────────────────────────────────────────────

type Tab = 'chat' | 'agents' | 'crm' | 'screen' | 'files' | 'pc' | 'tasks' | 'voip' | 'calendar' | 'email' | 'media' | 'docs' | 'tools'

const TABS: { id: Tab; icon: React.ReactNode; label: string }[] = [
  { id: 'chat',     icon: <MessageSquare className="w-4 h-4" />, label: 'Chat'     },
  { id: 'agents',   icon: <LayoutList    className="w-4 h-4" />, label: 'Agents'   },
  { id: 'crm',      icon: <Users         className="w-4 h-4" />, label: 'CRM'      },
  { id: 'screen',   icon: <Monitor       className="w-4 h-4" />, label: 'Screen'   },
  { id: 'files',    icon: <FolderOpen    className="w-4 h-4" />, label: 'Files'    },
  { id: 'pc',       icon: <Cpu           className="w-4 h-4" />, label: 'PC'       },
  { id: 'tasks',    icon: <CheckSquare   className="w-4 h-4" />, label: 'Tasks'    },
  { id: 'voip',     icon: <Phone         className="w-4 h-4" />, label: 'Calls'    },
  { id: 'calendar', icon: <Calendar      className="w-4 h-4" />, label: 'Calendar' },
  { id: 'email',    icon: <Mail          className="w-4 h-4" />, label: 'Email'    },
  { id: 'media',    icon: <Library       className="w-4 h-4" />, label: 'Media'    },
  { id: 'docs',     icon: <FileText      className="w-4 h-4" />, label: 'Docs'     },
  { id: 'tools',    icon: <Wrench        className="w-4 h-4" />, label: 'Tools'    },
]

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
  queued:    <Clock       className="w-3.5 h-3.5 text-on-surface-variant/60" />,
  running:   <Loader2     className="w-3.5 h-3.5 text-primary animate-spin" />,
  complete:  <CheckCircle2 className="w-3.5 h-3.5 text-success" />,
  failed:    <AlertCircle  className="w-3.5 h-3.5 text-error" />,
  cancelled: <X           className="w-3.5 h-3.5 text-on-surface-variant/40" />,
}

// ── TaskItem ───────────────────────────────────────────────────────────────────

function TaskItem({ task, onCancel }: { task: SurfaceTask; onCancel: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className={cn(
      "rounded-xl border text-sm transition-colors",
      task.status === 'running'   && "border-primary/30 bg-primary/5",
      task.status === 'complete'  && "border-success/20 bg-success/5",
      task.status === 'failed'    && "border-error/20 bg-error/5",
      task.status === 'queued'    && "border-outline-variant/30 bg-surface-variant/30",
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
            ? <ChevronDown  className="w-3.5 h-3.5 text-on-surface-variant/40 flex-shrink-0" />
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

// ── AgentsPanel ────────────────────────────────────────────────────────────────

function AgentsPanel() {
  const [tasks, setTasks]     = useState<SurfaceTask[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState<'all' | 'active' | 'done'>('all')

  const loadTasks = async () => {
    try {
      const res = await api.get('/api/surface/tasks?surface=workspace')
      setTasks(res.data || [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTasks()
    const token = localStorage.getItem('accessToken') || ''
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
        let buf = '', evType = ''
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
                JSON.parse(line.slice(6))
                if (['task_spawned', 'task_updated', 'task_cancelled'].includes(evType)) loadTasks()
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
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <LayoutList className="w-4 h-4 text-on-surface-variant" />
        <span className="text-sm font-semibold text-on-surface">Agent Tasks</span>
        {activeCount > 0 && (
          <span className="px-1.5 py-0.5 text-xs font-medium bg-primary text-on-primary rounded-full">
            {activeCount}
          </span>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 flex-shrink-0">
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
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
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

// ── ChatTab ────────────────────────────────────────────────────────────────────

function ChatTab() {
  const [taskPanelOpen, setTaskPanelOpen] = useState(false)

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main chat */}
      <div className={cn("flex-1 overflow-hidden", taskPanelOpen && "border-r border-outline-variant/20")}>
        <ErrorBoundary fallback={
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-8">
            <AlertCircle className="w-10 h-10 text-error/50" />
            <div>
              <p className="text-sm font-medium text-on-surface">Chat failed to load</p>
              <p className="text-xs text-on-surface-variant/60 mt-1">The server may be restarting. Try refreshing.</p>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high transition-colors text-on-surface-variant"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
          </div>
        }>
          <AssistantChat />
        </ErrorBoundary>
      </div>

      {/* Collapsible agent task sidebar */}
      <AnimatePresence>
        {taskPanelOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 300, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="flex-shrink-0 overflow-hidden bg-surface-container-low"
            style={{ width: 300 }}
          >
            <AgentsPanel />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toggle button */}
      <button
        onClick={() => setTaskPanelOpen(!taskPanelOpen)}
        className={cn(
          "absolute bottom-4 right-4 flex items-center gap-1.5 text-xs px-3 py-2 rounded-xl shadow-lg transition-colors z-10",
          taskPanelOpen
            ? "bg-primary text-on-primary"
            : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
        )}
      >
        <LayoutList className="w-3.5 h-3.5" />
        Tasks
      </button>
    </div>
  )
}

// ── WorkspaceView ──────────────────────────────────────────────────────────────

export default function WorkspaceView() {
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const saved = localStorage.getItem('ws_active_tab') as Tab | null
    return (saved && TABS.some((t) => t.id === saved)) ? saved : 'chat'
  })
  const [refreshKey, setRefreshKey] = useState(0)

  const handleRefresh = () => setRefreshKey((k) => k + 1)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'F5' || (e.ctrlKey && e.key === 'r' && !e.altKey)) {
        e.preventDefault()
        handleRefresh()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">

      {/* Header bar */}
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
            onClick={handleRefresh}
            title="Refresh data (F5)"
            className="w-7 h-7 flex items-center justify-center rounded-lg text-on-surface-variant/50 hover:text-on-surface hover:bg-surface-variant/50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Body: icon tab strip (left) + content (right) */}
      <div className="flex flex-1 overflow-hidden">

        {/* Icon tab strip */}
        <div className="flex flex-col items-center py-3 px-1.5 gap-1 border-r border-outline-variant/15 bg-surface-container-low/30 flex-shrink-0 w-14">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => { setActiveTab(t.id); localStorage.setItem('ws_active_tab', t.id) }}
              title={t.label}
              className={cn(
                "relative w-9 h-9 flex items-center justify-center rounded-xl transition-all",
                activeTab === t.id
                  ? "bg-primary/15 text-primary"
                  : "text-on-surface-variant/50 hover:bg-surface-variant/50 hover:text-on-surface"
              )}
            >
              {t.icon}
              {/* Active dot */}
              {activeTab === t.id && (
                <div className="absolute left-0.5 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-primary rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden relative">
          {activeTab === 'chat' && <ChatTab key={`chat-${refreshKey}`} />}

          {activeTab === 'agents' && (
            <div className="h-full overflow-y-auto" key={`agents-${refreshKey}`}>
              <AgentsPanel />
            </div>
          )}

          {activeTab === 'crm' && (
            <div className="h-full" key={`crm-${refreshKey}`}>
              <CRMPanel />
            </div>
          )}

          {activeTab === 'screen' && (
            <div className="h-full" key={`screen-${refreshKey}`}>
              <ScreenPanel />
            </div>
          )}

          {activeTab === 'files' && (
            <div className="h-full flex flex-col gap-0 overflow-hidden">
              <div className="flex-1 overflow-hidden">
                <FilesPanel />
              </div>
              <div className="border-t border-outline-variant/10 p-3 bg-surface-container-low/20 flex-shrink-0">
                <DocumentDropZone surface="workspace" compact />
              </div>
            </div>
          )}

          {activeTab === 'pc' && (
            <div className="h-full overflow-y-auto p-4">
              <SystemMetricsPanel />
            </div>
          )}

          {activeTab === 'tasks' && (
            <div className="h-full flex flex-col overflow-hidden">
              <div className="flex-1 min-h-0 overflow-hidden">
                <TaskManagerPanel />
              </div>
              <div className="border-t border-outline-variant/10 bg-surface-container-low/20 flex-shrink-0 max-h-72 overflow-y-auto">
                <AutomationPanel />
              </div>
            </div>
          )}

          {activeTab === 'voip' && (
            <div className="h-full">
              <VoIPPanel />
            </div>
          )}

          {activeTab === 'calendar' && (
            <div className="h-full">
              <CalendarPanel />
            </div>
          )}

          {activeTab === 'email' && (
            <div className="h-full">
              <EmailPanel />
            </div>
          )}

          {activeTab === 'media' && (
            <div className="h-full">
              <MediaLibraryPanel />
            </div>
          )}

          {activeTab === 'docs' && (
            <div className="h-full" key={`docs-${refreshKey}`}>
              <DocumentsPanel />
            </div>
          )}

          {activeTab === 'tools' && (
            <div className="h-full" key={`tools-${refreshKey}`}>
              <ToolsPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
