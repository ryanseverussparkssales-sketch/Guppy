/**
 * DropNotifier
 *
 * Connects to /api/drop/stream (SSE) and shows a toast for every file
 * dropped into ~/Desktop/GuppyDrop/. Each toast has three actions:
 *   • Insert into chat  — sets pendingDraftText in Zustand store
 *   • Save to library   — POSTs to /api/library/items
 *   • ✕               — dismisses
 *
 * Mounts once at the app root. No visible UI of its own.
 */
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { MessageSquare, BookOpen, X } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import api from '@/api/client'

interface DropItem {
  id: string
  filename: string
  path: string
  format: string
  text: string
  token_estimate?: number
  file_size?: string
  pages?: number
  slides?: number
  sheets?: number
  truncated?: boolean
  dropped_at: string
}

const FORMAT_ICONS: Record<string, string> = {
  pdf: '📄',
  docx: '📝',
  doc: '📝',
  xlsx: '📊',
  xls: '📊',
  csv: '📊',
  pptx: '📽',
  ppt: '📽',
  jpg: '🖼',
  jpeg: '🖼',
  png: '🖼',
  txt: '📃',
  md: '📃',
  py: '🐍',
  js: '⚡',
  ts: '⚡',
}

function formatLabel(item: DropItem): string {
  const parts: string[] = []
  if (item.file_size) parts.push(item.file_size)
  if (item.token_estimate) parts.push(`~${item.token_estimate.toLocaleString()} tokens`)
  if (item.pages) parts.push(`${item.pages}p`)
  if (item.slides) parts.push(`${item.slides} slides`)
  if (item.sheets) parts.push(`${item.sheets} sheets`)
  return parts.join(' · ')
}

export function DropNotifier() {
  const setPendingDraftText = useAppStore((s) => s.setPendingDraftText)
  const shownIds = useRef<Set<string>>(new Set())

  useEffect(() => {
    const base = (import.meta.env.VITE_API_URL as string) || ''
    let cancelled = false
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    async function connect() {
      if (cancelled) return
      try {
        const token = localStorage.getItem('accessToken')
        const res = await fetch(`${base}/api/drop/stream`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        })
        if (!res.ok || !res.body) {
          throw new Error(`HTTP ${res.status}`)
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let eventType = ''

        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              if (eventType === 'drop' || eventType === '') {
                try {
                  const item: DropItem = JSON.parse(line.slice(6))
                  if (!shownIds.current.has(item.id)) {
                    shownIds.current.add(item.id)
                    showDropToast(item)
                  }
                } catch { /* ignore malformed */ }
              }
              eventType = ''
            }
          }
        }
      } catch {
        // ignore — reconnect below
      }

      if (!cancelled) {
        retryTimeout = setTimeout(connect, 5000)
      }
    }

    connect()
    return () => {
      cancelled = true
      if (retryTimeout) clearTimeout(retryTimeout)
    }
  }, [])

  function showDropToast(item: DropItem) {
    const icon = FORMAT_ICONS[item.format?.toLowerCase()] ?? '📁'
    const meta = formatLabel(item)

    const insertIntoChat = () => {
      const prefix = `[File: ${item.filename}]\n\n`
      setPendingDraftText(prefix + item.text)
      dismissItem(item.id)
      toast.dismiss(item.id)
      toast.success(`"${item.filename}" inserted into chat`)
    }

    const saveToLibrary = async () => {
      try {
        await api.post('/api/library/items', {
          type: 'artifact',
          title: item.filename,
          content: item.text,
          tags: [item.format],
        })
        dismissItem(item.id)
        toast.dismiss(item.id)
        toast.success(`"${item.filename}" saved to library`)
      } catch {
        toast.error('Failed to save to library')
      }
    }

    const dismiss = () => {
      dismissItem(item.id)
      toast.dismiss(item.id)
    }

    toast.custom(
      () => (
        <div className="flex flex-col gap-2 bg-surface border border-outline-variant rounded-xl shadow-2xl p-4 w-[360px]">
          {/* Header */}
          <div className="flex items-start gap-2">
            <span className="text-2xl leading-none mt-0.5">{icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-on-surface truncate">{item.filename}</p>
              {meta && <p className="text-xs text-on-surface-variant mt-0.5">{meta}</p>}
              {item.truncated && (
                <p className="text-xs text-warning mt-0.5">⚠ Truncated — file too large for full context</p>
              )}
            </div>
            <button
              onClick={dismiss}
              className="p-1 rounded hover:bg-surface-variant text-on-surface-variant shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Preview */}
          {item.text && (
            <p className="text-xs text-on-surface-variant bg-surface-variant rounded-lg px-3 py-2 font-mono line-clamp-3">
              {item.text.slice(0, 200)}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={insertIntoChat}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Insert into chat
            </button>
            <button
              onClick={saveToLibrary}
              className="flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-outline-variant text-on-surface-variant rounded-lg hover:bg-surface-variant transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5" />
              Save
            </button>
          </div>
        </div>
      ),
      {
        id: item.id,
        duration: Infinity,  // stays until dismissed
        position: 'bottom-right',
      }
    )
  }

  async function dismissItem(id: string) {
    try {
      await api.delete(`/api/drop/items/${id}`)
    } catch {
      // best-effort — item is already gone from UI
    }
  }

  return null
}
