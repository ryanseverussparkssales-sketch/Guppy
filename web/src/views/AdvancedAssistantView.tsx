import { useState, useRef, useEffect } from 'react'
import { Send, Mic, StopCircle, Plus, Download, Trash2 } from 'lucide-react'
import { useVoice } from '../hooks/useVoice'
import { useWebSocket } from '../hooks/useWebSocket'
import { useChatHistory, ChatMessage } from '../hooks/useChatHistory'
import FileUploadZone from '../components/FileUploadZone'
import api from '../api/client'
import './AdvancedAssistantView.css'

export default function AdvancedAssistantView() {
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [showFileUpload, setShowFileUpload] = useState(false)
  const [streamingResponse, setStreamingResponse] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { isListening, isSpeaking, transcript, startListening, stopListening, speak } = useVoice({
    onTranscript: (text) => setInput(input + ' ' + text),
  })

  const { isConnected, send: sendWS } = useWebSocket({
    url: 'ws://localhost:8081/ws',
    onMessage: (data) => {
      if (data.type === 'chunk') {
        setStreamingResponse((prev) => prev + data.content)
      } else if (data.type === 'end') {
        setStreamingResponse('')
        setIsLoading(false)
      }
    },
    onError: () => console.error('WebSocket error'),
    reconnect: true,
  })

  const {
    currentSession,
    sessions,
    setCurrentSession,
    createSession,
    deleteSession,
    clearSession,
    addMessage,
  } = useChatHistory()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [currentSession?.messages])

  const handleSendMessage = async (text: string) => {
    if (!text.trim() && selectedFiles.length === 0) return

    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
      metadata: {
        files: selectedFiles.map((f) => f.name),
      },
    }

    if (!currentSession) {
      const session = await createSession(text.slice(0, 50) + '...')
      await addMessage(userMessage)
    } else {
      await addMessage(userMessage)
    }

    setInput('')
    setSelectedFiles([])
    setShowFileUpload(false)
    setIsLoading(true)

    try {
      // Create FormData for file upload
      const formData = new FormData()
      formData.append('message', text)
      selectedFiles.forEach((file, index) => {
        formData.append(`file_${index}`, file)
      })

      // Use WebSocket if available, otherwise fall back to HTTP
      if (isConnected) {
        sendWS({ type: 'chat', message: text, files: selectedFiles.map((f) => f.name) })
      } else {
        const response = await api.post('/chat', formData)

        // Add assistant message
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.response,
          timestamp: Date.now(),
          metadata: {
            source: response.data.source,
          },
        }

        if (currentSession) {
          await addMessage(assistantMessage)
        }

        // Speak the response if voice is enabled
        if (isSpeaking === false) {
          speak(response.data.response, 1, 1)
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: Date.now(),
      }
      if (currentSession) {
        await addMessage(errorMessage)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const downloadChat = () => {
    if (!currentSession) return

    const chatText = currentSession.messages
      .map(
        (msg) =>
          `${msg.role.toUpperCase()}: ${msg.content}\n(${new Date(msg.timestamp).toLocaleString()})`
      )
      .join('\n\n')

    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(chatText))
    element.setAttribute('download', `${currentSession.title}.txt`)
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  return (
    <div className="advanced-assistant">
      {/* Sidebar with chat history */}
      <div className="chat-sidebar">
        <div className="sidebar-header">
          <h3>Chats</h3>
          <button className="sidebar-btn" onClick={() => createSession()} title="New chat">
            <Plus size={18} />
          </button>
        </div>

        <div className="chat-list">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`chat-item ${currentSession?.id === session.id ? 'active' : ''}`}
              onClick={() => setCurrentSession(session)}
            >
              <span className="chat-title">{session.title}</span>
              <span className="chat-count">{session.messages.length}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main chat area */}
      <div className="chat-main">
        {currentSession ? (
          <>
            <div className="chat-header">
              <h2>{currentSession.title}</h2>
              <div className="header-actions">
                <button
                  className="header-btn"
                  onClick={downloadChat}
                  title="Download chat"
                  disabled={currentSession.messages.length === 0}
                >
                  <Download size={18} />
                </button>
                <button
                  className="header-btn"
                  onClick={() => clearSession(currentSession.id)}
                  title="Clear chat"
                  disabled={currentSession.messages.length === 0}
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </div>

            <div className="messages-container">
              {currentSession.messages.length === 0 ? (
                <div className="empty-state">
                  <h3>Start a conversation</h3>
                  <p>Use voice, text, or upload files to chat with the AI</p>
                </div>
              ) : (
                currentSession.messages.map((msg) => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="message-content">
                      <p>{msg.content}</p>
                      {msg.metadata?.files && msg.metadata.files.length > 0 && (
                        <div className="message-files">
                          {msg.metadata.files.map((file, idx) => (
                            <small key={idx}>📎 {file}</small>
                          ))}
                        </div>
                      )}
                      <span className="message-time">
                        {new Date(msg.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </div>
                ))
              )}

              {isLoading && (
                <div className="message assistant">
                  <div className="message-content">
                    {streamingResponse ? (
                      <p>{streamingResponse}</p>
                    ) : (
                      <div className="typing-indicator">
                        <span></span><span></span><span></span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* File upload zone */}
            {showFileUpload && (
              <div className="file-upload-container">
                <FileUploadZone
                  onFilesSelected={setSelectedFiles}
                  acceptedTypes={['*']}
                  maxSize={50 * 1024 * 1024}
                />
              </div>
            )}

            {/* Input area */}
            <div className="input-area">
              <div className="input-toolbar">
                <button
                  className="input-btn"
                  onClick={() => setShowFileUpload(!showFileUpload)}
                  title="Upload files"
                >
                  📎
                </button>

                <input
                  type="text"
                  className="message-input"
                  placeholder="Type message or press / for commands..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSendMessage(input)
                    }
                  }}
                  disabled={isLoading}
                />

                <button
                  className={`input-btn voice-btn ${isListening ? 'listening' : ''}`}
                  onClick={isListening ? stopListening : startListening}
                  title={isListening ? 'Stop recording' : 'Start recording'}
                >
                  {isListening ? <StopCircle size={18} /> : <Mic size={18} />}
                </button>

                <button
                  className="input-btn send-btn"
                  onClick={() => handleSendMessage(input)}
                  disabled={!input.trim() || isLoading}
                >
                  <Send size={18} />
                </button>
              </div>

              {transcript && (
                <div className="transcript-preview">
                  <small>Transcript: {transcript}</small>
                </div>
              )}

              {selectedFiles.length > 0 && (
                <div className="selected-files">
                  <small>{selectedFiles.length} file(s) selected</small>
                </div>
              )}

              <small className="input-hint">
                Shift+Enter for newline • Voice support available • Drag & drop files to chat
              </small>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <h2>Welcome to Guppy</h2>
            <p>Start a new conversation or select one from the sidebar</p>
            <button className="btn btn-primary" onClick={() => createSession('New Chat')}>
              Start New Chat
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
