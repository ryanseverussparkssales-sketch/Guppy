/**
 * =============================================================================
 * CHAT MESSAGE QUEUE HOOK (useChatQueue)
 * =============================================================================
 *
 * Prevents message loss and race conditions during chat send operations.
 * Supports both direct API streaming and custom handler functions (e.g., syncManager integration).
 *
 * Features:
 * - Queues outbound messages (prevents rapid-fire orphans)
 * - Processes queue serially (one message at a time)
 * - Automatic retry with exponential backoff (1s → 2s → 4s, max 3 attempts)
 * - Persists queue to localStorage for recovery on reload
 * - User feedback via Sonner toasts (retry + permanent failure)
 * - Supports custom handler functions (via `handler` field) for advanced use cases
 * - Default: Works with streaming chat endpoint (`/api/chat/stream`)
 *
 * Usage (streamChat default):
 *   const { enqueue } = useChatQueue()
 *   enqueue({
 *     message: userInput,
 *     sessionId: currentSession,
 *     workspaceId: workspace?.id,
 *   })
 *
 * Usage (custom handler - e.g., syncManager):
 *   const { enqueue } = useChatQueue()
 *   enqueue({
 *     message: userInput,
 *     conversationId: convoId,
 *     handler: async () => {
 *       await syncManager.addMessage(convoId, 'user', userInput)
 *       await syncManager.getAIResponse(convoId, userInput)
 *     },
 *   })
 *
 * =============================================================================
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { streamChat } from '../api/client'
import { toast } from 'sonner'

export interface ChatMessage {
  message: string
  sessionId?: string
  workspaceId?: string | null
  mode?: string
  conversationId?: string  // For syncManager integration
  onToken?: (token: string) => void  // Token callback for streaming UI updates
  handler?: () => Promise<void>  // Custom handler function (overrides streamChat default)
}

interface QueuedMessage extends ChatMessage {
  id: string
  retryCount: number
  maxRetries: number
  createdAt: number
}

const STORAGE_KEY = 'guppy_chat_queue'

/**
 * Generate a unique ID for each queued message
 */
function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

/**
 * Calculate exponential backoff delay in milliseconds
 * Retry 1: 1000ms, Retry 2: 2000ms, Retry 3: 4000ms
 */
function getBackoffDelay(retryCount: number): number {
  return Math.pow(2, retryCount) * 1000
}

/**
 * Hook to manage chat message queue with automatic retry
 *
 * This hook:
 * 1. Queues messages to prevent race conditions
 * 2. Processes queue serially (one message at a time)
 * 3. Retries failed messages with exponential backoff
 * 4. Persists queue to localStorage for recovery
 * 5. Shows toast notifications for retry and failure events
 *
 * @returns Object with queue state and control functions
 */
