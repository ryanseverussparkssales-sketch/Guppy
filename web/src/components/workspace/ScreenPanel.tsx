/**
 * ScreenPanel — Screenpipe activity viewer
 *
 * Shows recent screen/audio captures from the Screenpipe daemon.
 * Two sub-tabs: Recent (last N minutes) | Search (keyword + filters)
 *
 * API:
 *   GET /api/screenpipe/status
 *   GET /api/screenpipe/recent?minutes=30&limit=20
 *   GET /api/screenpipe/search?query=&limit=20&content_type=all
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Monitor, Search, Clock, RefreshCw, AlertCircle,
  Volume2, FileText, Image, BarChart2, Layers, Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ScreenpipeItem {
  id?: string | number
  content?: string
  timestamp?: string
  type?: string       // 'ocr' | 'audio' | 'image'
  app_name?: string
  window_name?: string
  text?: string       // screenpipe search uses "text"
  transcription?: string
  file_path?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function ContentTypeIcon({ type }: { type?: string }) {
  if (type === 'audio') return <Volume2 className="w-3.5 h-3.5 text-secondary" />
  if (type === 'image') return <Image className="w-3.5 h-3.5 text-tertiary" />
  return <FileText className="w-3.5 h-3.5 text-primary" />
}

function ItemCard({ item }: { item: ScreenpipeItem }) {
  const body = item.text || item.content || item.transcription || ''
  const ts   = item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''

  return (
    <div className="bg-surface-container rounded-xl p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        <ContentTypeIcon type={item.type} />
        <span className="text-xs font-medium text-on-surface truncate flex-1">
          {item.app_name || item.window_name || 'Screen activity'}
        </span>
        {ts && <span className="text-xs text-on-surface-variant/40 flex-shrink-0">{ts}</span>}
      </div>
      {body && (
        <p className="text-xs text-on-surface-variant/70 leading-relaxed line-clamp-3">
          {body}
        </p>
      )}
      {item.window_name && item.app_name && item.window_name !== item.app_name && (
        <p className="text-xs text-on-surface-variant/40">{item.window_name}</p>
      )}
    </div>
  )
}

// ── StatusBanner ──────────────────────────────────────────────────────────────

function StatusBanner({ alive }: { alive: boolean | null }) {
  if (alive === null) return null
  if (alive) return null  // healthy — no banner needed
  return (
    <div className="flex items-center gap-2 bg-warning/10 border border-warning/20 rounded-xl px-3 py-2 text-xs text-warning">
      <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
      <span>Screenpipe not running. Start it to see activity.</span>
    </div>
  )
}

// ── RecentTab ─────────────────────────────────────────────────────────────────

function RecentTab({ alive }: { alive: boolean | null }) {
  const [items, setItems]       = useState<ScreenpipeItem[]>([])
  const [loading, setLoading]   = useState(false)
  const [minutes, setMinutes]   = useState(30)

  const load = useCallback(async (m = minutes) => {
    setLoading(true)
    try {
      const res = await api.get(`/api/screenpipe/recent?minutes=${m}&limit=30`)
      // response may be list or { items: [] }
      const data = res.data
      setItems(Array.isArray(data) ? data : (data?.results ?? data?.data ?? []))
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [minutes])

  useEffect(() => { if (alive !== false) load() }, [alive, load])

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Time range selector */}
      <div className="flex items-center gap-2">
        <Clock className="w-3.5 h-3.5 text-on-surface-variant/50" />
        <span className="text-xs text-on-surface-variant/60">Last</span>
        {([15, 30, 60, 120] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMinutes(m); load(m) }}
            className={cn(
              "text-xs px-2 py-1 rounded-lg transition-colors",
              minutes === m
                ? "bg-primary/10 text-primary font-medium"
                : "text-on-surface-variant/60 hover:text-on-surface"
            )}
          >
            {m < 60 ? `${m}m` : `${m / 60}h`}
          </button>
        ))}
        <button
          onClick={() => load(minutes)}
          className="ml-auto p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Items */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-10">
            <Monitor className="w-8 h-8 text-on-surface-variant/20 mx-auto mb-2" />
            <p className="text-xs text-on-surface-variant/40">No recent activity captured</p>
          </div>
        ) : (
          items.map((item, i) => <ItemCard key={item.id ?? i} item={item} />)
        )}
      </div>
    </div>
  )
}

// ── SearchTab ─────────────────────────────────────────────────────────────────

