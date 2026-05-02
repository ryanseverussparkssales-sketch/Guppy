/**
 * VoIPPanel — Call log management
 *
 * Lists inbound/outbound calls, lets the user log a call manually,
 * update notes, and see Quo integration status.
 *
 * API:
 *   GET    /api/voip/calls
 *   POST   /api/voip/calls    { phone_number, contact_name, direction, status, duration_s, notes }
 *   PATCH  /api/voip/calls/{id}  { notes?, status? }
 *   DELETE /api/voip/calls/{id}
 *   GET    /api/voip/status
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed, Plus, Trash2,
  RefreshCw, Edit3, Check, X, AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Call {
  id: string
  contact_name: string
  phone_number: string
  direction: 'inbound' | 'outbound'
  status: 'completed' | 'missed' | 'failed' | 'incoming'
  duration_s: number | null
  notes: string
  called_at: string
  external_id: string | null
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function CallIcon({ direction, status }: { direction: string; status: string }) {
  if (status === 'missed')  return <PhoneMissed   className="w-4 h-4 text-error/70" />
  if (direction === 'inbound') return <PhoneIncoming className="w-4 h-4 text-secondary" />
  return <PhoneOutgoing className="w-4 h-4 text-primary" />
}

function fmtDuration(s: number | null) {
  if (!s) return ''
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function relTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// ── NoteEditor ────────────────────────────────────────────────────────────────

function NoteEditor({ callId, initialNote, onSaved }: { callId: string; initialNote: string; onSaved: (note: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [note, setNote]       = useState(initialNote)
  const [saving, setSaving]   = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await api.patch(`/api/voip/calls/${callId}`, { notes: note })
      onSaved(note)
      setEditing(false)
      toast.success('Note saved')
    } catch {
      toast.error('Failed to save note')
      setNote(initialNote)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (!editing) return (
    <div className="flex items-start gap-1.5">
      <p className="text-xs text-on-surface-variant/60 flex-1 italic">{note || 'No notes'}</p>
      <button type="button" title="Edit note" onClick={() => setEditing(true)} className="p-0.5 rounded text-on-surface-variant/30 hover:text-on-surface transition-colors">
        <Edit3 className="w-3 h-3" />
      </button>
    </div>
  )

  return (
    <div className="flex gap-1.5">
      <textarea
        aria-label="Call note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        className="flex-1 text-xs bg-surface border border-outline-variant/30 rounded-lg px-2 py-1 outline-none focus:border-primary/50 text-on-surface resize-none"
        autoFocus
      />
      <div className="flex flex-col gap-1">
        <button type="button" title="Save note" onClick={save} disabled={saving} className="p-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors">
          {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
        </button>
        <button type="button" title="Cancel edit" onClick={() => { setEditing(false); setNote(initialNote) }} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 transition-colors">
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}

// ── CallRow ───────────────────────────────────────────────────────────────────

function CallRow({ call, deleting, onDelete, onNoteUpdate }: {
  call: Call
  deleting: boolean
  onDelete: (id: string) => void
  onNoteUpdate: (id: string, note: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-surface-container rounded-xl overflow-hidden">
      <div
        className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer hover:bg-surface-variant/20 transition-colors group"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center flex-shrink-0">
          <CallIcon direction={call.direction} status={call.status} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-on-surface truncate">
            {call.contact_name || call.phone_number}
          </p>
          <p className="text-xs text-on-surface-variant/50">
            {call.contact_name ? call.phone_number + ' · ' : ''}
            {call.direction} · {call.status}
            {call.duration_s ? ` · ${fmtDuration(call.duration_s)}` : ''}
          </p>
        </div>
        <span className="text-xs text-on-surface-variant/40 flex-shrink-0">{relTime(call.called_at)}</span>
        <button
          type="button"
          title="Delete call"
          disabled={deleting}
          onClick={(e) => { e.stopPropagation(); onDelete(call.id) }}
          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-error/10 text-on-surface-variant/30 hover:text-error transition-all disabled:opacity-30"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-outline-variant/10 pt-2">
          <NoteEditor
            callId={call.id}
            initialNote={call.notes}
            onSaved={(n) => onNoteUpdate(call.id, n)}
          />
          {call.external_id && (
            <p className="text-xs text-on-surface-variant/30 mt-1.5 font-mono">{call.external_id}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── LogCallForm ───────────────────────────────────────────────────────────────

function LogCallForm({ onLogged }: { onLogged: () => void }) {
  const [open, setOpen]             = useState(false)
  const [saving, setSaving]         = useState(false)
  const [form, setForm]             = useState({
    phone_number: '', contact_name: '', direction: 'outbound',
    status: 'completed', duration_s: '', notes: '',
  })

  const save = async () => {
    if (!form.phone_number.trim()) return
    setSaving(true)
    try {
      await api.post('/api/voip/calls', {
        ...form,
        duration_s: form.duration_s ? parseInt(form.duration_s) : null,
      })
      setForm({ phone_number: '', contact_name: '', direction: 'outbound', status: 'completed', duration_s: '', notes: '' })
      setOpen(false)
      onLogged()
      toast.success('Call logged')
    } catch {
      toast.error('Failed to log call')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return (
    <button
      type="button"
      onClick={() => setOpen(true)}
      className="w-full flex items-center justify-center gap-2 text-xs text-on-surface-variant/60 hover:text-primary transition-colors py-2 border border-dashed border-outline-variant/30 rounded-xl hover:border-primary/30"
    >
      <Plus className="w-3.5 h-3.5" /> Log Call
    </button>
  )

  return (
    <div className="bg-surface-container rounded-xl p-3 space-y-2.5 border border-primary/20">
      <div className="grid grid-cols-2 gap-2">
        <input
          value={form.phone_number}
          onChange={(e) => setForm((p) => ({ ...p, phone_number: e.target.value }))}
          placeholder="Phone number *"
          className="col-span-2 text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
        />
        <input
          value={form.contact_name}
          onChange={(e) => setForm((p) => ({ ...p, contact_name: e.target.value }))}
          placeholder="Contact name"
          className="text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
        />
        <input
          value={form.duration_s}
          onChange={(e) => setForm((p) => ({ ...p, duration_s: e.target.value }))}
          placeholder="Duration (seconds)"
          type="number"
          min={0}
          className="text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
        />
        <select
          aria-label="Call direction"
          value={form.direction}
          onChange={(e) => setForm((p) => ({ ...p, direction: e.target.value }))}
          className="text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        >
          <option value="outbound">Outbound</option>
          <option value="inbound">Inbound</option>
        </select>
        <select
          aria-label="Call status"
          value={form.status}
          onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
          className="text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        >
          <option value="completed">Completed</option>
          <option value="missed">Missed</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      <textarea
        value={form.notes}
        onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
        placeholder="Notes…"
        rows={2}
        className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40 resize-none"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={save}
          disabled={saving || !form.phone_number.trim()}
          className="flex-1 text-xs bg-primary text-on-primary rounded-lg py-1.5 hover:bg-primary/90 disabled:opacity-40 transition-colors"
        >
          {saving ? 'Saving…' : 'Log Call'}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="px-3 text-xs text-on-surface-variant/60 hover:text-on-surface">Cancel</button>
      </div>
    </div>
  )
}

// ── VoIPPanel ─────────────────────────────────────────────────────────────────

export function VoIPPanel() {
  const [calls, setCalls]             = useState<Call[]>([])
  const [loading, setLoading]         = useState(true)
  const [syncing, setSyncing]         = useState(false)
  const [quoStatus, setQuoStatus]     = useState<{ configured: boolean } | null>(null)
  const [filter, setFilter]           = useState<'all' | 'inbound' | 'outbound'>('all')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [callsRes, statusRes] = await Promise.all([
        api.get(`/api/voip/calls${filter !== 'all' ? `?direction=${filter}` : ''}`),
        api.get('/api/voip/status'),
      ])
      setCalls(Array.isArray(callsRes.data) ? callsRes.data : [])
      setQuoStatus({ configured: statusRes.data?.quo_configured ?? false })
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [filter])

  const syncFromQuo = async () => {
    setSyncing(true)
    try {
      await api.post('/api/voip/sync', {})
      await load()
    } catch { /* ignore */ } finally {
      setSyncing(false)
    }
  }

  useEffect(() => { load() }, [load])

  const [deletingId, setDeletingId] = useState<string | null>(null)

  const deleteCall = async (id: string) => {
    if (!window.confirm('Delete this call record?')) return
    setDeletingId(id)
    try {
      await api.delete(`/api/voip/calls/${id}`)
      setCalls((c) => c.filter((x) => x.id !== id))
    } catch {
      alert('Failed to delete call. Please try again.')
    } finally {
      setDeletingId(null)
    }
  }

  const updateNote = (id: string, note: string) => {
    setCalls((c) => c.map((x) => x.id === id ? { ...x, notes: note } : x))
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Phone className="w-4 h-4 text-on-surface-variant" />
        <span className="text-sm font-semibold text-on-surface">Call Log</span>
        {quoStatus && (
          <div className={cn(
            "ml-1 flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full",
            quoStatus.configured
              ? "bg-success/10 text-success"
              : "bg-surface-variant text-on-surface-variant/50"
          )}>
            <div className={cn("w-1.5 h-1.5 rounded-full", quoStatus.configured ? "bg-success" : "bg-on-surface-variant/30")} />
            {quoStatus.configured ? 'Quo' : 'No Quo'}
          </div>
        )}
        {quoStatus?.configured && (
          <button type="button" onClick={syncFromQuo} disabled={syncing} title="Sync from Quo" className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors">
            <RefreshCw className={cn("w-3.5 h-3.5", syncing && "animate-spin")} />
          </button>
        )}
        <button type="button" onClick={load} title="Refresh" className="ml-auto p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors">
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Quo not configured notice */}
      {quoStatus && !quoStatus.configured && (
        <div className="flex items-start gap-2 bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface-variant/60">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span>Set <code className="text-on-surface">QUO_API_KEY</code> and <code className="text-on-surface">QUO_PHONE_NUMBER_ID</code> env vars to enable live Quo integration.</span>
        </div>
      )}

      {/* Direction filter */}
      <div className="flex gap-1 flex-shrink-0">
        {(['all', 'inbound', 'outbound'] as const).map((f) => (
          <button
            type="button"
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "text-xs px-2.5 py-1 rounded-lg capitalize transition-colors",
              filter === f ? "bg-primary/10 text-primary font-medium" : "text-on-surface-variant/60 hover:text-on-surface"
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Call list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="space-y-2 p-1">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 rounded-xl bg-surface-variant/30 animate-pulse" />
            ))}
          </div>
        ) : calls.length === 0 ? (
          <div className="text-center py-10">
            <Phone className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No calls logged</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">Log one below or connect Quo for live tracking</p>
          </div>
        ) : (
          calls.map((c) => (
            <CallRow key={c.id} call={c} deleting={deletingId === c.id} onDelete={deleteCall} onNoteUpdate={updateNote} />
          ))
        )}
      </div>

      {/* Log call form */}
      <div className="flex-shrink-0">
        <LogCallForm onLogged={load} />
      </div>
    </div>
  )
}
