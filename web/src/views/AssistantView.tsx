/**
 * AssistantView - Chat Interface
 *
 * Displays conversations, messages, and allows sending new messages.
 * All data comes from Zustand store, all mutations go through syncManager.
 *
 * BACKEND INTEGRATION:
 * - GET /api/chat/history - Load conversations
 * - GET /api/chat/history/{id} - Load conversation with messages
 * - POST /api/chat/history/{id}/messages - Send message
 * - DELETE /api/chat/history/{id} - Delete conversation
 */

import { useState, useEffect, useRef } from 'react'
import { Send, Plus, Trash2, MessageCircle, AlertCircle, WifiOff, Clock, Mic, MicOff, StopCircle, Navigation, Volume2, VolumeX } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { format } from 'date-fns'
import { cn } from '@/lib/utils'
import { useChatStore, useWorkspaceStore, syncManager } from '@/store'
import { useQueueMonitoring } from '@/hooks/useMonitoring'
import { MarkdownMessage } from '@/components/chat/MarkdownMessage'
import { useVoice } from '@/hooks/useVoice'
import api from '../api/client'

export default function AssistantView() {
  // Store hooks
  const { conversations, activeConversationId, messages, loading, error } = useChatStore()
  const { activeWorkspaceId } = useWorkspaceStore()

  // Monitoring hook for queue status
  const queueStatus = useQueueMonitoring(1000)

  // Local state
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)
  const [localError, setLocalError] = useState<string | null>(null)
  const [streamingContent, setStreamingContent] = useState('')
  const [isSteerMode, setIsSteerMode] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const voice = useVoice({
    onTranscript: (text) => setInputValue(text),
    onError: () => {/* silently ignore — mic may be unavailable */},
  })

  const handleMicClick = async () => {
    if (voice.isListening) {
      voice.stopListening()
      return
    }
    // Interrupt TTS if currently speaking
    if (voice.isSpeaking) {
      voice.stopSpeaking()
      try { await api.post('/api/voices/stop') } catch { /* best-effort */ }
    }
    voice.startListening()
  }

  // Get current conversation from store
  const activeConversation = conversations.find((c) => c.id === activeConversationId)

  // Auto-scroll to bottom when messages or streaming content change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Auto-create conversation when workspace becomes available
  useEffect(() => {
    if (!activeWorkspaceId || conversations.length > 0 || loading) return
    syncManager
      .createConversation(activeWorkspaceId, `Chat ${new Date().toLocaleString()}`)
      .catch((err: any) => setLocalError(err?.message || 'Failed to create conversation'))
  }, [activeWorkspaceId])

  const handleNewConversation = async () => {
    try {
      setLocalError(null)
      if (!activeWorkspaceId) {
        setLocalError('No active workspace')
        return
      }
      await syncManager.createConversation(activeWorkspaceId, `Chat ${new Date().toLocaleString()}`)
    } catch (error: any) {
      setLocalError(error?.message || 'Failed to create conversation')
    }
  }

  const handleStop = () => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    if (voice.isSpeaking) voice.stopSpeaking()
    setStreamingContent('')
    setIsSending(false)
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !activeConversationId) {
      return
    }

    const messageText = inputValue
    const sendMode = isSteerMode ? 'steer' : undefined
    setInputValue('')
    setIsSteerMode(false)   // auto-reset steer after send
    setIsSending(true)
    setLocalError(null)

    // Create abort controller for this request
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      // Send user message (syncManager handles optimistic update)
      await syncManager.addMessage(activeConversationId, 'user', messageText)

      // Get AI response with live token streaming
      setStreamingContent('')
      const fullResponse = await syncManager.getAIResponse(
        activeConversationId,
        messageText,
        sendMode,
        (token) => {
          setStreamingContent((prev) => prev + token)
        },
        controller.signal
      )
      setStreamingContent('')

      // TTS: speak the completed response if enabled
      if (ttsEnabled && fullResponse && typeof fullResponse === 'string' && fullResponse.trim()) {
        voice.speak(fullResponse)
      }

      // Clear any previous errors on success
      setLocalError(null)
    } catch (error: any) {
      setStreamingContent('')
      // Abort is user-initiated — not an error
      if (error?.name === 'AbortError') return
      setLocalError(error?.message || 'Failed to send message')
      // Re-populate input on error
      setInputValue(messageText)

      // Clear error after 4 seconds to avoid stale messages
      setTimeout(() => {
        setLocalError(null)
      }, 4000)
    } finally {
      abortControllerRef.current = null
      setIsSending(false)
      inputRef.current?.focus()
    }
  }

  const handleDeleteConversation = async (conversationId: string) => {
    if (!window.confirm('Delete this conversation?')) {
      return
    }

    try {
      setLocalError(null)
      await syncManager.deleteConversation(conversationId)
    } catch (error: any) {
      setLocalError(error?.message || 'Failed to delete conversation')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Messages to display (from store)
  const currentMessages = activeConversationId ? messages : []

  return (
    <div className="flex h-full bg-background">
      {/* Sidebar */}
      {showSidebar && (
        <div className="w-64 border-r border-border flex flex-col bg-surface">
          <div className="p-4 border-b border-border">
            <button
              onClick={handleNewConversation}
              disabled={loading || !activeWorkspaceId}
              className={cn(
                'w-full px-4 py-2 rounded-lg flex items-center gap-2 font-medium',
                loading
                  ? 'bg-surface-variant text-on-surface-variant cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-primary/90'
              )}
            >
              <Plus className="w-4 h-4" />
              New Chat
            </button>
          </div>

          {/* Conversations List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-on-surface-variant text-sm">
                {loading ? 'Loading conversations...' : 'No conversations yet'}
              </div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={cn(
                    'p-3 rounded-lg cursor-pointer transition-colors group flex items-center justify-between',
                    activeConversationId === conv.id
                      ? 'bg-primary/20 text-primary'
                      : 'hover:bg-surface-container text-on-surface'
                  )}
                >
                  <button
                    onClick={() => syncManager.loadConversation(conv.id)}
                    className="flex-1 text-left truncate"
                    title={conv.title}
                  >
                    {conv.title}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteConversation(conv.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-error/20 rounded transition-opacity"
                  >
                    <Trash2 className="w-4 h-4 text-error" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b border-border p-4 flex items-center justify-between bg-surface">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="p-2 hover:bg-surface-container rounded-lg transition-colors"
              title="Toggle sidebar"
            >
              <MessageCircle className="w-5 h-5" />
            </button>
            <div>
              <h1 className="font-bold text-lg">{activeConversation?.title || 'Chat'}</h1>
              <p className="text-xs text-on-surface-variant">
                {activeConversation ? `${activeConversation.message_count || 0} messages` : 'No conversation selected'}
              </p>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Loading State */}
          {loading && currentMessages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-3">
                <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-sm text-on-surface-variant">Loading messages...</p>
              </div>
            </div>
          )}

          {/* Error State */}
          {(error || localError) && (
            <div className="p-4 rounded-lg bg-error/10 border border-error/20 flex gap-3 items-start">
              <AlertCircle className="w-5 h-5 text-error flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-error">Error</p>
                <p className="text-sm text-error/80">{error || localError}</p>
              </div>
            </div>
          )}

          {/* Empty State */}
          {currentMessages.length === 0 && !loading && !error && activeConversationId && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-3 text-on-surface-variant">
                <MessageCircle className="w-12 h-12 mx-auto opacity-50" />
                <p>No messages yet. Start the conversation!</p>
              </div>
            </div>
          )}

          {/* Messages */}
          <AnimatePresence initial={false}>
            {currentMessages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                <div
                  className={cn(
                    'max-w-xs lg:max-w-2xl px-4 py-2 rounded-lg',
                    message.role === 'user'
                      ? 'bg-primary text-white rounded-br-none'
                      : 'bg-surface-container text-on-surface rounded-bl-none'
                  )}
                >
                  <MarkdownMessage content={message.content} isUser={message.role === 'user'} />
                  <p className="text-xs mt-1 opacity-70">
                    {format(new Date(message.created_at), 'HH:mm')}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Live streaming bubble */}
          {streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-xs lg:max-w-2xl px-4 py-2 rounded-lg bg-surface-container text-on-surface rounded-bl-none">
                <MarkdownMessage content={streamingContent} />
                <div className="flex gap-1 mt-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        {activeConversationId ? (
          <div className="border-t border-border p-4 bg-surface space-y-3">
            {/* Queue Status Indicator */}
            {queueStatus.queuedCount > 0 && (
              <div className="flex items-center gap-2 text-sm text-on-surface-variant bg-surface-container px-3 py-2 rounded-lg">
                {queueStatus.isPaused ? (
                  <>
                    <WifiOff className="w-4 h-4 text-error" />
                    <span>Offline • {queueStatus.queuedCount} request{queueStatus.queuedCount === 1 ? '' : 's'} queued</span>
                  </>
                ) : (
                  <>
                    <Clock className="w-4 h-4 text-warning" />
                    <span>{queueStatus.queuedCount} request{queueStatus.queuedCount === 1 ? '' : 's'} queued • Oldest: {queueStatus.oldestAgeSeconds}s ago</span>
                  </>
                )}
              </div>
            )}

            {/* Connection Status */}
            {queueStatus.isPaused && queueStatus.queuedCount === 0 && (
              <div className="flex items-center gap-2 text-sm text-on-surface-variant bg-surface-container px-3 py-2 rounded-lg">
                <WifiOff className="w-4 h-4 text-error" />
                <span>Currently offline • Requests will be queued when you regain connection</span>
              </div>
            )}

            {/* Mode controls: Steer + TTS toggles */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsSteerMode((v) => !v)}
                title="Steer mode — send a correction or redirect to the AI"
                disabled={isSending}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                  isSteerMode
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    : 'bg-surface-variant text-on-surface-variant hover:bg-surface-container border border-transparent'
                )}
              >
                <Navigation className="w-3.5 h-3.5" />
                Steer
              </button>
              <button
                onClick={() => {
                  if (ttsEnabled && voice.isSpeaking) voice.stopSpeaking()
                  setTtsEnabled((v) => !v)
                }}
                title={ttsEnabled ? 'Disable text-to-speech' : 'Enable text-to-speech for AI replies'}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                  ttsEnabled
                    ? 'bg-primary/20 text-primary border border-primary/30'
                    : 'bg-surface-variant text-on-surface-variant hover:bg-surface-container border border-transparent'
                )}
              >
                {ttsEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
                TTS
              </button>
              {isSteerMode && (
                <span className="text-xs text-amber-400/80 italic">
                  Next message will steer the AI's direction
                </span>
              )}
            </div>

            <div className="flex gap-2">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  voice.isListening
                    ? 'Listening…'
                    : isSteerMode
                    ? 'Type a correction or new direction…'
                    : 'Type a message… (Shift+Enter for new line)'
                }
                disabled={isSending}
                className={cn(
                  'flex-1 px-4 py-2 rounded-lg border bg-background text-on-background',
                  'resize-none max-h-32 focus:outline-none transition-colors',
                  isSending && 'opacity-50 cursor-not-allowed',
                  voice.isListening && 'border-error focus:border-error',
                  isSteerMode
                    ? 'border-amber-500/60 focus:border-amber-500'
                    : 'border-outline focus:border-primary'
                )}
                rows={3}
              />
              {voice.isSupported && (
                <button
                  onClick={handleMicClick}
                  title={voice.isListening ? 'Stop listening' : 'Voice input'}
                  className={cn(
                    'px-3 py-2 rounded-lg flex items-center transition-colors',
                    voice.isListening
                      ? 'bg-error text-white animate-pulse'
                      : 'bg-surface-variant text-on-surface-variant hover:bg-surface-container'
                  )}
                >
                  {voice.isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              )}
              {isSending ? (
                <button
                  onClick={handleStop}
                  title="Stop generating"
                  className="px-4 py-2 rounded-lg flex items-center gap-2 font-medium bg-error/90 text-white hover:bg-error transition-colors"
                >
                  <StopCircle className="w-4 h-4" />
                  Stop
                </button>
              ) : (
                <button
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim()}
                  className={cn(
                    'px-4 py-2 rounded-lg flex items-center gap-2 font-medium transition-colors',
                    !inputValue.trim()
                      ? 'bg-surface-variant text-on-surface-variant cursor-not-allowed'
                      : isSteerMode
                      ? 'bg-amber-500 text-white hover:bg-amber-600'
                      : 'bg-primary text-white hover:bg-primary/90'
                  )}
                >
                  <Send className="w-4 h-4" />
                  {isSteerMode ? 'Steer' : 'Send'}
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="border-t border-border p-4 bg-surface text-center text-on-surface-variant">
            <p>No conversation selected. Create or select one to start chatting.</p>
          </div>
        )}
      </div>
    </div>
  )
}