export function useChatQueue() {
  const [queue, setQueue] = useState<QueuedMessage[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const processingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  /**
   * Load queue from localStorage on mount
   */
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved) as QueuedMessage[]
        // Only restore messages created within last hour (prevent stale queue)
        const hourAgo = Date.now() - 60 * 60 * 1000
        const fresh = parsed.filter((msg) => msg.createdAt > hourAgo)
        if (fresh.length > 0) {
          setQueue(fresh)
          console.debug(`Restored ${fresh.length} queued messages from storage`)
        }
      }
    } catch (error) {
      console.warn('Failed to restore queue from storage:', error)
    }
  }, [])

  /**
   * Persist queue to localStorage whenever it changes
   */
  useEffect(() => {
    try {
      if (queue.length > 0) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(queue))
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch (error) {
      console.warn('Failed to persist queue to storage:', error)
    }
  }, [queue])

  /**
   * Process the message queue serially
   */
  const processQueue = useCallback(async (messages: QueuedMessage[]) => {
    if (messages.length === 0) {
      setIsProcessing(false)
      return
    }

    const message = messages[0]
    const remaining = messages.slice(1)

    setIsProcessing(true)

    try {
      // Create abort controller for this message
      abortControllerRef.current = new AbortController()

      // Use custom handler if provided, otherwise use default streamChat
      if (message.handler) {
        // Custom handler (e.g., syncManager-based integration)
        console.debug(`Message ${message.id} using custom handler`)
        await message.handler()
      } else {
        // Default: stream chat via API
        let streamSucceeded = false

        await streamChat(
          {
            message: message.message,
            session_id: message.sessionId,
            workspace_id: message.workspaceId,
            mode: message.mode,
          },
          // onToken callback
          (token) => {
            streamSucceeded = true
            message.onToken?.(token)
          },
          abortControllerRef.current.signal
        )

        if (!streamSucceeded) {
          throw new Error('Stream did not produce tokens')
        }
      }

      console.debug(`Message sent: ${message.id}`)
      // Move to next message
      setQueue(remaining)
      await processQueue(remaining)
    } catch (error) {
      // Check if this is a network/server error (retryable)
      const isNetworkError =
        error instanceof Error &&
        (error.message.includes('Stream request failed') ||
          error.message.includes('TypeError') ||
          error.message.includes('NetworkError'))

      if (message.retryCount < message.maxRetries && isNetworkError) {
        const delay = getBackoffDelay(message.retryCount)
        const newMessage = {
          ...message,
          retryCount: message.retryCount + 1,
        }

        console.warn(
          `Message ${message.id} failed, retrying in ${delay}ms (attempt ${newMessage.retryCount}/${message.maxRetries})`
        )

        toast.loading(
          `Retrying message send (attempt ${newMessage.retryCount}/${message.maxRetries})...`
        )

        // Schedule retry
        processingTimeoutRef.current = setTimeout(() => {
          setQueue([newMessage, ...remaining])
          processQueue([newMessage, ...remaining])
        }, delay)
      } else {
        // Permanent failure (max retries exceeded or non-retryable error)
        console.error(
          `Message ${message.id} failed permanently:`,
          error instanceof Error ? error.message : error
        )

        toast.error(
          `Failed to send message after ${message.maxRetries} attempts. Please try again.`,
          { duration: 5000 }
        )

        // Remove failed message and continue with next
        setQueue(remaining)
        await processQueue(remaining)
      }
    } finally {
      setIsProcessing(false)
    }
  }, [])

  /**
   * Watch queue and process whenever it's not empty and not already processing
   */
  useEffect(() => {
    if (queue.length > 0 && !isProcessing) {
      processQueue(queue)
    }
  }, [queue, isProcessing, processQueue])

  /**
   * Enqueue a message for sending
   */
  const enqueue = useCallback((message: ChatMessage) => {
    const queuedMessage: QueuedMessage = {
      ...message,
      id: generateMessageId(),
      retryCount: 0,
      maxRetries: 3,
      createdAt: Date.now(),
    }

    setQueue((prev) => [...prev, queuedMessage])
    console.debug(`Message queued: ${queuedMessage.id}`)
  }, [])

  /**
   * Dequeue a specific message (manual removal)
   */
  const dequeue = useCallback((messageId: string) => {
    setQueue((prev) => prev.filter((msg) => msg.id !== messageId))
    console.debug(`Message dequeued: ${messageId}`)
  }, [])

  /**
   * Clear entire queue (emergency reset)
   */
  const clearQueue = useCallback(() => {
    setQueue([])
    localStorage.removeItem(STORAGE_KEY)
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    if (processingTimeoutRef.current) {
      clearTimeout(processingTimeoutRef.current)
    }
    console.debug('Chat queue cleared')
  }, [])

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      if (processingTimeoutRef.current) {
        clearTimeout(processingTimeoutRef.current)
      }
    }
  }, [])

  return {
    queue,
    isProcessing,
    queueLength: queue.length,
    enqueue,
    dequeue,
    clearQueue,
  }
}

/**
 * Export a global queue instance for use across multiple components
 * (Alternative to prop drilling or context)
 */
let globalQueueInstance: ReturnType<typeof useChatQueue> | null = null

export function setGlobalChatQueue(
  instance: ReturnType<typeof useChatQueue>
): void {
  globalQueueInstance = instance
}

export function getGlobalChatQueue(): ReturnType<typeof useChatQueue> | null {
  return globalQueueInstance
}
