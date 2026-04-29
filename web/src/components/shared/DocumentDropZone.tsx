/**
 * DocumentDropZone — reusable drag-and-drop document upload widget
 *
 * Works in all three surfaces (Companion / Workspace / Codespace).
 * Uploads to POST /api/documents/upload with a `surface` tag.
 * Shows uploaded documents as dismissable cards with AI analysis option.
 *
 * Usage:
 *   <DocumentDropZone surface="workspace" />
 *   <DocumentDropZone surface="companion" compact />
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Upload, File, FileText, Image, FileCode, FilePdf,
  X, Sparkles, RefreshCw, Download, ChevronDown, ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface UploadedDoc {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  surface: string
  summary: string
  created_at: string
}

interface UploadState {
  name: string
  progress: 'uploading' | 'done' | 'error'
  error?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtBytes(b: number) {
  if (b === 0) return '0 B'
  const k = 1024
  const sz = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(k))
  return `${(b / Math.pow(k, i)).toFixed(1)} ${sz[i]}`
}

function FileIcon({ mime }: { mime: string }) {
  if (mime.startsWith('image/'))
    return <Image className="w-4 h-4 text-secondary/70" />
  if (mime === 'application/pdf' || mime.includes('pdf'))
    return <FileText className="w-4 h-4 text-error/70" />
  if (mime.startsWith('text/') || mime.includes('json') || mime.includes('xml'))
    return <FileCode className="w-4 h-4 text-primary/70" />
  return <File className="w-4 h-4 text-on-surface-variant/50" />
}

function relTime(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60000)
    if (m < 1)  return 'just now'
    if (m < 60) return `${m}m ago`
    return `${Math.floor(m / 60)}h ago`
  } catch { return '' }
}

// ── DocCard ───────────────────────────────────────────────────────────────────

function DocCard({ doc, onDelete, onAnalyze }: {
  doc: UploadedDoc
  onDelete: (id: string) => void
  onAnalyze: (id: string) => void
}) {
  const [expanded,  setExpanded]  = useState(false)
  const [analyzing, setAnalyzing] = useState(false)

  const analyze = async () => {
    setAnalyzing(true)
    await onAnalyze(doc.id)
    setAnalyzing(false)
  }

  return (
    <div className="bg-surface-container rounded-xl border border-outline-variant/20 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <FileIcon mime={doc.mime_type} />
        <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <p className="text-xs font-medium text-on-surface truncate">{doc.filename}</p>
          <p className="text-[10px] text-on-surface-variant/40">{fmtBytes(doc.size_bytes)} · {relTime(doc.created_at)}</p>
        </div>
        {/* AI analysis */}
        <button
          onClick={analyze}
          disabled={analyzing}
          className={cn(
            "p-1 rounded transition-colors",
            doc.summary
              ? "text-secondary/60 hover:text-secondary"
              : "text-on-surface-variant/30 hover:text-secondary"
          )}
          title={doc.summary ? "View AI summary" : "Analyze with AI"}
        >
          {analyzing
            ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            : <Sparkles className="w-3.5 h-3.5" />
          }
        </button>
        {/* Download — use api client so auth header is included */}
        <button
          onClick={async () => {
            try {
              const r = await api.get(`/api/documents/${doc.id}/download`, { responseType: 'blob' })
              const url = URL.createObjectURL(r.data)
              const a = document.createElement('a')
              a.href = url; a.download = doc.filename; a.click()
              URL.revokeObjectURL(url)
            } catch { /* ignore */ }
          }}
          className="p-1 rounded text-on-surface-variant/30 hover:text-on-surface transition-colors"
          title={`Download ${doc.filename}`}
        >
          <Download className="w-3.5 h-3.5" />
        </button>
        {/* Delete */}
        <button onClick={() => onDelete(doc.id)}
          className="p-1 rounded text-on-surface-variant/20 hover:text-error transition-colors">
          <X className="w-3.5 h-3.5" />
        </button>
        {expanded
          ? <ChevronDown  className="w-3 h-3 text-on-surface-variant/30" />
          : <ChevronRight className="w-3 h-3 text-on-surface-variant/30" />
        }
      </div>
      {expanded && doc.summary && (
        <div className="border-t border-outline-variant/10 px-3 py-2 bg-secondary/3">
          <div className="flex items-start gap-1.5">
            <Sparkles className="w-3 h-3 text-secondary/60 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-on-surface/80 leading-relaxed">{doc.summary}</p>
          </div>
        </div>
      )}
    </div>
  )
}

// ── DocumentDropZone ──────────────────────────────────────────────────────────

interface DocumentDropZoneProps {
  surface: 'companion' | 'workspace' | 'codespace'
  compact?: boolean   // compact mode: smaller drop area, fewer items shown
  className?: string
}

