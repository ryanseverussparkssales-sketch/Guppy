/**
 * FilesPanel — File browser backed by /api/files/browse
 *
 * Navigable directory tree with breadcrumb trail.
 * Click a directory to enter, click a file to preview it.
 *
 * API:
 *   GET  /api/files/browse?path=&pattern=*
 *   POST /api/files/read  { path, max_chars }
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Folder, FolderOpen, ChevronRight, ArrowLeft,
  RefreshCw, Eye, X, HardDrive, FileText, FileCode,
  FileSpreadsheet, FileImage, Film, Music, Package,
  File as FileIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface FileEntry {
  name: string
  path: string
  type: 'dir' | 'file'   // from backend: "dir" or "file"
  size?: string           // already human-readable: "1.2 MB"
  size_bytes?: number
  modified?: string       // relative: "2 hours ago"
  extension?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────


const ROOTS = [
  { path: 'C:/', label: 'C: Drive', sub: 'System' },
  { path: 'D:/', label: 'D: Drive', sub: 'Data' },
  { path: 'E:/', label: 'E: Drive', sub: 'Extra' },
  { path: '~',   label: 'Home',     sub: 'User folder' },
]

const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'py', 'ts', 'tsx', 'js', 'jsx', 'json', 'yaml', 'yml',
  'toml', 'ini', 'cfg', 'sh', 'bat', 'ps1', 'html', 'css', 'sql',
  'csv', 'log', 'xml', 'rst', 'env',
])

function isReadable(ext?: string) {
  // Backend returns extension with leading dot e.g. ".py" — strip it
  return ext ? TEXT_EXTENSIONS.has(ext.toLowerCase().replace(/^\./, '')) : false
}

function FileTypeIcon({ ext, className }: { ext?: string; className?: string }) {
  const e = (ext || '').toLowerCase().replace('.', '')
  const cls = cn('shrink-0', className)
  if (['py', 'ts', 'tsx', 'js', 'jsx', 'sh', 'bat', 'ps1', 'html', 'css', 'sql', 'json', 'yaml', 'toml'].includes(e))
    return <FileCode className={cn(cls, 'text-blue-400/80')} />
  if (['txt', 'md', 'log', 'rst', 'env', 'ini', 'cfg'].includes(e))
    return <FileText className={cn(cls, 'text-on-surface-variant/60')} />
  if (['csv', 'xlsx', 'xls'].includes(e))
    return <FileSpreadsheet className={cn(cls, 'text-emerald-400/80')} />
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'].includes(e))
    return <FileImage className={cn(cls, 'text-violet-400/80')} />
  if (['mp4', 'mkv', 'avi', 'mov', 'webm'].includes(e))
    return <Film className={cn(cls, 'text-orange-400/80')} />
  if (['mp3', 'wav', 'flac', 'ogg', 'm4a'].includes(e))
    return <Music className={cn(cls, 'text-pink-400/80')} />
  if (['zip', 'tar', 'gz', 'rar', '7z'].includes(e))
    return <Package className={cn(cls, 'text-amber-400/80')} />
  return <FileIcon className={cn(cls, 'text-on-surface-variant/40')} />
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────

function Breadcrumb({ path, onNavigate }: { path: string; onNavigate: (p: string) => void }) {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean)
  const crumbs: { label: string; path: string }[] = []
  let acc = ''
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p
    crumbs.push({ label: p, path: acc.endsWith(':') ? acc + '/' : acc })
  }

  return (
    <div className="flex items-center gap-1 text-xs flex-wrap min-w-0">
      <button
        onClick={() => onNavigate('')}
        className="text-on-surface-variant/50 hover:text-primary transition-colors shrink-0"
        title="Drive root"
      >
        <HardDrive className="w-3.5 h-3.5" />
      </button>
      {crumbs.map((c, i) => (
        <span key={i} className="flex items-center gap-1 min-w-0">
          <ChevronRight className="w-3 h-3 text-on-surface-variant/25 shrink-0" />
          <button
            onClick={() => onNavigate(c.path)}
            className={cn(
              'transition-colors truncate max-w-[100px]',
              i === crumbs.length - 1
                ? 'text-on-surface font-medium'
                : 'text-on-surface-variant/50 hover:text-primary'
            )}
          >
            {c.label}
          </button>
        </span>
      ))}
    </div>
  )
}

// ── FilePreview ───────────────────────────────────────────────────────────────

function FilePreview({ path, onClose }: { path: string; onClose: () => void }) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    api.post('/api/files/read', { path, max_chars: 20000 })
      .then((r) => setContent(typeof r.data === 'string' ? r.data : (r.data?.text ?? JSON.stringify(r.data, null, 2))))
      .catch((e) => setError(e?.response?.data?.detail ?? 'Could not read file'))
      .finally(() => setLoading(false))
  }, [path])

  const filename = path.split(/[\\/]/).pop() ?? path
  const ext = filename.includes('.') ? filename.split('.').pop() : undefined

  return (
    <div className="absolute inset-0 bg-surface z-10 flex flex-col rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/20 flex-shrink-0 bg-surface-container-low">
        <FileTypeIcon ext={ext} className="w-4 h-4" />
        <span className="text-sm font-medium text-on-surface flex-1 truncate">{filename}</span>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/50 hover:text-on-surface transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 bg-surface-container/30">
        {loading ? (
          <div className="flex items-center justify-center h-full gap-2 text-on-surface-variant/50">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span className="text-sm">Loading…</span>
          </div>
        ) : error ? (
          <p className="text-sm text-error/70 bg-error/5 rounded-lg px-4 py-3">{error}</p>
        ) : (
          <pre className="text-xs font-mono text-on-surface/80 whitespace-pre-wrap leading-relaxed">
            {content}
          </pre>
        )}
      </div>
    </div>
  )
}

// ── FilesPanel ────────────────────────────────────────────────────────────────

export function FilesPanel() {
  const [currentPath, setCurrentPath] = useState('')
  const [entries, setEntries]         = useState<FileEntry[]>([])
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState<string | null>(null)
  const [previewPath, setPreviewPath] = useState<string | null>(null)
  const [pattern, setPattern]         = useState('*')
  const [hoveredRoot, setHoveredRoot] = useState<string | null>(null)

  const browse = useCallback(async (p: string, pat = pattern) => {
    if (!p) { setCurrentPath(''); setEntries([]); setError(null); return }
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(
        `/api/files/browse?path=${encodeURIComponent(p)}&pattern=${encodeURIComponent(pat)}`
      )
      const data = res.data
      // Backend returns { path: "/resolved/abs/path", entries: [...] }
      // Each entry has name but no path — construct full path from resolved parent
      const resolvedParent = (data?.path || p).replace(/\\/g, '/')
      const rawEntries: any[] = Array.isArray(data) ? data : (data?.entries ?? data?.files ?? [])
      const list: FileEntry[] = rawEntries.map((e) => ({
        ...e,
        path: resolvedParent.replace(/\/$/, '') + '/' + e.name,
      }))
      setEntries(list)
      setCurrentPath(resolvedParent)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Could not browse directory')
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [pattern])

  const navigate = (p: string) => {
    setPreviewPath(null)
    browse(p)
  }

  const goUp = () => {
    // currentPath is already normalized to forward slashes after browse()
    const parts = currentPath.split('/').filter(Boolean)
    if (parts.length <= 1) { navigate(''); return }
    // Preserve drive letter: "C:" becomes "C:/"
    const parent = parts.slice(0, -1).join('/')
    navigate(parent.match(/^[A-Za-z]:$/) ? parent + '/' : parent)
  }

  const dirs  = entries.filter((e) => e.type === 'dir')
  const files = entries.filter((e) => e.type === 'file')

  return (
    <div className="relative flex flex-col h-full">
      {previewPath && (
        <FilePreview path={previewPath} onClose={() => setPreviewPath(null)} />
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/15 flex-shrink-0">
        {currentPath && (
          <button
            onClick={goUp}
            className="p-1.5 rounded-lg hover:bg-surface-container text-on-surface-variant/60 hover:text-on-surface transition-colors shrink-0"
            title="Go up"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        )}
        <div className="flex-1 min-w-0">
          {currentPath ? (
            <Breadcrumb path={currentPath} onNavigate={navigate} />
          ) : (
            <span className="text-xs text-on-surface-variant/50 font-medium">Choose a drive or folder</span>
          )}
        </div>
        {currentPath && (
          <button
            onClick={() => browse(currentPath)}
            className="p-1.5 rounded-lg hover:bg-surface-container text-on-surface-variant/40 hover:text-on-surface transition-colors shrink-0"
            title="Refresh"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
          </button>
        )}
      </div>

      {/* Pattern filter chips */}
      {currentPath && (
        <div className="flex gap-1 flex-wrap px-4 py-2 border-b border-outline-variant/10 flex-shrink-0">
          {(['*', '*.py', '*.ts', '*.md', '*.csv', '*.txt', '*.json'] as const).map((p) => (
            <button
              key={p}
              onClick={() => { setPattern(p); browse(currentPath, p) }}
              className={cn(
                'text-xs px-2.5 py-0.5 rounded-full transition-colors border font-mono',
                pattern === p
                  ? 'bg-primary/12 text-primary border-primary/25'
                  : 'text-on-surface-variant/50 border-outline-variant/20 hover:border-primary/20 hover:text-on-surface'
              )}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0 p-4">
        {error && (
          <div className="flex items-center gap-2 text-sm text-error bg-error/8 border border-error/15 rounded-xl px-4 py-3 mb-3">
            <X className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {!currentPath ? (
          /* Drive root selector */
          <div className="grid grid-cols-2 gap-3">
            {ROOTS.map((root) => (
              <button
                key={root.path}
                onClick={() => navigate(root.path)}
                onMouseEnter={() => setHoveredRoot(root.path)}
                onMouseLeave={() => setHoveredRoot(null)}
                className={cn(
                  'flex items-center gap-3 rounded-xl p-4 border transition-all text-left',
                  hoveredRoot === root.path
                    ? 'bg-primary/8 border-primary/25 shadow-sm'
                    : 'bg-surface-container border-outline-variant/15 hover:border-outline-variant/30'
                )}
              >
                <div className={cn(
                  'w-10 h-10 rounded-lg flex items-center justify-center transition-colors shrink-0',
                  hoveredRoot === root.path ? 'bg-primary/15' : 'bg-surface-container-high'
                )}>
                  <HardDrive className={cn('w-5 h-5', hoveredRoot === root.path ? 'text-primary' : 'text-on-surface-variant/60')} />
                </div>
                <div>
                  <p className="text-sm font-medium text-on-surface">{root.label}</p>
                  <p className="text-xs text-on-surface-variant/50">{root.sub}</p>
                </div>
              </button>
            ))}
          </div>
        ) : loading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-on-surface-variant/50">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span className="text-sm">Loading…</span>
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-on-surface-variant/40">
            <FolderOpen className="w-8 h-8" />
            <span className="text-sm">Empty directory</span>
          </div>
        ) : (
          <div className="space-y-0.5">
            {/* Directories */}
            {dirs.map((e) => (
              <button
                key={e.path}
                onClick={() => navigate(e.path)}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface-container transition-colors text-left group"
              >
                <Folder className="w-4 h-4 text-primary/50 group-hover:text-primary/80 transition-colors shrink-0" />
                <span className="text-sm text-on-surface flex-1 truncate">{e.name}</span>
                {e.modified && <span className="text-xs text-on-surface-variant/35 shrink-0 hidden sm:block">{e.modified}</span>}
                <ChevronRight className="w-3.5 h-3.5 text-on-surface-variant/25 shrink-0" />
              </button>
            ))}

            {/* Divider between dirs and files */}
            {dirs.length > 0 && files.length > 0 && (
              <div className="border-t border-outline-variant/10 my-1" />
            )}

            {/* Files */}
            {files.map((e) => {
              const readable = isReadable(e.extension)
              return (
                <div
                  key={e.path}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface-container transition-colors group"
                >
                  <FileTypeIcon ext={e.extension} className="w-4 h-4" />
                  <span className="text-sm text-on-surface flex-1 truncate">{e.name}</span>
                  {e.modified && <span className="text-xs text-on-surface-variant/35 shrink-0 hidden sm:block">{e.modified}</span>}
                  {e.size && (
                    <span className="text-xs text-on-surface-variant/40 shrink-0 font-mono">{e.size}</span>
                  )}
                  {readable && (
                    <button
                      onClick={() => setPreviewPath(e.path)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-primary/10 text-on-surface-variant/50 hover:text-primary transition-all shrink-0"
                      title="Preview"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
