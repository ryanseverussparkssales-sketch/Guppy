import { useState, useRef, useEffect } from 'react'
import { Send, Paperclip, Sparkles, ArrowRight, LayoutGrid, FileText, Copy, Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '../api/client'
import { useWorkspaces } from '@/hooks/useWorkspaces'
import { useChatHistory } from '@/hooks/useChatHistory'
import { ChatHistorySidebar } from '@/components/chat/ChatHistorySidebar'

/**
 * Chat message interface
 *
 * BACKEND INTEGRATION:
 * - Messages are sent via POST /api/chat
 * - Request: { message: string, mode: string, model?: string, workspace_id?: string }
 * - Response: { response: string, source?: string }
 */
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  source?: string
  timestamp: Date
  isProcessing?: boolean
  observations?: { title: string; content: string }[]
}

const MODES = [
  { value: 'auto', label: 'Auto' },
  { value: 'claude', label: 'Claude' },
  { value: 'openai', label: 'GPT-4' },
  { value: 'local', label: 'Local' },
  { value: 'code', label: 'Code' },
]

/**
 * AssistantView - Editorial-style chat interface
 *
 * BACKEND INTEGRATION:
 * - POST /api/chat - Send messages and receive responses
 * - GET /providers - Fetch available local models
 * - WebSocket /ws/chat - For streaming responses (TODO)
 * - The `mode` parameter controls which LLM backend to use
 * - The `model` parameter selects a specific model (e.g., "fast", "code", "main")
 */
