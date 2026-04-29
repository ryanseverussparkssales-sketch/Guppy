/**
 * EmailPanel — Gmail inbox viewer + thread reader + compose
 *
 * Shows a "Connect Gmail" CTA until GOOGLE credentials are configured.
 * Local draft management works immediately.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Mail, Inbox, Send, FileEdit, Star, Search, RefreshCw, X,
  ChevronRight, AlertCircle, CheckCircle2, Link2, Reply,
  Trash2, Clock,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface EmailThread {
  id: string
  subject: string
  snippet: string
  from_addr: string
  labels: string[]
  unread: boolean
  starred: boolean
  message_count: number
  last_message_at: string
}

interface EmailMessage {
  id: string
  from_addr: string
  to_addrs: string
  subject: string
  body_text: string
  sent_at: string
}

interface ThreadDetail extends EmailThread {
  messages: EmailMessage[]
}

type Folder = 'inbox' | 'starred' | 'drafts'

// ── Helpers ───────────────────────────────────────────────────────────────────

function relTime(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60000)
    if (m < 1)  return 'just now'
    if (m < 60) return `${m}m ago`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h ago`
    return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch { return '' }
}

function initials(addr: string) {
  const name = addr.split('<')[0].trim() || addr
  return name.slice(0, 2).toUpperCase()
}

// ── ComposeModal ──────────────────────────────────────────────────────────────

function ComposeModal({ onClose, initialTo = '' }: { onClose: () => void; initialTo?: string }) {
  const [to,      setTo]      = useState(initialTo)
  const [cc,      setCc]      = useState('')
  const [subject, setSubject] = useState('')
  const [body,    setBody]    = useState('')
  const [saving,  setSaving]  = useState(false)
  const [err,     setErr]     = useState('')
  const [saved,   setSaved]   = useState(false)

  const saveDraft = async () => {
    setSaving(true)
    try {
      await api.post('/api/email/draft', { to_addrs: to, cc_addrs: cc, subject, body })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch { setErr('Failed to save draft') } finally { setSaving(false) }
  }

  return (
    <div className="absolute inset-0 bg-surface z-20 flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-outline-variant/20 flex-shrink-0">
        <FileEdit className="w-4 h-4 text-primary/60" />
        <span className="text-xs font-semibold text-on-surface flex-1">New Message</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 flex flex-col gap-0 overflow-hidden">
        {[
          { label: 'To', val: to, set: setTo },
          { label: 'Cc', val: cc, set: setCc },
          { label: 'Subject', val: subject, set: setSubject },
        ].map(({ label, val, set }) => (
          <div key={label} className="flex items-center border-b border-outline-variant/10 px-3">
            <span className="text-xs text-on-surface-variant/40 w-12 flex-shrink-0">{label}</span>
            <input className="flex-1 py-2 text-sm text-on-surface bg-transparent focus:outline-none"
              value={val} onChange={(e) => set(e.target.value)} />
          </div>
        ))}
        <textarea
          className="flex-1 p-3 text-sm text-on-surface bg-transparent focus:outline-none resize-none"
          placeholder="Message body…"
          value={body} onChange={(e) => setBody(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-2 px-3 py-2.5 border-t border-outline-variant/15 bg-surface-container-low/30 flex-shrink-0">
        {err && <span className="text-xs text-error/80 flex-1">{err}</span>}
        {saved && <span className="text-xs text-success flex-1">Draft saved</span>}
        {!err && !saved && <span className="flex-1" />}
        <button onClick={saveDraft} disabled={saving}
          className="text-xs px-3 py-1.5 rounded-lg bg-surface-variant text-on-surface-variant hover:bg-surface-container-high transition-colors">
          {saving ? 'Saving…' : 'Save draft'}
        </button>
        <button
          className="text-xs px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium"
          onClick={() => { setErr('Send requires Gmail credentials. Save as draft instead.') }}
        >
          <Send className="w-3.5 h-3.5 inline mr-1" />Send
        </button>
      </div>
    </div>
  )
}

// ── ThreadView ────────────────────────────────────────────────────────────────

function ThreadView({ threadId, onClose, onReply }: {
  threadId: string
  onClose: () => void
  onReply: (to: string) => void
}) {
  const [thread,  setThread]  = useState<ThreadDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/api/email/threads/${threadId}`)
      .then((r) => setThread(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [threadId])

  return (
    <div className="absolute inset-0 bg-surface z-10 flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-outline-variant/20 flex-shrink-0">
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50">
          <ChevronRight className="w-4 h-4 rotate-180" />
        </button>
        <span className="text-xs font-medium text-on-surface flex-1 truncate">
          {thread?.subject || 'Loading…'}
        </span>
        {thread && (
          <button onClick={() => onReply(thread.from_addr)}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
            <Reply className="w-3 h-3" /> Reply
          </button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-3 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : !thread ? (
          <p className="text-xs text-error/70">Could not load thread.</p>
        ) : thread.messages.map((msg) => (
          <div key={msg.id} className="bg-surface-container rounded-xl p-3 space-y-2">
            <div className="flex items-start gap-2">
              <div className="w-7 h-7 rounded-full bg-primary/15 text-primary text-xs flex items-center justify-center font-semibold flex-shrink-0">
                {initials(msg.from_addr)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-on-surface truncate">{msg.from_addr}</p>
                <p className="text-xs text-on-surface-variant/40">{relTime(msg.sent_at)}</p>
              </div>
            </div>
            <pre className="text-xs text-on-surface/80 whitespace-pre-wrap leading-relaxed font-sans">
              {msg.body_text || '(no text body)'}
            </pre>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── EmailPanel ────────────────────────────────────────────────────────────────

export function EmailPanel() {
  const [threads,    setThreads]    = useState<EmailThread[]>([])
  const [loading,    setLoading]    = useState(true)
  const [folder,     setFolder]     = useState<Folder>('inbox')
  const [search,     setSearch]     = useState('')
  const [connected,  setConnected]  = useState<boolean | null>(null)
  const [unread,     setUnread]     = useState(0)
  const [openThread, setOpenThread] = useState<string | null>(null)
  const [composeTo,  setComposeTo]  = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusRes, threadsRes] = await Promise.all([
        api.get('/api/email/status'),
        api.get(`/api/email/threads?limit=50${search ? `&search=${encodeURIComponent(search)}` : ''}${folder === 'starred' ? '&starred=1' : ''}`),
      ])
      setConnected(statusRes.data?.gmail_configured ?? false)
      setUnread(statusRes.data?.unread_count ?? 0)
      setThreads(Array.isArray(threadsRes.data) ? threadsRes.data : [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [folder, search])

  useEffect(() => { load() }, [load])

  const syncEmail = async () => {
    await api.post('/api/email/sync').catch(() => {})
    load()
  }

  const FOLDERS: { id: Folder; label: string; icon: React.ReactNode }[] = [
    { id: 'inbox',   label: 'Inbox',   icon: <Inbox   className="w-3.5 h-3.5" /> },
    { id: 'starred', label: 'Starred', icon: <Star    className="w-3.5 h-3.5" /> },
    { id: 'drafts',  label: 'Drafts',  icon: <FileEdit className="w-3.5 h-3.5" /> },
  ]

  return (
    <div className="relative flex flex-col h-full">
      {/* Thread view overlay */}
      {openThread && !composeTo && (
        <ThreadView
          threadId={openThread}
          onClose={() => { setOpenThread(null); load() }}
          onReply={(to) => setComposeTo(to)}
        />
      )}
      {/* Compose overlay */}
      {composeTo !== null && (
        <ComposeModal initialTo={composeTo} onClose={() => { setComposeTo(null) }} />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/10 flex-shrink-0">
        <Mail className="w-4 h-4 text-primary/70" />
        <span className="text-sm font-semibold text-on-surface">Email</span>
        {unread > 0 && (
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-primary text-on-primary font-medium">{unread}</span>
        )}
        {connected === false && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-warning/10 text-warning">Not connected</span>
        )}
        {connected === true && (
          <CheckCircle2 className="w-3.5 h-3.5 text-success" />
        )}
        <div className="ml-auto flex items-center gap-1">
          <button onClick={syncEmail} className="text-xs px-2 py-1 rounded-lg bg-surface-variant text-on-surface-variant/60 hover:text-on-surface transition-colors">
            Sync
          </button>
          <button onClick={() => setComposeTo('')}
            className="text-xs px-2.5 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/15 transition-colors font-medium">
            Compose
          </button>
        </div>
      </div>

      {/* Gmail CTA */}
      {connected === false && (
        <div className="mx-4 mt-3 flex items-start gap-2.5 bg-primary/5 rounded-xl p-3 border border-primary/10 flex-shrink-0">
          <Link2 className="w-4 h-4 text-primary/60 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-on-surface">Connect Gmail</p>
            <p className="text-xs text-on-surface-variant/50 mt-0.5">
              Set <span className="font-mono text-primary/70">GOOGLE_CLIENT_ID</span>,{' '}
              <span className="font-mono text-primary/70">GOOGLE_CLIENT_SECRET</span>, and{' '}
              <span className="font-mono text-primary/70">GOOGLE_REFRESH_TOKEN</span> to sync your inbox.
              Drafts work without Gmail credentials.
            </p>
          </div>
        </div>
      )}

      {/* Folder tabs + search */}
      <div className="flex items-center gap-1 px-3 pt-2 flex-shrink-0">
        {FOLDERS.map((f) => (
          <button key={f.id} onClick={() => setFolder(f.id)}
            className={cn(
              "flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg transition-colors",
              folder === f.id
                ? "bg-primary/10 text-primary font-medium"
                : "text-on-surface-variant/50 hover:text-on-surface"
            )}>
            {f.icon}{f.label}
          </button>
        ))}
        <div className="ml-auto relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-on-surface-variant/40" />
          <input
            className="bg-surface-container rounded-lg pl-6 pr-2 py-1 text-xs text-on-surface placeholder-on-surface-variant/40 focus:outline-none w-28"
            placeholder="Search…"
            value={search} onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button onClick={load} className="p-1 text-on-surface-variant/40 hover:text-on-surface">
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0 mt-2">
        {loading && threads.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : threads.length === 0 ? (
          <div className="text-center py-10">
            <Mail className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">
              {search ? 'No matching threads' : 'No emails yet'}
            </p>
            {!connected && (
              <p className="text-xs text-on-surface-variant/30 mt-1">Connect Gmail to load your inbox</p>
            )}
          </div>
        ) : (
          threads.map((t) => (
            <button
              key={t.id}
              onClick={() => setOpenThread(t.id)}
              className={cn(
                "w-full text-left px-4 py-3 border-b border-outline-variant/10 hover:bg-surface-variant/20 transition-colors",
                t.unread && "bg-primary/3",
              )}
            >
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-surface-container text-xs flex items-center justify-center font-semibold text-on-surface-variant/60 flex-shrink-0 mt-0.5">
                  {initials(t.from_addr)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className={cn("text-xs truncate flex-1", t.unread ? "font-semibold text-on-surface" : "text-on-surface/70")}>
                      {t.from_addr.split('<')[0].trim() || t.from_addr}
                    </p>
                    <span className="text-xs text-on-surface-variant/40 flex-shrink-0">{relTime(t.last_message_at)}</span>
                  </div>
                  <p className={cn("text-xs truncate mt-0.5", t.unread ? "text-on-surface font-medium" : "text-on-surface/60")}>
                    {t.subject || '(no subject)'}
                  </p>
                  <p className="text-xs text-on-surface-variant/40 truncate mt-0.5">{t.snippet}</p>
                </div>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
