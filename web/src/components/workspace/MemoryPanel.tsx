/**
 * MemoryPanel — Browse, search, create, and delete semantic memory entries.
 *
 * API: GET/POST /api/memory/entries  DELETE /api/memory/entries/{key}
 *      GET /api/memory/entries/search?q=&n=
 *      DELETE /api/memory/entries?confirm=true
 *
 * Category tabs: All | General | Tool Outcomes | Session Summaries | Workspace Results | User Preferences
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Brain, Plus, X, RefreshCw, Trash2, Search,
  ChevronDown, ChevronUp, AlertTriangle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface MemoryEntry {
  key:      string
  category: string
  value:    string
  created:  string
}

type CategoryFilter = 'all' | 'general' | 'tool_outcome' | 'session_summary' | 'workspace_result' | 'user_preference'

const CATEGORY_LABELS: Record<CategoryFilter, string> = {
  all:              'All',
  general:          'General',
  tool_outcome:     'Tool Outcomes',
  session_summary:  'Session Summaries',
  workspace_result: 'Workspace Results',
  user_preference:  'User Preferences',
}

const CATEGORY_BADGE: Record<string, string> = {
  general:          'bg-surface-variant text-on-surface-variant',
  tool_outcome:     'bg-primary/10 text-primary',
  session_summary:  'bg-secondary/10 text-secondary',
  workspace_result: 'bg-tertiary/10 text-tertiary',
  user_preference:  'bg-warning/10 text-warning',
}

function badgeClass(cat: string) {
  return CATEGORY_BADGE[cat] ?? 'bg-surface-variant text-on-surface-variant'
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

// ── EntryCard ─────────────────────────────────────────────────────────────────

function EntryCard({ entry, onDelete }: {
  entry: MemoryEntry
  onDelete: (key: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const isLong = entry.value.length > 200

  return (
    <div className="rounded-xl border border-outline-variant/20 bg-surface-container p-3 space-y-1.5">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-on-surface truncate">{entry.key}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full font-medium", badgeClass(entry.category))}>
              {entry.category}
            </span>
            <span className="text-[10px] text-on-surface-variant/40">{fmtDate(entry.created)}</span>
          </div>
        </div>
        <button
          onClick={() => onDelete(entry.key)}
          className="p-1 rounded hover:bg-error/10 text-on-surface-variant/30 hover:text-error transition-colors flex-shrink-0"
          title="Delete entry"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      <p className={cn(
        "text-xs text-on-surface-variant/70 whitespace-pre-wrap break-words leading-relaxed",
        !expanded && isLong && "line-clamp-3",
      )}>
        {entry.value}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-[10px] text-primary/60 hover:text-primary transition-colors"
        >
          {expanded ? <><ChevronUp className="w-3 h-3" />Show less</> : <><ChevronDown className="w-3 h-3" />Show more</>}
        </button>
      )}
    </div>
  )
}

// ── NewMemoryForm ─────────────────────────────────────────────────────────────

const CATEGORIES: CategoryFilter[] = ['general', 'tool_outcome', 'session_summary', 'workspace_result', 'user_preference']

function NewMemoryForm({ onSave, onClose }: { onSave: () => void; onClose: () => void }) {
  const [key,      setKey]      = useState('')
  const [value,    setValue]    = useState('')
  const [category, setCategory] = useState<CategoryFilter>('general')
  const [saving,   setSaving]   = useState(false)
  const [err,      setErr]      = useState('')

  const save = async () => {
    if (!key.trim())   { setErr('Key is required');   return }
    if (!value.trim()) { setErr('Value is required'); return }
    setSaving(true)
    try {
      await api.post('/api/memory/entries', { key: key.trim(), value: value.trim(), category })
      toast.success('Memory stored')
      onSave()
    } catch {
      setErr('Failed to save memory')
      toast.error('Failed to save memory')
    } finally { setSaving(false) }
  }

  return (
    <div className="absolute inset-0 bg-surface z-20 flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/20 flex-shrink-0">
        <Brain className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold text-on-surface flex-1">New Memory</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        <div>
          <label className="text-xs text-on-surface-variant/50 mb-1 block">Key</label>
          <input
            className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
            placeholder="e.g. user_preferred_model"
            value={key} onChange={(e) => setKey(e.target.value)}
            autoFocus
          />
        </div>
        <div>
          <label className="text-xs text-on-surface-variant/50 mb-1 block">Value</label>
          <textarea
            className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40 resize-none"
            placeholder="Memory content…"
            rows={4} value={value} onChange={(e) => setValue(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs text-on-surface-variant/50 mb-1 block">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as CategoryFilter)}
            className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface border border-outline-variant/20 focus:outline-none"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>
        {err && <p className="text-xs text-error/80">{err}</p>}
      </div>
      <div className="flex gap-2 px-4 py-3 border-t border-outline-variant/15 flex-shrink-0">
        <button onClick={onClose}
          className="flex-1 py-2 text-xs rounded-xl bg-surface-variant text-on-surface-variant hover:bg-surface-container-high transition-colors">
          Cancel
        </button>
        <button onClick={save} disabled={saving}
          className="flex-1 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium">
          {saving ? 'Saving…' : 'Save memory'}
        </button>
      </div>
    </div>
  )
}

// ── ClearAllDialog ────────────────────────────────────────────────────────────

function ClearAllDialog({ onConfirm, onClose }: { onConfirm: () => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-2xl shadow-xl p-6 max-w-xs w-full mx-4 space-y-4">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-error flex-shrink-0" />
          <p className="text-sm font-semibold text-on-surface">Clear all memories?</p>
        </div>
        <p className="text-xs text-on-surface-variant/70">
          This will permanently delete every memory entry. This action cannot be undone.
        </p>
        <div className="flex gap-2">
          <button onClick={onClose}
            className="flex-1 py-2 text-xs rounded-xl bg-surface-variant text-on-surface-variant hover:bg-surface-container-high transition-colors">
            Cancel
          </button>
          <button onClick={onConfirm}
            className="flex-1 py-2 text-xs rounded-xl bg-error/10 text-error hover:bg-error/15 transition-colors font-medium">
            Clear all
          </button>
        </div>
      </div>
    </div>
  )
}

// ── MemoryPanel ───────────────────────────────────────────────────────────────

export function MemoryPanel() {
  const [entries,     setEntries]     = useState<MemoryEntry[]>([])
  const [total,       setTotal]       = useState(0)
  const [loading,     setLoading]     = useState(true)
  const [query,       setQuery]       = useState('')
  const [catFilter,   setCatFilter]   = useState<CategoryFilter>('all')
  const [adding,      setAdding]      = useState(false)
  const [confirmClear,setConfirmClear]= useState(false)
  const debounceRef   = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async (q?: string, cat?: CategoryFilter) => {
    setLoading(true)
    try {
      const activeCat = cat ?? catFilter
      const activeQ   = q   ?? query
      if (activeQ.trim()) {
        const r = await api.get('/api/memory/entries/search', {
          params: { q: activeQ.trim(), n: 50 },
        })
        setEntries(r.data.entries ?? [])
        setTotal(r.data.total ?? 0)
      } else {
        const params: Record<string, unknown> = { limit: 200, offset: 0 }
        if (activeCat !== 'all') params.category = activeCat
        const r = await api.get('/api/memory/entries', { params })
        setEntries(r.data.entries ?? [])
        setTotal(r.data.total ?? 0)
      }
    } catch { /* silent */ } finally { setLoading(false) }
  }, [catFilter, query])

  useEffect(() => { load() }, [load])

  // Debounce search
  const handleSearch = (val: string) => {
    setQuery(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      load(val, catFilter)
    }, 300)
  }

  const handleCatChange = (cat: CategoryFilter) => {
    setCatFilter(cat)
    load(query, cat)
  }

  const deleteEntry = async (key: string) => {
    setEntries((es) => es.filter((e) => e.key !== key))
    try {
      await api.delete(`/api/memory/entries/${encodeURIComponent(key)}`)
      toast.success('Memory deleted')
    } catch {
      toast.error('Failed to delete memory')
      load()
    }
  }

  const clearAll = async () => {
    setConfirmClear(false)
    try {
      await api.delete('/api/memory/entries', { params: { confirm: true } })
      toast.success('All memories cleared')
      load()
    } catch {
      toast.error('Failed to clear memories')
    }
  }

  // Category tabs showing counts
  const catTabs: CategoryFilter[] = ['all', 'general', 'tool_outcome', 'session_summary', 'workspace_result', 'user_preference']
  const countByCat = entries.reduce<Record<string, number>>((acc, e) => {
    acc[e.category] = (acc[e.category] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {adding && (
        <NewMemoryForm
          onSave={() => { setAdding(false); load() }}
          onClose={() => setAdding(false)}
        />
      )}
      {confirmClear && (
        <ClearAllDialog
          onConfirm={clearAll}
          onClose={() => setConfirmClear(false)}
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Brain className="w-4 h-4 text-primary/70" />
        <span className="text-sm font-semibold text-on-surface">Memory</span>
        <span className="text-xs px-1.5 py-0.5 rounded-full bg-surface-container text-on-surface-variant/50">
          {total}
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            onClick={() => setConfirmClear(true)}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg text-error/60 hover:bg-error/10 hover:text-error transition-colors"
            title="Clear all memories"
          >
            <Trash2 className="w-3 h-3" />
            Clear all
          </button>
          <button
            onClick={() => load()}
            className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/40"
            title="Refresh"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative flex-shrink-0">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-on-surface-variant/40" />
        <input
          className="w-full bg-surface-container rounded-xl pl-9 pr-3 py-2 text-xs text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
          placeholder="Search memories…"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      {/* Category tabs */}
      <div className="flex items-center gap-1 overflow-x-auto flex-shrink-0 pb-0.5">
        {catTabs.map((cat) => {
          const count = cat === 'all' ? total : (countByCat[cat] ?? 0)
          return (
            <button
              key={cat}
              onClick={() => handleCatChange(cat)}
              className={cn(
                "flex items-center gap-1 text-[10px] px-2.5 py-1 rounded-full whitespace-nowrap transition-colors",
                catFilter === cat
                  ? "bg-primary/15 text-primary font-medium"
                  : "bg-surface-container text-on-surface-variant/50 hover:text-on-surface hover:bg-surface-variant/60",
              )}
            >
              {CATEGORY_LABELS[cat]}
              {count > 0 && (
                <span className="text-[9px] opacity-60">{count}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* Entries */}
      {loading && entries.length === 0 ? (
        <div className="flex items-center justify-center flex-1">
          <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
        </div>
      ) : entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 text-center px-8 gap-3">
          <Brain className="w-10 h-10 text-on-surface-variant/15" />
          <p className="text-sm text-on-surface-variant/40">
            {query ? 'No matching memories' : 'No memories stored yet'}
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
          {entries.map((e) => (
            <EntryCard key={e.key} entry={e} onDelete={deleteEntry} />
          ))}
        </div>
      )}

      {/* Add button */}
      <button
        onClick={() => setAdding(true)}
        className="flex items-center justify-center gap-2 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 transition-colors font-medium flex-shrink-0"
      >
        <Plus className="w-3.5 h-3.5" />
        New memory
      </button>
    </div>
  )
}
