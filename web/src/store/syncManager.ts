/**
 * SyncManager - API Orchestration Layer
 *
 * Responsible for:
 * - Calling API endpoints
 * - Handling errors and retries
 * - Updating store with API responses
 * - Managing loading/error states
 * - Debouncing rapid changes
 * - Deduplicating concurrent requests
 *
 * Data flow: UI → syncManager → API → syncManager → store → UI
 */

import api from '../api/client'
import { useAppStore, ChatMessage, Conversation, Settings, Workspace, Provider } from './appStore'

// ============= TYPES =============

interface SyncManagerConfig {
  retryAttempts?: number
  retryDelay?: number
  debounceDelay?: number
}

// ============= ERROR HANDLING =============

export class APIError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public details?: any
  ) {
    super(message)
    this.name = 'APIError'
  }
}

const handleError = (error: any, defaultMessage: string): APIError => {
  if (error.response) {
    // API returned an error response
    const statusCode = error.response.status
    const message = error.response.data?.error || error.response.data?.detail || defaultMessage
    return new APIError(statusCode, message, error.response.data)
  } else if (error.request) {
    // Request made but no response
    return new APIError(0, 'No response from server', error)
  } else {
    // Error in request setup
    return new APIError(-1, error.message || defaultMessage, error)
  }
}

// ============= RETRY LOGIC =============

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<T> {
  let lastError: Error = new Error('Unknown error')

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error as Error
      // Don't retry on 400-level errors (validation issues)
      if (error instanceof APIError && error.statusCode >= 400 && error.statusCode < 500) {
        throw error
      }
      if (attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, delayMs * Math.pow(2, attempt)))
      }
    }
  }

  throw lastError
}

// ============= DEBOUNCING =============

const debounceTimers = new Map<string, NodeJS.Timeout>()

function debounce<T extends any[], R>(
  key: string,
  fn: (...args: T) => Promise<R>,
  delayMs: number = 500
) {
  return (...args: T) => {
    return new Promise<R>((resolve, reject) => {
      // Cancel previous timer
      if (debounceTimers.has(key)) {
        clearTimeout(debounceTimers.get(key))
      }

      // Set new timer
      const timer = setTimeout(async () => {
        try {
          const result = await fn(...args)
          resolve(result)
        } catch (error) {
          reject(error)
        } finally {
          debounceTimers.delete(key)
        }
      }, delayMs)

      debounceTimers.set(key, timer)
    })
  }
}

// ============= SYNC MANAGER CLASS =============

export class SyncManager {
  private config: Required<SyncManagerConfig>

  constructor(config: SyncManagerConfig = {}) {
    this.config = {
      retryAttempts: config.retryAttempts || 3,
      retryDelay: config.retryDelay || 1000,
      debounceDelay: config.debounceDelay || 500,
    }
  }

  // ============= WORKSPACE OPERATIONS =============

