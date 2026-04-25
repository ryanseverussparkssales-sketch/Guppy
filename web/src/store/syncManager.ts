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
 * Errors: syncManager catches errors and can report to error store for display
 */

import api, { setupCircuitBreakerMonitoring, streamChat } from '../api/client'
import { useAppStore, ChatMessage, Provider } from './appStore'
import { getErrorStore } from './errorStore'
import { getCircuitBreaker } from '../utils/circuitBreaker'
import { RequestQueue } from '../utils/requestQueue'
import { ErrorCode } from '../utils/errorCodes'
import { telemetry } from '../utils/telemetry'

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

const handleError = (error: any, defaultMessage: string, endpoint?: string): APIError => {
  // Handle circuit breaker open error
  if (error.isCircuitBreakerOpen) {
    telemetry.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { reason: 'circuit_breaker_open', defaultMessage },
    })
    return new APIError(
      -2,
      'Service temporarily unavailable - request queued for later',
      { queued: true, code: ErrorCode.SYSTEM_SERVICE_UNAVAILABLE }
    )
  }

  if (error.response) {
    // API returned an error response
    const statusCode = error.response.status
    const message = error.response.data?.error || error.response.data?.detail || defaultMessage

    // Determine error code based on status
    let errorCode = ErrorCode.SYSTEM_INTERNAL_ERROR
    if (statusCode >= 500) {
      errorCode = ErrorCode.SYSTEM_SERVICE_UNAVAILABLE
    } else if (statusCode === 429) {
      errorCode = ErrorCode.SYSTEM_TOO_MANY_REQUESTS
    } else if (statusCode === 401) {
      errorCode = ErrorCode.AUTH_UNAUTHORIZED
    } else if (statusCode === 403) {
      errorCode = ErrorCode.AUTH_FORBIDDEN
    } else if (statusCode >= 400) {
      errorCode = ErrorCode.VALIDATION_INVALID_INPUT
    }

    // Record telemetry
    telemetry.recordRequestError(endpoint || 'UNKNOWN', errorCode, statusCode)

    return new APIError(statusCode, message, {
      ...error.response.data,
      errorCode,
      queued: error.queued || false,
    })
  } else if (error.request) {
    // Request made but no response
    telemetry.recordRequestError(endpoint || 'UNKNOWN', 'CONNECTION_FAILED')
    return new APIError(0, 'No response from server', {
      code: ErrorCode.OLLAMA_CONNECTION_FAILED,
      queued: error.queued || false,
    })
  } else if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
    // DNS or connection error
    telemetry.recordRequestError(endpoint || 'UNKNOWN', 'CONNECTION_FAILED')
    return new APIError(-1, 'Cannot reach API server', {
      code: ErrorCode.OLLAMA_CONNECTION_FAILED,
      queued: error.queued || false,
    })
  } else {
    // Error in request setup
    telemetry.recordEvent({
      type: 'request_failed',
      endpoint,
      errorCode: 'REQUEST_SETUP_ERROR',
      details: { message: error.message || defaultMessage },
    })
    return new APIError(-1, error.message || defaultMessage, { queued: error.queued || false })
  }
}

/**
 * Report error to error store for display as toast
 * Call this when you want to show an error to the user
 * @param error - The error to report
 * @param showToast - Whether to show this error as a toast (default: true)
 * @param onRetry - Optional retry callback
 */
