/**
 * CompanionView — Voice / Chat / Vision / Personality Surface
 *
 * Phase 2 enhancements:
 * - AvatarPresence with animated states
 * - Personality quick-switcher (sharp/creative/voice/thinking)
 * - Camera / image upload for vision queries
 * - Voice session toggle (wake-word mode)
 * - Tool policy enforcement (companion whitelist)
 * - Enhanced escalation with context packaging
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  ArrowUp, Mic, MicOff, StopCircle, Zap, Camera, X,
  Sparkles, ChevronDown, Maximize2, Minimize2, RefreshCw,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useWorkspaceStore, syncManager } from '@/store'
import { useAppStore } from '@/store/appStore'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { useVoice } from '@/hooks/useVoice'
import { AvatarPresence, type AvatarState } from '@/components/surface/AvatarPresence'
import { BackendSelector } from '@/components/surface/BackendSelector'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'
import { DocumentDropZone } from '@/components/shared/DocumentDropZone'
import api from '@/api/client'

// ── Types ──────────────────────────────────────────────────────────────────────

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: string
  imageUrl?: string   // preview for vision queries
}

interface PersonalityPreset {
  label: string
  model: string
  description: string
}

interface PersonalityData {
  active_preset: string
  presets: Record<string, PersonalityPreset>
}

// ── Voice config ───────────────────────────────────────────────────────────────

interface VoiceOption { id: string; name: string; lang: string }
interface ProviderOption { id: string; name: string; available: boolean }

async function loadVoiceMeta() {
  try {
    const res = await api.get('/api/voices')
    const d = res.data
    const provider = d?.tts?.active_provider || 'auto'
    const voiceId  = d?.tts?.active_voice || ''
    const allVoices: Record<string, VoiceOption[]> = d?.tts?.voices || {}
    const options: VoiceOption[] = allVoices[provider] || allVoices['kokoro'] || []
    const providers: ProviderOption[] = (d?.tts?.providers || []).filter((p: ProviderOption) => p.available)
    return { provider, voiceId: voiceId || options[0]?.id || 'bm_lewis', options, providers, allVoices }
  } catch {
    return { provider: 'auto', voiceId: 'bm_lewis', options: [] as VoiceOption[], providers: [] as ProviderOption[], allVoices: {} as Record<string, VoiceOption[]> }
  }
}

// ── Utilities ──────────────────────────────────────────────────────────────────

function useAutoHeight(value: string, minRows = 1, maxRows = 5) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    const lineH = parseInt(getComputedStyle(el).lineHeight) || 20
    el.style.height = `${Math.min(lineH * maxRows + 16, Math.max(lineH * minRows + 16, el.scrollHeight))}px`
  }, [value, minRows, maxRows])
  return ref
}

// ── Personality picker ─────────────────────────────────────────────────────────

function PersonalityPicker({ onSwitch }: { onSwitch: () => void }) {
  const [data, setData]   = useState<PersonalityData | null>(null)
  const [open, setOpen]   = useState(false)
  const [busy, setBusy]   = useState(false)
  const ref               = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get('/api/companion/personality').then((r) => setData(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const select = async (preset: string) => {
    setBusy(true)
    try {
      await api.put('/api/companion/personality', { preset })
      const r = await api.get('/api/companion/personality')
      setData(r.data)
      onSwitch()
      toast.success(`Personality: ${r.data.presets[preset]?.label}`)
    } catch { toast.error('Could not switch personality') }
    finally { setBusy(false); setOpen(false) }
  }

  if (!data) return null

  const active = data.presets[data.active_preset]

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg bg-surface-variant hover:bg-surface-container text-on-surface-variant border border-outline-variant/30 transition-colors"
      >
        <Sparkles className="w-3 h-3" />
        <span className="max-w-[80px] truncate">{active?.label ?? '…'}</span>
        <ChevronDown className={cn("w-3 h-3 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 w-64 bg-surface border border-outline-variant/30 rounded-xl shadow-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-outline-variant/10">
            <p className="text-xs font-semibold text-on-surface">Personality</p>
          </div>
          {Object.entries(data.presets).map(([key, preset]) => (
            <button
              key={key}
              onClick={() => select(key)}
              className={cn(
                "w-full text-left px-3 py-2.5 text-sm hover:bg-surface-variant/50 transition-colors",
                data.active_preset === key && "bg-primary/10"
              )}
            >
              <p className={cn("font-medium", data.active_preset === key ? "text-primary" : "text-on-surface")}>
                {preset.label} {data.active_preset === key && '✓'}
              </p>
              <p className="text-xs text-on-surface-variant/60 mt-0.5">{preset.description}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main view ──────────────────────────────────────────────────────────────────

export default function CompanionView() {
  const { activeWorkspaceId } = useWorkspaceStore()
  const { pendingDraftText, setPendingDraftText } = useAppStore()

  const [messages, setMessages]           = useState<Message[]>(() => {
    try {
      const saved = sessionStorage.getItem('companion_messages')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [input, setInput]                 = useState('')
  const [streaming, setStreaming]         = useState('')
  const [isSending, setIsSending]         = useState(false)
  const [ttsEnabled, setTtsEnabled]       = useState(true)
  const [activeConvId, setActiveConvId]   = useState<string | null>(null)
  const [voiceOptions, setVoiceOptions]   = useState<VoiceOption[]>([])
  const [selectedVoiceId, setSelectedVoiceId] = useState('bm_lewis')
  const [ttsProvider, setTtsProvider]     = useState('auto')
  const [providerOptions, setProviderOptions] = useState<ProviderOption[]>([])
  const [allVoices, setAllVoices]         = useState<Record<string, VoiceOption[]>>({})
  const [wakeMode, setWakeMode]           = useState(false)
  const [ambientMode, setAmbientMode]     = useState(false)
  const [workspaceAlert, setWsAlert]      = useState<string | null>(null)
  const [attachedImage, setAttachedImage] = useState<{ base64: string; url: string; name: string } | null>(null)

  const abortRef    = useRef<AbortController | null>(null)
  const bottomRef   = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useAutoHeight(input)

  useEffect(() => {
    try { sessionStorage.setItem('companion_messages', JSON.stringify(messages.slice(-50))) } catch {}
  }, [messages])

  const voice = useVoice({
    onTranscript: (text) => {
      setInput(text)
      // Auto-send after voice transcript — is_voice flag routes to Hermes3 fast-path
      setTimeout(() => handleSend(text, true), 300)
    },
    onError: () => {},
    voiceId:     selectedVoiceId,
    ttsProvider: ttsProvider,
  })

  // Load voice options on mount
  useEffect(() => {
    loadVoiceMeta().then((meta) => {
      setVoiceOptions(meta.options)
      setSelectedVoiceId(meta.voiceId)
      setTtsProvider(meta.provider)
      setProviderOptions(meta.providers)
      setAllVoices(meta.allVoices)
    })
  }, [])

  // Avatar state derived from voice + sending state
  const avatarState: AvatarState =
    voice.isListening ? 'listening'
    : voice.isSpeaking ? 'speaking'
    : isSending       ? 'thinking'
    : 'idle'

  // Inject from GuppyDrop folder
  useEffect(() => {
    if (pendingDraftText) {
      setInput(pendingDraftText)
      setPendingDraftText(null)
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }, [pendingDraftText, setPendingDraftText, textareaRef])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  useEffect(() => {
    if (!activeWorkspaceId) return
    syncManager
      .createConversation(activeWorkspaceId, `Companion ${new Date().toLocaleDateString()}`)
      .then((conv: any) => setActiveConvId(conv?.id ?? null))
      .catch(() => {})
  }, [activeWorkspaceId])

  // Subscribe to workspace SSE alerts for ambient mode
  useEffect(() => {
    if (!ambientMode) return
    const token = localStorage.getItem('accessToken') || ''
    let cancelled = false
    async function sub() {
      try {
        const res = await fetch('/api/surface/events', { headers: { Authorization: `Bearer ${token}` } })
        if (!res.body) return
        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = '', evType = ''
        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('event: ')) evType = line.slice(7).trim()
            else if (line.startsWith('data: ')) {
              try {
                const payload = JSON.parse(line.slice(6))
                if (evType === 'task_spawned' || evType === 'task_updated') {
                  const label = payload.title || payload.status || 'Workspace update'
                  setWsAlert(label)
                  if (ttsEnabled) voice.speak(label.slice(0, 120))
                  setTimeout(() => setWsAlert(null), 6000)
                }
              } catch { /* ignore */ }
              evType = ''
            }
          }
        }
      } catch { /* ignore */ }
    }
    sub()
    return () => { cancelled = true }
  }, [ambientMode, ttsEnabled, voice])

  // Wake word session toggle
  const toggleWakeMode = async () => {
    try {
      if (wakeMode) {
        await api.delete('/api/companion/voice/session')
        setWakeMode(false)
        toast.success('Wake word off')
      } else {
        await api.post('/api/companion/voice/session')
        setWakeMode(true)
        toast.success('Listening for "Hey Guppy"…')
      }
    } catch {
      toast.error('Could not toggle wake word mode')
    }
  }

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    if (voice.isSpeaking) voice.stopSpeaking()
    setStreaming('')
    setIsSending(false)
  }, [voice])

  const handleSend = useCallback(async (override?: string, isVoice = false) => {
    const text = override ?? input
    if (!text.trim() || isSending) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      ts: new Date().toISOString(),
      imageUrl: attachedImage?.url,
    }
    setMessages((m) => [...m, userMsg])
    if (!override) setInput('')
    const currentImage = attachedImage
    setAttachedImage(null)
    setIsSending(true)
    setStreaming('')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      let fullText = ''

      // Vision query path
      if (currentImage) {
        try {
          const form = new FormData()
          form.append('text', text)
          const blob = await fetch(currentImage.url).then((r) => r.blob())
          form.append('image', blob, currentImage.name)
          const res = await api.post('/api/companion/vision', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          fullText = res.data?.response ?? ''
        } catch {
          // Fall through to standard chat
        }
      }

      // Standard chat path (or fallback)
      if (!fullText && activeConvId) {
        await syncManager.addMessage(activeConvId, 'user', text)
        fullText = await syncManager.getAIResponse(
          activeConvId,
          text,
          'local',
          (token: string) => setStreaming((p) => p + token),
          controller.signal,
          (replaced: string) => setStreaming(replaced),
          () => {},
          currentImage?.base64,
          'companion',
          isVoice,
        )
      } else if (!fullText) {
        const res = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.getItem('accessToken') || ''}`,
          },
          body: JSON.stringify({ message: text, mode: 'local', surface: 'companion', is_voice: isVoice }),
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
            buf = lines.pop() ?? ''
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue
              const payload = line.slice(6).trim()
              if (payload === '[DONE]') break outer
              try {
                const ev = JSON.parse(payload)
                if (ev.tool_exec) {
                  setStreaming(`using ${ev.tool_exec}…`)
                } else if (ev.replace !== undefined) {
                  fullText = ev.replace
                  setStreaming(fullText)
                } else if (ev.token) {
                  fullText += ev.token
                  setStreaming(fullText)
                } else if (ev.done || ev.error) {
                  break outer
                }
              } catch { /* non-JSON SSE line */ }
            }
          }
        }
      }

      const finalText = fullText || streaming
      setMessages((m) => [...m, {
        id: crypto.randomUUID(), role: 'assistant', content: finalText, ts: new Date().toISOString(),
      }])
      setStreaming('')

      if (ttsEnabled && finalText) {
        voice.speak(finalText.slice(0, 800))
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setMessages((m) => [...m, {
          id: crypto.randomUUID(), role: 'assistant',
          content: '⚠ Something went wrong. Try again.', ts: new Date().toISOString(),
        }])
      }
    } finally {
      setStreaming('')
      setIsSending(false)
      abortRef.current = null
    }
  }, [input, isSending, activeConvId, ttsEnabled, voice, streaming, attachedImage])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleImageFile = (file: File) => {
    const url = URL.createObjectURL(file)
    const reader = new FileReader()
    reader.onload = (ev) => {
      const b64 = (ev.target?.result as string).split(',')[1] ?? ''
      setAttachedImage({ base64: b64, url, name: file.name })
    }
    reader.readAsDataURL(file)
  }

  const escalateToWorkspace = async (content: string) => {
    try {
      await api.post('/api/surface/spawn', {
        surface:     'workspace',
        title:       content.slice(0, 80),
        description: content,
        source:      'companion',
      })
      toast.success('Sent to Workspace')
    } catch {
      toast.error('Could not escalate to Workspace')
    }
  }

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">

      {/* Ambient mode overlay — fullscreen avatar + workspace alert */}
      <AnimatePresence>
        {ambientMode && (
          <motion.div
            key="ambient"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-surface flex flex-col items-center justify-center gap-6"
          >
            {/* Exit button */}
            <button
              onClick={() => setAmbientMode(false)}
              className="absolute top-4 right-4 p-2 rounded-xl hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors"
            >
              <Minimize2 className="w-5 h-5" />
            </button>

            {/* Giant avatar */}
            <AvatarPresence state={avatarState} size="lg" />

            {/* Wake mode status */}
            <p className={cn(
              "text-sm transition-colors",
              wakeMode ? "text-primary/70" : "text-on-surface-variant/30"
            )}>
              {wakeMode ? 'Listening for "Hey Guppy"' : 'Say something or type below'}
            </p>

            {/* Workspace alert banner */}
            <AnimatePresence>
              {workspaceAlert && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  className="absolute bottom-24 left-1/2 -translate-x-1/2 bg-secondary/20 border border-secondary/30 rounded-2xl px-5 py-3 text-sm text-secondary max-w-sm text-center"
                >
                  <Zap className="w-4 h-4 inline-block mr-1.5 mb-0.5" />
                  {workspaceAlert}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Minimal input in ambient mode */}
            <div className="absolute bottom-8 w-full max-w-md px-6">
              <div className="flex items-center gap-2 bg-surface-container rounded-2xl px-3 py-2 border border-outline-variant/20 shadow-lg">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                  placeholder="Type a message…"
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/40 resize-none outline-none leading-relaxed"
                />
                <button
                  onClick={voice.isListening ? voice.stopListening : voice.startListening}
                  className={cn(
                    "p-2 rounded-xl flex-shrink-0 transition-colors",
                    voice.isListening ? "bg-error text-white animate-pulse" : "text-on-surface-variant/50"
                  )}
                >
                  {voice.isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
                <button onClick={() => handleSend()} disabled={!input.trim()}
                  className="p-2 rounded-xl bg-primary text-on-primary disabled:opacity-30 transition-colors flex-shrink-0">
                  <ArrowUp className="w-4 h-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-outline-variant/20 flex-shrink-0">
        <div className="flex items-center gap-2">
          <PersonalityPicker onSwitch={() => {}} />
        </div>
        <div className="flex items-center gap-2">
          {/* Ambient mode toggle */}
          <button
            onClick={() => setAmbientMode(true)}
            className="p-1.5 rounded-lg text-on-surface-variant/40 hover:text-on-surface hover:bg-surface-variant transition-colors"
            title="Enter ambient mode"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          {/* Wake mode toggle */}
          <button
            onClick={toggleWakeMode}
            className={cn(
              "text-xs px-2.5 py-1 rounded-full border transition-colors",
              wakeMode
                ? "bg-primary/10 border-primary/30 text-primary"
                : "border-outline-variant/20 text-on-surface-variant/50 hover:text-on-surface-variant"
            )}
            title="Toggle wake-word mode"
          >
            {wakeMode ? '🎙 Wake on' : '🎙 Wake off'}
          </button>
          <SurfaceStatusBar surface="workspace" compact label="Workspace" />
          <BackendSelector surface="companion" compact />
          <button
            onClick={() => { setMessages([]); try { sessionStorage.removeItem('companion_messages') } catch {} }}
            title="Clear conversation (Escape)"
            className="w-7 h-7 flex items-center justify-center rounded-lg text-on-surface-variant/40 hover:text-on-surface-variant hover:bg-surface-variant/50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Avatar — shown when no messages or always-visible */}
      <div className={cn(
        "flex-shrink-0 flex justify-center transition-all duration-500",
        messages.length === 0 ? "pt-12 pb-6" : "pt-4 pb-2"
      )}>
        <AvatarPresence
          state={avatarState}
          size={messages.length === 0 ? 'lg' : 'sm'}
        />
      </div>

      {/* Empty state prompt */}
      {messages.length === 0 && !isSending && (
        <div className="flex-shrink-0 text-center px-8 pb-6">
          <p className="text-sm text-on-surface-variant/60">
            Talk, type, or drop an image.
          </p>
          <p className="text-xs text-on-surface-variant/40 mt-1">
            Shift+Enter for new line · voice sends automatically
          </p>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-3 space-y-3">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={cn("flex gap-3", msg.role === 'user' ? "justify-end" : "justify-start")}
            >
              <div className={cn(
                "group max-w-[78%] rounded-2xl px-4 py-2.5 text-sm",
                msg.role === 'user'
                  ? "bg-primary text-on-primary rounded-br-sm"
                  : "bg-surface-container text-on-surface rounded-bl-sm"
              )}>
                {msg.imageUrl && (
                  <img src={msg.imageUrl} alt="attached" className="rounded-lg mb-2 max-h-48 object-cover" />
                )}
                {msg.role === 'assistant'
                  ? <MarkdownMessage content={msg.content} />
                  : <p className="whitespace-pre-wrap">{msg.content}</p>
                }
                {msg.role === 'assistant' && (
                  <button
                    onClick={() => escalateToWorkspace(msg.content)}
                    className="mt-2 flex items-center gap-1 text-xs text-on-surface-variant/50 hover:text-primary transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Zap className="w-3 h-3" />
                    Escalate to Workspace
                  </button>
                )}
              </div>
            </motion.div>
          ))}

          {streaming && (
            <motion.div key="streaming" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 justify-start">
              <div className="max-w-[78%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm bg-surface-container">
                <MarkdownMessage content={streaming} />
                <span className="inline-block w-1.5 h-3.5 bg-primary/60 ml-0.5 animate-pulse rounded-sm" />
              </div>
            </motion.div>
          )}

          {isSending && !streaming && (
            <motion.div key="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex gap-3 justify-start">
              <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-surface-container">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-1.5 h-1.5 bg-on-surface-variant/40 rounded-full animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Attached image preview */}
      <AnimatePresence>
        {attachedImage && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex-shrink-0 px-5 pb-1"
          >
            <div className="relative inline-block">
              <img src={attachedImage.url} alt="preview" className="h-16 rounded-xl object-cover border border-outline-variant/30" />
              <button
                onClick={() => setAttachedImage(null)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-error text-white flex items-center justify-center"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input bar */}
      <div className="flex-shrink-0 px-5 pb-5 pt-2 border-t border-outline-variant/10">
        <div className="flex items-end gap-2 bg-surface-container rounded-2xl px-3 py-2 shadow-sm border border-outline-variant/20 focus-within:border-primary/40 transition-colors">
          {/* Image attachment */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImageFile(f) }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "p-2 rounded-xl transition-colors flex-shrink-0",
              attachedImage
                ? "bg-primary/20 text-primary"
                : "text-on-surface-variant/50 hover:bg-surface-variant hover:text-on-surface"
            )}
            title="Attach image for vision"
          >
            <Camera className="w-4 h-4" />
          </button>

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Talk to Guppy…"
            rows={1}
            className="flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/50 resize-none outline-none py-1.5 leading-relaxed"
          />

          {/* Voice */}
          <button
            onClick={voice.isListening ? voice.stopListening : voice.startListening}
            disabled={isSending}
            className={cn(
              "p-2 rounded-xl transition-all duration-200 flex-shrink-0",
              voice.isListening
                ? "bg-error text-white animate-pulse"
                : "text-on-surface-variant/50 hover:bg-surface-variant hover:text-on-surface"
            )}
            title={voice.isListening ? 'Stop' : 'Push to talk'}
          >
            {voice.isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          {/* Send / Stop */}
          {isSending ? (
            <button onClick={handleStop}
              className="p-2 rounded-xl bg-error/10 text-error hover:bg-error/20 transition-colors flex-shrink-0">
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button onClick={() => handleSend()} disabled={!input.trim() && !attachedImage}
              className="p-2 rounded-xl bg-primary text-on-primary disabled:opacity-30 hover:bg-primary/90 transition-colors flex-shrink-0">
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 mt-2 px-1 flex-wrap">
          <button onClick={() => { if (ttsEnabled && voice.isSpeaking) voice.stopSpeaking(); setTtsEnabled(!ttsEnabled) }}
            className={cn("text-xs px-2 py-0.5 rounded-full transition-colors flex-shrink-0",
              ttsEnabled ? "bg-primary/10 text-primary" : "text-on-surface-variant/40 hover:text-on-surface-variant"
            )}>
            {ttsEnabled ? '🔊 Voice on' : '🔇 Voice off'}
          </button>

          {/* Provider picker */}
          {providerOptions.length > 1 && (
            <select
              value={ttsProvider}
              onChange={(e) => {
                const p = e.target.value
                setTtsProvider(p)
                const pVoices = allVoices[p] || []
                setVoiceOptions(pVoices)
                if (pVoices.length > 0) setSelectedVoiceId(pVoices[0].id)
                api.put('/api/voices/settings', { tts_provider: p }).catch(() => {})
              }}
              title="TTS provider"
              className="text-[11px] bg-surface-container border border-outline-variant/30 rounded-lg text-on-surface-variant px-2 py-0.5 outline-none cursor-pointer hover:border-primary/40 transition-colors"
            >
              {providerOptions.map((p) => (
                <option key={p.id} value={p.id}>{p.name.replace(/ \(.*\)/, '')}</option>
              ))}
            </select>
          )}

          {/* Voice picker */}
          {voiceOptions.length > 0 && (
            <select
              value={selectedVoiceId}
              onChange={(e) => {
                setSelectedVoiceId(e.target.value)
                api.put('/api/voices/settings', { tts_voice: e.target.value }).catch(() => {})
              }}
              title="Select voice"
              className="text-[11px] bg-surface-container border border-outline-variant/30 rounded-lg text-on-surface-variant px-2 py-0.5 outline-none cursor-pointer hover:border-primary/40 transition-colors max-w-[150px] truncate"
            >
              {voiceOptions.map((v) => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </select>
          )}

          <button onClick={() => { setMessages([]); try { sessionStorage.removeItem('companion_messages') } catch {} }}
            className="text-xs text-on-surface-variant/40 hover:text-on-surface-variant transition-colors ml-auto">
            Clear
          </button>
        </div>
        {/* Document drop zone — compact, collapsed by default */}
        <DocumentDropZone surface="companion" compact className="mt-2 px-1" />
      </div>
    </div>
  )
}
