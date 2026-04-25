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
  const { data, error, isLoading, mutate: revalidate } = useSWR<{ instances: Instance[] }>(
    "/api/instances",
    fetcher,
    { refreshInterval: 5000 }
  )

  return {
    instances: data?.instances ?? [],
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
  const { data, error, isLoading, mutate: revalidate } = useSWR<{ models: Model[] }>(
    "/api/models",
    fetcher
  )

  return {
    models: data?.models ?? [],
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
// PROVIDER / ACTIVE MODEL HOOKS
// =============================================================================

interface LocalModelMeta { id: string; name: string; tier: string; tags: string[] }
interface ProviderInfo {
  configured: boolean
  active_model: string
  models: LocalModelMeta[]
  backend?: string
  tags?: string[]
}
interface ProvidersResponse { anthropic: ProviderInfo; openai: ProviderInfo; google: ProviderInfo; local: ProviderInfo }

export function useProviders() {
  const { data, error, isLoading, mutate: revalidate } = useSWR<ProvidersResponse>(
    "/providers",
    fetcher,
    { refreshInterval: 10000 }
  )
  return { providers: data ?? null, isLoading, error, revalidate }
}

export function useActiveModel() {
  const { providers, isLoading } = useProviders()
  const { data: settingData } = useSWR<{ active_provider: string }>(
    "/api/settings/provider",
    fetcher,
    { refreshInterval: 10000 }
  )

  const activeProvider = settingData?.active_provider ?? "local"
  const providerInfo = providers?.[activeProvider as keyof ProvidersResponse]
  const activeModelId = providerInfo?.active_model ?? ""
  const modelMeta = providerInfo?.models?.find(m => m.id === activeModelId)

  const setProvider = useCallback(async (provider: string) => {
    await api.post("/api/settings/provider", { provider })
    mutate("/api/settings/provider")
  }, [])

  const setModel = useCallback(async (provider: string, modelId: string) => {
    await api.post(`/providers/${provider}/active-model`, { model_id: modelId })
    mutate("/providers")
  }, [])

  return {
    activeProvider,
    activeModelId,
    modelName: modelMeta?.name ?? activeModelId,
    modelTags: modelMeta?.tags ?? [],
    providers,
    isLoading,
    setProvider,
    setModel,
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

  const toggleTool = useCallback(async (toolId: string, enable: boolean) => {
    const action = enable ? "enable" : "disable"
    await api.post(`/api/tools/${toolId}/${action}`)
    await revalidate()
  }, [revalidate])

  return {
    tools: data ?? [],
    isLoading,
    error,
    revalidate,
    toggleTool,
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
    isHealthy: data?.status === "healthy",
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
    isConnected: !error && status?.status !== undefined,
    isLoading,
    health: status?.status ?? "unknown",
    services: undefined,
  }
}
