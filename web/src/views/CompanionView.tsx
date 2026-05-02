/**
 * CompanionView — Personality-first voice + chat surface
 *
 * Layout: large avatar orb (center) | personality picker | chat area | input bar
 * Voice: mic STT → send → TTS speak. Wake-word toggle calls /api/companion/voice/session.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic, MicOff, Volume2, VolumeX, StopCircle, ArrowUp,
  Radio, RadioTower, RefreshCw,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { AvatarPresence, type AvatarState } from '@/components/surface/AvatarPresence'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'
import { useVoice } from '@/hooks/useVoice'
import api from '../api/client'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Preset { key: string; label: string; description: string }
interface Message { id: string; role: 'user' | 'assistant'; content: string }

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
  const [presets, setPresets]               = useState<Preset[]>([])
  const [activePreset, setActivePreset]     = useState('sharp')
  const [presetLoading, setPresetLoading]   = useState(false)
  const [avatarState, setAvatarState]       = useState<AvatarState>('idle')

  const abortRef  = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useAutoHeight(input)

  const voice = useVoice({
    onTranscript: (text) => { setInput((prev) => prev + text) },
    onError: () => {},
  })

  // Sync avatar state
  useEffect(() => {
    if (voice.isListening)    setAvatarState('listening')
    else if (isSending)        setAvatarState('thinking')
    else if (voice.isSpeaking) setAvatarState('speaking')
    else                       setAvatarState('idle')
  }, [voice.isListening, isSending, voice.isSpeaking])

  // Scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  // Load personality presets on mount; rehydrate session if one exists
  useEffect(() => {
    api.get('/api/companion/personality').then((r) => {
      const data = r.data
      const raw = data.presets || {}
      const list: Preset[] = Object.entries(raw).map(([key, v]: any) => ({
        key, label: v.label || key, description: v.description || '',
      }))
      setPresets(list)
      setActivePreset(data.active || 'sharp')
    }).catch(() => {})

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

  const switchPreset = useCallback(async (key: string) => {
    if (key === activePreset || presetLoading) return
    setPresetLoading(true)
    try {
      await api.put('/api/companion/personality', { preset: key })
      setActivePreset(key)
    } catch {}
    setPresetLoading(false)
  }, [activePreset, presetLoading])

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
  }, [voice])

  const handleSend = useCallback(async (override?: string) => {
    const text = (override ?? input).trim()
    if (!text || isSending) return

    // Ensure a session ID exists before sending; persist it for rehydration
    let currentSessionId = sessionId
    if (!currentSessionId) {
      currentSessionId = crypto.randomUUID()
      setSessionId(currentSessionId)
      sessionStorage.setItem('companion_session_id', currentSessionId)
    }

    setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'user', content: text }])
    if (!override) setInput('')
    setIsSending(true)
    setStreaming('')

    const controller = new AbortController()
    abortRef.current = controller

    let fullText = ''
    try {
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
                // Companion non-tool path: full response delivered as one replace event
                fullText = evt.replace
                setStreaming(fullText)
                if (ttsEnabled) voice.speak(fullText)
              } else if (evt.token != null) {
                // Tool-call pass-2 streaming tokens
                fullText += evt.token
                setStreaming(fullText)
                if (ttsEnabled) voice.speakQueued(evt.token)
              }
              // evt.tool_exec: ignore status events (could show a toast later)
            } catch { /* non-JSON line, skip */ }
          }
        }
      }

      setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', content: fullText || streaming }])
      setStreaming('')
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: 'assistant', content: '⚠ Something went wrong.' }])
      }
    } finally {
      setStreaming('')
      setIsSending(false)
      abortRef.current = null
    }
  }, [input, isSending, sessionId, streaming, ttsEnabled, voice])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleMicClick = useCallback(() => {
    if (voice.isListening) voice.stopListening()
    else voice.startListening()
  }, [voice])

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-outline-variant/20 flex-shrink-0 bg-surface-container-low/50">
        <div className="flex items-center gap-3">
          <AvatarPresence state={avatarState} size="sm" className="!gap-0" />
          <h1 className="text-sm font-semibold text-on-surface">Companion</h1>
        </div>
        <div className="flex items-center gap-2">
          <SurfaceStatusBar surface="workspace" compact label="Workspace" />
          <SurfaceStatusBar surface="codespace" compact label="Codespace" />
          {/* Wake-word toggle */}
          <button
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

      {/* Avatar + personality picker */}
      <div className="flex flex-col items-center pt-6 pb-3 flex-shrink-0 gap-4">
        <AvatarPresence state={avatarState} size="lg" />
        {/* Personality pills */}
        <div className="flex flex-wrap justify-center gap-1.5 px-4">
          {presets.map((p) => (
            <button
              key={p.key}
              onClick={() => switchPreset(p.key)}
              disabled={presetLoading}
              title={p.description}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-colors border',
                activePreset === p.key
                  ? 'bg-primary/15 border-primary/30 text-primary'
                  : 'bg-surface-container border-outline-variant/25 text-on-surface-variant hover:border-primary/20 hover:text-on-surface',
                presetLoading && 'opacity-50 cursor-not-allowed'
              )}
            >
              {p.label.split(' ')[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-2 space-y-4">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              <div className={cn(
                'max-w-[85%] rounded-2xl px-4 py-3 text-sm',
                msg.role === 'user'
                  ? 'bg-primary text-on-primary rounded-br-sm'
                  : 'bg-surface-container text-on-surface rounded-bl-sm',
              )}>
                {msg.role === 'assistant'
                  ? <MarkdownMessage content={msg.content} />
                  : <span className="leading-relaxed">{msg.content}</span>}
              </div>
            </motion.div>
          ))}

          {streaming && (
            <motion.div key="streaming" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-3 text-sm bg-surface-container text-on-surface">
                <MarkdownMessage content={streaming} />
                <span className="inline-block w-1.5 h-3 bg-primary/50 ml-0.5 animate-pulse rounded-sm" />
              </div>
            </motion.div>
          )}

          {isSending && !streaming && (
            <motion.div key="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-surface-container">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 px-4 pb-5 pt-3 border-t border-outline-variant/10">
        <div className="flex items-end gap-2 bg-surface-container rounded-2xl px-3 py-2 border border-outline-variant/20 focus-within:border-primary/40 transition-colors">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={voice.isListening ? 'Listening…' : 'Say something or type…'}
            rows={1}
            className={cn(
              'flex-1 bg-transparent text-sm text-on-surface resize-none outline-none py-1.5 leading-relaxed',
              'placeholder:text-on-surface-variant/40',
              voice.isListening && 'placeholder:text-error'
            )}
          />

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

          {/* Send / Stop */}
          {isSending ? (
            <button type="button" onClick={handleStop}
              className="p-2 mb-1 rounded-xl bg-error/10 text-error hover:bg-error/20 transition-colors flex-shrink-0">
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button type="button" onClick={() => handleSend()}
              disabled={!input.trim()}
              className="p-2 mb-1 rounded-xl bg-primary text-on-primary disabled:opacity-30 hover:bg-primary/90 transition-colors flex-shrink-0">
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
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
    </div>
  )
}
