/**
 * CodespaceView — Code Sandbox & Self-Triage Surface
 *
 * Code-focused chat with syntax highlighting. Backend defaults to guppy-code / hermes4.
 * Phase 1: clean code chat with backend selector and surface status.
 * Phase 4 will add: Docker sandboxes, self-triage panel, project scaffolding.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { ArrowUp, StopCircle, Code2, Terminal, FolderCog, Braces } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { useWorkspaceStore, syncManager } from '@/store'
import { useAppStore } from '@/store/appStore'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { BackendSelector } from '@/components/surface/BackendSelector'
import { SurfaceStatusBar } from '@/components/surface/SurfaceStatusBar'

function useAutoHeight(value: string, minRows = 3, maxRows = 12) {
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

// Quick-action prompts surfaced as buttons
const QUICK_PROMPTS = [
  { icon: <Code2 className="w-3.5 h-3.5" />, label: 'Review this code', prompt: 'Review the following code for bugs, performance issues, and style:\n\n```\n\n```' },
  { icon: <Terminal className="w-3.5 h-3.5" />, label: 'Write a script', prompt: 'Write a Python script that ' },
  { icon: <FolderCog className="w-3.5 h-3.5" />, label: 'Scaffold project', prompt: 'Scaffold a new project structure for: ' },
  { icon: <Braces className="w-3.5 h-3.5" />, label: 'Explain code', prompt: 'Explain this code step by step:\n\n```\n\n```' },
]

export default function CodespaceView() {
  const { activeWorkspaceId } = useWorkspaceStore()
  const { pendingDraftText, setPendingDraftText } = useAppStore()

  const [messages, setMessages]         = useState<Message[]>([])
  const [input, setInput]               = useState('')
  const [streaming, setStreaming]       = useState('')
  const [isSending, setIsSending]       = useState(false)
  const [activeConvId, setActiveConvId] = useState<string | null>(null)

  const abortRef    = useRef<AbortController | null>(null)
  const bottomRef   = useRef<HTMLDivElement>(null)
  const textareaRef = useAutoHeight(input)

  // Inject from drop folder
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
      .createConversation(activeWorkspaceId, `Code ${new Date().toLocaleDateString()}`)
      .then((conv: any) => setActiveConvId(conv?.id ?? null))
      .catch(() => {})
  }, [activeWorkspaceId])

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming('')
    setIsSending(false)
  }, [])

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
      let fullText = ''
      if (activeConvId) {
        await syncManager.addMessage(activeConvId, 'user', text)
        fullText = await syncManager.getAIResponse(
          activeConvId,
          text,
          'code',   // codespace mode
          (token: string) => setStreaming((p) => p + token),
          controller.signal,
          (replaced: string) => setStreaming(replaced),
          () => {},
        )
      } else {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.getItem('accessToken') || ''}`,
          },
          body: JSON.stringify({ message: text, mode: 'code', surface: 'codespace' }),
          signal: controller.signal,
        })
        if (res.body) {
          const reader = res.body.getReader()
          const dec = new TextDecoder()
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            fullText += dec.decode(value, { stream: true })
            setStreaming(fullText)
          }
        }
      }

      setMessages((m) => [...m, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: fullText || streaming,
        ts: new Date().toISOString(),
      }])
      setStreaming('')
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setMessages((m) => [...m, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '⚠ Something went wrong.',
          ts: new Date().toISOString(),
        }])
      }
    } finally {
      setStreaming('')
      setIsSending(false)
      abortRef.current = null
    }
  }, [input, isSending, activeConvId, streaming])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full bg-surface text-on-surface">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-outline-variant/20 flex-shrink-0 bg-surface-container-low/50">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-tertiary/20 flex items-center justify-center">
            <Code2 className="w-3.5 h-3.5 text-tertiary" />
          </div>
          <h1 className="text-sm font-semibold text-on-surface">Codespace</h1>
          <span className="text-xs text-on-surface-variant/50 bg-surface-variant px-2 py-0.5 rounded-full">
            Ctrl+Enter to send
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SurfaceStatusBar surface="workspace" compact label="Workspace" />
          <BackendSelector surface="codespace" compact />
        </div>
      </div>

      {/* Quick prompts — shown when no messages yet */}
      {messages.length === 0 && !isSending && (
        <div className="flex-shrink-0 px-6 pt-8 pb-4">
          <p className="text-sm text-on-surface-variant/60 mb-4 text-center">
            Code-focused. Full context. No shortcuts.
          </p>
          <div className="grid grid-cols-2 gap-2 max-w-lg mx-auto">
            {QUICK_PROMPTS.map((qp) => (
              <button
                key={qp.label}
                onClick={() => setInput(qp.prompt)}
                className="flex items-center gap-2 px-3 py-2.5 text-sm text-left rounded-xl border border-outline-variant/30 hover:border-primary/30 hover:bg-primary/5 text-on-surface-variant transition-colors"
              >
                <span className="text-on-surface-variant/60">{qp.icon}</span>
                {qp.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-4 space-y-4">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "flex gap-3",
                msg.role === 'user' ? "justify-end" : "justify-start"
              )}
            >
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-tertiary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Code2 className="w-3.5 h-3.5 text-tertiary" />
                </div>
              )}
              <div className={cn(
                "max-w-[85%] rounded-2xl px-4 py-3 text-sm",
                msg.role === 'user'
                  ? "bg-primary text-on-primary rounded-br-sm font-mono text-xs"
                  : "bg-surface-container text-on-surface rounded-bl-sm"
              )}>
                {msg.role === 'assistant'
                  ? <MarkdownMessage content={msg.content} />
                  : <pre className="whitespace-pre-wrap leading-relaxed">{msg.content}</pre>
                }
              </div>
            </motion.div>
          ))}

          {streaming && (
            <motion.div
              key="streaming"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 justify-start"
            >
              <div className="w-7 h-7 rounded-lg bg-tertiary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Code2 className="w-3.5 h-3.5 text-tertiary" />
              </div>
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-3 text-sm bg-surface-container text-on-surface">
                <MarkdownMessage content={streaming} />
                <span className="inline-block w-1.5 h-3.5 bg-tertiary/60 ml-0.5 animate-pulse rounded-sm" />
              </div>
            </motion.div>
          )}

          {isSending && !streaming && (
            <motion.div
              key="thinking"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-3 justify-start"
            >
              <div className="w-7 h-7 rounded-lg bg-tertiary/20 flex items-center justify-center flex-shrink-0">
                <Code2 className="w-3.5 h-3.5 text-tertiary" />
              </div>
              <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-surface-container">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-1.5 h-1.5 bg-tertiary/40 rounded-full animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input — code-friendly: larger, monospace, Ctrl+Enter to send */}
      <div className="flex-shrink-0 px-6 pb-6 pt-3 border-t border-outline-variant/10">
        <div className="flex items-end gap-2 bg-surface-container rounded-2xl px-3 py-2 shadow-sm border border-outline-variant/20 focus-within:border-tertiary/40 transition-colors">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write code, ask technical questions, paste snippets… (Ctrl+Enter to send)"
            rows={3}
            className="flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/40 resize-none outline-none py-1.5 leading-relaxed font-mono"
          />
          {isSending ? (
            <button
              onClick={handleStop}
              className="p-2 mb-1 rounded-xl bg-error/10 text-error hover:bg-error/20 transition-colors flex-shrink-0"
            >
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              className="p-2 mb-1 rounded-xl bg-tertiary text-on-tertiary disabled:opacity-30 hover:bg-tertiary/90 transition-colors flex-shrink-0"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-3 mt-2 px-1">
          <button
            onClick={() => setMessages([])}
            className="text-xs text-on-surface-variant/40 hover:text-on-surface-variant transition-colors"
          >
            Clear session
          </button>
          <span className="text-xs text-on-surface-variant/30">Docker sandboxes coming in Phase 4</span>
        </div>
      </div>
    </div>
  )
}
