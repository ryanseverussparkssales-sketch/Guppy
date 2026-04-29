import { useState, useEffect, useCallback } from 'react'
import { Wrench, RefreshCw, ToggleLeft, ToggleRight, Search, Plus, Trash2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface Tool {
  id: string
  name: string
  description: string
  category: string
  type: string
  isEnabled: boolean
}

const CATEGORY_LABELS: Record<string, string> = {
  search:      'Search & Web',
  file:        'File & Docs',
  system:      'System',
  desktop:     'Desktop Control',
  vision:      'Vision',
  code:        'Code',
  comms:       'Communication',
  memory:      'Memory',
  tasks:       'Tasks',
  library:     'Ebook Library',
  productivity: 'Productivity',
  media:       'Media',
  api:         'Custom API',
}

const CATEGORY_ORDER = [
  'search', 'file', 'system', 'desktop', 'vision', 'library',
  'productivity', 'memory', 'tasks', 'comms', 'code', 'media', 'api',
]

export function ToolsPanel() {
  const [tools, setTools]       = useState<Tool[]>([])
  const [loading, setLoading]   = useState(true)
  const [filter, setFilter]     = useState('')
  const [catFilter, setCatFilter] = useState<string>('all')
  const [toast, setToast]       = useState('')
  const [addOpen, setAddOpen]   = useState(false)
  const [newName, setNewName]   = useState('')
  const [newDesc, setNewDesc]   = useState('')
  const [newCat, setNewCat]     = useState('api')
  const [saving, setSaving]     = useState(false)

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(''), 3000) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.get('/tools')
      setTools(Array.isArray(r.data) ? r.data : [])
    } catch { setTools([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const toggle = async (tool: Tool) => {
    const endpoint = tool.isEnabled ? `/tools/${tool.id}/disable` : `/tools/${tool.id}/enable`
    try {
      const r = await api.post(endpoint)
      setTools(ts => ts.map(t => t.id === tool.id ? { ...t, isEnabled: r.data?.isEnabled ?? !tool.isEnabled } : t))
    } catch { showToast('Failed to toggle tool') }
  }

  const deleteTool = async (tool: Tool) => {
    try {
      await api.delete(`/tools/${tool.id}`)
      setTools(ts => ts.filter(t => t.id !== tool.id))
      showToast(`Deleted ${tool.name}`)
    } catch { showToast('Delete failed') }
  }

  const createTool = async () => {
    if (!newName.trim() || !newDesc.trim()) return
    setSaving(true)
    try {
      const r = await api.post('/tools', { name: newName.trim(), description: newDesc.trim(), category: newCat })
      setTools(ts => [...ts, r.data])
      setNewName(''); setNewDesc(''); setNewCat('api'); setAddOpen(false)
      showToast(`Created ${r.data.name}`)
    } catch { showToast('Create failed') } finally { setSaving(false) }
  }

  const q = filter.toLowerCase()
  const visible = tools.filter(t => {
    if (catFilter !== 'all' && t.category !== catFilter) return false
    if (!q) return true
    return t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.id.includes(q)
  })

  const byCategory: Record<string, Tool[]> = {}
  for (const t of visible) {
    (byCategory[t.category] ??= []).push(t)
  }

  const enabledCount = tools.filter(t => t.isEnabled).length
  const categories = [...new Set(tools.map(t => t.category))]
    .sort((a, b) => (CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b)))

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <Wrench className="w-4 h-4 text-tertiary/70" />
          <span className="text-sm font-semibold text-on-surface">Tools</span>
          <span className="text-xs text-on-surface-variant/40">
            {enabledCount}/{tools.length} enabled
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setAddOpen(o => !o)}
            className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
            <Plus className="w-3 h-3" /> Custom
          </button>
          <button onClick={load}
            className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 transition-colors">
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {toast && (
        <div className="flex items-center gap-2 bg-primary/10 rounded-xl px-3 py-2 text-xs text-primary font-medium flex-shrink-0">
          {toast}
        </div>
      )}

      {/* Add custom tool form */}
      {addOpen && (
        <div className="bg-surface-container rounded-2xl p-4 border border-outline-variant/20 flex-shrink-0 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-on-surface">New Custom Tool</span>
            <button onClick={() => setAddOpen(false)} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/40">
              <X className="w-3 h-3" />
            </button>
          </div>
          <input
            className="w-full text-xs bg-surface rounded-lg px-3 py-2 border border-outline-variant/20 text-on-surface placeholder:text-on-surface-variant/30 outline-none focus:border-primary/40"
            placeholder="Tool name"
            value={newName} onChange={e => setNewName(e.target.value)}
          />
          <textarea
            className="w-full text-xs bg-surface rounded-lg px-3 py-2 border border-outline-variant/20 text-on-surface placeholder:text-on-surface-variant/30 outline-none focus:border-primary/40 resize-none"
            placeholder="What this tool does (shown to the AI)"
            rows={2}
            value={newDesc} onChange={e => setNewDesc(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <select
              className="flex-1 text-xs bg-surface rounded-lg px-3 py-2 border border-outline-variant/20 text-on-surface outline-none"
              value={newCat} onChange={e => setNewCat(e.target.value)}>
              {categories.map(c => (
                <option key={c} value={c}>{CATEGORY_LABELS[c] ?? c}</option>
              ))}
            </select>
            <button
              onClick={createTool}
              disabled={saving || !newName.trim() || !newDesc.trim()}
              className="text-xs px-3 py-2 rounded-lg bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-40 transition-colors">
              {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : 'Create'}
            </button>
          </div>
        </div>
      )}

      {/* Search + category filter */}
      <div className="flex gap-2 flex-shrink-0">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-on-surface-variant/40" />
          <input
            className="w-full text-xs bg-surface-container rounded-lg pl-7 pr-3 py-2 border border-outline-variant/20 text-on-surface placeholder:text-on-surface-variant/30 outline-none focus:border-primary/40"
            placeholder="Search tools…"
            value={filter} onChange={e => setFilter(e.target.value)}
          />
        </div>
        <select
          className="text-xs bg-surface-container rounded-lg px-2 py-2 border border-outline-variant/20 text-on-surface outline-none"
          value={catFilter} onChange={e => setCatFilter(e.target.value)}>
          <option value="all">All</option>
          {categories.map(c => (
            <option key={c} value={c}>{CATEGORY_LABELS[c] ?? c}</option>
          ))}
        </select>
      </div>

      {/* Tool list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : visible.length === 0 ? (
          <div className="text-center py-10">
            <Wrench className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No tools match</p>
          </div>
        ) : (
          CATEGORY_ORDER
            .filter(cat => byCategory[cat]?.length)
            .concat(Object.keys(byCategory).filter(c => !CATEGORY_ORDER.includes(c)))
            .map(cat => (
              <div key={cat}>
                <p className="text-[10px] font-semibold text-on-surface-variant/40 uppercase tracking-wider mb-1.5 px-1">
                  {CATEGORY_LABELS[cat] ?? cat}
                </p>
                <div className="space-y-1">
                  {byCategory[cat].map(tool => (
                    <div key={tool.id}
                      className={cn(
                        "flex items-start gap-3 rounded-xl p-2.5 transition-colors",
                        tool.isEnabled
                          ? "bg-surface-container"
                          : "bg-surface-container/40 opacity-60"
                      )}>
                      <button
                        onClick={() => toggle(tool)}
                        className="flex-shrink-0 mt-0.5 text-on-surface-variant/50 hover:text-primary transition-colors"
                        title={tool.isEnabled ? 'Disable' : 'Enable'}>
                        {tool.isEnabled
                          ? <ToggleRight className="w-4 h-4 text-primary" />
                          : <ToggleLeft className="w-4 h-4" />}
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-on-surface">{tool.name}</span>
                          <span className="text-[9px] font-mono text-on-surface-variant/30 bg-surface px-1 rounded">{tool.id}</span>
                          {tool.type === 'custom' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-secondary/10 text-secondary">custom</span>
                          )}
                        </div>
                        <p className="text-[10px] text-on-surface-variant/50 mt-0.5 leading-relaxed">{tool.description}</p>
                      </div>
                      {tool.type === 'custom' && (
                        <button
                          onClick={() => deleteTool(tool)}
                          className="flex-shrink-0 mt-0.5 p-1 rounded hover:bg-error/10 text-on-surface-variant/30 hover:text-error transition-colors">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
        )}
      </div>
    </div>
  )
}
