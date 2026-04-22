import { useState, useRef, useEffect } from 'react'
import { Send, Mic, Plus } from 'lucide-react'
import api from '../api/client'
import './AssistantView.css'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function AssistantView() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

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
      // Call the chat endpoint
      const response = await api.post('/chat', {
        message: text,
        mode: 'auto',
      })

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response || response.data.message || 'No response',
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const toggleVoiceInput = () => {
    setIsListening(!isListening)
    // TODO: Implement voice input using Web Audio API
  }

  const startNewChat = () => {
    setMessages([])
    setInput('')
  }

  return (
    <div className="assistant-view">
      {messages.length === 0 ? (
        <div className="assistant-welcome">
          <div className="welcome-content">
            <h1>Welcome to Guppy</h1>
            <p>Your AI assistant is ready to help. Start a conversation below.</p>
            <div className="welcome-suggestions">
              <button className="suggestion-btn" onClick={() => setInput('What can you help me with?')}>
                What can you help me with?
              </button>
              <button className="suggestion-btn" onClick={() => setInput('Tell me about yourself')}>
                Tell me about yourself
              </button>
              <button className="suggestion-btn" onClick={() => setInput('Help me code something')}>
                Help me code something
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="assistant-messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-content">
                <p>{msg.content}</p>
                <span className="message-time">
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      <div className="assistant-input-area">
        <div className="input-toolbar">
          <button
            className="input-btn"
            onClick={startNewChat}
            title="Start new chat"
            disabled={messages.length === 0}
          >
            <Plus size={18} />
          </button>
          <input
            type="text"
            className="message-input"
            placeholder="Type your message... or press / for commands"
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
            className="input-btn voice-btn"
            onClick={toggleVoiceInput}
            title="Voice input"
            disabled={isLoading}
          >
            <Mic size={18} className={isListening ? 'active' : ''} />
          </button>
          <button
            className="input-btn send-btn"
            onClick={() => handleSendMessage(input)}
            disabled={!input.trim() || isLoading}
            title="Send message (Ctrl+Enter)"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
