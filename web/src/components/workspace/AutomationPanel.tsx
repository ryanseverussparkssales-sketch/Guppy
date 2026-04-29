/**
 * AutomationPanel — Reminders management
 *
 * Lists pending reminders, lets users add new ones, and cancel existing ones.
 * Polls /api/reminders for the live list.
 *
 * API:
 *   GET    /api/reminders           — list all undelivered reminders
 *   POST   /api/reminders           — { message, due_iso | delay_minutes }
 *   DELETE /api/reminders/{id}      — cancel a reminder
 */
import { useState, useEffect, useCallback } from 'react'
import { Bell, Plus, Trash2, RefreshCw, Clock, AlarmClock } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Reminder {
  id: string
  message: string
  due_at: string
  delivered: boolean
  created_at: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string) {
  const diff = new Date(iso).getTime() - Date.now()
  if (diff < 0) return 'Overdue'
  const mins = Math.round(diff / 60000)
  if (mins < 1) return 'Any moment'
  if (mins < 60) return `in ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `in ${hrs}h ${mins % 60}m`
  return `in ${Math.floor(hrs / 24)}d`
}

function formatDue(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── AddReminderForm ───────────────────────────────────────────────────────────

function AddReminderForm({ onAdded }: { onAdded: () => void }) {
  const [open, setSaving_]          = useState(false)
  const [saving, setSaving]         = useState(false)
  const [message, setMessage]       = useState('')
  const [mode, setMode]             = useState<'delay' | 'datetime'>('delay')
  const [delayMins, setDelayMins]   = useState('30')
  const [dueIso, setDueIso]         = useState(() => {
    const d = new Date(); d.setHours(d.getHours() + 1); d.setMinutes(0, 0, 0)
    return d.toISOString().slice(0, 16)  // yyyy-MM-ddTHH:mm for datetime-local
  })

  const submit = async () => {
    if (!message.trim()) return
    setSaving(true)
    try {
      const body: Record<string, unknown> = { message: message.trim() }
      if (mode === 'delay') {
        body.delay_minutes = parseFloat(delayMins) || 30
      } else {
        body.due_iso = new Date(dueIso).toISOString()
      }
      await api.post('/api/reminders', body)
      setMessage('')
      setSaving_(false)
      onAdded()
    } catch { /* ignore */ } finally {
      setSaving(false)
    }
  }

  if (!open) return (
    <button
      onClick={() => setSaving_(true)}
      className="w-full flex items-center justify-center gap-2 text-xs text-on-surface-variant/60 hover:text-primary transition-colors py-2 border border-dashed border-outline-variant/30 rounded-xl hover:border-primary/30"
    >
      <Plus className="w-3.5 h-3.5" /> Add Reminder
    </button>
  )

  return (
    <div className="bg-surface-container rounded-xl p-3 space-y-2.5 border border-primary/20">
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Reminder message…"
        rows={2}
        className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40 resize-none"
      />

      {/* Mode toggle */}
      <div className="flex gap-1 bg-surface-container-low rounded-lg p-0.5">
        {(['delay', 'datetime'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              "flex-1 text-xs py-1 rounded-md transition-colors",
              mode === m ? "bg-surface text-on-surface font-medium" : "text-on-surface-variant/60"
            )}
          >
            {m === 'delay' ? 'In X minutes' : 'At a time'}
          </button>
        ))}
      </div>

      {mode === 'delay' ? (
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-on-surface-variant/50 flex-shrink-0" />
          <input
            type="number"
            value={delayMins}
            onChange={(e) => setDelayMins(e.target.value)}
            min={1}
            className="flex-1 text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
          />
          <span className="text-xs text-on-surface-variant/50">minutes</span>
        </div>
      ) : (
        <input
          type="datetime-local"
          value={dueIso}
          onChange={(e) => setDueIso(e.target.value)}
          className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        />
      )}

      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={saving || !message.trim()}
          className="flex-1 text-xs bg-primary text-on-primary rounded-lg py-1.5 hover:bg-primary/90 disabled:opacity-40 transition-colors"
        >
          {saving ? 'Saving…' : 'Set Reminder'}
        </button>
        <button
          onClick={() => setSaving_(false)}
          className="px-3 text-xs text-on-surface-variant/60 hover:text-on-surface transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── AutomationPanel ───────────────────────────────────────────────────────────

export function AutomationPanel() {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [loading, setLoading]     = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/reminders')
      setReminders(Array.isArray(res.data) ? res.data : [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const cancel = async (id: string) => {
    try {
      await api.delete(`/api/reminders/${id}`)
      setReminders((r) => r.filter((x) => x.id !== id))
    } catch { /* ignore */ }
  }

  const sorted = [...reminders].sort(
    (a, b) => new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
  )

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Bell className="w-4 h-4 text-on-surface-variant" />
        <span className="text-sm font-semibold text-on-surface">Reminders</span>
        {reminders.length > 0 && (
          <span className="px-1.5 py-0.5 text-xs font-medium bg-primary/10 text-primary rounded-full">
            {reminders.length}
          </span>
        )}
        <button
          onClick={load}
          className="ml-auto p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Reminder list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : sorted.length === 0 ? (
          <div className="text-center py-10">
            <AlarmClock className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No reminders set</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">
              Add one below or ask Guppy to remind you of something
            </p>
          </div>
        ) : (
          sorted.map((r) => {
            const overdue = new Date(r.due_at).getTime() < Date.now()
            return (
              <div
                key={r.id}
                className={cn(
                  "bg-surface-container rounded-xl px-3 py-2.5 flex items-start gap-2.5 group",
                  overdue && "border border-warning/30 bg-warning/5"
                )}
              >
                <div className={cn(
                  "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5",
                  overdue ? "bg-warning/20" : "bg-primary/10"
                )}>
                  <Bell className={cn("w-3.5 h-3.5", overdue ? "text-warning" : "text-primary/70")} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-on-surface leading-snug">{r.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Clock className="w-3 h-3 text-on-surface-variant/40" />
                    <span className={cn(
                      "text-xs",
                      overdue ? "text-warning font-medium" : "text-on-surface-variant/50"
                    )}>
                      {relativeTime(r.due_at)} · {formatDue(r.due_at)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => cancel(r.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-error/10 text-on-surface-variant/40 hover:text-error transition-all flex-shrink-0 mt-0.5"
                  title="Cancel reminder"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })
        )}
      </div>

      {/* Add form */}
      <div className="flex-shrink-0">
        <AddReminderForm onAdded={load} />
      </div>
    </div>
  )
}