const reportError = (
  error: APIError,
  showToast: boolean = true,
  onRetry?: () => Promise<void>
) => {
  if (showToast) {
    const errorStore = getErrorStore()
    let message = error.message

    // For queued requests, provide user-friendly message
    if (error.details?.queued) {
      message = 'Request queued - will be sent when service is available'
    }

    errorStore.updateError(error.statusCode.toString(), message, onRetry)
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

// ============= SYNC MANAGER CLASS =============

export class SyncManager {
  private config: Required<SyncManagerConfig>
  private requestQueue: RequestQueue
  private sendingByConversation = new Map<string, Promise<void>>()

  constructor(config: SyncManagerConfig = {}) {
    this.config = {
      retryAttempts: config.retryAttempts || 3,
      retryDelay: config.retryDelay || 1000,
      debounceDelay: config.debounceDelay || 500,
    }

    this.requestQueue = RequestQueue.getInstance()

    // Setup circuit breaker monitoring for key endpoints
    this.setupCircuitBreakerMonitoring()
  }

  /**
   * Setup circuit breaker state monitoring for critical endpoints
   */
  private setupCircuitBreakerMonitoring(): void {
    const endpoints = [
      'POST /api/chat',
      'POST /api/chat/history',
      'GET /api/chat/history',
      'GET /api/workspaces',
      'GET /api/settings',
    ]

    for (const endpoint of endpoints) {
      try {
        setupCircuitBreakerMonitoring(endpoint)
      } catch (error) {
        console.warn(`Failed to setup circuit breaker monitoring for ${endpoint}:`, error)
      }
    }

    // Listen for circuit breaker state changes
    if (typeof window !== 'undefined') {
      window.addEventListener('circuitBreakerStateChange', (event: any) => {
        const { endpoint, to } = event.detail
        console.log(`Circuit breaker state changed: ${endpoint} → ${to}`)

        // Report to error store if opening
        if (to === 'OPEN') {
          const errorStore = getErrorStore()
          errorStore.updateError(
            'CIRCUIT_BREAKER_OPEN',
            `Service temporarily unavailable: ${endpoint}`
          )
        }
      })
    }
  }

  /**
   * Get current circuit breaker and queue diagnostics
   */
  getRequestDiagnostics() {
    return {
      circuitBreakers: this.getCircuitBreakerStates(),
      queue: this.requestQueue.getStats(),
    }
  }

  /**
   * Get all circuit breaker states
   */
  private getCircuitBreakerStates(): Record<string, string> {
    const endpoints = [
      'POST /api/chat',
      'POST /api/chat/history',
      'GET /api/chat/history',
      'GET /api/workspaces',
      'GET /api/settings',
    ]

    const states: Record<string, string> = {}
    for (const endpoint of endpoints) {
      const breaker = getCircuitBreaker(endpoint)
      states[endpoint] = breaker.getState()
    }
    return states
  }

  /**
   * Manually flush queued requests
   */
  async flushQueuedRequests(): Promise<void> {
    return this.requestQueue.flush()
  }

  // ============= WORKSPACE OPERATIONS =============

  async fetchWorkspaces() {
    const store = useAppStore.getState()
    store.setWorkspacesLoading(true)

    const endpoint = 'GET /api/workspaces'
    telemetry.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { operation: 'fetchWorkspaces' },
    })

    try {
      const response = await withRetry(() => api.get('/api/workspaces'), this.config.retryAttempts)
      const workspaces = response.data.workspaces || []

      store.setWorkspaces(workspaces)
      store.setSyncStatus('workspaces', {
        loading: false,
        error: null,
        lastSync: new Date().toISOString(),
      })

      telemetry.recordEvent({
        type: 'request_success',
        endpoint,
        details: { operation: 'fetchWorkspaces', count: workspaces.length },
      })

      return workspaces
    } catch (error) {
      const apiError = handleError(error, 'Failed to fetch workspaces', endpoint)
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

    const endpoint = 'GET /api/chat/history'
    telemetry.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { operation: 'fetchConversations', workspaceId },
    })

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

      telemetry.recordEvent({
        type: 'request_success',
        endpoint,
        details: { operation: 'fetchConversations', count: conversations.length },
      })

      return conversations
    } catch (error) {
      const apiError = handleError(error, 'Failed to fetch conversations', endpoint)
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
    // RACE CONDITION FIX: Prevent duplicate sends if user clicks send multiple times
    // Check if a send is already in progress for this conversation
    if (this.sendingByConversation.has(conversationId)) {
      console.warn(`Message send already in progress for conversation ${conversationId}, ignoring duplicate request`)
      // Silently ignore - UI should have disabled send button while sending
      return
    }

    const store = useAppStore.getState()
    const tempMessageId = `temp-${Date.now()}`
    const endpoint = 'POST /api/chat/history/:conversationId/messages'

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

    // Record telemetry
    telemetry.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { operation: 'addMessage', role, conversationId, messageLength: content.length },
    })

    // Create the send operation as a promise
    const sendOperation = (async () => {
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

        // Record success
        telemetry.recordEvent({
          type: 'request_success',
          endpoint,
          details: { operation: 'addMessage', role, messageId: message.id },
        })

        return message
      } catch (error) {
        // Check if request was queued (circuit breaker open or retryable error)
        if ((error as any).queued) {
          // Keep temp message but mark as queued
          store.addMessage({
            ...tempMessage,
            id: (error as any).queuedRequestId || tempMessageId,
          })

          telemetry.recordEvent({
            type: 'request_queued',
            endpoint,
            details: { operation: 'addMessage', reason: 'circuit_breaker_or_retryable' },
          })

          const apiError = handleError(error, 'Failed to send message', endpoint)
          reportError(apiError, true)

          // Don't throw - allow UI to continue
          return tempMessage
        }

        // Remove optimistic message on error
        store.deleteMessage(conversationId, tempMessageId)
        const apiError = handleError(error, 'Failed to send message', endpoint)
        store.setSyncStatus('chat', { error: apiError.message })
        reportError(apiError, true)
        throw apiError
      }
    })()

    // Track this send operation
    this.sendingByConversation.set(conversationId, sendOperation as Promise<void>)

    try {
      return await sendOperation
    } finally {
      // Always clean up the lock when done
      this.sendingByConversation.delete(conversationId)
    }
  }

  async getAIResponse(
    conversationId: string,
    userMessage: string,
    model?: string,
    onToken?: (token: string) => void
  ) {
    const store = useAppStore.getState()
    const endpoint = 'POST /api/chat'

    telemetry.recordEvent({
      type: 'request_queued',
      endpoint,
      details: { operation: 'getAIResponse', model, messageLength: userMessage.length },
    })

    // Try streaming path if caller wants live tokens
    if (onToken) {
      try {
        let fullResponse = ''
        await streamChat(
          {
            message: userMessage,
            session_id: conversationId,
            workspace_id: store.activeWorkspaceId,
            mode: model || 'auto',
          },
          (token) => {
            fullResponse += token
            onToken(token)
          }
        )
        if (fullResponse.trim()) {
          await this.addMessage(conversationId, 'assistant', fullResponse, model)
          telemetry.recordEvent({
            type: 'request_success',
            endpoint,
            details: { operation: 'getAIResponse', streaming: true, responseLength: fullResponse.length },
          })
          return fullResponse
        }
      } catch (streamErr) {
        console.warn('Streaming chat failed, falling back to non-streaming:', streamErr)
        // Fall through to non-streaming below
      }
    }

    try {
      // Non-streaming fallback
      const response = await api.post('/api/chat', {
        message: userMessage,
        session_id: conversationId,
        workspace_id: store.activeWorkspaceId,
        mode: model || 'auto',
      })

      const aiResponse = response.data.response

      telemetry.recordEvent({
        type: 'request_success',
        endpoint,
        details: { operation: 'getAIResponse', streaming: false, responseLength: aiResponse.length },
      })

      await this.addMessage(conversationId, 'assistant', aiResponse, model)

      return aiResponse
    } catch (error) {
      if ((error as any).queued) {
        telemetry.recordEvent({
          type: 'request_queued',
          endpoint,
          details: { operation: 'getAIResponse', reason: 'circuit_breaker_or_retryable' },
        })

        const apiError = handleError(error, 'Failed to get AI response', endpoint)
        reportError(apiError, true)
        return '[Request queued - response will be sent when service is available]'
      }

      const apiError = handleError(error, 'Failed to get AI response', endpoint)
      store.setSyncStatus('chat', { error: apiError.message })
      reportError(apiError, true)
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

      // Hydrate activeWorkspaceId from the server-side is_active flag first
      // (avoids an extra POST /activate round-trip when the API already knows)
      if (!store.activeWorkspaceId && workspaces.length > 0) {
        const serverActive = workspaces.find((w: any) => w.is_active)
        const target = serverActive || workspaces[0]
        store.setActiveWorkspace(target.id)
        // Tell the server too (fire-and-forget — don't block init on failure)
        api.post(`/api/workspaces/${target.id}/activate`).catch(() => {})
      }

      // Fetch settings
      await this.fetchSettings()

      return { success: true }
    } catch (error) {
      console.error('App initialization failed:', error)
      return { success: false, error }
    }
  }

  /**
   * Load all data for a workspace
   */
  async loadWorkspaceData(workspaceId: string) {
    try {
      await Promise.all([this.fetchConversations(workspaceId), this.fetchSettings()])
    } catch (error) {
      console.error('Failed to load workspace data:', error)
      throw error
    }
  }

  /**
   * Check if any requests are queued (for UI status display)
   */
  hasQueuedRequests(): boolean {
    return this.requestQueue.getStats().total > 0
  }

  /**
   * Get queue status for UI display
   */
  getQueueStatus(): {
    queuedCount: number
    isPaused: boolean
    isFlushing: boolean
    oldestRequestAge: number | null
  } {
    const stats = this.requestQueue.getStats()
    const oldestAge = stats.oldestRequest
      ? Date.now() - stats.oldestRequest
      : null

    return {
      queuedCount: stats.total,
      isPaused: stats.isPaused,
      isFlushing: stats.isFlushing,
      oldestRequestAge: oldestAge,
    }
  }

  /**
   * Check if circuit breaker is open for a specific endpoint
   */
  isCircuitBreakerOpen(endpoint: string): boolean {
    const breaker = getCircuitBreaker(endpoint)
    return breaker.isOpen()
  }
}

// ============= SINGLETON INSTANCE =============

export const syncManager = new SyncManager({
  retryAttempts: 3,
  retryDelay: 1000,
  debounceDelay: 500,
})
