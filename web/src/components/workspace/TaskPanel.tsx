/**
 * Task Panel Component for WorkspaceView
 * 
 * Displays:
 * - Task list with state badges
 * - Step trace accordion for each task
 * - Confirm/cancel/run buttons
 * - Real-time SSE updates
 */

import { useState, useEffect } from 'react'
import { ChevronDown, Play, XCircle, Check, AlertCircle, Clock } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/api/client'
import { cn } from '@/lib/utils'

export interface WorkspaceTask {
  id: string
  task_description: string
  source: string
  state: string
  created_at: string
  completed_at?: string
}

export interface WorkspaceTaskDetail extends WorkspaceTask {
  started_at?: string
  result?: string
  error?: string
  steps: WorkspaceTaskStep[]
}

export interface WorkspaceTaskStep {
  id: string
  step_number: number
  tool_name: string
  tool_args: Record<string, unknown>
  result?: Record<string, unknown>
  requires_confirmation: boolean
  confirmation_given: boolean
  created_at: string
  completed_at?: string
}

const STATE_COLORS = {
  queued: 'bg-slate-100 text-slate-700 border-slate-300',
  planning: 'bg-blue-100 text-blue-700 border-blue-300',
  running: 'bg-orange-100 text-orange-700 border-orange-300 animate-pulse',
  blocked: 'bg-red-100 text-red-700 border-red-300',
  complete: 'bg-green-100 text-green-700 border-green-300',
  failed: 'bg-red-100 text-red-700 border-red-300',
  cancelled: 'bg-gray-100 text-gray-700 border-gray-300',
}

/**
 * TaskPanel — displays list of workspace tasks with real-time updates
 */
