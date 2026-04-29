/**
 * CRMPanel — Contacts & Tasks from the memory module.
 *
 * Two sub-tabs: Contacts | Tasks
 * Contacts: search, add, delete row
 * Tasks:    add, complete, delete row
 *
 * API:
 *   GET  /api/workspace/contacts?q=
 *   POST /api/workspace/contacts
 *   DELETE /api/workspace/contacts/{name}
 *   GET  /api/workspace/tasks?status=
 *   POST /api/workspace/tasks
 *   PUT  /api/workspace/tasks/{id}/complete
 *   DELETE /api/workspace/tasks/{id}
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Users, CheckSquare, Search, Plus, Trash2, Check,
  RefreshCw, ChevronDown, ChevronUp, User,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Contact {
  id?: number
  name: string
  company: string
  email: string
  phone: string
  notes: string
  last_contact?: string
}

interface Task {
  id: number
  task: string
  due_date: string
  status: string
  created: string
}

// ── ContactRow ────────────────────────────────────────────────────────────────

function ContactRow({ contact, onDelete }: { contact: Contact; onDelete: (name: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="border-b border-outline-variant/10 last:border-0">
      <div
        className="flex items-center gap-2 px-3 py-2 hover:bg-surface-variant/20 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="w-6 h-6 rounded-full bg-primary/15 flex items-center justify-center flex-shrink-0">
          <User className="w-3 h-3 text-primary/70" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-on-surface truncate">{contact.name}</p>
          {contact.company && (
            <p className="text-xs text-on-surface-variant/60 truncate">{contact.company}</p>
          )}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(contact.name) }}
          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-error/10 text-on-surface-variant/40 hover:text-error transition-colors"
          title="Delete contact"
        >
          <Trash2 className="w-3 h-3" />
        </button>
        {expanded ? <ChevronUp className="w-3.5 h-3.5 text-on-surface-variant/40 flex-shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-on-surface-variant/40 flex-shrink-0" />}
      </div>
      {expanded && (
        <div className="px-3 pb-2 pl-11 space-y-1 text-xs text-on-surface-variant/70">
          {contact.email && <p>✉ {contact.email}</p>}
          {contact.phone && <p>📞 {contact.phone}</p>}
          {contact.notes && <p className="italic opacity-70">{contact.notes}</p>}
          {contact.last_contact && (
            <p className="text-on-surface-variant/40">
              Last: {new Date(contact.last_contact).toLocaleDateString()}
            </p>
          )}
          <button
            onClick={() => onDelete(contact.name)}
            className="text-error/70 hover:text-error transition-colors flex items-center gap-1 mt-1"
          >
            <Trash2 className="w-3 h-3" /> Delete contact
          </button>
        </div>
      )}
    </div>
  )
}

// ── AddContactForm ────────────────────────────────────────────────────────────

function AddContactForm({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ name: '', company: '', email: '', phone: '', notes: '' })

  const save = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      await api.post('/api/workspace/contacts', form)
      setForm({ name: '', company: '', email: '', phone: '', notes: '' })
      setOpen(false)
      onAdded()
    } catch { /* ignore */ } finally {
      setSaving(false)
    }
  }

  if (!open) return (
    <button
      onClick={() => setOpen(true)}
      className="w-full flex items-center justify-center gap-2 text-xs text-on-surface-variant/60 hover:text-primary transition-colors py-2 border border-dashed border-outline-variant/30 rounded-lg hover:border-primary/30"
    >
      <Plus className="w-3.5 h-3.5" /> Add Contact
    </button>
  )

  return (
    <div className="bg-surface-container rounded-xl p-3 space-y-2 border border-primary/20">
      {(['name', 'company', 'email', 'phone'] as const).map((f) => (
        <input
          key={f}
          value={form[f]}
          onChange={(e) => setForm((p) => ({ ...p, [f]: e.target.value }))}
          placeholder={f.charAt(0).toUpperCase() + f.slice(1) + (f === 'name' ? ' *' : '')}
          className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
        />
      ))}
      <textarea
        value={form.notes}
        onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
        placeholder="Notes…"
        rows={2}
        className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40 resize-none"
      />
      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving || !form.name.trim()}
          className="flex-1 text-xs bg-primary text-on-primary rounded-lg py-1.5 hover:bg-primary/90 disabled:opacity-40 transition-colors"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="px-3 text-xs text-on-surface-variant/60 hover:text-on-surface transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── ContactsTab ───────────────────────────────────────────────────────────────