export function DocumentDropZone({ surface, compact = false, className }: DocumentDropZoneProps) {
  const [docs,      setDocs]      = useState<UploadedDoc[]>([])
  const [uploads,   setUploads]   = useState<UploadState[]>([])
  const [dragging,  setDragging]  = useState(false)
  const [loading,   setLoading]   = useState(true)
  const [collapsed, setCollapsed] = useState(compact)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadDocs = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.get(`/api/documents?surface=${surface}&limit=${compact ? 5 : 20}`)
      setDocs(Array.isArray(r.data) ? r.data : [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [surface, compact])

  useEffect(() => { loadDocs() }, [loadDocs])

  const uploadFiles = async (files: FileList | File[]) => {
    const fileArr = Array.from(files)
    for (const file of fileArr) {
      setUploads((u) => [...u, { name: file.name, progress: 'uploading' }])
      const form = new FormData()
      form.append('file', file)
      form.append('surface', surface)
      try {
        await api.post('/api/documents/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        setUploads((u) => u.map((x) => x.name === file.name ? { ...x, progress: 'done' } : x))
        setTimeout(() => {
          setUploads((u) => u.filter((x) => x.name !== file.name))
        }, 2000)
        loadDocs()
      } catch (e) {
        setUploads((u) => u.map((x) => x.name === file.name
          ? { ...x, progress: 'error', error: 'Upload failed' } : x))
      }
    }
  }

  const deleteDoc = async (id: string) => {
    setDocs((d) => d.filter((x) => x.id !== id))
    await api.delete(`/api/documents/${id}`).catch(() => { loadDocs() })
  }

  const analyzeDoc = async (id: string) => {
    try {
      const r = await api.post(`/api/documents/${id}/analyze`)
      if (r.data?.summary) {
        setDocs((d) => d.map((x) => x.id === id ? { ...x, summary: r.data.summary } : x))
      }
    } catch { /* ignore */ }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length > 0) uploadFiles(e.dataTransfer.files)
  }

  const recentCount = docs.length

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* Collapsible header (compact mode) */}
      {compact && (
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 text-xs text-on-surface-variant/50 hover:text-on-surface transition-colors"
        >
          <Upload className="w-3.5 h-3.5" />
          <span>Documents {recentCount > 0 ? `(${recentCount})` : ''}</span>
          {collapsed
            ? <ChevronRight className="w-3 h-3 ml-auto" />
            : <ChevronDown  className="w-3 h-3 ml-auto" />
          }
        </button>
      )}

      {!collapsed && (
        <>
          {/* Drop zone */}
          <div
            className={cn(
              "border-2 border-dashed rounded-xl transition-colors cursor-pointer",
              compact ? "py-3 px-3" : "py-5 px-4",
              dragging
                ? "border-primary bg-primary/5"
                : "border-outline-variant/30 hover:border-primary/40 hover:bg-primary/2",
            )}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
          >
            <input ref={fileRef} type="file" multiple className="hidden"
              onChange={(e) => { if (e.target.files) uploadFiles(e.target.files) }} />
            <div className="flex items-center justify-center gap-2 text-on-surface-variant/40">
              <Upload className={cn(dragging && "text-primary", compact ? "w-3.5 h-3.5" : "w-4 h-4")} />
              <span className={cn(compact ? "text-xs" : "text-sm")}>
                {dragging ? 'Drop to upload' : 'Drop files or click to upload'}
              </span>
            </div>
            {!compact && (
              <p className="text-xs text-on-surface-variant/30 text-center mt-1">
                PDF, DOCX, images, text, code — any file type
              </p>
            )}
          </div>

          {/* Active uploads */}
          {uploads.map((u, i) => (
            <div key={i} className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-xl text-xs",
              u.progress === 'uploading' ? "bg-primary/5 text-primary" :
              u.progress === 'done'      ? "bg-success/5 text-success" :
                                           "bg-error/5 text-error"
            )}>
              {u.progress === 'uploading' && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              <span className="truncate flex-1">{u.name}</span>
              <span>{u.progress === 'uploading' ? 'Uploading…' : u.progress === 'done' ? '✓' : u.error}</span>
            </div>
          ))}

          {/* Uploaded docs */}
          {loading && docs.length === 0 ? null : (
            <div className="space-y-1.5">
              {docs.map((doc) => (
                <DocCard key={doc.id} doc={doc} onDelete={deleteDoc} onAnalyze={analyzeDoc} />
              ))}
              {docs.length === 0 && !loading && !compact && (
                <p className="text-xs text-on-surface-variant/30 text-center py-2">
                  No documents uploaded yet
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
