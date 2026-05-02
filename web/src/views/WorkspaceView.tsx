/**
 * WorkspaceView — Operations Hub
 *
 * Icon tab strip (11 tabs):
 *   Chat | Agents | CRM | Screen | Files | PC | Tasks | Calls | Calendar | Email | Media
 * Each tab mounts its panel in a consistent scrollable container.
 * Chat tab keeps the full AssistantView + collapsible AgentTaskPanel sidebar.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  MessageSquare, LayoutList, Users, Monitor, FolderOpen,
  Cpu, Phone, Zap, AlertCircle, Calendar, Mail, Library,
  CheckSquare, RefreshCw, FileText, Wrench, Brain,
} from 'lucide-react'
import { toast } from 'sonner'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useSurfaceEvents } from '@/hooks/useSurfaceEvents'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
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
import { TaskPanel } from '@/components/workspace/TaskPanel'
import { AutomationPanel } from '@/components/workspace/AutomationPanel'
import { DocumentDropZone } from '@/components/shared/DocumentDropZone'
import { DocumentsPanel } from '@/components/workspace/DocumentsPanel'
import { ToolsPanel } from '@/components/workspace/ToolsPanel'
import { MemoryPanel } from '@/components/workspace/MemoryPanel'
import AssistantChat from './AssistantView'

// ── Tab config ─────────────────────────────────────────────────────────────────

type Tab = 'chat' | 'agents' | 'crm' | 'screen' | 'files' | 'pc' | 'tasks' | 'voip' | 'calendar' | 'email' | 'media' | 'docs' | 'tools' | 'memory'

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
  { id: 'memory',   icon: <Brain         className="w-4 h-4" />, label: 'Memory'   },
]

// ── Panel error fallback ───────────────────────────────────────────────────────

function PanelFallback({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
      <AlertCircle className="w-8 h-8 text-error/40" />
      <p className="text-sm text-on-surface-variant/50">{label} panel encountered an error.</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-surface-variant hover:bg-surface-container-high text-on-surface-variant transition-colors"
      >
        <RefreshCw className="w-3 h-3" />
        Reload
      </button>
    </div>
  )
}

// ── AgentsPanel ────────────────────────────────────────────────────────────────

function AgentsPanel() {
  // Simplified to use new TaskPanel component wired to /api/workspace/tasks
  return <TaskPanel />
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
          <AssistantChat surface="workspace" />
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
  const [agentCallbacks, setAgentCallbacks] = useState(0)

  const handleSurfaceEvent = useCallback((type: string, payload: any) => {
    if (type === 'task_callback') {
      const title = payload?.data?.title ?? 'Task'
      const summary = payload?.data?.result_summary ?? ''
      toast.success(`Fix ready: ${title}`, {
        description: summary ? summary.slice(0, 120) : undefined,
        action: { label: 'View', onClick: () => setActiveTab('agents') },
        duration: 8000,
      })
      setAgentCallbacks((n) => n + 1)
    }
  }, [])

  useSurfaceEvents(handleSurfaceEvent)

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
              onClick={() => {
                setActiveTab(t.id)
                localStorage.setItem('ws_active_tab', t.id)
                if (t.id === 'agents') setAgentCallbacks(0)
              }}
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
              {/* Callback badge — red dot on Agents tab when fix results arrive */}
              {t.id === 'agents' && agentCallbacks > 0 && activeTab !== 'agents' && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-error" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden relative">
          {activeTab === 'chat' && <ChatTab key={`chat-${refreshKey}`} />}

          {activeTab === 'agents' && (
            <div className="h-full overflow-y-auto" key={`agents-${refreshKey}`}>
              <ErrorBoundary fallback={<PanelFallback label="Agents" />}>
                <AgentsPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'crm' && (
            <div className="h-full" key={`crm-${refreshKey}`}>
              <ErrorBoundary fallback={<PanelFallback label="CRM" />}>
                <CRMPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'screen' && (
            <div className="h-full" key={`screen-${refreshKey}`}>
              <ErrorBoundary fallback={<PanelFallback label="Screen" />}>
                <ScreenPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'files' && (
            <div className="h-full flex flex-col gap-0 overflow-hidden">
              <div className="flex-1 overflow-hidden">
                <ErrorBoundary fallback={<PanelFallback label="Files" />}>
                  <FilesPanel />
                </ErrorBoundary>
              </div>
              <div className="border-t border-outline-variant/10 p-3 bg-surface-container-low/20 flex-shrink-0">
                <DocumentDropZone surface="workspace" compact />
              </div>
            </div>
          )}

          {activeTab === 'pc' && (
            <div className="h-full overflow-y-auto p-4">
              <ErrorBoundary fallback={<PanelFallback label="System Metrics" />}>
                <SystemMetricsPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'tasks' && (
            <div className="h-full flex flex-col overflow-hidden">
              <div className="flex-1 min-h-0 overflow-hidden">
                <ErrorBoundary fallback={<PanelFallback label="Tasks" />}>
                  <TaskManagerPanel />
                </ErrorBoundary>
              </div>
              <div className="border-t border-outline-variant/10 bg-surface-container-low/20 flex-shrink-0 max-h-72 overflow-y-auto">
                <ErrorBoundary fallback={<PanelFallback label="Automation" />}>
                  <AutomationPanel />
                </ErrorBoundary>
              </div>
            </div>
          )}

          {activeTab === 'voip' && (
            <div className="h-full">
              <ErrorBoundary fallback={<PanelFallback label="Calls" />}>
                <VoIPPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'calendar' && (
            <div className="h-full">
              <ErrorBoundary fallback={<PanelFallback label="Calendar" />}>
                <CalendarPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'email' && (
            <div className="h-full">
              <ErrorBoundary fallback={<PanelFallback label="Email" />}>
                <EmailPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'media' && (
            <div className="h-full">
              <ErrorBoundary fallback={<PanelFallback label="Media" />}>
                <MediaLibraryPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'docs' && (
            <div className="h-full" key={`docs-${refreshKey}`}>
              <ErrorBoundary fallback={<PanelFallback label="Documents" />}>
                <DocumentsPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'tools' && (
            <div className="h-full" key={`tools-${refreshKey}`}>
              <ErrorBoundary fallback={<PanelFallback label="Tools" />}>
                <ToolsPanel />
              </ErrorBoundary>
            </div>
          )}

          {activeTab === 'memory' && (
            <div className="h-full" key={`memory-${refreshKey}`}>
              <ErrorBoundary fallback={<PanelFallback label="Memory" />}>
                <MemoryPanel />
              </ErrorBoundary>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
