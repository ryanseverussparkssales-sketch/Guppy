import { useState, useCallback } from 'react'
import { toast } from 'sonner'
import { type Provider } from '@/store'
import {
  useSettings,
  useStoreCredential,
  useDeleteCredential,
  useSetActiveProvider,
} from '@/api/queries'

export interface ProviderCredentialsState {
  credentialInputs: Record<string, string>
  visibleKeys: Record<string, boolean>
  savingProviders: Set<Provider>
  deletingProviders: Set<Provider>
  deleteConfirm: { provider: Provider | null; visible: boolean }
  apiError: string | null
  handleCredentialChange: (provider: Provider, value: string) => void
  toggleKeyVisibility: (provider: Provider) => void
  handleSaveCredential: (provider: Provider) => Promise<void>
  handleDeleteClick: (provider: Provider) => void
  handleConfirmDelete: () => Promise<void>
  handleCancelDelete: () => void
  handleSetActiveProvider: (provider: Provider) => Promise<void>
  isProviderConfigured: (provider: Provider) => boolean
}

export function useProviderCredentials(): ProviderCredentialsState {
  const { data: settings } = useSettings()
  const storeCredentialMut = useStoreCredential()
  const deleteCredentialMut = useDeleteCredential()
  const setActiveProviderMut = useSetActiveProvider()

  const [credentialInputs, setCredentialInputs] = useState<Record<string, string>>({})
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({})
  const [savingProviders, setSavingProviders] = useState<Set<Provider>>(new Set())
  const [deletingProviders, setDeletingProviders] = useState<Set<Provider>>(new Set())
  const [deleteConfirm, setDeleteConfirm] = useState<{ provider: Provider | null; visible: boolean }>({
    provider: null,
    visible: false,
  })
  const [apiError, setApiError] = useState<string | null>(null)

  const toggleKeyVisibility = (provider: Provider) =>
    setVisibleKeys((prev) => ({ ...prev, [provider]: !prev[provider] }))

  const handleCredentialChange = (provider: Provider, value: string) => {
    setCredentialInputs((prev) => ({ ...prev, [provider]: value }))
    setApiError(null)
  }

  const handleSaveCredential = useCallback(
    async (provider: Provider) => {
      const apiKey = credentialInputs[provider]?.trim()
      if (!apiKey) { setApiError(`Please enter an API key for ${provider}`); return }

      setSavingProviders((prev) => new Set([...prev, provider]))
      setApiError(null)
      try {
        await storeCredentialMut.mutateAsync({ provider, api_key: apiKey })
        setCredentialInputs((prev) => ({ ...prev, [provider]: '' }))
        toast.success(`${provider} credentials saved`)
      } catch {
        setApiError(`Failed to save ${provider} credentials`)
      } finally {
        setSavingProviders((prev) => { const n = new Set(prev); n.delete(provider); return n })
      }
    },
    [credentialInputs, storeCredentialMut]
  )

  const handleDeleteClick = (provider: Provider) =>
    setDeleteConfirm({ provider, visible: true })

  const handleCancelDelete = () =>
    setDeleteConfirm({ provider: null, visible: false })

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteConfirm.provider) return
    const provider = deleteConfirm.provider
    setDeletingProviders((prev) => new Set([...prev, provider]))
    setDeleteConfirm({ provider: null, visible: false })
    setApiError(null)
    try {
      await deleteCredentialMut.mutateAsync(provider)
      toast.success(`${provider} credentials deleted`)
    } catch {
      setApiError(`Failed to delete ${provider} credentials`)
    } finally {
      setDeletingProviders((prev) => { const n = new Set(prev); n.delete(provider); return n })
    }
  }, [deleteConfirm.provider, deleteCredentialMut])

  const handleSetActiveProvider = useCallback(
    async (provider: Provider) => {
      setSavingProviders((prev) => new Set([...prev, provider]))
      setApiError(null)
      try {
        await setActiveProviderMut.mutateAsync(provider)
        toast.success(`Switched to ${provider}`)
      } catch {
        setApiError(`Failed to switch to ${provider}`)
      } finally {
        setSavingProviders((prev) => { const n = new Set(prev); n.delete(provider); return n })
      }
    },
    [setActiveProviderMut]
  )

  const isProviderConfigured = (provider: Provider): boolean => {
    if (provider === 'local') return true
    return settings?.credentials?.[provider]?.configured ?? false
  }

  return {
    credentialInputs,
    visibleKeys,
    savingProviders,
    deletingProviders,
    deleteConfirm,
    apiError,
    handleCredentialChange,
    toggleKeyVisibility,
    handleSaveCredential,
    handleDeleteClick,
    handleConfirmDelete,
    handleCancelDelete,
    handleSetActiveProvider,
    isProviderConfigured,
  }
}
