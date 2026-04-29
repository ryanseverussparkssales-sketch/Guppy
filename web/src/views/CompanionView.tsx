/**
 * CompanionView — Voice / Chat / Personality Surface
 *
 * The "face" of Guppy. Voice-first, minimal, uncensored personality.
 * No conversation list sidebar — one focused exchange at a time.
 * Can escalate tasks to Workspace via /api/surface/spawn.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { ArrowUp, Mic, MicOff, StopCircle, Zap } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { useWorkspaceStore, syncManager } from '@/store'
import { useAppStore } from '@/store/appStore'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { useVoice } from '@/hooks/useVoice'
import api from '@/api/client'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'
import { BackendSelector } from '@/components/surface/BackendSelector'

function useAutoHeight(value: string, minRows = 1, maxRows = 5) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    const lineH = parseInt(getComputedStyle(el).lineHeight) || 20
    const min = lineH * minRows + 16
    const max = lineH * maxRows + 16
    el.style.height = `${Math.min(max, Math.max(min, el.scrollHeight))}px`
  }, [value, minRows, maxRows])
  return ref
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: string
}

export default function CompanionView() {
  const { activeWorkspaceId } = useWorkspaceStore()
  const { pendingDraftText, setPendingDraftText } = useAppStore()

  const [messages, setMessages]           = useState<Message[]>([])
  const [input, setInput]                 = useState('')
  const [streaming, setStreaming]         = useState('')
  const [isSending, setIsSending]         = useState(false)
  const [ttsEnabled, setTtsEnabled]       = useState(true)
  const [activeConvId, setActiveConvId]   = useState<string | null>(null)
  const [escalating, setEscalating]       = useState<string | null>(null)  // message id being escalated

  const abortRef   = useRef<AbortController | null>(null)
  const bottomRef  = useRef<HTMLDivElement>(null)
  const textareaRef = useAutoHeight(input)

  // Voice hook
  const voice = useVoice({
    onTranscript: (text) => setInput(text),
    onError: () => {},
    voiceId: 'bm_lewis',
    ttsProvider: 'auto',
  })

  // Inject from drop folder
  useEffect(() => {
    if (pendingDraftText) {
      setInput(pendingDraftText)
      setPendingDraftText(null)
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }, [pendingDraftText, setPendingDraftText, textareaRef])

  // Scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  // Create or reuse a conversation for this session
  useEffect(() => {
    if (!activeWorkspaceId) return
    syncManager
      .createConversation(activeWorkspaceId, `Companion ${new Date().toLocaleDateString()}`)
      .then((conv: any) => setActiveConvId(conv?.id ?? null))
      .catch(() => {})
  }, [activeWorkspaceId])

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    if (voice.isSpeaking) voice.stopSpeaking()
    setStreaming('')
    setIsSending(false)
  }, [voice])

  const handleSend = useCallback(async (override?: string) => {
    const text = override ?? input
    if (!text.trim() || isSending) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      ts: new Date().toISOString(),
    }
    setMessages((m) => [...m, userMsg])
    if (!override) setInput('')
    setIsSending(true)
    setStreaming('')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      // If we have a proper conversation, use syncManager
      let fullText = ''
      if (activeConvId) {
        await syncManager.addMessage(activeConvId, 'user', text)
        fullText = await syncManager.getAIResponse(
          activeConvId,
          text,
          'local',  // companion always uses local backend
          (token: string) => setStreaming((p) => p + token),
          controller.signal,
          (replaced: string) => setStreaming(replaced),
          () => {},
        )
      } else {
        // Fallback: direct API call
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.getItem('accessToken') || ''}`,
          },
          body: JSON.stringify({ message: text, mode: 'local', surface: 'companion' }),
          signal: controller.signal,
        })
        if (res.body) {
          const reader = res.body.getReader()
          const dec = new TextDecoder()
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            const chunk = dec.decode(value, { stream: true })
            fullText += chunk
            setStreaming(fullText)
          }
        }
      }

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: fullText || streaming,
        ts: new Date().toISOString(),
      }
      setMessages((m) => [...m, assistantMsg])
      setStreaming('')

      // TTS the response
      if (ttsEnabled && fullText) {
        voice.speak(fullText.slice(0, 800))  // cap for speed
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setMessages((m) => [...m, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '⚠ Something went wrong. Try again.',
          ts: new Date().toISOString(),
        }])
      }
    } finally {
      setStreaming('')
      setIsSending(false)
      abortRef.current = null
    }
  }, [input, isSending, activeConvId, ttsEnabled, voice, streaming])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const escalateToWorkspace = async (content: string) => {
    const msgId = crypto.randomUUID()
    setEscalating(msgId)
    try {
      await api.post('/api/surface/spawn', {
        surface: 'workspace',
        title: content.slice(0, 80),
        description: content,
        source: 'companion',
      })
      // Visual feedback — briefly show escalated state
      setTimeout(() => setEscalating(null), 2000)
    } catch {
      setEscalating(null)
    }
  }

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-outline-variant/20 flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* Avatar orb */}
          <div className={cn(
            "w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300",
            voice.isSpeaking
              ? "bg-primary animate-pulse shadow-lg shadow-primary/30"
              : voice.isListening
              ? "bg-error/80 animate-pulse"
              : isSending
              ? "bg-secondary/70 animate-pulse"
              : "bg-primary/20"
          )}>
            <span className="text-base font-bold text-primary">G</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-on-surface leading-none">Companion</h1>
            <p className="text-xs text-on-surface-variant mt-0.5">
              {voice.isSpeaking ? 'Speaking…' : voice.isListening ? 'Listening…' : isSending ? 'Thinking…' : 'Ready'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <BackendSelector surface="companion" compact />
          <SurfaceStatusBar surface="workspace" compact label="Workspace" />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-4 space-y-4">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={cn(
                "flex gap-3",
                msg.role === 'user' ? "justify-end" : "justify-start"
              )}
            >
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-bold text-primary">G</span>
                </div>
              )}
              <div className={cn(
                "group max-w-[75%] rounded-2xl px-4 py-2.5 text-sm",
                msg.role === 'user'
                  ? "bg-primary text-on-primary rounded-br-sm"
                  : "bg-surface-container text-on-surface rounded-bl-sm"
              )}>
                {msg.role === 'assistant'
                  ? <MarkdownMessage content={msg.content} />
                  : <p className="whitespace-pre-wrap">{msg.content}</p>
                }
                {/* Escalate button on assistant messages */}
                {msg.role === 'assistant' && (
                  <button
                    onClick={() => escalateToWorkspace(msg.content)}
                    className={cn(
                      "mt-2 flex items-center gap-1 text-xs text-on-surface-variant/60 hover:text-primary transition-colors opacity-0 group-hover:opacity-100",
                      escalating === msg.id && "opacity-100 text-primary"
                    )}
                  >
                    <Zap className="w-3 h-3" />
                    {escalating === msg.id ? 'Sent to Workspace ✓' : 'Escalate to Workspace'}
                  </button>
                )}
              </div>
            </motion.div>
          ))}

          {/* Streaming */}
          {streaming && (
            <motion.div
              key="streaming"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 justify-start"
            >
              <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-bold text-primary">G</span>
              </div>
              <div className="max-w-[75%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm bg-surface-container text-on-surface">
                <MarkdownMessage content={streaming} />
                <span className="inline-block w-1.5 h-3.5 bg-primary/60 ml-0.5 animate-pulse rounded-sm" />
              </div>
            </motion.div>
          )}

          {/* Thinking dots when no streaming yet */}
          {isSending && !streaming && (
            <motion.div
              key="thinking"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-3 justify-start"
            >
              <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-primary">G</span>
              </div>
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

      {/* Input bar */}
      <div className="flex-shrink-0 px-6 pb-6 pt-3 border-t border-outline-variant/10">
        <div className="flex items-end gap-2 bg-surface-container rounded-2xl px-3 py-2 shadow-sm border border-outline-variant/20 focus-within:border-primary/40 transition-colors">
          {/* Voice button */}
          <button
            onClick={voice.isListening ? voice.stopListening : voice.startListening}
            disabled={isSending}
            className={cn(
              "p-2 rounded-xl transition-all duration-200 flex-shrink-0",
              voice.isListening
                ? "bg-error text-white animate-pulse"
                : "text-on-surface-variant hover:bg-surface-variant hover:text-on-surface"
            )}
            title={voice.isListening ? 'Stop listening' : 'Push to talk'}
          >
            {voice.isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
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

          {isSending ? (
            <button
              onClick={handleStop}
              className="p-2 rounded-xl bg-error/10 text-error hover:bg-error/20 transition-colors flex-shrink-0"
            >
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              className="p-2 rounded-xl bg-primary text-on-primary disabled:opacity-30 hover:bg-primary/90 transition-colors flex-shrink-0"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Quick actions row */}
        <div className="flex items-center gap-3 mt-2 px-1">
          <button
            onClick={() => setTtsEnabled(!ttsEnabled)}
            className={cn(
              "text-xs px-2 py-0.5 rounded-full transition-colors",
              ttsEnabled
                ? "bg-primary/10 text-primary"
                : "text-on-surface-variant/50 hover:text-on-surface-variant"
            )}
          >
            {ttsEnabled ? '🔊 Voice on' : '🔇 Voice off'}
          </button>
          <button
            onClick={() => setMessages([])}
            className="text-xs text-on-surface-variant/40 hover:text-on-surface-variant transition-colors"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  )
}