  async fetchWorkspaces() {
    const store = useAppStore.getState()
    store.setWorkspacesLoading(true)

    try {
      const response = await withRetry(() => api.get('/api/workspaces'), this.config.retryAttempts)
      const workspaces = response.data.workspaces || []

      store.setWorkspaces(workspaces)
      store.setSyncStatus('workspaces', {
        loading: false,
        error: null,
        lastSync: new Date().toISOString(),
      })

      return workspaces
    } catch (error) {
      const apiError = handleError(error, 'Failed to fetch workspaces')
      store.setSyncStatus('workspaces', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  async createWorkspace(name: string, description: string = '') {
    const store = useAppStore.getState()

    try {
      const response = await api.post('/api/workspaces', { name, description })
      const workspace = response.data

      store.addWorkspace(workspace)
      return workspace
    } catch (error) {
      const apiError = handleError(error, 'Failed to create workspace')
      store.setSyncStatus('workspaces', { error: apiError.message })
      throw apiError
    }
  }

  async switchWorkspace(workspaceId: string) {
    const store = useAppStore.getState()

    try {
      await api.post(`/api/workspaces/${workspaceId}/activate`)
      store.setActiveWorkspace(workspaceId)
      // Load conversations for the new workspace
      await this.fetchConversations(workspaceId)
    } catch (error) {
      const apiError = handleError(error, 'Failed to switch workspace')
      store.setSyncStatus('workspaces', { error: apiError.message })
      throw apiError
    }
  }

  // ============= CHAT OPERATIONS =============

  async fetchConversations(workspaceId: string) {
    const store = useAppStore.getState()
    store.setChatLoading(true)

    try {
      const response = await withRetry(
        () => api.get('/api/chat/history', { params: { workspace_id: workspaceId } }),
        this.config.retryAttempts
      )
      const conversations = response.data.conversations || []

      store.setConversations(conversations)
      store.setSyncStatus('chat', {
        loading: false,
        error: null,
        lastSync: new Date().toISOString(),
      })

      return conversations
    } catch (error) {
      const apiError = handleError(error, 'Failed to fetch conversations')
      store.setSyncStatus('chat', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  async createConversation(workspaceId: string, title?: string) {
    const store = useAppStore.getState()

    try {
      const response = await api.post('/api/chat/history', {
        workspace_id: workspaceId,
        title: title || `Chat ${new Date().toLocaleString()}`,
      })
      const conversation = response.data

      store.addConversation(conversation)
      store.setActiveConversation(conversation.id)

      return conversation
    } catch (error) {
      const apiError = handleError(error, 'Failed to create conversation')
      store.setSyncStatus('chat', { error: apiError.message })
      throw apiError
    }
  }

  async loadConversation(conversationId: string) {
    const store = useAppStore.getState()
    store.setChatLoading(true)

    try {
      const response = await withRetry(
        () => api.get(`/api/chat/history/${conversationId}`),
        this.config.retryAttempts
      )
      const conversation = response.data

      // Update conversation in list
      store.updateConversation(conversationId, conversation)

      // Set as active
      store.setActiveConversation(conversationId)

      // Load messages
      if (conversation.messages) {
        store.setMessages(conversationId, conversation.messages)
      }

      store.setSyncStatus('chat', {
        loading: false,
        error: null,
      })

      return conversation
    } catch (error) {
      const apiError = handleError(error, 'Failed to load conversation')
      store.setSyncStatus('chat', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  async addMessage(conversationId: string, role: 'user' | 'assistant', content: string, model?: string) {
    const store = useAppStore.getState()
    const tempMessageId = `temp-${Date.now()}`

    // Optimistic update: show message immediately in UI
    const tempMessage: ChatMessage = {
      id: tempMessageId,
      conversation_id: conversationId,
      role,
      content,
      model,
      created_at: new Date().toISOString(),
    }
    store.addMessage(tempMessage)

    try {
      const response = await api.post(`/api/chat/history/${conversationId}/messages`, {
        role,
        content,
        model,
      })
      const message = response.data

      // Remove temp message and add real message
      store.deleteMessage(conversationId, tempMessageId)
      store.addMessage(message)

      return message
    } catch (error) {
      // Remove optimistic message on error
      store.deleteMessage(conversationId, tempMessageId)
      const apiError = handleError(error, 'Failed to send message')
      store.setSyncStatus('chat', { error: apiError.message })
      throw apiError
    }
  }

  async getAIResponse(conversationId: string, userMessage: string, model?: string) {
    const store = useAppStore.getState()

    try {
      // Call the AI endpoint to get response
      const response = await api.post('/api/chat', {
        message: userMessage,
        session_id: conversationId,
        workspace_id: store.activeWorkspaceId,
        mode: model || 'auto',
      })

      const aiResponse = response.data.response

      // Save the AI response as an assistant message
      await this.addMessage(conversationId, 'assistant', aiResponse, model)

      return aiResponse
    } catch (error) {
      const apiError = handleError(error, 'Failed to get AI response')
      store.setSyncStatus('chat', { error: apiError.message })
      throw apiError
    }
  }

  async deleteConversation(conversationId: string) {
    const store = useAppStore.getState()

    try {
      await api.delete(`/api/chat/history/${conversationId}`)
      store.deleteConversation(conversationId)
    } catch (error) {
      const apiError = handleError(error, 'Failed to delete conversation')
      store.setSyncStatus('chat', { error: apiError.message })
      throw apiError
    }
  }

  async updateConversationTitle(conversationId: string, title: string) {
    const store = useAppStore.getState()

    try {
      const response = await api.put(`/api/chat/history/${conversationId}`, { title })
      const updated = response.data

      store.updateConversation(conversationId, updated)
      return updated
    } catch (error) {
      const apiError = handleError(error, 'Failed to update conversation')
      store.setSyncStatus('chat', { error: apiError.message })
      throw apiError
    }
  }

  // ============= SETTINGS OPERATIONS =============

  async fetchSettings() {
    const store = useAppStore.getState()
    store.setSettingsLoading(true)

    try {
      const response = await withRetry(() => api.get('/api/settings'), this.config.retryAttempts)
      const settings = response.data

      store.setSettings(settings)
      store.setSyncStatus('settings', {
        loading: false,
        error: null,
        lastSync: new Date().toISOString(),
      })

      return settings
    } catch (error) {
      const apiError = handleError(error, 'Failed to fetch settings')
      store.setSyncStatus('settings', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  async storeCredential(provider: Provider, apiKey: string) {
    const store = useAppStore.getState()
    store.setSettingsLoading(true)

    try {
      const response = await api.post('/api/settings/credentials', {
        provider,
        api_key: apiKey,
      })

      store.setCredentialStatus(provider, true)
      store.setSettingsLoading(false)

      return response.data
    } catch (error) {
      const apiError = handleError(error, `Failed to save ${provider} credentials`)
      store.setSyncStatus('settings', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  async deleteCredential(provider: Provider) {
    const store = useAppStore.getState()
    store.setSettingsLoading(true)

    try {
      await api.delete(`/api/settings/credentials/${provider}`)
      store.setCredentialStatus(provider, false)
      store.setSettingsLoading(false)
    } catch (error) {
      const apiError = handleError(error, `Failed to delete ${provider} credentials`)
      store.setSyncStatus('settings', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  async setActiveProvider(provider: Provider) {
    const store = useAppStore.getState()
    store.setSettingsLoading(true)

    try {
      const response = await api.post('/api/settings/provider', { provider })

      store.setActiveProvider(provider)
      store.setSettingsLoading(false)

      return response.data
    } catch (error) {
      const apiError = handleError(error, `Failed to switch to ${provider}`)
      store.setSyncStatus('settings', {
        loading: false,
        error: apiError.message,
      })
      throw apiError
    }
  }

  // ============= BATCH INITIALIZATION =============

  /**
   * Initialize all data on app startup
   * Call this once in App.tsx useEffect
   */
  async initializeApp() {
    const store = useAppStore.getState()

    try {
      // Fetch workspaces first
      const workspaces = await this.fetchWorkspaces()

      // If no active workspace, use first one
      if (!store.activeWorks