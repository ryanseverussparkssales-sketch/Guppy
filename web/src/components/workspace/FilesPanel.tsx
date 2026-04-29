/**
 * FilesPanel — File browser backed by /api/files/browse
 *
 * Navigable directory tree with breadcrumb trail.
 * Click a directory to enter, click a file to read it in a preview pane.
 *
 * API:
 *   GET  /api/files/browse?path=&pattern=*
 *   POST /api/files/read  { path, max_chars }
 *   GET  /api/files/info?path=
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Folder, FolderOpen, File, ChevronRight, ArrowLeft,
  RefreshCw, Eye, X, HardDrive,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  size?: number
  modified?: string
  extension?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtSize(bytes?: number) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

const ROOTS = ['C:/', 'D:/', 'E:/', '~']

const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'py', 'ts', 'tsx', 'js', 'jsx', 'json', 'yaml', 'yml',
  'toml', 'ini', 'cfg', 'sh', 'bat', 'ps1', 'html', 'css', 'sql',
  'csv', 'log', 'xml', 'rst', 'env',
])

function isReadable(ext?: string) {
  return ext ? TEXT_EXTENSIONS.has(ext.toLowerCase().replace('.', '')) : false
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────

function Breadcrumb({ path, onNavigate }: { path: string; onNavigate: (p: string) => void }) {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean)
  const crumbs: { label: string; path: string }[] = []
  let acc = ''
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p
    // handle drive letter e.g. "C:"
    crumbs.push({ label: p, path: acc.endsWith(':') ? acc + '/' : acc })
  }

  return (
    <div className="flex items-center gap-1 text-xs flex-wrap">
      <button
        onClick={() => onNavigate('')}
        className="text-on-surface-variant/60 hover:text-primary transition-colors"
      >
        <HardDrive className="w-3.5 h-3.5" />
      </button>
      {crumbs.map((c, i) => (
        <span key={i} className="flex items-center gap-1">
          <ChevronRight className="w-3 h-3 text-on-surface-variant/30" />
          <button
            onClick={() => onNavigate(c.path)}
            className={cn(
              "transition-colors truncate max-w-[120px]",
              i === crumbs.length - 1
                ? "text-on-surface font-medium"
                : "text-on-surface-variant/60 hover:text-primary"
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

  return (
    <div className="absolute inset-0 bg-surface z-10 flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-outline-variant/20 flex-shrink-0">
        <File className="w-4 h-4 text-on-surface-variant" />
        <span className="text-xs font-medium text-on-surface flex-1 truncate">{filename}</span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 hover:text-on-surface transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : error ? (
          <p className="text-xs text-error/70">{error}</p>
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

  const browse = useCallback(async (p: string, pat = pattern) => {
    if (!p) { setCurrentPath(''); setEntries([]); setError(null); return }
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(
        `/api/files/browse?path=${encodeURIComponent(p)}&pattern=${encodeURIComponent(pat)}`
      )
      const data = res.data
      // normalize: API may return { entries: [] } or []
      const list: FileEntry[] = Array.isArray(data) ? data : (data?.entries ?? data?.files ?? [])
      setEntries(list)
      setCurrentPath(p)
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
    const norm = currentPath.replace(/\\/g, '/')
    const parent = norm.split('/').slice(0, -1).join('/')
    navigate(parent || '')
  }

  const dirs  = entries.filter((e) => e.is_dir)
  const files = entries.filter((e) => !e.is_dir)

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {/* Preview overlay */}
      {previewPath && (
        <FilePreview path={previewPath} onClose={() => setPreviewPath(null)} />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {currentPath && (
          <button
            onClick={goUp}
            className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/50 hover:text-on-surface transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        )}
        <div className="flex-1 min-w-0">
          {currentPath ? (
            <Breadcrumb path={currentPath} onNavigate={navigate} />
          ) : (
            <span className="text-xs text-on-surface-variant/60">Select a drive or folder</span>
          )}
        </div>
        {currentPath && (
          <button
            onClick={() => browse(currentPath)}
            className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          </button>
        )}
      </div>

      {/* Pattern filter */}
      {currentPath && (
        <div className="flex gap-1 flex-wrap flex-shrink-0">
          {(['*', '*.py', '*.ts', '*.md', '*.pdf', '*.txt'] as const).map((p) => (
            <button
              key={p}
              onClick={() => { setPattern(p); browse(currentPath, p) }}
              className={cn(
                "text-xs px-2 py-0.5 rounded-full transition-colors border",
                pattern === p
                  ? "bg-primary/10 text-primary border-primary/20"
                  : "text-on-surface-variant/50 border-outline-variant/20 hover:border-primary/20 hover:text-on-surface"
              )}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Roots or directory listing */}
      <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
        {error && (
          <p className="text-xs text-error/70 bg-error/5 rounded-lg px-3 py-2 mb-2">{error}</p>
        )}

        {!currentPath ? (
          /* Root selector */
          <div className="grid grid-cols-2 gap-2">
            {ROOTS.map((root) => (
              <button
                key={root}
                onClick={() => navigate(root)}
                className="flex flex-col items-center gap-2 bg-surface-container rounded-xl p-4 hover:bg-surface-container-high transition-colors"
              >
                <HardDrive className="w-8 h-8 text-on-surface-variant/50" />
                <span className="text-xs font-medium text-on-surface">{root}</span>
              </button>
            ))}
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : entries.length === 0 ? (
          <p className="text-center text-xs text-on-surface-variant/40 py-10">Empty directory</p>
        ) : (
          <div className="space-y-0.5">
            {/* Directories first */}
            {dirs.map((e) => (
              <button
                key={e.path}
                onClick={() => navigate(e.path)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-container transition-colors text-left"
              >
                <Folder className="w-4 h-4 text-primary/60 flex-shrink-0" />
                <span className="text-xs text-on-surface flex-1 truncate">{e.name}</span>
                <ChevronRight className="w-3 h-3 text-on-surface-variant/30 flex-shrink-0" />
              </button>
            ))}

            {/* Files */}
            {files.map((e) => {
              const readable = isReadable(e.extension)
              return (
                <div
                  key={e.path}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-container transition-colors group"
                >
                  <File className="w-4 h-4 text-on-surface-variant/40 flex-shrink-0" />
                  <span className="text-xs text-on-surface flex-1 truncate">{e.name}</span>
                  {e.size !== undefined && (
                    <span className="text-xs text-on-surface-variant/40 flex-shrink-0">{fmtSize(e.size)}</span>
                  )}
                  {readable && (
                    <button
                      onClick={() => setPreviewPath(e.path)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-primary/10 text-on-surface-variant/40 hover:text-primary transition-all"
                      title="Preview file"
                    >
                      <Eye className="w-3 h-3" />
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
