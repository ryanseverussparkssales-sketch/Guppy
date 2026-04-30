import { useState, useEffect, useRef, useCallback } from 'react'
import { FileText, Upload, Trash2, Sparkles, Download, RefreshCw, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface Doc {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  surface: string
  summary: string
  tags: string[]
  created_at: string
}

function fmtBytes(b: number) {
  if (b === 0) return '0 B'
  const k = 1024, sz = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(k))
  return `${(b / Math.pow(k, i)).toFixed(1)} ${sz[i]}`
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const MIME_ICON: Record<string, string> = {
  'application/pdf':  '📄',
  'text/plain':       '📝',
  'application/json': '🗂️',
}

function mimeIcon(m: string) {
  if (MIME_ICON[m]) return MIME_ICON[m]
  if (m.startsWith('image/'))  return '🖼️'
  if (m.includes('word'))      return '📘'
  if (m.includes('sheet'))     return '📊'
  return '📎'
}

export function DocumentsPanel() {
  const [docs,      setDocs]     = useState<Doc[]>([])
  const [loading,   setLoading]  = useState(true)
  const [uploading, setUploading]= useState(false)
  const [analyzing, setAnalyzing]= useState<string | null>(null)
  const [preview,   setPreview]  = useState<{ id: string; filename: string; summary: string; text?: string } | null>(null)
  const [drag,      setDrag]     = useState(false)
  const [toast,     setToast]    = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(''), 3500) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/documents')
      setDocs(Array.isArray(r.data) ? r.data : [])
    } catch { setDocs([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('surface', 'workspace')
        await api.post('/api/documents/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      }
      showToast(`Uploaded ${files.length} file${files.length > 1 ? 's' : ''}`)
      await load()
    } catch { showToast('Upload failed') } finally { setUploading(false) }
  }

  const analyze = async (id: string) => {
    setAnalyzing(id)
    try {
      const r = await api.post(`/api/documents/${id}/analyze`)
      if (r.data?.summary) {
        setDocs(ds => ds.map(d => d.id === id ? { ...d, summary: r.data.summary } : d))
        showToast('AI summary generated')
      } else {
        showToast(r.data?.message || 'No text to analyze')
      }
    } catch { showToast('Analysis failed') } finally { setAnalyzing(null) }
  }

  const remove = async (id: string) => {
    try {
      await api.delete(`/api/documents/${id}`)
      setDocs(ds => ds.filter(d => d.id !== id))
      if (preview?.id === id) setPreview(null)
    } catch { showToast('Delete failed') }
  }

  const openPreview = async (doc: Doc) => {
    try {
      const r = await api.get(`/api/documents/${doc.id}`)
      setPreview({ id: doc.id, filename: doc.filename, summary: r.data?.summary || doc.summary, text: r.data?.text_preview })
    } catch { setPreview({ id: doc.id, filename: doc.filename, summary: doc.summary }) }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDrag(false)
    upload(e.dataTransfer.files)
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-tertiary/70" />
          <span className="text-sm font-semibold text-on-surface">Documents</span>
          {docs.length > 0 && <span className="text-xs text-on-surface-variant/40">({docs.length})</span>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors">
            {uploading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
            Upload
          </button>
          <button onClick={load} className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 transition-colors">
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </div>
      <input ref={fileRef} type="file" multiple className="hidden"
        onChange={e => upload(e.target.files)} />

      {toast && (
        <div className="flex items-center gap-2 bg-primary/10 rounded-xl px-3 py-2 text-xs text-primary font-medium flex-shrink-0">
          {toast}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={cn(
          "flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-2xl py-6 cursor-pointer transition-all flex-shrink-0",
          drag
            ? "border-primary/60 bg-primary/5"
            : "border-outline-variant/20 hover:border-outline-variant/40 hover:bg-surface-container/50"
        )}
      >
        <Upload className="w-6 h-6 text-on-surface-variant/30" />
        <p className="text-xs text-on-surface-variant/50">{drag ? 'Drop to upload' : 'Drag files here or click to browse'}</p>
        <p className="text-[10px] text-on-surface-variant/30">PDF, Word, TXT, images, JSON…</p>
      </div>

      {/* Preview modal */}
      {preview && (
        <div className="bg-surface-container rounded-2xl p-4 border border-outline-variant/20 flex-shrink-0 relative">
          <button onClick={() => setPreview(null)}
            className="absolute top-3 right-3 p-1 rounded hover:bg-surface-variant text-on-surface-variant/40">
            <X className="w-3.5 h-3.5" />
          </button>
          <p className="text-xs font-semibold text-on-surface mb-2">{preview.filename}</p>
          {preview.summary && (
            <p className="text-xs text-on-surface-variant/70 mb-2 leading-relaxed border-l-2 border-primary/30 pl-3">{preview.summary}</p>
          )}
          {preview.text && (
            <pre className="text-[10px] text-on-surface-variant/50 font-mono bg-surface rounded-xl p-2 overflow-y-auto max-h-40 whitespace-pre-wrap">
              {preview.text.slice(0, 1500)}{preview.text.length > 1500 ? '\n…' : ''}
            </pre>
          )}
        </div>
      )}

      {/* Document list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-10">
            <FileText className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No documents yet</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">Upload a PDF, Word doc, or text file</p>
          </div>
        ) : docs.map(doc => (
          <div key={doc.id} className="bg-surface-container rounded-xl p-3 space-y-1.5">
            <div className="flex items-start gap-2">
              <span className="text-base leading-none flex-shrink-0 mt-0.5">{mimeIcon(doc.mime_type)}</span>
              <div className="flex-1 min-w-0">
                <button onClick={() => openPreview(doc)} className="text-xs font-medium text-on-surface hover:text-primary transition-colors text-left w-full truncate">
                  {doc.filename}
                </button>
                <div className="flex items-center gap-2 text-[10px] text-on-surface-variant/40 mt-0.5">
                  <span>{fmtBytes(doc.size_bytes)}</span>
                  <span>{fmtDate(doc.created_at)}</span>
                  {doc.surface !== 'workspace' && <span className="px-1.5 py-0.5 rounded bg-surface text-on-surface-variant/30">{doc.surface}</span>}
                </div>
                {doc.summary && (
                  <p className="text-[10px] text-on-surface-variant/60 mt-1 leading-relaxed line-clamp-2">{doc.summary}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 pt-0.5">
              <button onClick={() => analyze(doc.id)} disabled={analyzing === doc.id}
                className="flex items-center gap-1 text-[10px] text-on-surface-variant/50 hover:text-secondary transition-colors disabled:opacity-40">
                {analyzing === doc.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                {doc.summary ? 'Re-analyze' : 'Analyze'}
              </button>
              <span className="text-on-surface-variant/20 text-[10px]">·</span>
              <a href={`/api/documents/${doc.id}/download`}
                className="flex items-center gap-1 text-[10px] text-on-surface-variant/50 hover:text-primary transition-colors">
                <Download className="w-3 h-3" /> Download
              </a>
              <button onClick={() => remove(doc.id)}
                className="flex items-center gap-1 text-[10px] text-on-surface-variant/50 hover:text-error transition-colors ml-auto">
                <Trash2 className="w-3 h-3" /> Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
