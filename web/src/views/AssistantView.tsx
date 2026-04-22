import { useState, useRef, useEffect } from 'react'
import { Send, Mic, Plus, Bot, User, Copy, Check, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import api from '../api/client'

/**
 * Chat message interface
 * 
 * BACKEND INTEGRATION:
 * - Messages are sent via POST /api/chat
 * - Request: { message: string, mode: string }
 * - Response: { response: string, source?: string }
 */
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  source?: string
  timestamp: Date
}

const MODES = [
  { value: 'auto', label: 'Auto', description: 'Automatically select best model' },
  { value: 'claude', label: 'Claude', description: 'Anthropic Claude' },
  { value: 'openai', label: 'OpenAI', description: 'GPT-4 / GPT-3.5' },
  { value: 'google', label: 'Google', description: 'Gemini' },
  { value: 'local', label: 'Local', description: 'Local LLM' },
  { value: 'code', label: 'Code', description: 'Optimized for coding' },
]

const SUGGESTIONS = [
  { text: 'What can you help me with?', icon: '?' },
  { text: 'Help me write some code', icon: '</>' },
  { text: 'Explain a concept to me', icon: '?' },
  { text: 'Analyze this data', icon: '#' },
]

/**
 * AssistantView - Main chat interface for Guppy AI assistant
 * 
 * BACKEND INTEGRATION:
 * - POST /api/chat - Send messages and receive responses
 * - WebSocket /ws/chat - For streaming responses (TODO)
 * - The `mode` parameter controls which LLM backend to use
 */
export default function AssistantView() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [mode, setMode] = useState('auto')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  /**
   * BACKEND: POST /api/chat
   * Request body: { message: string, mode: string }
   * Response: { response: string, source?: string }
   */
  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await api.post('/chat', { message: text, mode })
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response || response.data.message || 'No response',
        source: response.data.source,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (error: unknown) {
      console.error('Failed to send message:', error)
      let errorContent = 'Sorry, I encountered an error processing your request.'
      const axiosError = error as { response?: { status?: number; data?: { detail?: string } } }
      if (axiosError.response?.status === 503) {
        errorContent = 'Guppy core is not available. Please ensure all services are properly configured.'
      } else if (axiosError.response?.data?.detail) {
        errorContent = `Error: ${axiosError.response.data.detail}`
      }
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 2).toString(), role: 'assistant', content: errorContent, timestamp: new Date() },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const toggleVoiceInput = () => {
    setIsListening(!isListening)
    // TODO: Implement voice input using Web Audio API
  }

  const startNewChat = () => {
    setMessages([])
    setInput('')
    inputRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {messages.length === 0 ? (
        /* Welcome Screen */
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-2xl mx-auto text-center px-4">
            <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-primary/10 flex items-center justify-center">
              <Sparkles className="w-8 h-8 text-primary" />
            </div>
            <h1 className="text-3xl font-bold text-foreground mb-3">
              Welcome to Guppy
            </h1>
            <p className="text-muted-foreground mb-8">
              Your AI assistant is ready to help. Start a conversation or choose a suggestion below.
            </p>
            <div className="grid grid-cols-2 gap-3 max-w-md mx-auto">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion.text}
                  onClick={() => handleSendMessage(suggestion.text)}
                  className="flex items-center gap-3 p-4 rounded-xl border border-border bg-card hover:bg-accent/50 transition-colors text-left group"
                >
                  <span className="text-lg text-muted-foreground group-hover:text-foreground">
                    {suggestion.icon}
                  </span>
                  <span className="text-sm text-foreground">{suggestion.text}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* Messages Area */
        <ScrollArea className="flex-1 px-4">
          <div className="max-w-3xl mx-auto py-6 space-y-6">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex gap-4",
                  msg.role === 'user' ? "justify-end" : "justify-start"
                )}
              >
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-primary" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-4 py-3",
                    msg.role === 'user'
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  <div className="flex items-center gap-2 mt-2 text-xs opacity-70">
                    {msg.source && (
                      <Badge variant="secondary" className="text-xs">
                        {msg.source}
                      </Badge>
                    )}
                    <span>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {msg.role === 'assistant' && (
                      <button
                        onClick={() => copyToClipboard(msg.content, msg.id)}
                        className="ml-auto hover:opacity-100 transition-opacity"
                        title="Copy to clipboard"
                      >
                        {copiedId === msg.id ? (
                          <Check className="w-3 h-3" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
                {msg.role === 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-secondary flex items-center justify-center">
                    <User className="w-4 h-4 text-secondary-foreground" />
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
                <div className="bg-muted rounded-2xl px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <span className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <span className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce" />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
      )}

      {/* Input Area */}
      <div className="border-t border-border bg-background p-4">
        <div className="max-w-3xl mx-auto space-y-3">
          {/* Mode Selector */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {MODES.map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                disabled={isLoading}
                className={cn(
                  "px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors",
                  mode === m.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
                title={m.description}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={startNewChat}
              disabled={messages.length === 0}
              title="New chat"
            >
              <Plus className="w-5 h-5" />
            </Button>
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage(input)
                  }
                }}
                placeholder="Type your message..."
                disabled={isLoading}
                className="w-full h-12 px-4 rounded-xl border border-border bg-muted/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleVoiceInput}
              disabled={isLoading}
              title="Voice input"
              className={cn(isListening && "text-destructive")}
            >
              <Mic className="w-5 h-5" />
            </Button>
            <Button
              onClick={() => handleSendMessage(input)}
              disabled={!input.trim() || isLoading}
              title="Send message"
            >
              <Send className="w-4 h-4 mr-2" />
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
