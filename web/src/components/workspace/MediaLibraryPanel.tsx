/**
 * MediaLibraryPanel — qBittorrent torrents + media catalog + book acquisition
 *
 * Sub-tabs:
 *   Torrents  — qBittorrent proxy: list, add magnet/URL, pause/resume/remove
 *   Library   — local media catalog (movies, music, podcasts) + Calibre books link
 *   Acquire   — LazyLibrarian + Prowlarr acquisition queue
 *   Record    — call/meeting recording upload + Whisper transcription
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Download, Library, Mic, Search, Plus, RefreshCw, Play, Pause,
  Trash2, AlertCircle, CheckCircle2, BookOpen, Film, Music,
  Headphones, Upload, FileAudio,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Torrent {
  hash: string
  name: string
  state: string
  progress: number
  size_bytes: number
  dl_speed: number
  ul_speed: number
  eta: number
  num_seeds: number
  category: string
}

interface MediaItem {
  id: string
  title: string
  type: string
  year?: number
  genre: string
  description: string
  tags: string[]
}

interface Recording {
  id: string
  title: string
  source_type: string
  file_size: number
  transcript_status: string
  recorded_at: string
}

interface ProwlarrResult {
  title?: string
  Title?: string
  size?: number
  seeders?: number
  indexer?: string
  downloadUrl?: string
  magnetUrl?: string
}

type Tab = 'torrents' | 'library' | 'acquire' | 'record'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtBytes(b: number) {
  if (b === 0) return '0 B'
  const k = 1024
  const sz = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(b) / Math.log(k))
  return `${(b / Math.pow(k, i)).toFixed(1)} ${sz[i]}`
}

function fmtSpeed(bps: number) {
  if (bps < 1024) return `${bps} B/s`
  return `${(bps / 1024).toFixed(0)} KB/s`
}

function fmtEta(s: number) {
  if (s < 0 || s > 86400 * 7) return '∞'
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m`
  return `${Math.floor(s / 3600)}h`
}

const STATE_COLOR: Record<string, string> = {
  downloading: 'text-primary',
  uploading:   'text-success',
  pausedDL:    'text-on-surface-variant/50',
  pausedUP:    'text-on-surface-variant/50',
  stalledDL:   'text-warning',
  error:       'text-error',
  checkingDL:  'text-secondary',
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  movie:   <Film     className="w-3.5 h-3.5" />,
  music:   <Music    className="w-3.5 h-3.5" />,
  podcast: <Headphones className="w-3.5 h-3.5" />,
  book:    <BookOpen  className="w-3.5 h-3.5" />,
  other:   <Library   className="w-3.5 h-3.5" />,
}

// ── TorrentsTab ───────────────────────────────────────────────────────────────

function TorrentsTab() {
  const [torrents, setTorrents] = useState<Torrent[]>([])
  const [loading,  setLoading]  = useState(true)
  const [alive,    setAlive]    = useState<boolean | null>(null)
  const [addUrl,   setAddUrl]   = useState('')
  const [adding,   setAdding]   = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusRes, torrentRes] = await Promise.all([
        api.get('/api/media/status'),
        api.get('/api/media/torrents'),
      ])
      setAlive(statusRes.data?.qbittorrent_available ?? false)
      setTorrents(Array.isArray(torrentRes.data) ? torrentRes.data : [])
    } catch { setAlive(false) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const addTorrent = async () => {
    if (!addUrl.trim()) return
    setAdding(true)
    try {
      await api.post('/api/media/torrents', { url: addUrl.trim() })
      setAddUrl('')
      setTimeout(load, 1500)
    } catch { /* ignore */ } finally { setAdding(false) }
  }

  const pause  = (hash: string) => api.post(`/api/media/torrents/${hash}/pause`).then(load)
  const resume = (hash: string) => api.post(`/api/media/torrents/${hash}/resume`).then(load)
  const remove = (hash: string) => api.delete(`/api/media/torrents/${hash}`).then(load)

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Add torrent */}
      <div className="flex gap-2 flex-shrink-0">
        <input
          className="flex-1 bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
          placeholder="Magnet link or .torrent URL…"
          value={addUrl} onChange={(e) => setAddUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addTorrent()}
        />
        <button onClick={addTorrent} disabled={adding || !addUrl.trim()}
          className="px-3 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium flex-shrink-0">
          {adding ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
        </button>
        <button onClick={load} className="p-2 rounded-xl hover:bg-surface-variant text-on-surface-variant/40">
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Status */}
      {alive === false && (
        <div className="flex items-center gap-2 bg-warning/5 rounded-xl px-3 py-2 border border-warning/15 flex-shrink-0">
          <AlertCircle className="w-4 h-4 text-warning/70" />
          <p className="text-xs text-on-surface/70">
            qBittorrent not running. Start it and set <span className="font-mono">QBITTORRENT_URL</span> if not on localhost:8080.
          </p>
        </div>
      )}

      {/* Torrent list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading && torrents.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : torrents.length === 0 ? (
          <div className="text-center py-10">
            <Download className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No active torrents</p>
          </div>
        ) : torrents.map((t) => (
          <div key={t.hash} className="bg-surface-container rounded-xl p-3 space-y-2">
            <div className="flex items-start gap-2">
              <Download className="w-3.5 h-3.5 text-on-surface-variant/40 flex-shrink-0 mt-0.5" />
              <p className="text-xs font-medium text-on-surface flex-1 leading-snug">{t.name}</p>
              <div className="flex items-center gap-1 flex-shrink-0">
                {t.state.includes('paused') ? (
                  <button onClick={() => resume(t.hash)} className="p-1 rounded hover:bg-primary/10 text-on-surface-variant/40 hover:text-primary transition-colors">
                    <Play className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button onClick={() => pause(t.hash)} className="p-1 rounded hover:bg-warning/10 text-on-surface-variant/40 hover:text-warning transition-colors">
                    <Pause className="w-3.5 h-3.5" />
                  </button>
                )}
                <button onClick={() => remove(t.hash)} className="p-1 rounded hover:bg-error/10 text-on-surface-variant/40 hover:text-error transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            {/* Progress bar */}
            <div className="space-y-1">
              <div className="h-1.5 bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${t.progress}%` }} />
              </div>
              <div className="flex items-center justify-between text-[10px] text-on-surface-variant/50">
                <span className={STATE_COLOR[t.state] || 'text-on-surface-variant/50'}>{t.state}</span>
                <span>{t.progress}% of {fmtBytes(t.size_bytes)}</span>
                {t.dl_speed > 0 && <span>↓ {fmtSpeed(t.dl_speed)}</span>}
                {t.eta > 0 && <span>ETA {fmtEta(t.eta)}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── LibraryTab ────────────────────────────────────────────────────────────────

function LibraryTab() {
  const [items,   setItems]   = useState<MediaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [type,    setType]    = useState('')
  const [search,  setSearch]  = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newType,  setNewType]  = useState('movie')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '200' })
      if (type)   params.set('type', type)
      if (search) params.set('search', search)
      const r = await api.get(`/api/media/items?${params}`)
      setItems(Array.isArray(r.data) ? r.data : [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [type, search])

  useEffect(() => { load() }, [load])

  const addItem = async () => {
    if (!newTitle.trim()) return
    await api.post('/api/media/items', { title: newTitle, type: newType }).catch(() => {})
    setNewTitle(''); setAddOpen(false); load()
  }

  const TYPES = [
    { id: '', label: 'All' },
    { id: 'movie',   label: 'Movies' },
    { id: 'music',   label: 'Music' },
    { id: 'podcast', label: 'Podcasts' },
    { id: 'other',   label: 'Other' },
  ]

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-on-surface-variant/40" />
          <input className="w-full bg-surface-container rounded-xl pl-8 pr-3 py-2 text-xs text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none"
            placeholder="Search media…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <button onClick={() => setAddOpen(!addOpen)}
          className="p-2 rounded-xl bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
          <Plus className="w-3.5 h-3.5" />
        </button>
        <button onClick={load} className="p-2 rounded-xl hover:bg-surface-variant text-on-surface-variant/40">
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {addOpen && (
        <div className="flex gap-2 flex-shrink-0">
          <input className="flex-1 bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none"
            placeholder="Title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <select value={newType} onChange={(e) => setNewType(e.target.value)}
            className="bg-surface-container rounded-xl px-2 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none">
            <option value="movie">Movie</option>
            <option value="music">Music</option>
            <option value="podcast">Podcast</option>
            <option value="other">Other</option>
          </select>
          <button onClick={addItem} className="px-3 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
            Add
          </button>
        </div>
      )}

      {/* Type filter */}
      <div className="flex gap-1 flex-shrink-0">
        {TYPES.map((t) => (
          <button key={t.id} onClick={() => setType(t.id)}
            className={cn("text-xs px-2.5 py-1 rounded-lg transition-colors",
              type === t.id ? "bg-primary/10 text-primary font-medium" : "text-on-surface-variant/50 hover:text-on-surface")}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Items grid */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-10">
            <Library className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">
              {search || type ? 'No matching items' : 'No media in catalog'}
            </p>
            <p className="text-xs text-on-surface-variant/30 mt-1">
              Also see Calibre at <span className="font-mono">/api/calibre/search</span> for books
            </p>
          </div>
        ) : items.map((item) => (
          <div key={item.id} className="flex items-center gap-3 bg-surface-container rounded-xl px-3 py-2.5">
            <div className="text-on-surface-variant/50">{TYPE_ICON[item.type] || TYPE_ICON.other}</div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-on-surface truncate">{item.title}</p>
              <p className="text-[10px] text-on-surface-variant/40">
                {item.type}{item.year ? ` · ${item.year}` : ''}{item.genre ? ` · ${item.genre}` : ''}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── AcquireTab ────────────────────────────────────────────────────────────────

function AcquireTab() {
  const [query,   setQuery]   = useState('')
  const [results, setResults] = useState<ProwlarrResult[]>([])
  const [loading, setLoading] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [status,  setStatus]  = useState<Record<string, any> | null>(null)

  useEffect(() => {
    api.get('/api/acquisition/status').then((r) => setStatus(r.data)).catch(() => {})
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const r = await api.get(`/api/acquisition/prowlarr/search?q=${encodeURIComponent(query)}&limit=20`)
      setResults(Array.isArray(r.data) ? r.data : [])
    } catch { setResults([]) } finally { setLoading(false) }
  }

  const llAlive   = (status as Record<string, Record<string, unknown>> | null)?.lazylibrarian?.available
  const prowlAlive = (status as Record<string, Record<string, unknown>> | null)?.prowlarr?.available

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Status */}
      <div className="flex gap-2 flex-shrink-0">
        <div className={cn("flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg",
          llAlive ? "bg-success/10 text-success" : "bg-surface-container text-on-surface-variant/50")}>
          <div className={cn("w-1.5 h-1.5 rounded-full", llAlive ? "bg-success" : "bg-on-surface-variant/30")} />
          LazyLibrarian
        </div>
        <div className={cn("flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg",
          prowlAlive ? "bg-success/10 text-success" : "bg-surface-container text-on-surface-variant/50")}>
          <div className={cn("w-1.5 h-1.5 rounded-full", prowlAlive ? "bg-success" : "bg-on-surface-variant/30")} />
          Prowlarr
        </div>
      </div>

      {/* Search */}
      <div className="flex gap-2 flex-shrink-0">
        <input className="flex-1 bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none"
          placeholder="Search across all indexers…"
          value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()} />
        <button onClick={search} disabled={loading || !prowlAlive}
          className="px-3 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium">
          {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
        </button>
      </div>

      {!prowlAlive && (
        <div className="flex items-center gap-2 bg-warning/5 rounded-xl px-3 py-2 border border-warning/15 flex-shrink-0">
          <AlertCircle className="w-4 h-4 text-warning/70 flex-shrink-0" />
          <p className="text-xs text-on-surface/70">
            Prowlarr not running. Start it and set <span className="font-mono">PROWLARR_URL</span> + <span className="font-mono">PROWLARR_API_KEY</span>.
            For books use LazyLibrarian. For torrents add directly in the Torrents tab.
          </p>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {results.length === 0 ? (
          <div className="text-center py-10">
            <Search className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">Search to find content</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">Results come from Prowlarr indexers</p>
          </div>
        ) : results.map((r, i) => (
          <div key={i} className="bg-surface-container rounded-xl p-3 space-y-1">
            <p className="text-xs font-medium text-on-surface">{String(r.title || r.Title || 'Unknown')}</p>
            <div className="flex gap-3 text-[10px] text-on-surface-variant/50">
              {r.size && <span>{fmtBytes(Number(r.size))}</span>}
              {r.seeders !== undefined && <span>{String(r.seeders)} seeds</span>}
              {r.indexer && <span>{String(r.indexer)}</span>}
            </div>
            {(r.downloadUrl || r.magnetUrl) && (
              <button
                onClick={() => api.post('/api/media/torrents', { url: String(r.downloadUrl || r.magnetUrl) })}
                className="text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1">
                <Download className="w-3 h-3" /> Add torrent
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── RecordTab ─────────────────────────────────────────────────────────────────

function RecordTab() {
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [loading,    setLoading]    = useState(true)
  const [uploading,  setUploading]  = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/media/recordings')
      setRecordings(Array.isArray(r.data) ? r.data : [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const uploadFile = async (file: File) => {
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    form.append('source_type', 'call')
    form.append('title', file.name)
    try {
      await api.post('/api/media/recordings/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      load()
    } catch { /* ignore */ } finally { setUploading(false) }
  }

  const transcribe = async (id: string) => {
    await api.post(`/api/media/recordings/${id}/transcribe`).catch(() => {})
    setTimeout(load, 1000)
  }

  const TRANSCRIPT_LABEL: Record<string, string> = {
    pending:    'Not transcribed',
    processing: 'Transcribing…',
    done:       'Transcript ready',
    failed:     'Transcription failed',
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Upload area */}
      <div
        className="flex items-center justify-center gap-2 bg-surface-container border-2 border-dashed border-outline-variant/30 rounded-xl py-5 cursor-pointer hover:border-primary/30 hover:bg-primary/3 transition-colors flex-shrink-0"
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) uploadFile(f) }}
      >
        <input ref={fileRef} type="file" accept="audio/*,video/*,.mp3,.mp4,.wav,.m4a,.ogg,.webm"
          className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadFile(f) }} />
        {uploading ? (
          <RefreshCw className="w-4 h-4 animate-spin text-primary/60" />
        ) : (
          <Upload className="w-4 h-4 text-on-surface-variant/40" />
        )}
        <span className="text-xs text-on-surface-variant/50">
          {uploading ? 'Uploading…' : 'Drop recording or click to upload'}
        </span>
      </div>

      {/* Recordings list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : recordings.length === 0 ? (
          <div className="text-center py-10">
            <FileAudio className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No recordings yet</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">Upload a call or meeting recording to transcribe it</p>
          </div>
        ) : recordings.map((r) => (
          <div key={r.id} className="bg-surface-container rounded-xl p-3 space-y-2">
            <div className="flex items-start gap-2">
              <FileAudio className="w-4 h-4 text-on-surface-variant/50 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-on-surface truncate">{r.title}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={cn("text-[10px]",
                    r.transcript_status === 'done' ? 'text-success' :
                    r.transcript_status === 'processing' ? 'text-primary' :
                    r.transcript_status === 'failed' ? 'text-error' : 'text-on-surface-variant/40'
                  )}>
                    {TRANSCRIPT_LABEL[r.transcript_status] || r.transcript_status}
                  </span>
                  {r.file_size && <span className="text-[10px] text-on-surface-variant/40">{fmtBytes(r.file_size)}</span>}
                </div>
              </div>
              {r.transcript_status === 'pending' && (
                <button onClick={() => transcribe(r.id)}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-secondary/10 text-secondary hover:bg-secondary/15 transition-colors flex-shrink-0">
                  <Mic className="w-3 h-3" /> Transcribe
                </button>
              )}
              {r.transcript_status === 'processing' && (
                <RefreshCw className="w-4 h-4 animate-spin text-primary/60 flex-shrink-0" />
              )}
              {r.transcript_status === 'done' && (
                <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
              )}
            </div>
          </div>
        ))}
      </div>

      <button onClick={load} className="flex items-center justify-center gap-1.5 text-xs text-on-surface-variant/40 hover:text-on-surface transition-colors flex-shrink-0">
        <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} /> Refresh
      </button>
    </div>
  )
}

// ── MediaLibraryPanel ─────────────────────────────────────────────────────────

export function MediaLibraryPanel() {
  const [tab, setTab] = useState<Tab>('torrents')

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'torrents', label: 'Torrents', icon: <Download className="w-3.5 h-3.5" /> },
    { id: 'library',  label: 'Library',  icon: <Library  className="w-3.5 h-3.5" /> },
    { id: 'acquire',  label: 'Acquire',  icon: <Search   className="w-3.5 h-3.5" /> },
    { id: 'record',   label: 'Record',   icon: <Mic      className="w-3.5 h-3.5" /> },
  ]

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Library className="w-4 h-4 text-tertiary/70" />
        <span className="text-sm font-semibold text-on-surface">Media & Library</span>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 bg-surface-container rounded-xl p-1 flex-shrink-0">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn("flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded-lg transition-colors",
              tab === t.id ? "bg-surface text-on-surface shadow-sm font-medium" : "text-on-surface-variant/50 hover:text-on-surface")}>
            {t.icon}<span className="hidden sm:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden min-h-0">
        {tab === 'torrents' && <TorrentsTab />}
        {tab === 'library'  && <LibraryTab />}
        {tab === 'acquire'  && <AcquireTab />}
        {tab === 'record'   && <RecordTab />}
      </div>
    </div>
  )
}
