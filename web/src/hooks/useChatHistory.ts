import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  model?: string
  created_at: string
}

export interface Conversation {
  id: string
  workspace_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  messages?: ChatMessage[]
}

export function useChatHistory(workspaceId: string | null) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchResults, setSearchResults] = useState<Conversation[]>([])

  // Fetch all conversations in workspace
  const fetchConversations = useCallback(async () => {
    if (!workspaceId) return

    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/chat/history', { params: { workspace_id: workspaceId } })
      setConversations(res.data.conversations || [])
    } catch (err) {
      setError('Failed to fetch conversations')
      console.error('Fetch conversations error:', err)
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  // Create new conversation
  const createConversation = useCallback(
    async (title?: string) => {
      if (!workspaceId) return null

      try {
        const res = await api.post('/api/chat/history', {
          workspace_id: workspaceId,
          title,
        })
        setConversations((prev) => [res.data, ...prev])
        return res.data
      } catch (err) {
        setError('Failed to create conversation')
        console.error('Create conversation error:', err)
        throw err
      }
    },
    [workspaceId]
  )

  // Load conversation with all messages
  const loadConversation = useCallback(async (convId: string) => {
    try {
      const res = await api.get(`/api/chat/history/${convId}`)
      setActiveConversation(res.data)
      return res.data
    } catch (err) {
      setError('Failed to load conversation')
      console.error('Load conversation error:', err)
      throw err
    }
  }, [])

  // Add message to conversation
  const addMessage = useCallback(
    async (convId: string, role: 'user' | 'assistant', content: string, model?: string) => {
      try {
        const res = await api.post(`/api/chat/history/${convId}/messages`, {
          role,
          content,
          model,
        })

        // Update active conversation if it's the current one
        if (activeConversation?.id === convId) {
          setActiveConversation((prev) => {
            if (!prev) return prev
            return {
              ...prev,
              messages: [...(prev.messages || []), res.data],
              message_count: (prev.message_count || 0) + 1,
              updated_at: new Date().toISOString(),
            }
          })
        }

        // Update conversation in list
        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId
              ? { ...c, message_count: (c.message_count || 0) + 1, updated_at: new Date().toISOString() }
              : c
          )
        )

        return res.data
      } catch (err) {
        setError('Failed to add message')
        console.error('Add message error:', err)
        throw err
      }
    },
    [activeConversation?.id]
  )

  // Update conversation title
  const updateTitle = useCallback(async (convId: string, title: string) => {
    try {
      const res = await api.put(`/api/chat/history/${convId}`, { title })

      // Update in lists
      setConversations((prev) => prev.map((c) => (c.id === convId ? res.data : c)))
      if (activeConversation?.id === convId) {
        setActiveConversation(res.data)
      }

      return res.data
    } catch (err) {
      setError('Failed to update conversation')
      console.error('Update conversation error:', err)
      throw err
    }
  }, [activeConversation?.id])

  // Delete conversation
  const deleteConversation = useCallback(async (convId: string) => {
    try {
      await api.delete(`/api/chat/history/${convId}`)

      // Remove from lists
      setConversations((prev) => prev.filter((c) => c.id !== convId))
      if (activeConversation?.id === convId) {
        setActiveConversation(null)
      }
    } catch (err) {
      setError('Failed to delete conversation')
      console.error('Delete conversation error:', err)
    }
  }, [activeConversation?.id])

  // Search conversations
  const searchConversations = useCallback(
    async (query: string) => {
      if (!workspaceId || !query.trim()) {
        setSearchResults([])
        return []
      }

      try {
        const res = await api.get(`/api/chat/history/search/${workspaceId}`, { params: { q: query } })
        setSearchResults(res.data.results || [])
        return res.data.results
      } catch (err) {
        setError('Search failed')
        console.error('Search error:', err)
        throw err
      }
    },
    [workspaceId]
  )

  // Load conversations when workspace changes
  useEffect(() => {
    if (workspaceId) {
      fetchConversations()
      setActiveConversation(null)
    }
  }, [workspaceId, fetchConversations])

  return {
    conversations,
    activeConversation,
    searchResults,
    loading,
    error,
    fetchConversations,
    createConversation,
    loadConversation,
    addMessage,
    updateTitle,
    deleteConversation,
    searchConversations,
  }
}
