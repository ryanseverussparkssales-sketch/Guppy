import { useState, useCallback } from 'react'
import api from '../api/client'

export type Provider = 'local' | 'anthropic' | 'openai' | 'google'

export interface CredentialStatus {
  anthropic: { configured: boolean }
  openai: { configured: boolean }
  google: { configured: boolean }
}

export interface Settings {
  active_provider: Provider
  credentials: CredentialStatus
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch current settings
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

  // Store API credential
  const storeCredential = useCallback(async (provider: Provider, apiKey: string) => {
    try {
      const res = await api.post('/api/settings/credentials', {
        provider,
        api_key: apiKey,
      })

      // Update local state
      setSettings((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          credentials: {
            ...prev.credentials,
            [provider]: { configured: true },
          },
        }
      })

      return res.data
    } catch (err) {
      setError('Failed to store credential')
      console.error('Store credential error:', err)
      throw err
    }
  }, [])

  // Delete API credential
  const deleteCredential = useCallback(async (provider: Provider) => {
    try {
      await api.delete(`/api/settings/credentials/${provider}`)

      // Update local state
      setSettings((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          credentials: {
            ...prev.credentials,
            [provider]: { configured: false },
          },
        }
      })
    } catch (err) {
      setError('Failed to delete credential')
      console.error('Delete credential error:', err)
      throw err
    }
  }, [])

  // Set active provider
  const setActiveProvider = useCallback(async (provider: Provider) => {
    try {
      const res = await api.post('/api/settings/provider', { provider })

      // Update local state
      setSettings((prev) => {
        if (!prev) return prev
        return { ...prev, active_provider: provider }
      })

      return res.data
    } catch (err) {
      setError('Failed to set provider')
      console.error('Set provider error:', err)
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
  }
}
