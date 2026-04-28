/**
 * AssistantView — Chat Interface
 *
 * Condensed, professional layout: conversation list panel + main chat area.
 * No duplicate header (TopBar handles branding). All controls inline in
 * the input bar. Auto-growing textarea.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  PenSquare, Trash2, AlertCircle, WifiOff, Clock,
  Mic, MicOff, StopCircle, Navigation, Volume2, VolumeX,
  ArrowUp, Bot, Copy, Check, Pencil, RefreshCw, Timer, Sparkles, Search, X, Paperclip, ImageIcon,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { format } from 'date-fns'
import { cn } from '@/lib/utils'
import { useChatStore, useWorkspaceStore, syncManager } from '@/store'
import { useQueueMonitoring } from '@/hooks/useMonitoring'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { useVoice } from '@/hooks/useVoice'
import api from '../api/client'

// ── Voice config loader ────────────────────────────────────────────────────────
interface VoiceOption { id: string; name: string; lang: string }
interface VoiceMeta {
  provider: string
  voiceId: string
  options: VoiceOption[]
}

async function loadVoiceMeta(): Promise<VoiceMeta> {
  try {
    const res = await api.get('/api/voices')
    const d = res.data
    const provider = d?.tts?.active_provider || 'auto'
    const voiceId  = d?.tts?.active_voice || 'bm_lewis'
    const options: VoiceOption[] = d?.tts?.voices?.[provider] || d?.tts?.voices?.['kokoro'] || []
    return { provider, voiceId, options }
  } catch {
    return { provider: 'auto', voiceId: 'bm_lewis', options: [] }
  }
}

// ── auto-grow textarea height ─────────────────────────────────────────────────
function useAutoHeight(value: string, minRows = 1, maxRows = 6) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    const lineH = parseInt(getComputedStyle(el).lineHeight) || 20
    const min = lineH * minRows + 16  // +padding
    const max = lineH * maxRows + 16
    el.style.height = `${Math.min(max, Math.max(min, el.scrollHeight))}px`
  }, [value, minRows, maxRows])
  return ref
}

// ── copy-to-clipboard with transient ✓ ────────────────────────────────────────
function useCopyFeedback() {
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const copy = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    }).catch(() => {})
  }, [])
  return { copiedId, copy }
}

// ── format elapsed seconds ────────────────────────────────────────────────────
function fmtElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// ── main view ─────────────────────────────────────────────────────────────────
export default function AssistantView() {
  const { conversations, activeConversationId, messages, loading, error } = useChatStore()
  const { activeWorkspaceId } = useWorkspaceStore()
  const queueStatus = useQueueMonitoring(1000)

  const [inputValue, setInputValue]     = useState('')
  const [isSending, setIsSending]       = useState(false)
  const [localError, setLocalError]     = useState<string | null>(null)
  const [streamingContent, setStreamingContent] = useState('')
  const [isSteerMode, setIsSteerMode]   = useState(false)
  const [ttsEnabled, setTtsEnabled]     = useState(false)
  // 'auto' | 'local' | 'claude'
  const [forcedMode, setForcedMode]     = useState<'auto' | 'local' | 'claude'>('auto')

  // Voice selector state
  const [voiceOptions, setVoiceOptions] = useState<VoiceOption[]>([])
  const [selectedVoiceId, setSelectedVoiceId] = useState('bm_lewis')
  const [ttsProvider, setTtsProvider] = useState('auto')

  // Follow-up suggestions shown after last assistant reply
  const [followUps, setFollowUps] = useState<string[]>([])

  // Image attachment for multimodal sends
  const [attachedImage, setAttachedImage] = useState<{ base64: string; name: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Conversation search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<typeof conversations | null>(null)
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Response timing + model attribution
  const streamStartRef = useRef<number>(0)
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)
  const [lastSource, setLastSource] = useState<string | null>(null)

  const messagesEndRef       = useRef<HTMLDivElement>(null)
  const abortControllerRef   = useRef<AbortController | null>(null)
  const textareaRef          = useAutoHeight(inputValue)

  const { copiedId, copy } = useCopyFeedback()

  const voice = useVoice({
    onTranscript: (text) => setInputValue(text),
    onError: () => {},
    voiceId: selectedVoiceId,
    ttsProvider: ttsProvider,
  })

  // Load voice options once
  useEffect(() => {
    loadVoiceMeta().then((meta) => {
      setVoiceOptions(meta.options)
      setSelectedVoiceId(meta.voiceId)
      setTtsProvider(meta.provider)
    })
  }, [])

  // scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // auto-create conversation
  useEffect(() => {
    if (!activeWorkspaceId || conversations.length > 0 || loading) return
    syncManager
      .createConversation(activeWorkspaceId, `Chat ${new Date().toLocaleString()}`)
      .catch((err: any) => setLocalError(err?.message || 'Failed to create conversation'))
  }, [activeWorkspaceId])

  // reset timing + source when conversation switches
  useEffect(() => {
    setElapsedMs(null)
    setLastSource(null)
  }, [activeConversationId])

  // ── actions ───────────────────────────────────────────────────────────────

  const handleNewConversation = useCallback(async () => {
    if (!activeWorkspaceId) return
    try {
      setLocalError(null)
      await syncManager.createConversation(activeWorkspaceId, `Chat ${new Date().toLocaleString()}`)
    } catch (err: any) {
      setLocalError(err?.message || 'Failed to create conversation')
    }
  }, [activeWorkspaceId])

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    if (voice.isSpeaking) voice.stopSpeaking()
    setStreamingContent('')
    setIsSending(false)
  }, [voice])

  const handleSend = useCallback(async (overrideText?: string) => {
    const text = overrideText ?? inputValue
    if (!text.trim() || !activeConversationId || isSending) return

    // Build the effective routing mode: steer overrides, otherwise use forced model selection
    const sendMode = isSteerMode ? 'steer' : forcedMode !== 'auto' ? forcedMode : undefined
    if (!overrideText) {
      setInputValue('')
      setIsSteerMode(false)
    }
    setIsSending(true)
    setLocalError(null)
    setFollowUps([])
    streamStartRef.current = Date.now()

    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      await syncManager.addMessage(activeConversationId, 'user', text)
      setStreamingContent('')
      setLastSource(null)

      const currentImage = attachedImage
      setAttachedImage(null)
      const full = await syncManager.getAIResponse(
        activeConversationId,
        text,
        sendMode,
        (token) => setStreamingContent((p) => p + token),
        controller.signal,
        (replaced) => setStreamingContent(replaced),
        (src) => setLastSource(src),
        currentImage?.base64,
      )
      setStreamingContent('')

      // record timing — we'll show it on the last assistant message in the current render
      const elapsed = Date.now() - streamStartRef.current
      setElapsedMs(elapsed)

      if (ttsEnabled && full && typeof full === 'string' && full.trim()) {
        voice.speak(full)
      }

      // Generate contextual follow-up suggestions from the response
      if (full && typeof full === 'string' && full.trim()) {
        setFollowUps(generateFollowUps(full))
      }

      setLocalError(null)
    } catch (err: any) {
      setStreamingContent('')
      if (err?.name === 'AbortError') return
      setLocalError(err?.message || 'Failed to send message')
      if (!overrideText) setInputValue(text)
      setTimeout(() => setLocalError(null), 4000)
    } finally {
      abortControllerRef.current = null
      setIsSending(false)
      textareaRef.current?.focus()
    }
  }, [inputValue, activeConversationId, isSending, isSteerMode, ttsEnabled, voice, textareaRef])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleMicClick = async () => {
    if (voice.isListening) { voice.stopListening(); return }
    if (voice.isSpeaking) {
      voice.stopSpeaking()
      try { await api.post('/api/voices/stop') } catch {}
    }
    voice.startListening()
  }

  const handleDeleteConversation = async (id: string) => {
    if (!window.confirm('Delete this conversation?')) return
    try {
      await syncManager.deleteConversation(id)
    } catch (err: any) {
      setLocalError(err?.message || 'Failed to delete')
    }
  }

  const handleSearchChange = useCallback((q: string) => {
    setSearchQuery(q)
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    if (!q.trim()) { setSearchResults(null); return }
    searchDebounceRef.current = setTimeout(async () => {
      if (!activeWorkspaceId) return
      try {
        const res = await api.get(`/api/chat/history/search/${activeWorkspaceId}`, { params: { q } })
        setSearchResults(res.data?.results ?? [])
      } catch { setSearchResults([]) }
    }, 300)
  }, [activeWorkspaceId])

  const handleImagePick = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string
      // Strip "data:image/...;base64," prefix
      const base64 = dataUrl.split(',')[1] ?? ''
      setAttachedImage({ base64, name: file.name })
    }
    reader.readAsDataURL(file)
    // Reset so same file can be picked again
    e.target.value = ''
  }, [])

  // Edit a user message — populate textarea and focus
  const handleEditMessage = useCallback((content: string) => {
    setInputValue(content)
    setTimeout(() => textareaRef.current?.focus(), 50)
  }, [textareaRef])

  // Regenerate: find the user message preceding this assistant message by index
  const handleRegenerate = useCallback((userText: string) => {
    handleSend(userText)
  }, [handleSend])

  const currentMessages = activeConversationId ? messages : []

  return (
    <div className="flex h-full overflow-hidden bg-surface">

      {/* ── Conversation panel ──────────────────────────────────────────────── */}
      <aside className="w-52 shrink-0 flex flex-col border-r border-outline-variant/20 bg-surface-container-low overflow-hidden">

        {/* New chat */}
        <div className="p-3 shrink-0">
          <button
            onClick={handleNewConversation}
            disabled={loading || !activeWorkspaceId}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold
                       text-on-surface hover:bg-surface-container transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <PenSquare className="w-4 h-4 shrink-0" />
            New chat
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2 shrink-0">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-surface-container text-on-surface-variant">
            <Search className="w-3.5 h-3.5 shrink-0 opacity-50" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search chats…"
              className="flex-1 bg-transparent text-xs outline-none placeholder:text-on-surface-variant/50 min-w-0"
            />
            {searchQuery && (
              <button onClick={() => { setSearchQuery(''); setSearchResults(null) }} className="opacity-60 hover:opacity-100">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
          {loading && conversations.length === 0 && (
            <p className="text-xs text-on-surface-variant/50 px-3 py-4">Loading…</p>
          )}
          {searchResults !== null && searchResults.length === 0 && (
            <p className="text-xs text-on-surface-variant/50 px-3 py-2">No results</p>
          )}
          {(searchResults ?? conversations).map((conv) => {
            const active = conv.id === activeConversationId
            return (
              <div
                key={conv.id}
                className={cn(
                  'group flex items-center gap-1 rounded-lg px-2 py-1.5 cursor-pointer transition-colors',
                  active ? 'bg-primary/12 text-primary' : 'hover:bg-surface-container text-on-surface-variant'
                )}
                onClick={() => syncManager.loadConversation(conv.id)}
              >
                <span className="flex-1 text-xs font-medium truncate leading-snug">
                  {conv.title}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id) }}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-error transition-all shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      </aside>

      {/* ── Main chat area ──────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Messages scroll region */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">

            {/* Error banner */}
            {(error || localError) && (
              <div className="flex gap-3 items-start p-3 rounded-xl bg-error/8 border border-error/20 text-sm">
                <AlertCircle className="w-4 h-4 text-error shrink-0 mt-0.5" />
                <p className="text-error">{error || localError}</p>
              </div>
            )}

            {/* Queue status */}
            {queueStatus.queuedCount > 0 && (
              <div className="flex items-center gap-2 text-xs text-on-surface-variant bg-surface-container px-3 py-2 rounded-xl">
                {queueStatus.isPaused
                  ? <><WifiOff className="w-3.5 h-3.5 text-error" /><span>Offline · {queueStatus.queuedCount} queued</span></>
                  : <><Clock className="w-3.5 h-3.5" /><span>{queueStatus.queuedCount} queued · {queueStatus.oldestAgeSeconds}s</span></>
                }
              </div>
            )}

            {/* Empty state */}
            {currentMessages.length === 0 && !loading && !error && activeConversationId && (
              <EmptyState onPrompt={(p) => { setInputValue(p); textareaRef.current?.focus() }} />
            )}

            {/* Loading skeleton */}
            {loading && currentMessages.length === 0 && (
              <div className="flex justify-center py-20">
                <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            )}

            {/* Messages */}
            <AnimatePresence initial={false}>
              {currentMessages.map((msg, idx) => {
                const isUser = msg.role === 'user'
                // Show timing only on the last assistant message in this session
                const asstIndices = currentMessages.map((m, i) => m.role === 'assistant' ? i : -1).filter(i => i >= 0)
                const lastAsstIdx = asstIndices.length > 0 ? asstIndices[asstIndices.length - 1] : -1
                const isLastAsst = !isUser && idx === lastAsstIdx
                const showTiming = isLastAsst && elapsedMs != null
                // For regenerate: find the closest preceding user message
                const prevUserMsg = !isUser
                  ? [...currentMessages].slice(0, idx).reverse().find((m) => m.role === 'user')
                  : null

                return (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15, ease: 'easeOut' }}
                    className={cn('group flex', isUser ? 'justify-end' : 'justify-start')}
                  >
                    {isUser ? (
                      /* User bubble */
                      <div className="max-w-[78%] flex flex-col items-end gap-0.5">
                        <div className="px-4 py-2.5 rounded-2xl rounded-tr-sm bg-primary text-white text-sm leading-relaxed">
                          <MarkdownMessage content={msg.content} isUser />
                        </div>
                        {/* User message actions */}
                        <div className="flex items-center gap-1 h-6 opacity-0 group-hover:opacity-100 transition-opacity">
                          <MsgAction
                            icon={<Pencil className="w-3 h-3" />}
                            label="Edit"
                            onClick={() => handleEditMessage(msg.content)}
                          />
                          <MsgAction
                            icon={copiedId === msg.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                            label={copiedId === msg.id ? 'Copied' : 'Copy'}
                            onClick={() => copy(msg.content, msg.id)}
                          />
                          <span className="text-[11px] text-on-surface-variant/40 pl-1">
                            {format(new Date(msg.created_at), 'HH:mm')}
                          </span>
                        </div>
                        {/* Timestamp (always visible fallback when not hovered) */}
                        <span className="text-[11px] text-on-surface-variant/40 pr-1 group-hover:hidden">
                          {format(new Date(msg.created_at), 'HH:mm')}
                        </span>
                      </div>
                    ) : (
                      /* Assistant — no bubble, prose width */
                      <div className="flex gap-3 max-w-full w-full">
                        <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0 mt-0.5">
                          <Bot className="w-4 h-4 text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm leading-relaxed text-on-surface prose-sm">
                            <MarkdownMessage content={msg.content} isUser={false} />
                          </div>
                          {/* Assistant message footer */}
                          <div className="flex items-center gap-2 mt-1 h-6">
                            {/* Always-visible timestamp */}
                            <span className="text-[11px] text-on-surface-variant/40">
                              {format(new Date(msg.created_at), 'HH:mm')}
                            </span>
                            {/* Timing badge */}
                            {showTiming && (
                              <span className="flex items-center gap-1 text-[11px] text-on-surface-variant/40">
                                <Timer className="w-3 h-3" />
                                {fmtElapsed(elapsedMs!)}
                              </span>
                            )}
                            {/* Model source badge */}
                            {isLastAsst && lastSource && (
                              <span
                                title={lastSource}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant/50 font-mono truncate max-w-[140px]"
                              >
                                {lastSource.length > 22 ? lastSource.slice(0, 20) + '…' : lastSource}
                              </span>
                            )}
                            {/* Hover actions */}
                            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity ml-1">
                              <MsgAction
                                icon={copiedId === msg.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                                label={copiedId === msg.id ? 'Copied' : 'Copy'}
                                onClick={() => copy(msg.content, msg.id)}
                              />
                              {prevUserMsg && !isSending && (
                                <MsgAction
                                  icon={<RefreshCw className="w-3 h-3" />}
                                  label="Regenerate"
                                  onClick={() => handleRegenerate(prevUserMsg.content)}
                                />
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </motion.div>
                )
              })}
            </AnimatePresence>

            {/* Thinking — shown before first token arrives */}
            {isSending && !streamingContent && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="flex gap-3"
              >
                <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0 mt-0.5 relative">
                  <Bot className="w-4 h-4 text-primary" />
                  {/* Pulsing ring */}
                  <span className="absolute inset-0 rounded-full border border-primary/30 animate-ping" style={{ animationDuration: '1.6s' }} />
                </div>
                <div className="flex items-center gap-2 py-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-primary/50 animate-pulse" />
                  <span className="text-sm text-on-surface-variant/60">Thinking</span>
                  <span className="flex gap-0.5">
                    {[0, 180, 360].map((d) => (
                      <span
                        key={d}
                        className="w-1 h-1 rounded-full bg-primary/50 animate-bounce"
                        style={{ animationDelay: `${d}ms`, animationDuration: '1s' }}
                      />
                    ))}
                  </span>
                </div>
              </motion.div>
            )}

            {/* Live streaming */}
            {streamingContent && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-3"
              >
                <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm leading-relaxed text-on-surface">
                    <MarkdownMessage content={streamingContent} isUser={false} />
                  </div>
                  <div className="flex gap-1 mt-2">
                    {[0, 150, 300].map((d) => (
                      <span
                        key={d}
                        className="w-1.5 h-1.5 rounded-full bg-primary/50 animate-bounce"
                        style={{ animationDelay: `${d}ms` }}
                      />
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {/* Follow-up suggestions */}
            {followUps.length > 0 && !isSending && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: 0.1 }}
                className="flex flex-wrap gap-2 pl-10"
              >
                {followUps.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleSend(suggestion)}
                    className={cn(
                      'px-3 py-1.5 rounded-full text-xs border transition-all',
                      'border-outline-variant/30 text-on-surface-variant',
                      'hover:border-primary/50 hover:text-primary hover:bg-primary/5',
                      'active:scale-95'
                    )}
                  >
                    {suggestion}
                  </button>
                ))}
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ── Input bar ───────────────────────────────────────────────────── */}
        <div className="shrink-0 px-4 py-3 border-t border-outline-variant/15">
          <div className="max-w-3xl mx-auto">
            <div
              className={cn(
                'rounded-2xl border transition-colors bg-surface-container-lowest shadow-sm',
                isSteerMode
                  ? 'border-amber-500/60 ring-1 ring-amber-500/20'
                  : 'border-outline-variant/30 focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/10',
                !activeConversationId && 'opacity-50 pointer-events-none'
              )}
            >
              {/* Steer mode label */}
              {isSteerMode && (
                <div className="px-4 pt-2.5 pb-0 text-[11px] text-amber-500 font-semibold tracking-wide">
                  ↗ STEERING — next message redirects the conversation
                </div>
              )}

              {/* Image attachment preview */}
              {attachedImage && (
                <div className="flex items-center gap-2 px-4 pt-2">
                  <ImageIcon className="w-3.5 h-3.5 text-primary shrink-0" />
                  <span className="text-xs text-on-surface-variant truncate max-w-[180px]">{attachedImage.name}</span>
                  <button onClick={() => setAttachedImage(null)} className="text-on-surface-variant/50 hover:text-error shrink-0">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              {/* Textarea */}
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  !activeConversationId
                    ? 'Select or create a conversation…'
                    : voice.isListening
                    ? 'Listening…'
                    : 'Send a message'
                }
                disabled={isSending || !activeConversationId}
                rows={1}
                className={cn(
                  'w-full bg-transparent px-4 pt-3 pb-1 text-sm text-on-surface',
                  'resize-none outline-none placeholder:text-on-surface-variant/40',
                  'transition-colors leading-relaxed',
                  (isSending || !activeConversationId) && 'cursor-not-allowed',
                  voice.isListening && 'placeholder:text-error'
                )}
                style={{ minHeight: '44px', maxHeight: '168px' }}
              />

              {/* Bottom toolbar */}
              <div className="flex items-center justify-between px-3 pb-2.5 gap-2">
                {/* Left: mode toggles */}
                <div className="flex items-center gap-1">
                  {/* Model picker: Auto / Local / Claude */}
                  <div className="flex items-center rounded-lg border border-outline-variant/25 bg-surface-container/60 p-0.5 gap-0.5">
                    {(['auto', 'local', 'claude'] as const).map((m) => (
                      <button
                        key={m}
                        onClick={() => setForcedMode(m)}
                        title={m === 'auto' ? 'Auto-route (default)' : m === 'local' ? 'Force local model (Pepe)' : 'Force Claude'}
                        className={cn(
                          'px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors leading-tight',
                          forcedMode === m
                            ? m === 'local'
                              ? 'bg-emerald-500/20 text-emerald-600'
                              : m === 'claude'
                              ? 'bg-violet-500/20 text-violet-600'
                              : 'bg-surface-container-high text-on-surface'
                            : 'text-on-surface-variant/50 hover:text-on-surface'
                        )}
                      >
                        {m === 'auto' ? 'Auto' : m === 'local' ? '🏠 Local' : '☁ Claude'}
                      </button>
                    ))}
                  </div>

                  {/* Steer toggle */}
                  <IconToggle
                    on={isSteerMode}
                    onClick={() => setIsSteerMode((v) => !v)}
                    title={isSteerMode ? 'Cancel steer mode' : 'Steer — redirect the AI'}
                    onClass="text-amber-500 bg-amber-500/10"
                  >
                    <Navigation className="w-3.5 h-3.5" />
                  </IconToggle>

                  {/* Image attach (for MiniCPM-o multimodal) */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleImagePick}
                  />
                  <IconToggle
                    on={!!attachedImage}
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach image (MiniCPM-o vision)"
                    onClass="text-primary bg-primary/10"
                  >
                    <Paperclip className="w-3.5 h-3.5" />
                  </IconToggle>

                  {/* TTS toggle */}
                  <IconToggle
                    on={ttsEnabled}
                    onClick={() => { if (ttsEnabled && voice.isSpeaking) voice.stopSpeaking(); setTtsEnabled((v) => !v) }}
                    title={ttsEnabled ? 'Disable voice reply' : 'Speak AI replies aloud'}
                    onClass="text-primary bg-primary/10"
                  >
                    {ttsEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
                  </IconToggle>

                  {/* Voice selector — only shown when TTS is on */}
                  {ttsEnabled && voiceOptions.length > 0 && (
                    <select
                      value={selectedVoiceId}
                      onChange={(e) => setSelectedVoiceId(e.target.value)}
                      title="Select voice"
                      className={cn(
                        'text-[11px] bg-surface-container border border-outline-variant/30 rounded-lg',
                        'text-on-surface-variant px-2 py-1 outline-none cursor-pointer',
                        'hover:border-primary/40 transition-colors max-w-[120px] truncate'
                      )}
                    >
                      {voiceOptions.map((v) => (
                        <option key={v.id} value={v.id}>{v.name}</option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Right: mic + send/stop */}
                <div className="flex items-center gap-1.5">
                  {/* Mic */}
                  {voice.isSupported && (
                    <button
                      onClick={handleMicClick}
                      title={voice.isListening ? 'Stop listening' : 'Voice input'}
                      className={cn(
                        'p-1.5 rounded-lg transition-colors',
                        voice.isListening
                          ? 'text-error bg-error/10 animate-pulse'
                          : 'text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-container'
                      )}
                    >
                      {voice.isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                    </button>
                  )}

                  {/* Stop / Send */}
                  {isSending ? (
                    <button
                      onClick={handleStop}
                      title="Stop generating"
                      className="w-8 h-8 flex items-center justify-center rounded-full bg-error text-white hover:bg-error/80 transition-colors"
                    >
                      <StopCircle className="w-4 h-4" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleSend()}
                      disabled={!inputValue.trim() || !activeConversationId}
                      title="Send (Enter)"
                      className={cn(
                        'w-8 h-8 flex items-center justify-center rounded-full transition-colors',
                        inputValue.trim() && activeConversationId
                          ? isSteerMode
                            ? 'bg-amber-500 text-white hover:bg-amber-600'
                            : 'bg-primary text-white hover:bg-primary/80'
                          : 'bg-surface-container text-on-surface-variant/30 cursor-not-allowed'
                      )}
                    >
                      <ArrowUp className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Hint */}
            <p className="text-center text-[11px] text-on-surface-variant/35 mt-1.5">
              Enter to send · Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Small inline action button ────────────────────────────────────────────────
function MsgAction({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] text-on-surface-variant/50
                 hover:text-on-surface hover:bg-surface-container transition-colors"
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

// ── Icon toggle helper ────────────────────────────────────────────────────────
function IconToggle({
  on, onClick, title, onClass, children,
}: {
  on: boolean; onClick: () => void; title: string; onClass: string; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        'p-1.5 rounded-lg transition-colors text-xs font-medium',
        on
          ? onClass
          : 'text-on-surface-variant/50 hover:text-on-surface hover:bg-surface-container'
      )}
    >
      {children}
    </button>
  )
}

// ── Follow-up suggestion generator ───────────────────────────────────────────
function generateFollowUps(content: string): string[] {
  const low = content.toLowerCase()
  const hasCode     = content.includes('```') || (content.split('`').length - 1) >= 2
  const hasSteps    = /(\d+\.\s|\n-\s)/.test(content) && content.length > 200
  const hasError    = /\b(error|bug|fix|issue|fail|exception|crash|broken)\b/.test(low)
  const hasOptions  = /\b(option|alternative|approach|either|instead|or you can|you could also)\b/.test(low)
  const hasProcess  = /\b(step|process|procedure|workflow|sequence|first.*then|next)\b/.test(low)
  const isTech      = hasCode || /\b(function|class|api|database|server|deploy|install|config|import|module)\b/.test(low)
  const isExplainer = content.length > 400 && !hasCode
  const hasNumbers  = /\b(\d{2,}|percent|%|price|\$|cost|budget)\b/.test(low)

  const pool: string[] = []

  // Contextual suggestions — most specific first
  if (hasCode)    pool.push('Can you walk me through this code?', 'What happens if I change this?', 'Are there edge cases to handle?')
  if (hasError)   pool.push('What\'s the most common cause of this?', 'How do I prevent this in future?', 'Can you show a fixed version?')
  if (hasOptions) pool.push('Which option do you recommend and why?', 'What are the tradeoffs?', 'Can you compare these side by side?')
  if (hasProcess) pool.push('What comes after this?', 'What could go wrong at each step?', 'Can you give a real-world example?')
  if (hasNumbers) pool.push('How does this compare to industry averages?', 'What factors affect this most?')
  if (isTech)     pool.push('What are the best practices here?', 'Are there any gotchas to watch out for?')
  if (isExplainer)pool.push('Can you give me a simpler analogy?', 'What\'s the most important takeaway?')
  if (hasSteps)   pool.push('Can you condense this into bullet points?', 'Which step do people usually get wrong?')

  // Generic fallbacks
  const generic = [
    'Can you give me a concrete example?',
    'What should I do next?',
    'What are the alternatives?',
    'Can you expand on that?',
    'What\'s the most important thing to remember?',
    'How does this work in practice?',
  ]

  // De-dup and pick 3
  const seen = new Set<string>()
  const picks: string[] = []
  for (const s of [...pool, ...generic]) {
    if (!seen.has(s) && picks.length < 3) { seen.add(s); picks.push(s) }
  }
  return picks
}

// ── Empty state ───────────────────────────────────────────────────────────────
const PROMPT_SUGGESTIONS = [
  'Summarise what we discussed last time',
  'Help me debug some code',
  'Explain a concept simply',
  'Draft a quick message',
]

function EmptyState({ onPrompt }: { onPrompt: (p: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-6 text-center select-none">
      <div className="w-14 h-14 rounded-2xl bg-primary-container flex items-center justify-center shadow-sm">
        <Bot className="w-8 h-8 text-primary" />
      </div>
      <div>
        <h2 className="text-xl font-semibold text-on-surface mb-1">How can I help?</h2>
        <p className="text-sm text-on-surface-variant/70">Ask anything, or pick a suggestion below.</p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center max-w-md">
        {PROMPT_SUGGESTIONS.map((p) => (
          <button
            key={p}
            onClick={() => onPrompt(p)}
            className="px-3 py-1.5 rounded-full border border-outline-variant/30 text-xs text-on-surface-variant
                       hover:border-primary/40 hover:text-primary hover:bg-primary/5 transition-colors"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  )
}