function SearchTab({ alive }: { alive: boolean | null }) {
  const [query, setQuery]       = useState('')
  const [type, setType]         = useState<'all' | 'ocr' | 'audio'>('all')
  const [items, setItems]       = useState<ScreenpipeItem[]>([])
  const [loading, setLoading]   = useState(false)
  const [searched, setSearched] = useState(false)

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const res = await api.get(
        `/api/screenpipe/search?q=${encodeURIComponent(query)}&limit=30&content_type=${type}`
      )
      const data = res.data
      setItems(Array.isArray(data) ? data : (data?.results ?? data?.data ?? []))
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-on-surface-variant/40" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder="Search screen history…"
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-container border border-outline-variant/20 rounded-lg outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
          />
        </div>
        <button
          onClick={search}
          disabled={loading || !query.trim() || alive === false}
          className="px-3 text-xs bg-primary text-on-primary rounded-lg hover:bg-primary/90 disabled:opacity-40 transition-colors"
        >
          {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Search'}
        </button>
      </div>

      {/* Type filter */}
      <div className="flex gap-1">
        {(['all', 'ocr', 'audio'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={cn(
              "text-xs px-2.5 py-1 rounded-lg capitalize transition-colors",
              type === t
                ? "bg-primary/10 text-primary font-medium"
                : "text-on-surface-variant/60 hover:text-on-surface"
            )}
          >
            {t === 'all' ? 'All types' : t === 'ocr' ? 'Screen text' : 'Audio'}
          </button>
        ))}
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : !searched ? (
          <div className="text-center py-10">
            <Search className="w-8 h-8 text-on-surface-variant/20 mx-auto mb-2" />
            <p className="text-xs text-on-surface-variant/40">Search your screen history</p>
          </div>
        ) : items.length === 0 ? (
          <p className="text-center text-xs text-on-surface-variant/40 py-10">No results found</p>
        ) : (
          items.map((item, i) => <ItemCard key={item.id ?? i} item={item} />)
        )}
      </div>
    </div>
  )
}

// ── TimelineTab ───────────────────────────────────────────────────────────────

interface TimelineWindow {
  id: string
  window_start: string
  window_end: string
  apps: string[]
  highlights: string[]
  item_count: number
  word_count: number
}

function TimelineTab() {
  const [windows, setWindows] = useState<TimelineWindow[]>([])
  const [loading, setLoading] = useState(true)
  const [snapping, setSnapping] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/screen/timeline/today')
      setWindows(Array.isArray(res.data) ? res.data : [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const snapshot = async () => {
    setSnapping(true)
    try {
      await api.post('/api/screen/timeline/snapshot?minutes=30')
      load()
    } catch { /* ignore */ } finally {
      setSnapping(false)
    }
  }

  function fmtTime(iso: string) {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Controls */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-on-surface-variant/60">Today's activity</span>
        <button
          onClick={snapshot}
          disabled={snapping}
          className="ml-auto flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors"
        >
          {snapping ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
          Capture now
        </button>
        <button onClick={load} className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors">
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Timeline list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : windows.length === 0 ? (
          <div className="text-center py-10">
            <BarChart2 className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No activity captured yet</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">
              The monitor captures a snapshot every 30 min. Hit "Capture now" to start.
            </p>
          </div>
        ) : (
          windows.map((w) => (
            <div key={w.id} className="bg-surface-container rounded-xl p-3 space-y-2">
              {/* Time range */}
              <div className="flex items-center gap-2">
                <Clock className="w-3.5 h-3.5 text-primary/60 flex-shrink-0" />
                <span className="text-xs font-medium text-on-surface">
                  {fmtTime(w.window_start)} – {fmtTime(w.window_end)}
                </span>
                <span className="ml-auto text-xs text-on-surface-variant/40">
                  {w.item_count} captures · {w.word_count} words
                </span>
              </div>

              {/* Apps used */}
              {w.apps.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {w.apps.slice(0, 6).map((app, i) => (
                    <span key={i} className="text-xs bg-surface px-2 py-0.5 rounded-full text-on-surface-variant/70 border border-outline-variant/20">
                      {app}
                    </span>
                  ))}
                  {w.apps.length > 6 && (
                    <span className="text-xs text-on-surface-variant/40">+{w.apps.length - 6}</span>
                  )}
                </div>
              )}

              {/* Highlights */}
              {w.highlights.length > 0 && (
                <div className="space-y-1 border-t border-outline-variant/10 pt-2">
                  {w.highlights.slice(0, 2).map((h, i) => (
                    <p key={i} className="text-xs text-on-surface-variant/60 leading-relaxed line-clamp-2 italic">
                      "{h}"
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ── ScreenPanel ───────────────────────────────────────────────────────────────

export function ScreenPanel() {
  const [tab, setTab]   = useState<'recent' | 'search' | 'timeline'>('recent')
  const [alive, setAlive] = useState<boolean | null>(null)

  useEffect(() => {
    api.get('/api/screenpipe/status')
      .then((r) => setAlive(r.data?.available ?? true))
      .catch(() => setAlive(false))
  }, [])

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Monitor className="w-4 h-4 text-on-surface-variant" />
        <span className="text-sm font-semibold text-on-surface">Screen Activity</span>
        <div className={cn(
          "ml-auto w-2 h-2 rounded-full",
          alive === null ? "bg-on-surface-variant/30" : alive ? "bg-success" : "bg-error/60"
        )} />
        <span className="text-xs text-on-surface-variant/40">
          {alive === null ? '…' : alive ? 'Connected' : 'Offline'}
        </span>
      </div>

      <StatusBanner alive={alive} />

      {/* Sub-tabs */}
      <div className="flex gap-1 bg-surface-container-low rounded-xl p-1 flex-shrink-0">
        {(['recent', 'search', 'timeline'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "flex-1 text-xs py-1.5 rounded-lg capitalize transition-colors",
              tab === t
                ? "bg-surface text-on-surface font-medium shadow-sm"
                : "text-on-surface-variant/60 hover:text-on-surface"
            )}
          >
            {t === 'recent' ? 'Recent' : t === 'search' ? 'Search' : 'Timeline'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0">
        {tab === 'recent'   && <RecentTab alive={alive} />}
        {tab === 'search'   && <SearchTab alive={alive} />}
        {tab === 'timeline' && <TimelineTab />}
      </div>
    </div>
  )
}