export default function AssistantView() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [mode, setMode] = useState('auto')
  const [localModels, setLocalModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Workspace context
  const { activeWorkspaceId } = useWorkspaces()

  // Chat history persistence
  const {
    conversations,
    activeConversation,
    loading: historyLoading,
    createConversation,
    loadConversation,
    addMessage: saveMessage,
    searchConversations,
  } = useChatHistory(activeWorkspaceId)

  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [showSidebar, setShowSidebar] = useState(true)

  // Auto-create conversation for workspace
  useEffect(() => {
    if (activeWorkspaceId && !currentConversationId) {
      createConversation(`Conversation ${new Date().toLocaleDateString()}`)
        .then((conv) => {
          if (conv) setCurrentConversationId(conv.id)
        })
        .catch(console.error)
    }
  }, [activeWorkspaceId])

  // Fetch available local models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await api.get('/providers')
        const models = res.data.local?.models?.map((m: { id: string }) => m.id) || []
        setLocalModels(models)
        if (models.length > 0 && !selectedModel) {
          setSelectedModel(models[0])
        }
      } catch (err) {
        console.error('Failed to fetch models:', err)
      }
    }
    fetchModels()
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

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
      const chatPayload: { message: string; mode: string; model?: string; workspace_id?: string } = {
        message: text,
        mode,
      }
      if (selectedModel && mode === 'local') {
        chatPayload.model = selectedModel
      }
      if (activeWorkspaceId) {
        chatPayload.workspace_id = activeWorkspaceId
      }

      const response = await api.post('/chat', chatPayload)
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response || response.data.message || 'No response',
        source: response.data.source,
        timestamp: new Date(),
        observations: response.data.observations,
      }
      setMessages((prev) => [...prev, assistantMessage])

      // Save messages to chat history if conversation exists
      if (currentConversationId) {
        try {
          await saveMessage(currentConversationId, 'user', text, selectedModel || undefined)
          await saveMessage(
            currentConversationId,
            'assistant',
            assistantMessage.content,
            selectedModel || undefined
          )
        } catch (err) {
          console.error('Failed to save message to history:', err)
        }
      }
    } catch (error: unknown) {
      console.error('Failed to send message:', error)
      let errorContent = 'I encountered an issue processing your request. Please verify the backend services are running.'
      const axiosError = error as { response?: { status?: number; data?: { detail?: string } } }
      if (axiosError.response?.status === 503) {
        errorContent = 'Guppy core is currently unavailable. Please ensure all services are properly configured.'
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

  return (
    <div className="flex h-[calc(100vh-80px)]">
      {/* Chat History Sidebar */}
      {showSidebar && (
        <ChatHistorySidebar
          conversations={conversations}
          activeConversationId={currentConversationId}
          loading={historyLoading}
          onSelectConversation={(convId) => {
            setCurrentConversationId(convId)
            loadConversation(convId)
              .then((conv) => {
                if (conv?.messages) {
                  setMessages(
                    conv.messages.map((msg) => ({
                      id: msg.id,
                      role: msg.role,
                      content: msg.content,
                      timestamp: new Date(msg.created_at),
                    }))
                  )
                }
              })
              .catch(console.error)
          }}
          onCreateNew={() => {
            if (activeWorkspaceId) {
              createConversation().then((conv) => {
                if (conv) {
                  setCurrentConversationId(conv.id)
                  setMessages([])
                }
              })
            }
          }}
          onDeleteConversation={(convId) => {
            // Delete is already handled by useChatHistory
            if (currentConversationId === convId) {
              setCurrentConversationId(null)
              setMessages([])
            }
          }}
          onSearch={searchConversations}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col px-12 py-8">
        {messages.length === 0 ? (
          /* Welcome State */
          <div className="flex-1 flex flex-col items-center justify-center max-w-2xl mx-auto">
            <div className="w-12 h-12 rounded-xl bg-primary-container flex items-center justify-center mb-6">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <span className="badge-verified mb-4">Intelligence Verified</span>
            <h1 className="text-4xl font-headline font-bold text-on-surface text-center mb-4">
              Analysis of Technical Ecosystem Integration
            </h1>
            <p className="text-on-surface-variant text-center leading-relaxed max-w-lg mb-8">
              The current architecture suggests a shift toward <em className="font-headline text-primary">Editorial Systems</em>. 
              I have compiled briefings regarding asynchronous data flows and their impact on user perception.
            </p>

            {/* Observation Cards */}
            <div className="grid grid-cols-2 gap-6 w-full mb-8">
              <div className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
                <span className="text-xs uppercase tracking-widest font-bold text-on-surface-variant mb-2 block">
                  Observation Alpha
                </span>
                <p className="text-on-surface font-headline">
                  Data density does not necessitate visual clutter.
                </p>
              </div>
              <div className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
                <span className="text-xs uppercase tracking-widest font-bold text-on-surface-variant mb-2 block">
                  Observation Beta
                </span>
                <p className="text-on-surface font-headline">
                  Asymmetry drives visual engagement in editorial layouts.
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* Messages */
          <div className="flex-1 overflow-auto custom-scrollbar">
            <div className="max-w-2xl mx-auto space-y-8 py-4">
              {messages.map((msg) => (
                <div key={msg.id}>
                  {msg.role === 'user' ? (
                    /* User Message */
                    <div className="bg-surface-container-low rounded-xl p-6 ml-12">
                      <p className="text-on-surface leading-relaxed">{msg.content}</p>
                      <p className="text-xs text-on-surface-variant/60 mt-3 text-right">
                        SENT {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toUpperCase()}
                      </p>
                    </div>
                  ) : (
                    /* Assistant Message */
                    <div className="flex gap-4">
                      <div className="flex-shrink-0">
                        <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center">
                          <Sparkles className="w-5 h-5 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        {msg.isProcessing ? (
                          <div className="flex items-center gap-2">
                            <span className="badge-in-progress flex items-center gap-2">
                              <span className="w-2 h-2 bg-secondary rounded-full animate-pulse" />
                              Processing Real-Time Metrics
                            </span>
                          </div>
                        ) : null}
                        <p className="text-on-surface font-headline italic text-lg leading-relaxed mt-2">
                          {msg.content}
                        </p>
                        {msg.observations && (
                          <div className="grid grid-cols-2 gap-4 mt-6">
                            {msg.observations.map((obs, i) => (
                              <div key={i} className="bg-surface-container-lowest rounded-lg p-4 ghost-border">
                                <span className="text-xs uppercase tracking-widest font-bold text-on-surface-variant block mb-1">
                                  {obs.title}
                                </span>
                                <p className="text-sm text-on-surface">{obs.content}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        <button
                          onClick={() => copyToClipboard(msg.content, msg.id)}
                          className="mt-3 text-xs text-on-surface-variant/60 hover:text-primary flex items-center gap-1 transition-colors"
                        >
                          {copiedId === msg.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                          {copiedId === msg.id ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-4">
                  <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex-1">
                    <span className="badge-in-progress flex items-center gap-2">
                      <span className="w-2 h-2 bg-secondary rounded-full animate-pulse" />
                      Processing Request
                    </span>
                    <p className="text-on-surface-variant italic mt-2">
                      Initializing workspace hooks... Connecting to technical telemetries.
                    </p>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="mt-auto pt-4">
          <div className="max-w-2xl mx-auto">
            {/* Input Box */}
            <div className="bg-surface-container-low rounded-xl p-4 ghost-border">
              <div className="flex items-start gap-3">
                <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                  <Paperclip className="w-5 h-5" />
                </button>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSendMessage(input)
                    }
                  }}
                  placeholder="Direct the Curator..."
                  disabled={isLoading}
                  rows={1}
                  className="flex-1 bg-transparent text-on-surface placeholder:text-on-surface-variant/50 font-headline italic resize-none focus:outline-none disabled:opacity-50"
                />
                <button
                  onClick={() => handleSendMessage(input)}
                  disabled={!input.trim() || isLoading}
                  className={cn(
                    "w-10 h-10 rounded-lg flex items-center justify-center transition-all",
                    input.trim() && !isLoading
                      ? "signature-gradient text-white shadow-md hover:shadow-lg"
                      : "bg-surface-container text-on-surface-variant"
                  )}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Actions Row */}
            <div className="flex items-center justify-center gap-6 mt-4">
              <button className="flex items-center gap-2 text-xs font-bold text-on-surface-variant hover:text-primary transition-colors">
                <LayoutGrid className="w-4 h-4" />
                Compare Models
              </button>
              <button className="flex items-center gap-2 text-xs font-bold text-on-surface-variant hover:text-primary transition-colors">
                <FileText className="w-4 h-4" />
                Review Citations
              </button>
            </div>

            {/* Mode Selector & Model Dropdown */}
            <div className="flex items-center justify-center gap-2 mt-4">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setMode(m.value)}
                  disabled={isLoading}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs font-bold transition-all",
                    mode === m.value
                      ? "bg-primary text-white"
                      : "text-on-surface-variant/60 hover:text-on-surface-variant"
                  )}
                >
                  {m.label}
                </button>
              ))}

              {/* Model Selector (shows when local mode active) */}
              {mode === 'local' && localModels.length > 0 && (
                <div className="relative ml-2">
                  <button
                    onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                    disabled={isLoading}
                    className="px-3 py-1.5 rounded-full text-xs font-bold transition-all bg-surface-container text-on-surface-variant/60 hover:text-on-surface-variant flex items-center gap-1"
                  >
                    {selectedModel || 'Select model'}
                    <ChevronDown className={cn("w-3 h-3 transition-transform", modelDropdownOpen && "rotate-180")} />
                  </button>

                  {/* Dropdown Menu */}
                  {modelDropdownOpen && (
                    <div className="absolute top-full mt-1 right-0 bg-surface-container rounded-lg shadow-lg border border-outline-variant/20 z-50 min-w-48">
                      {localModels.map((model) => (
                        <button
                          key={model}
                          onClick={() => {
                            setSelectedModel(model)
                            setModelDropdownOpen(false)
                          }}
                          className={cn(
                            "w-full text-left px-4 py-2 text-xs font-bold transition-colors",
                            selectedModel === model
                              ? "bg-primary/1