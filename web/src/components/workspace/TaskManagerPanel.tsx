/**
 * TaskManagerPanel — Personal task board + reminders
 *
 * A proper task manager with projects, priorities, due dates, and status.
 * Persists to /api/tasks (dedicated task board backend). Separate from
 * /api/workspace/tasks (agent CRM tasks) and AgentTaskPanel (AI job tracker).
 *
 * Views: Board (Todo | Doing | Done) | List (all, filterable)
 * API: GET/POST /api/tasks  PATCH/DELETE /api/tasks/{id}
 */
import { useState, useEffect, useCallback } from 'react'
import {
  CheckSquare, Plus, X, RefreshCw, Flag,
  Circle, CheckCircle2, Zap, Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Task {
  id: string
  title: string
  description?: string
  status: 'todo' | 'doing' | 'done'
  priority: 'low' | 'medium' | 'high'
  due_date?: string
  project?: string
  tags?: string[]
  created_at: string
}

type View = 'board' | 'list'

// ── Helpers ───────────────────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<Task['priority'], string> = {
  high:   'text-error',
  medium: 'text-warning',
  low:    'text-on-surface-variant/40',
}
const PRIORITY_BG: Record<Task['priority'], string> = {
  high:   'bg-error/10 border-error/20',
  medium: 'bg-warning/10 border-warning/20',
  low:    'bg-surface-container border-outline-variant/20',
}
const STATUS_COLS: Task['status'][] = ['todo', 'doing', 'done']
const STATUS_LABELS: Record<Task['status'], string> = { todo: 'To Do', doing: 'In Progress', done: 'Done' }
const STATUS_COLORS: Record<Task['status'], string> = {
  todo:  'text-on-surface-variant',
  doing: 'text-primary',
  done:  'text-success',
}

function relDue(iso: string) {
  try {
    const d   = new Date(iso)
    const now = new Date()
    const diff = d.getTime() - now.getTime()
    const days = Math.ceil(diff / 86400000)
    if (days < 0)  return { label: `${Math.abs(days)}d overdue`, color: 'text-error' }
    if (days === 0) return { label: 'Due today', color: 'text-warning' }
    if (days === 1) return { label: 'Due tomorrow', color: 'text-warning' }
    return { label: `Due in ${days}d`, color: 'text-on-surface-variant/50' }
  } catch { return { label: iso.slice(0, 10), color: 'text-on-surface-variant/50' } }
}

// ── AddTaskForm ───────────────────────────────────────────────────────────────

