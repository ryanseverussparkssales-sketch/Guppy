/**
 * =============================================================================
 * TYPED API HOOKS
 * =============================================================================
 * 
 * React hooks for API communication with full TypeScript support.
 * Uses SWR for caching and revalidation.
 * 
 * BACKEND INTEGRATION:
 * - Replace MOCK_* constants with actual API calls when backend is ready
 * - Each hook documents its expected endpoint
 * - Error handling follows consistent patterns
 * =============================================================================
 */

import { useState, useCallback } from "react"
import useSWR, { mutate } from "swr"
import { api } from "../api/client"
import type {
  Instance,
  CreateInstanceRequest,
  Model,
  Tool,
  Conversation,
  Message,
  SystemStatus,
  Settings,
  InstanceStatus,
} from "../types/api"

// =============================================================================
// FETCHER UTILITY
// =============================================================================

const fetcher = async <T>(url: string): Promise<T> => {
  const response = await api.get(url)
  return response.data
}

// =============================================================================
// INSTANCES HOOKS
// Endpoint: GET /api/instances
// =============================================================================

/**
 * Fetch all instances with real-time status
 * @backend GET /api/instances
 */
export function useInstances() {
  const { data, error, isLoading, mutate: revalidate } = useSWR<Instance[]>(
    "/api/instances",
    fetcher,
    { refreshInterval: 5000 } // Poll every 5s for status updates
  )

  return {
    instances: data ?? [],
    isLoading,
    error,
    revalidate,
  }
}

/**
 * Fetch a single instance by ID
 * @backend GET /api/instances/:id
 */
export function useInstance(id: string | null) {
  const { data, error, isLoading } = useSWR<Instance>(
    id ? `/api/instances/${id}` : null,
    fetcher
  )

  return {
    instance: data,
    isLoading,
    error,
  }
}

/**
 * Instance mutations (create, update, delete, start, stop)
 * @backend POST/PUT/DELETE /api/instances
 */
export function useInstanceMutations() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createInstance = useCallback(async (data: CreateInstanceRequest) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.post("/api/instances", data)
      await mutate("/api/instances")
      return response.data as Instance
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create instance")
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const startInstance = useCallback(async (id: string) => {
    setIsLoading(true)
    try {
      await api.post(`/api/instances/${id}/start`)
      await mutate("/api/instances")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start instance")
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const stopInstance = useCallback(async (id: string) => {
    setIsLoading(true)
    try {
      await api.post(`/api/instances/${id}/stop`)
      await mutate("/api/instances")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop instance")
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteInstance = useCallback(async (id: string) => {
    setIsLoading(true)
    try {
      await api.delete(`/api/instances/${id}`)
      await mutate("/api/instances")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete instance")
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    createInstance,
    startInstance,
    stopInstance,
    deleteInstance,
    isLoading,
    error,
  }
}

// =============================================================================
// MODELS HOOKS
// Endpoint: GET /api/models
// =============================================================================

/**
 * Fetch all available models
 * @backend GET /api/models
 */
export function useModels() {
  const { data, error, isLoading, mutate: revalidate } = useSWR<Model[]>(
    "/api/models",
    fetcher
  )

  return {
    models: data ?? [],
    isLoading,
    error,
    revalidate,
  }
}

/**
 * Model mutations (download, delete)
 * @backend POST /api/models/download, DELETE /api/models/:id
 */
export function useModelMutations() {
  const [isLoading, setIsLoading] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState<Record<string, number>>({})

  const downloadModel = useCallback(async (modelId: string, source: string) => {
    setIsLoading(true)
    setDownloadProgress(prev => ({ ...prev, [modelId]: 0 }))
    try {
      await api.post("/api/models/download", { modelId, source })
      // In real implementation, progress would come from WebSocket
      await mutate("/api/models")
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteModel = useCallback(async (id: string) => {
    setIsLoading(true)
    try {
      await api.delete(`/api/models/${id}`)
      await mutate("/api/models")
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    downloadModel,
    deleteModel,
    downloadProgress,
    isLoading,
  }
}

// =============================================================================
// TOOLS HOOKS
// Endpoint: GET /api/tools
// =============================================================================

/**
 * Fetch all tools
 * @backend GET /api/tools
 */
export function useTools() {
  const { data, error, isLoading, mutate: revalidate } = useSWR<Tool[]>(
    "/api/tools",
    fetcher
  )

  return {
    tools: data ?? [],
    isLoading,
    error,
    revalidate,
  }
}

// =============================================================================
// CONVERSATIONS HOOKS
// Endpoint: GET /api/conversations
// =============================================================================

/**
 * Fetch all conversations
 * @backend GET /api/conversations
 */
export function useConversations(instanceId?: string) {
  const url = instanceId
    ? `/api/conversations?instanceId=${instanceId}`
    : "/api/conversations"

  const { data, error, isLoading, mutate: revalidate } = useSWR<Conversation[]>(
    url,
    fetcher
  )

  return {
    conversations: data ?? [],
    isLoading,
    error,
    revalidate,
  }
}

/**
 * Fetch messages for a conversation
 * @backend GET /api/conversations/:id/messages
 */
export function useMessages(conversationId: string | null) {
  const { data, error, isLoading, mutate: revalidate } = useSWR<Message[]>(
    conversationId ? `/api/conversations/${conversationId}/messages` : null,
    fetcher
  )

  return {
    messages: data ?? [],
    isLoading,
    error,
    revalidate,
    addMessage: (message: Message) => {
      revalidate((current) => [...(current ?? []), message], false)
    },
    updateMessage: (id: string, updates: Partial<Message>) => {
      revalidate(
        (current) =>
          current?.map((m) => (m.id === id ? { ...m, ...updates } : m)),
        false
      )
    },
  }
}

// =============================================================================
// SYSTEM STATUS HOOKS
// Endpoint: GET /api/status
// =============================================================================

/**
 * Fetch system status with health info
 * @backend GET /api/status
 */
export function useSystemStatus() {
  const { data, error, isLoading } = useSWR<SystemStatus>(
    "/api/status",
    fetcher,
    { refreshInterval: 10000 } // Poll every 10s
  )

  return {
    status: data,
    isHealthy: data?.health === "healthy",
    isLoading,
    error,
  }
}

// =============================================================================
// SETTINGS HOOKS
// Endpoint: GET /api/settings, PUT /api/settings
// =============================================================================

/**
 * Fetch and update settings
 * @backend GET /api/settings, PUT /api/settings
 */
export function useSettings() {
  const { data, error, isLoading, mutate: revalidate } = useSWR<Settings>(
    "/api/settings",
    fetcher
  )

  const updateSettings = useCallback(async (updates: Partial<Settings>) => {
    try {
      await api.put("/api/settings", { settings: updates })
      await revalidate()
    } catch (err) {
      throw err
    }
  }, [revalidate])

  return {
    settings: data,
    isLoading,
    error,
    updateSettings,
  }
}

// =============================================================================
// CONNECTION STATUS HOOK
// For tracking backend connectivity
// =============================================================================

/**
 * Track backend connection status
 * Useful for showing connection indicators in the UI
 */
export function useConnectionStatus() {
  const { status, error, isLoading } = useSystemStatus()

  return {
    isConnected: !error && status?.health !== undefined,
    isLoading,
    health: status?.health ?? "unknown",
    services: status?.services,
  }
}