function ContactsTab() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(true)

  const load = useCallback(async (q = '') => {
    setLoading(true)
    try {
      const res = await api.get(`/api/workspace/contacts${q ? `?q=${encodeURIComponent(q)}` : ''}`)
      setContacts(res.data || [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSearch = (v: string) => {
    setSearch(v)
    load(v)
  }

  const deleteContact = async (name: string) => {
    try {
      await api.delete(`/api/workspace/contacts/${encodeURIComponent(name)}`)
      setContacts((c) => c.filter((x) => x.name !== name))
    } catch { /* ignore */ }
  }

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-on-surface-variant/40" />
        <input
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search contacts…"
          className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-container border border-outline-variant/20 rounded-lg outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
        />
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar bg-surface-container rounded-xl min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-4 h-4 animate-spin text-on-surface-variant/40" />
          </div>
        ) : contacts.length === 0 ? (
          <p className="text-center text-xs text-on-surface-variant/40 py-8">No contacts found</p>
        ) : (
          <div className="group">
            {contacts.map((c) => (
              <ContactRow key={c.name} contact={c} onDelete={deleteContact} />
            ))}
          </div>
        )}
      </div>

      {/* Add form */}
      <AddContactForm onAdded={() => load(search)} />
    </div>
  )
}

// ── TasksTab ──────────────────────────────────────────────────────────────────

function TasksTab() {
  const [tasks, setTasks]       = useState<Task[]>([])
  const [loading, setLoading]   = useState(true)
  const [statusFilter, setFilter] = useState<'pending' | 'completed'>('pending')
  const [newTask, setNewTask]   = useState('')
  const [newDue, setNewDue]     = useState('')
  const [saving, setSaving]     = useState(false)

  const load = useCallback(async (s = statusFilter) => {
    setLoading(true)
    try {
      const res = await api.get(`/api/workspace/tasks?status=${s}`)
      setTasks(res.data || [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { load(statusFilter) }, [statusFilter, load])

  const addTask = async () => {
    if (!newTask.trim()) return
    setSaving(true)
    try {
      await api.post('/api/workspace/tasks', { task: newTask, due_date: newDue })
      setNewTask(''); setNewDue('')
      load(statusFilter)
    } catch { /* ignore */ } finally {
      setSaving(false)
    }
  }

  const complete = async (id: number) => {
    try {
      await api.put(`/api/workspace/tasks/${id}/complete`)
      setTasks((t) => t.filter((x) => x.id !== id))
    } catch { /* ignore */ }
  }

  const remove = async (id: number) => {
    try {
      await api.delete(`/api/workspace/tasks/${id}`)
      setTasks((t) => t.filter((x) => x.id !== id))
    } catch { /* ignore */ }
  }

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Filter */}
      <div className="flex gap-1">
        {(['pending', 'completed'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "text-xs px-3 py-1.5 rounded-lg capitalize transition-colors",
              statusFilter === f
                ? "bg-primary/10 text-primary font-medium"
                : "text-on-surface-variant/60 hover:text-on-surface"
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Task list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-4 h-4 animate-spin text-on-surface-variant/40" />
          </div>
        ) : tasks.length === 0 ? (
          <p className="text-center text-xs text-on-surface-variant/40 py-8">
            {statusFilter === 'pending' ? 'No pending tasks' : 'No completed tasks'}
          </p>
        ) : (
          tasks.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-2 bg-surface-container rounded-xl px-3 py-2 group"
            >
              {statusFilter === 'pending' && (
                <button
                  onClick={() => complete(t.id)}
                  className="w-4 h-4 rounded border border-outline-variant/40 hover:border-primary/60 hover:bg-primary/10 flex items-center justify-center flex-shrink-0 transition-colors"
                  title="Mark complete"
                >
                  <Check className="w-2.5 h-2.5 text-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              )}
              {statusFilter === 'completed' && (
                <Check className="w-4 h-4 text-success flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-xs text-on-surface truncate",
                  statusFilter === 'completed' && "line-through text-on-surface-variant/50"
                )}>
                  {t.task}
                </p>
                {t.due_date && (
                  <p className="text-xs text-on-surface-variant/40">{t.due_date}</p>
                )}
              </div>
              <button
                onClick={() => remove(t.id)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-error/10 text-on-surface-variant/40 hover:text-error transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Add task */}
      {statusFilter === 'pending' && (
        <div className="space-y-1.5">
          <input
            value={newTask}
            onChange={(e) => setNewTask(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addTask()}
            placeholder="New task…"
            className="w-full text-xs bg-surface-container border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
          />
          <div className="flex gap-2">
            <input
              type="date"
              value={newDue}
              onChange={(e) => setNewDue(e.target.value)}
              className="flex-1 text-xs bg-surface-container border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
            />
            <button
              onClick={addTask}
              disabled={saving || !newTask.trim()}
              className="px-3 text-xs bg-primary text-on-primary rounded-lg hover:bg-primary/90 disabled:opacity-40 transition-colors flex items-center gap-1"
            >
              {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── CRMPanel ──────────────────────────────────────────────────────────────────

export function CRMPanel() {
  const [tab, setTab] = useState<'contacts' | 'tasks'>('contacts')

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Sub-tabs */}
      <div className="flex gap-1 bg-surface-container-low rounded-xl p-1 flex-shrink-0">
        <button
          onClick={() => setTab('contacts')}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg transition-colors",
            tab === 'contacts'
              ? "bg-surface text-on-surface font-medium shadow-sm"
              : "text-on-surface-variant/60 hover:text-on-surface"
          )}
        >
          <Users className="w-3.5 h-3.5" /> Contacts
        </button>
        <button
          onClick={() => setTab('tasks')}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg transition-colors",
            tab === 'tasks'
              ? "bg-surface text-on-surface font-medium shadow-sm"
              : "text-on-surface-variant/60 hover:text-on-surface"
          )}
        >
          <CheckSquare className="w-3.5 h-3.5" /> Tasks
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0">
        {tab === 'contacts' ? <ContactsTab /> : <TasksTab />}
      </div>
    </div>
  )
}