function AddTaskForm({ initialStatus = 'todo', onSave, onClose }: {
  initialStatus?: Task['status']
  onSave: () => void
  onClose: () => void
}) {
  const [title,    setTitle]    = useState('')
  const [desc,     setDesc]     = useState('')
  const [status,   setStatus]   = useState<Task['status']>(initialStatus)
  const [priority, setPriority] = useState<Task['priority']>('medium')
  const [project,  setProject]  = useState('')
  const [due,      setDue]      = useState('')
  const [saving,   setSaving]   = useState(false)
  const [err,      setErr]      = useState('')

  const save = async () => {
    if (!title.trim()) { setErr('Title required'); return }
    setSaving(true)
    try {
      await api.post('/api/tasks', {
        title: title.trim(), description: desc,
        status, priority, project,
        due_date: due || undefined,
      })
      onSave()
    } catch { setErr('Failed to create task') } finally { setSaving(false) }
  }

  return (
    <div className="absolute inset-0 bg-surface z-20 flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/20 flex-shrink-0">
        <Plus className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold text-on-surface flex-1">New Task</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        <input className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
          placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()} autoFocus />
        <textarea className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40 resize-none"
          placeholder="Description (optional)" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />

        <div className="grid grid-cols-2 gap-2">
          {/* Status */}
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value as Task['status'])}
              className="w-full bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none">
              {STATUS_COLS.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
          </div>
          {/* Priority */}
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">Priority</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value as Task['priority'])}
              className="w-full bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none">
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">Project</label>
            <input className="w-full bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none"
              placeholder="e.g. Guppy" value={project} onChange={(e) => setProject(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">Due date</label>
            <input type="date" className="w-full bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none"
              value={due} onChange={(e) => setDue(e.target.value)} />
          </div>
        </div>
        {err && <p className="text-xs text-error/80">{err}</p>}
      </div>
      <div className="flex gap-2 px-4 py-3 border-t border-outline-variant/15 flex-shrink-0">
        <button onClick={onClose} className="flex-1 py-2 text-xs rounded-xl bg-surface-variant text-on-surface-variant hover:bg-surface-container-high transition-colors">
          Cancel
        </button>
        <button onClick={save} disabled={saving}
          className="flex-1 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium">
          {saving ? 'Saving…' : 'Add task'}
        </button>
      </div>
    </div>
  )
}

// ── TaskCard ──────────────────────────────────────────────────────────────────

function TaskCard({ task, onUpdate, onDelete }: {
  task: Task
  onUpdate: (id: string, patch: Partial<Task>) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const due = task.due_date ? relDue(task.due_date) : null

  const cycleStatus = () => {
    const next: Record<Task['status'], Task['status']> = {
      todo: 'doing', doing: 'done', done: 'todo',
    }
    onUpdate(task.id, { status: next[task.status] })
  }

  return (
    <div className={cn("rounded-xl border text-sm transition-all", PRIORITY_BG[task.priority])}>
      <div className="flex items-start gap-2 px-3 py-2.5">
        <button onClick={cycleStatus} className="mt-0.5 flex-shrink-0">
          {task.status === 'done'
            ? <CheckCircle2 className="w-4 h-4 text-success" />
            : task.status === 'doing'
            ? <Zap className="w-4 h-4 text-primary" />
            : <Circle className="w-4 h-4 text-on-surface-variant/30" />
          }
        </button>
        <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <p className={cn("text-xs font-medium", task.status === 'done' && "line-through text-on-surface-variant/50")}>
            {task.title}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            {task.project && (
              <span className="text-[10px] text-on-surface-variant/50 truncate">{task.project}</span>
            )}
            {due && <span className={cn("text-[10px]", due.color)}>{due.label}</span>}
            <Flag className={cn("w-3 h-3 ml-auto", PRIORITY_COLORS[task.priority])} />
          </div>
        </div>
        <button onClick={(e) => { e.stopPropagation(); onDelete(task.id) }}
          className="p-0.5 rounded hover:bg-error/10 text-on-surface-variant/20 hover:text-error transition-colors flex-shrink-0">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      {expanded && task.description && (
        <div className="px-3 pb-2.5 pl-9 border-t border-outline-variant/10 pt-2">
          <p className="text-xs text-on-surface-variant/60">{task.description}</p>
        </div>
      )}
    </div>
  )
}

// ── TaskManagerPanel ──────────────────────────────────────────────────────────

export function TaskManagerPanel() {
  const [tasks,    setTasks]    = useState<Task[]>([])
  const [loading,  setLoading]  = useState(true)
  const [view,     setView]     = useState<View>('board')
  const [adding,   setAdding]   = useState(false)
  const [initStatus, setInitStatus] = useState<Task['status']>('todo')
  const [filter,   setFilter]   = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/tasks?limit=200')
      setTasks(Array.isArray(r.data) ? r.data : [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const updateTask = async (id: string, patch: Partial<Task>) => {
    setTasks((ts) => ts.map((t) => t.id === id ? { ...t, ...patch } : t))
    await api.patch(`/api/tasks/${id}`, patch).catch(() => { load() })
  }

  const deleteTask = async (id: string) => {
    setTasks((ts) => ts.filter((t) => t.id !== id))
    await api.delete(`/api/tasks/${id}`).catch(() => { load() })
  }

  const filtered = tasks.filter((t) =>
    !filter || t.title.toLowerCase().includes(filter.toLowerCase()) ||
    (t.project || '').toLowerCase().includes(filter.toLowerCase())
  )

  const byStatus = (s: Task['status']) => filtered.filter((t) => t.status === s)

  const totals = {
    todo:  tasks.filter((t) => t.status === 'todo').length,
    doing: tasks.filter((t) => t.status === 'doing').length,
    done:  tasks.filter((t) => t.status === 'done').length,
  }

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {adding && (
        <AddTaskForm
          initialStatus={initStatus}
          onSave={() => { setAdding(false); load() }}
          onClose={() => setAdding(false)}
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <CheckSquare className="w-4 h-4 text-primary/70" />
        <span className="text-sm font-semibold text-on-surface">Tasks</span>
        {totals.doing > 0 && (
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-primary text-on-primary font-medium">
            {totals.doing} active
          </span>
        )}
        {/* View toggle */}
        <div className="ml-auto flex items-center gap-1 bg-surface-container rounded-lg p-0.5">
          {(['board', 'list'] as const).map((v) => (
            <button key={v} onClick={() => setView(v)}
              className={cn("text-xs px-2 py-1 rounded-md capitalize transition-colors",
                view === v ? "bg-surface text-on-surface shadow-sm" : "text-on-surface-variant/50 hover:text-on-surface")}>
              {v}
            </button>
          ))}
        </div>
        <button onClick={load} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/40">
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Search filter */}
      <input
        className="bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none flex-shrink-0"
        placeholder="Filter tasks by title or project…"
        value={filter} onChange={(e) => setFilter(e.target.value)}
      />

      {/* Content */}
      {loading && tasks.length === 0 ? (
        <div className="flex items-center justify-center flex-1">
          <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
        </div>
      ) : view === 'board' ? (
        /* ── Board view ── */
        <div className="flex-1 overflow-x-auto min-h-0">
          <div className="flex gap-3 h-full" style={{ minWidth: '480px' }}>
            {STATUS_COLS.map((col) => {
              const colTasks = byStatus(col)
              return (
                <div key={col} className="flex-1 flex flex-col min-w-0 gap-2">
                  {/* Column header */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={cn("text-xs font-semibold", STATUS_COLORS[col])}>
                      {STATUS_LABELS[col]}
                    </span>
                    <span className="text-xs text-on-surface-variant/40 bg-surface-container px-1.5 py-0.5 rounded-full">
                      {colTasks.length}
                    </span>
                    <button
                      onClick={() => { setInitStatus(col); setAdding(true) }}
                      className="ml-auto p-1 rounded hover:bg-surface-variant text-on-surface-variant/30 hover:text-primary transition-colors">
                      <Plus className="w-3 h-3" />
                    </button>
                  </div>
                  {/* Tasks */}
                  <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
                    {colTasks.map((t) => (
                      <TaskCard key={t.id} task={t} onUpdate={updateTask} onDelete={deleteTask} />
                    ))}
                    {colTasks.length === 0 && (
                      <button
                        onClick={() => { setInitStatus(col); setAdding(true) }}
                        className="w-full py-4 text-xs text-on-surface-variant/30 border border-dashed border-outline-variant/20 rounded-xl hover:border-primary/30 hover:text-primary/40 transition-colors">
                        + Add task
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        /* ── List view ── */
        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5 min-h-0">
          {filtered.length === 0 ? (
            <div className="text-center py-10">
              <CheckSquare className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
              <p className="text-sm text-on-surface-variant/40">
                {filter ? 'No matching tasks' : 'No tasks yet'}
              </p>
            </div>
          ) : filtered.map((t) => (
            <TaskCard key={t.id} task={t} onUpdate={updateTask} onDelete={deleteTask} />
          ))}
        </div>
      )}

      {/* Add button */}
      <button onClick={() => { setInitStatus('todo'); setAdding(true) }}
        className="flex items-center justify-center gap-2 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 transition-colors font-medium flex-shrink-0">
        <Plus className="w-3.5 h-3.5" />
        New task
      </button>
    </div>
  )
}
