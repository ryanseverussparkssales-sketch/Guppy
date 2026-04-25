import { useState, useCallback } from 'react'
import api from '../api/client'
import type { Provider } from '@/store'

export interface CredentialStatus {
  anthropic: { configured: boolean }
  openai:    { configured: boolean }
  google:    { configured: boolean }
  cohere?:   { configured: boolean }
  mistral?:  { configured: boolean }
}

export interface ModelParams {
  temperature: number
  max_tokens: number
}

export interface Settings {
  active_provider: Provider
  credentials: CredentialStatus
  model_params: ModelParams
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/settings')
      setSettings(res.data)
    } catch (err) {
      setError('Failed to fetch settings')
      console.error('Fetch settings error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const storeCredential = useCallback(async (provider: Provider, apiKey: string) => {
    try {
      const res = await api.post('/api/settings/credentials', { provider, api_key: apiKey })
      setSettings((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          credentials: { ...prev.credentials, [provider]: { configured: true } },
        }
      })
      return res.data
    } catch (err) {
      setError('Failed to store credential')
      throw err
    }
  }, [])

  const deleteCredential = useCallback(async (provider: Provider) => {
    try {
      await api.delete(`/api/settings/credentials/${provider}`)
      setSettings((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          credentials: { ...prev.credentials, [provider]: { configured: false } },
        }
      })
    } catch (err) {
      setError('Failed to delete credential')
      throw err
    }
  }, [])

  const setActiveProvider = useCallback(async (provider: Provider) => {
    try {
      const res = await api.post('/api/settings/provider', { provider })
      setSettings((prev) => (prev ? { ...prev, active_provider: provider } : prev))
      return res.data
    } catch (err) {
      setError('Failed to set provider')
      throw err
    }
  }, [])

  const saveModelParams = useCallback(async (temperature: number, maxTokens: number) => {
    try {
      await api.put('/api/settings', { temperature, max_tokens: maxTokens })
      setSettings((prev) =>
        prev ? { ...prev, model_params: { temperature, max_tokens: maxTokens } } : prev
      )
    } catch (err) {
      setError('Failed to save model parameters')
      throw err
    }
  }, [])

  const setProviderActiveModel = useCallback(async (provider: string, modelId: string) => {
    try {
      await api.post(`/providers/${provider}/active-model`, { model_id: modelId })
    } catch (err) {
      setError('Failed to set active model')
      throw err
    }
  }, [])

  return {
    settings,
    loading,
    error,
    fetchSettings,
    storeCredential,
    deleteCredential,
    setActiveProvider,
    saveModelParams,
    setProviderActiveModel,
  }
}
