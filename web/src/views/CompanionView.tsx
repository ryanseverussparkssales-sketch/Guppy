/**
 * CompanionView — Personality-first voice + chat surface
 *
 * Layout: collapsible session sidebar | avatar orb | chat area | input bar
 * Voice: mic STT → send → TTS speak. Wake-word toggle calls /api/companion/voice/session.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic, MicOff, Volume2, VolumeX, StopCircle, ArrowUp,
  Radio, RadioTower, RefreshCw, Paperclip, X, Bot, Navigation,
  PanelLeft, PenSquare, Trash2, MessageSquare,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { AvatarPresence, type AvatarState } from '@/components/surface/AvatarPresence'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'
import { BackendSelector } from '@/components/surface/BackendSelector'
import { useVoice } from '@/hooks/useVoice'
import { useSurfaceEvents } from '@/hooks/useSurfaceEvents'
import api from '../api/client'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message { id: string; role: 'user' | 'assistant'; content: string }

interface Session {
  id: string
  session_title: string
  updated_at: string
  message_count: number
}

// ── Auto-grow textarea ────────────────────────────────────────────────────────

function useAutoHeight(value: string) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    const lineH = parseInt(getComputedStyle(el).lineHeight) || 20
    el.style.height = `${Math.min(lineH * 6 + 16, Math.max(lineH * 1 + 16, el.scrollHeight))}px`
  }, [value])
  return ref
}

// ── CompanionView ─────────────────────────────────────────────────────────────

export default function CompanionView() {
  const [messages, setMessages]             = useState<Message[]>([])
  const [sessionId, setSessionId]           = useState<string | null>(() => sessionStorage.getItem('companion_session_id'))
  const [input, setInput]                   = useState('')
  const [streaming, setStreaming]           = useState('')
  const [isSending, setIsSending]           = useState(false)
  const [ttsEnabled, setTtsEnabled]         = useState(true)
  const [wakeActive, setWakeActive]         = useState(false)
  const [wakeLoading, setWakeLoading]       = useState(false)
  const [avatarState, setAvatarState]       = useState<AvatarState>('idle')
  const [vadSending, setVadSending]         = useState(false)
  const [imageFile, setImageFile]           = useState<File | null>(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null)

  const [isSteerMode, setIsSteerMode]   = useState(false)
  const [sidebarOpen, setSidebarOpen]   = useState(false)
  const [sessions, setSessions]         = useState<Session[]>([])

  const abortRef    = useRef<AbortController | null>(null)
  const bottomRef   = useRef<HTMLDivElement>(null)
  const textareaRef = useAutoHeight(input)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Accumulates streaming tokens until a sentence boundary before speaking via TTS.
  // Prevents individual short tokens ("sys", "I", etc.) from firing TTS in isolation.
  const ttsBufRef   = useRef<string>('')
  // Tracks slow-model hint timer so we can clear it when response arrives.
  const slowHintRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const voice = useVoice({
    onTranscript: (text) => { setInput((prev) => prev + text) },
    onAutoSubmit:  (text) => {
      setVadSending(true)
      setTimeout(() => setVadSending(false), 800)
      handleSend(text)
    },
    onError: () => {},
    vadAutoSend: true,
  })

  // Sync avatar state
  useEffect(() => {
    if (voice.isListening)    setAvatarState('listening')
    else if (isSending)        setAvatarState('thinking')
    else if (voice.isSpeaking) setAvatarState('speaking')
    else                       setAvatarState('idle')
  }, [voice.isListening, isSending, voice.isSpeaking])

  // Cleanup on unmount: abort any in-flight stream and drain the TTS queue.
  // Without this, navigating away leaves the stream alive and TTS fires ghost audio
  // (e.g. the first few tokens of a slow-model response played ~60s later).
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      if (slowHintRef.current) clearTimeout(slowHintRef.current)
      voice.stopSpeaking()
      ttsBufRef.current = ''
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Proactive ambient nudges — calendar reminders and surface events voiced aloud
  const handleSurfaceEvent = useCallback((type: string, payload: any) => {
    if (!ttsEnabled) return
    if (type === 'reminder_due') {
      const msg = payload?.message || payload?.data?.message
      if (msg) voice.speak(`Reminder: ${msg}`)
    }
    if (type === 'proactive_nudge') {
      const nudgeType = payload?.type
      if (nudgeType === 'calendar_reminder') {
        const title = payload?.title || 'an event'
        const mins = payload?.starts_in_minutes ?? 0
        const loc = payload?.location ? ` at ${payload.location}` : ''
        const timeStr = mins <= 1 ? 'right now' : mins < 60 ? `in ${mins} minutes` : 'in about an hour'
        voice.speak(`Heads up — ${title} starts ${timeStr}${loc}.`)
      }
    }
  }, [ttsEnabled, voice])

  const { isReconnecting: sseReconnecting } = useSurfaceEvents(handleSurfaceEvent)

  // ── Session sidebar management ─────────────────────────────────────────────

  const loadSessions = useCallback(async () => {
    try {
      const r = await api.get('/api/conversations/sessions')
      setSessions(Array.isArray(r.data) ? r.data : [])
    } catch { /* silent */ }
  }, [])

  const switchSession = useCallback(async (s: Session) => {
    try {
      const r = await api.get(`/api/conversations/sessions/${s.id}/messages?limit=100`)
      const msgs: Message[] = (r.data || []).map((m: any) => ({
        id: m.id, role: m.role as 'user' | 'assistant', content: m.content,
      }))
      setMessages(msgs)
      setSessionId(s.id)
      sessionStorage.setItem('companion_session_id', s.id)
      setSidebarOpen(false)
      loadSessions()
    } catch { toast.error('Failed to load session') }
  }, [loadSessions])

  const deleteSession = useCallback(async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/conversations/sessions/${id}`)
      if (sessionId === id) {
        setMessages([])
        setSessionId(null)
        sessionStorage.removeItem('companion_session_id')
      }
      setSessions((s) => s.filter((x) => x.id !== id))
    } catch { toast.error('Failed to delete session') }
  }, [sessionId])

  const newChat = useCallback(() => {
    setMessages([])
    setSessionId(null)
    sessionStorage.removeItem('companion_session_id')
    setSidebarOpen(false)
  }, [])

  // Scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  // Rehydrate session + load session list on mount
  useEffect(() => {
    loadSessions()
    api.get('/api/companion/voice/session').then((r) => {
      setWakeActive(r.data?.active || false)
    }).catch(() => {})

    const savedSession = sessionStorage.getItem('companion_session_id')
    if (savedSession) {
      api.get(`/api/conversations/sessions/${savedSession}/messages?limit=50`)
        .then((r) => {
          const msgs: Message[] = (r.data || []).map((m: any) => ({
            id: m.id,
            role: m.role as 'user' | 'assistant',
            content: m.content,
          }))
          if (msgs.length > 0) setMessages(msgs)
        })
        .catch(() => {
          sessionStorage.removeItem('companion_session_id')
          setSessionId(null)
          toast.info('Previous session expired — starting fresh')
        })
    }
  }, [])

  const toggleWake = useCallback(async () => {
    setWakeLoading(true)
    try {
      if (wakeActive) {
        await api.delete('/api/companion/voice/session')
        setWakeActive(false)
      } else {
        await api.post('/api/companion/voice/session')
        setWakeActive(true)
      }
    } catch {}
    setWakeLoading(false)
  }, [wakeActive])

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    voice.stopSpeaking()
    setStreaming('')
    setIsSending(false)
    setIsSteerMode(false)
  }, [voice])

  const handleSteer = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    voice.stopSpeaking()
    setStreaming('')
    setIsSending(false)
    setIsSteerMode(true)
    setInput('')
    setTimeout(() => textareaRef.current?.focus(), 50)
  }, [voice, textareaRef])

  const handleSend = useCallback(async (override?: string) => {
    const text = (override ?? input).trim()
    if (!text || isSending) return

    // Ensure a session ID exists before sending; persist it for rehydration
    const isFirstMessage = messages.length === 0
    let currentSessionId = sessionId
    if (!currentSessionId) {
      currentSessionId = crypto.randomUUID()
      setSessionId(currentSessionId)
      sessionStorage.setItem('companion_session_id', currentSessionId)
    }

    // Auto-title the session from the first user message
    if (isFirstMessage) {
      const title = text.slice(0, 60).trim()
      api.patch(`/api/conversations/sessions/${currentSessionId}`, { session_title: title }).catch(() => {})
    }

    // Capture and clear image attachment before async work
    const attachedImage = imageFile
    if (attachedImage) {
      setImageFile(null)
      if (imagePreviewUrl) { URL.revokeObjectURL(imagePreviewUrl); setImagePreviewUrl(null) }
    }

    setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'user', content: text }])
    if (!override) setInput('')
    setIsSteerMode(false)
    setIsSending(true)
    setStreaming('')
    ttsBufRef.current = ''

    // Show a hint after 12s if the model hasn't responded yet (cold start / large model).
    if (slowHintRef.current) clearTimeout(slowHintRef.current)
    slowHintRef.current = setTimeout(() => {
      setStreaming('_hint_')   // sentinel that triggers the slow-model UI note
    }, 12000)

    const controller = new AbortController()
    abortRef.current = controller

    let fullText = ''
    try {
      // Vision path: multipart POST to /api/companion/vision when image attached
      if (attachedImage) {
        toast.info('Loading vision model…', { id: 'vision-load', duration: 8000 })
        const form = new FormData()
        form.append('text', text)
        form.append('image', attachedImage)
        const vRes = await api.post('/api/companion/vision', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        toast.dismiss('vision-load')
        const reply = vRes.data?.response ?? JSON.stringify(vRes.data)
        fullText = typeof reply === 'string' ? reply : JSON.stringify(reply)
        setStreaming(fullText)
        if (ttsEnabled) voice.speak(fullText)
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', content: fullText }])
        setStreaming('')
        return
      }

      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('accessToken') || ''}`,
        },
        body: JSON.stringify({ message: text, surface: 'companion', mode: 'auto', session_id: currentSessionId }),
        signal: controller.signal,
      })

      if (res.body) {
        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = ''
        outer: while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() || ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const raw = line.slice(6).trim()
            if (raw === '[DONE]') break outer
            try {
              const evt = JSON.parse(raw)
              if (evt.done) break outer
              if (evt.error) {
                fullText += ` ⚠ ${evt.error}`
                setStreaming(fullText)
                break outer
              }
              if (evt.replace != null) {
                // Clear slow-model hint on first real content
                if (slowHintRef.current) { clearTimeout(slowHintRef.current); slowHintRef.current = null }
                // Companion non-tool path: full response delivered as one replace event.
                // Speak the whole thing at once (not through the sentence accumulator).
                fullText = evt.replace
                setStreaming(fullText)
                if (ttsEnabled) voice.speak(fullText)
              } else if (evt.token != null) {
                // Clear slow-model hint on first real content
                if (slowHintRef.current) { clearTimeout(slowHintRef.current); slowHintRef.current = null }
                // Tool-call pass-2 streaming tokens — accumulate into sentences before
                // speaking. Calling speakQueued on every raw token causes short fragments
                // like "sys", "I", "The" to fire individually as spoken audio artifacts.
                fullText += evt.token
                setStreaming(fullText)
                if (ttsEnabled) {
                  ttsBufRef.current += evt.token
                  // Flush any complete sentences (ending with . ! ? or newline)
                  const SENT_RE = /[^.!?\n]+[.!?\n]+\s*/g
                  let m: RegExpExecArray | null
                  let consumed = 0
                  SENT_RE.lastIndex = 0
                  while ((m = SENT_RE.exec(ttsBufRef.current)) !== null) {
                    const sentence = m[0].trim()
                    if (sentence.length >= 6) voice.speakQueued(sentence)
                    consumed = SENT_RE.lastIndex
                  }
                  ttsBufRef.current = ttsBufRef.current.slice(consumed)
                }
              }
              // evt.tool_exec: ignore status events (could show a toast later)
            } catch { /* non-JSON line, skip */ }
          }
        }
      }

      // Flush any remaining TTS buffer (incomplete sentence at end of stream)
      if (ttsEnabled) {
        const tail = ttsBufRef.current.trim()
        if (tail.length >= 6) voice.speakQueued(tail)
        ttsBufRef.current = ''
      }

      setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', content: fullText }])
      setStreaming('')
      loadSessions()
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', content: '⚠ Something went wrong.' }])
      }
    } finally {
      if (slowHintRef.current) { clearTimeout(slowHintRef.current); slowHintRef.current = null }
      ttsBufRef.current = ''
      setStreaming('')
      setIsSending(false)
      abortRef.current = null
    }
  }, [input, isSending, messages.length, sessionId, ttsEnabled, voice, loadSessions])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleMicClick = useCallback(() => {
    if (voice.isListening) voice.stopListening()
    else voice.startListening()
  }, [voice])

  return (
    <div className="flex h-full bg-surface text-on-surface overflow-hidden">

      {/* Session sidebar */}
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            key="companion-sidebar"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 220, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="flex flex-col border-r border-outline-variant/20 bg-surface-container-low overflow-hidden flex-shrink-0"
          >
            {/* New chat button */}
            <div className="px-3 pt-3 pb-2">
              <button
                type="button"
                onClick={newChat}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-xs font-semibold transition-colors"
              >
                <PenSquare className="w-3.5 h-3.5" />
                New chat
              </button>
            </div>

            {/* Session list */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pb-3 space-y-0.5">
              {sessions.length === 0 && (
                <p className="text-[11px] text-on-surface-variant/40 px-2 py-3 text-center">No sessions yet</p>
              )}
              {sessions.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => switchSession(s)}
                  className={cn(
                    'w-full text-left px-2.5 py-2 rounded-lg text-xs transition-colors group flex items-start gap-1.5',
                    s.id === sessionId
                      ? 'bg-primary/15 text-primary font-medium'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  )}
                >
                  <MessageSquare className="w-3 h-3 mt-0.5 flex-shrink-0 opacity-60" />
                  <span className="flex-1 min-w-0">
                    <span className="block truncate leading-snug">{s.session_title}</span>
                    <span className="flex items-center gap-1.5 text-[10px] text-on-surface-variant/40 mt-0.5">
                      <span>{new Date(s.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                      {s.message_count > 0 && (
                        <span className="px-1 py-0 rounded bg-surface-container-high text-on-surface-variant/50">
                          {s.message_count}
                        </span>
                      )}
                    </span>
                  </span>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => deleteSession(s.id, e)}
                    onKeyDown={(e) => e.key === 'Enter' && deleteSession(s.id, e as any)}
                    title="Delete session"
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-error transition-all ml-auto flex-shrink-0"
                  >
                    <Trash2 className="w-3 h-3" />
                  </span>
                </button>
              ))}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0 h-full">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-outline-variant/20 flex-shrink-0 bg-surface-container-low/50">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => { setSidebarOpen((v) => !v); if (!sidebarOpen) loadSessions() }}
            title="Session history"
            className={cn(
              'p-1.5 rounded-lg transition-colors',
              sidebarOpen
                ? 'bg-primary/15 text-primary'
                : 'text-on-surface-variant/60 hover:bg-surface-container hover:text-on-surface'
            )}
          >
            <PanelLeft className="w-4 h-4" />
          </button>
          <AvatarPresence state={avatarState} size="sm" className="!gap-0" />
          <h1 className="text-sm font-semibold text-on-surface">Companion</h1>
        </div>
        <div className="flex items-center gap-2">
          {sseReconnecting && (
            <span className="text-[10px] text-warning/70 animate-pulse px-1">⟳ reconnecting</span>
          )}
          <SurfaceStatusBar surface="workspace" compact label="Workspace" />
          <SurfaceStatusBar surface="codespace" compact label="Codespace" />
          <BackendSelector surface="companion" simple />
          {/* Wake-word toggle */}
          <button
            type="button"
            onClick={toggleWake}
            disabled={wakeLoading}
            title={wakeActive ? 'Stop wake-word listening' : 'Start wake-word listening'}
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
              wakeActive
                ? 'bg-error/15 text-error animate-pulse'
                : 'bg-surface-container text-on-surface-variant hover:bg-surface-variant',
              wakeLoading && 'opacity-50 cursor-not-allowed'
            )}
          >
            {wakeActive ? <RadioTower className="w-3.5 h-3.5" /> : <Radio className="w-3.5 h-3.5" />}
            {wakeActive ? 'Wake' : 'Wake'}
          </button>
        </div>
      </div>

      {/* Avatar */}
      <div className="flex flex-col items-center pt-6 pb-3 flex-shrink-0">
        <AvatarPresence state={avatarState} size="lg" />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar py-4">
        <div className="max-w-2xl mx-auto px-4 space-y-5">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.15 }}
                className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start gap-3')}
              >
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-4 h-4 text-primary" />
                  </div>
                )}
                <div className={cn(
                  msg.role === 'user'
                    ? 'max-w-[78%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-primary text-white text-sm leading-relaxed'
                    : 'flex-1 min-w-0 text-sm leading-relaxed text-on-surface',
                )}>
                  {msg.role === 'assistant'
                    ? <MarkdownMessage content={msg.content} />
                    : <span>{msg.content}</span>}
                </div>
              </motion.div>
            ))}

            {streaming && streaming !== '_hint_' && (
              <motion.div key="streaming" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0 text-sm leading-relaxed text-on-surface">
                  <MarkdownMessage content={streaming} />
                  <span className="inline-block w-1.5 h-3 bg-primary/50 ml-0.5 animate-pulse rounded-sm" />
                </div>
              </motion.div>
            )}

            {isSending && (!streaming || streaming === '_hint_') && (
              <motion.div key="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0 mt-0.5 relative">
                  <Bot className="w-4 h-4 text-primary" />
                  <span className="absolute inset-0 rounded-full border border-primary/30 animate-ping" style={{ animationDuration: '1.6s' }} />
                </div>
                <div className="flex flex-col gap-0.5 py-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm text-on-surface-variant/60">Thinking</span>
                    {[0, 180, 360].map((d) => (
                      <span key={d} className="w-1 h-1 rounded-full bg-primary/50 animate-bounce"
                        style={{ animationDelay: `${d}ms`, animationDuration: '1s' }} />
                    ))}
                  </div>
                  {streaming === '_hint_' && (
                    <span className="text-[11px] text-on-surface-variant/40">Model may be cold — usually ready in 30–60s</span>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Hidden file input for image attachment */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        title="Attach image"
        aria-label="Attach image"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (!file) return
          if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl)
          setImageFile(file)
          setImagePreviewUrl(URL.createObjectURL(file))
          e.target.value = ''
        }}
      />

      {/* Input bar */}
      <div className="flex-shrink-0 px-4 pb-5 pt-3 border-t border-outline-variant/10">
        {/* Stop / Steer action strip — shown while generating */}
        {isSending && (
          <div className="flex items-center gap-2 mb-2">
            <button
              type="button"
              onClick={handleStop}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-error/10 text-error hover:bg-error/20 text-xs font-medium transition-colors"
            >
              <StopCircle className="w-3.5 h-3.5" />
              Stop
            </button>
            <button
              type="button"
              onClick={handleSteer}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 text-xs font-medium transition-colors"
            >
              <Navigation className="w-3.5 h-3.5" />
              Steer
            </button>
          </div>
        )}
        {/* Image thumbnail preview */}
        {imagePreviewUrl && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className="relative">
              <img src={imagePreviewUrl} alt="attachment" className="h-14 rounded-lg border border-outline-variant/30 object-cover" />
              <button
                type="button"
                onClick={() => { if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl); setImageFile(null); setImagePreviewUrl(null) }}
                title="Remove image"
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-error text-white flex items-center justify-center hover:bg-error/80 transition-colors"
              >
                <X className="w-2.5 h-2.5" />
              </button>
            </div>
            <span className="text-xs text-on-surface-variant/50 truncate max-w-[160px]">{imageFile?.name}</span>
          </div>
        )}
        <div className={cn(
          "flex flex-col bg-surface-container rounded-2xl border transition-colors",
          isSteerMode
            ? "border-amber-500/60 ring-1 ring-amber-500/20"
            : "border-outline-variant/20 focus-within:border-primary/40"
        )}>
          {isSteerMode && (
            <div className="px-3 pt-2 text-[11px] text-amber-600 font-semibold tracking-wide">
              ↗ STEERING — redirect the conversation
            </div>
          )}
          <div className="flex items-end gap-2 px-3 py-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              vadSending ? 'Sending…' :
              voice.isListening ? 'Listening…' :
              isSteerMode ? 'Where should we go instead?' :
              'Say something or type…'
            }
            rows={1}
            className={cn(
              'flex-1 bg-transparent text-sm text-on-surface resize-none outline-none py-1.5 leading-relaxed',
              'placeholder:text-on-surface-variant/40',
              voice.isListening && !vadSending && 'placeholder:text-error',
              vadSending && 'placeholder:text-primary',
            )}
          />

          {/* Image attachment */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            title="Attach image (vision)"
            className={cn(
              'p-1.5 mb-1 rounded-lg transition-colors flex-shrink-0',
              imageFile ? 'text-primary bg-primary/10' : 'text-on-surface-variant/50 hover:bg-surface-container-high'
            )}
          >
            <Paperclip className="w-4 h-4" />
          </button>

          {/* TTS toggle */}
          <button
            type="button"
            onClick={() => { if (ttsEnabled && voice.isSpeaking) voice.stopSpeaking(); setTtsEnabled((v) => !v) }}
            title={ttsEnabled ? 'Disable voice reply' : 'Speak replies aloud'}
            className={cn(
              'p-1.5 mb-1 rounded-lg transition-colors flex-shrink-0',
              ttsEnabled ? 'text-primary bg-primary/10' : 'text-on-surface-variant/50 hover:bg-surface-container-high'
            )}
          >
            {ttsEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          {/* Mic */}
          {voice.isSupported && (
            <button
              type="button"
              onClick={handleMicClick}
              title={voice.isListening ? 'Stop listening' : 'Voice input'}
              className={cn(
                'p-1.5 mb-1 rounded-lg transition-colors flex-shrink-0',
                voice.isListening
                  ? 'text-error bg-error/10 animate-pulse'
                  : 'text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-container-high'
              )}
            >
              {voice.isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          )}

          {/* Send */}
          <button type="button" onClick={() => handleSend()} title="Send"
            disabled={isSending || !input.trim()}
            className="p-2 mb-1 rounded-xl bg-primary text-on-primary disabled:opacity-30 hover:bg-primary/90 transition-colors flex-shrink-0">
            <ArrowUp className="w-4 h-4" />
          </button>
          </div>
        </div>

        <div className="flex items-center justify-between mt-1.5 px-1">
          <button
            type="button"
            onClick={() => {
              if (messages.length > 0 && window.confirm('Clear this conversation?')) {
                setMessages([])
                sessionStorage.removeItem('companion_session_id')
                setSessionId(null)
              }
            }}
            className="text-xs text-on-surface-variant/35 hover:text-on-surface-variant transition-colors"
          >
            <RefreshCw className="w-3 h-3 inline mr-1" />Clear
          </button>
          <span className="text-[11px] text-on-surface-variant/30">Enter to send · Shift+Enter new line</span>
        </div>
      </div>
      </div>{/* end main area */}
    </div>
  )
}