export function TaskPanel() {
  const [tasks, setTasks] = useState<WorkspaceTask[]>([])
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)
  const [detailedTask, setDetailedTask] = useState<WorkspaceTaskDetail | null>(null)
  const [loading, setLoading] = useState(false)

  const loadTasks = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/workspace/tasks')
      setTasks(r.data || [])
    } catch (e) {
      console.error('Failed to load tasks:', e)
      toast.error('Could not load tasks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTasks()
    // Refresh every 5 seconds
    const interval = setInterval(loadTasks, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadTaskDetail = async (taskId: string) => {
    try {
      const r = await api.get(`/api/workspace/tasks/${taskId}`)
      setDetailedTask(r.data)
    } catch (e) {
      console.error('Failed to load task detail:', e)
    }
  }

  const runTask = async (taskId: string) => {
    try {
      await api.post(`/api/workspace/tasks/${taskId}/run`)
      toast.success('Task started')
      loadTasks()
    } catch (e) {
      console.error('Failed to run task:', e)
      toast.error('Could not start task')
    }
  }

  const cancelTask = async (taskId: string) => {
    try {
      await api.post(`/api/workspace/tasks/${taskId}/cancel`)
      toast.success('Task cancelled')
      loadTasks()
    } catch (e) {
      console.error('Failed to cancel task:', e)
      toast.error('Could not cancel task')
    }
  }

  const confirmAction = async (taskId: string, stepId: string) => {
    try {
      await api.post(`/api/workspace/tasks/${taskId}/confirm`, { step_id: stepId })
      toast.success('Action confirmed')
      loadTaskDetail(taskId)
    } catch (e) {
      console.error('Failed to confirm action:', e)
      toast.error('Could not confirm action')
    }
  }

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">
      <div className="px-4 py-3 border-b border-outline-variant/20">
        <h2 className="text-lg font-semibold">Tasks</h2>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 p-3">
        {loading && tasks.length === 0 ? (
          <p className="text-sm text-on-surface-variant/50 text-center py-6">Loading tasks…</p>
        ) : tasks.length === 0 ? (
          <p className="text-sm text-on-surface-variant/50 text-center py-6">No tasks yet. Create one from Conversations.</p>
        ) : (
          tasks.map((task) => (
            <div key={task.id} className="border border-outline-variant/20 rounded-lg overflow-hidden">
              {/* Task header */}
              <button
                onClick={() => {
                  if (expandedTaskId === task.id) {
                    setExpandedTaskId(null)
                  } else {
                    setExpandedTaskId(task.id)
                    loadTaskDetail(task.id)
                  }
                }}
                className="w-full px-3 py-2 flex items-center gap-2 hover:bg-surface-variant/30 transition-colors"
              >
                <ChevronDown
                  className={cn(
                    "w-4 h-4 transition-transform flex-shrink-0",
                    expandedTaskId === task.id && "rotate-180"
                  )}
                />
                <div className="flex-1 text-left min-w-0">
                  <p className="text-sm font-medium truncate">{task.task_description}</p>
                  <p className="text-xs text-on-surface-variant/60 mt-0.5">
                    {new Date(task.created_at).toLocaleTimeString()}
                  </p>
                </div>
                <span
                  className={cn(
                    "px-2 py-1 rounded text-xs font-medium whitespace-nowrap flex-shrink-0 border",
                    STATE_COLORS[task.state as keyof typeof STATE_COLORS] || 'bg-gray-100'
                  )}
                >
                  {task.state}
                </span>
              </button>

              {/* Expanded detail */}
              {expandedTaskId === task.id && detailedTask?.id === task.id && (
                <div className="border-t border-outline-variant/20 bg-surface-variant/10 p-3 space-y-2">
                  {/* Task actions */}
                  <div className="flex gap-2">
                    {task.state === 'queued' && (
                      <button
                        onClick={() => runTask(task.id)}
                        className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors"
                      >
                        <Play className="w-3 h-3" />
                        Run
                      </button>
                    )}
                    {task.state === 'blocked' && detailedTask.steps.some((s) => s.requires_confirmation && !s.confirmation_given) && (
                      <button
                        onClick={() => {
                          const blockedStep = detailedTask.steps.find(
                            (s) => s.requires_confirmation && !s.confirmation_given
                          )
                          if (blockedStep) confirmAction(task.id, blockedStep.id)
                        }}
                        className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                      >
                        <Check className="w-3 h-3" />
                        Confirm
                      </button>
                    )}
                    {['queued', 'planning', 'running'].includes(task.state) && (
                      <button
                        onClick={() => cancelTask(task.id)}
                        className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs bg-error/20 text-error rounded-lg hover:bg-error/30 transition-colors"
                      >
                        <XCircle className="w-3 h-3" />
                        Cancel
                      </button>
                    )}
                  </div>

                  {/* Steps */}
                  {detailedTask.steps.length > 0 && (
                    <div className="mt-3 space-y-1.5 border-t border-outline-variant/20 pt-2">
                      <p className="text-xs font-semibold text-on-surface-variant">Steps</p>
                      {detailedTask.steps.map((step) => (
                        <div
                          key={step.id}
                          className="px-2 py-1.5 bg-surface rounded border border-outline-variant/10 text-xs"
                        >
                          <div className="flex items-start gap-1.5">
                            {step.completed_at ? (
                              <Check className="w-3 h-3 text-green-600 flex-shrink-0 mt-0.5" />
                            ) : step.requires_confirmation ? (
                              <AlertCircle className="w-3 h-3 text-orange-600 flex-shrink-0 mt-0.5" />
                            ) : (
                              <Clock className="w-3 h-3 text-blue-600 flex-shrink-0 mt-0.5" />
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="font-medium">
                                {step.step_number}. {step.tool_name}
                              </p>
                              {step.requires_confirmation && (
                                <p className="text-orange-700 mt-0.5">Requires confirmation</p>
                              )}
                              {step.result && (
                                <p className="text-on-surface-variant/60 mt-0.5 whitespace-normal">
                                  {JSON.stringify(step.result).slice(0, 80)}…
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Error message */}
                  {detailedTask.error && (
                    <div className="p-2 bg-error/10 border border-error/20 rounded text-xs text-error">
                      {detailedTask.error}
                    </div>
                  )}

                  {/* Result */}
                  {detailedTask.result && (
                    <div className="p-2 bg-green-100/50 border border-green-300/50 rounded text-xs text-green-700">
                      ✓ {detailedTask.result}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
