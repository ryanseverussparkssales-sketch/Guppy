/**
 * SettingsView - Complete application configuration
 *
 * FEATURES:
 * - Provider selection and credential management
 * - API key storage, update, and deletion with confirmation
 * - Active provider indicator
 * - Theme customization
 * - Model parameters (temperature, max tokens)
 * - Real-time provider status with configuration indicators
 * - System diagnostics dashboard
 *
 * BACKEND INTEGRATION:
 * - GET /api/settings - Fetch current settings
 * - POST /api/settings/credentials - Store API key
 * - DELETE /api/settings/credentials/:provider - Delete credential
 * - POST /api/settings/provider - Set active provider
 */

import { useEffect, useState, useCallback } from 'react'
import {
  Eye,
  EyeOff,
  CheckCircle,
  AlertCircle,
  Trash2,
  RefreshCw,
  Save,
  Activity,
  Cpu,
  Cloud,
  Lock,
  ExternalLink,
  Moon,
  Sun,
  Sliders,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { type Provider } from '@/store'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import DiagnosticDashboard from '@/components/DiagnosticDashboard'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSettings } from '@/hooks/useSettings'
import { useTheme } from '@/hooks/useTheme'

interface ProviderConfig {
  label: string
  icon: React.ReactNode
  color: string
  url: string
  placeholder: string
}

const PROVIDERS: Record<Provider, ProviderConfig> = {
  local: {
    label: 'Local',
    icon: <Cpu className="w-5 h-5" />,
    color: 'border-blue-500 bg-blue-50 dark:bg-blue-950',
    url: '',
    placeholder: 'No API key needed',
  },
  anthropic: {
    label: 'Anthropic Claude',
    icon: <Cloud className="w-5 h-5" />,
    color: 'border-purple-500 bg-purple-50 dark:bg-purple-950',
    url: 'https://console.anthropic.com/account/keys',
    placeholder: 'sk-ant-...',
  },
  openai: {
    label: 'OpenAI',
    icon: <Cloud className="w-5 h-5" />,
    color: 'border-green-500 bg-green-50 dark:bg-green-950',
    url: 'https://platform.openai.com/api-keys',
    placeholder: 'sk-...',
  },
  google: {
    label: 'Google Gemini',
    icon: <Cloud className="w-5 h-5" />,
    color: 'border-orange-500 bg-orange-50 dark:bg-orange-950',
    url: 'https://aistudio.google.com/app/apikey',
    placeholder: 'AIza...',
  },
}

interface CredentialInput {
  [key: string]: string
}

interface DeleteConfirmation {
  provider: Provider | null
  visible: boolean
}

export default function SettingsView() {
  const { settings, loading, error, fetchSettings, storeCredential, deleteCredential, setActiveProvider } =
    useSettings()
  const { toggleTheme, resolvedTheme } = useTheme()

  // Tab state
  const [activeTab, setActiveTab] = useState<'providers' | 'diagnostics'>('providers')

  // Form state
  const [credentialInputs, setCredentialInputs] = useState<CredentialInput>({})
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({})
  const [savingProvider, setSavingProvider] = useState<Provider | null>(null)
  const [deletingProvider, setDeletingProvider] = useState<Provider | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<DeleteConfirmation>({
    provider: null,
    visible: false,
  })
  const [apiError, setApiError] = useState<string | null>(null)
  const [apiSuccess, setApiSuccess] = useState<string | null>(null)

  // Model parameters state
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState('4096')
  const [saved, setSaved] = useState(false)

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  // Load saved settings
  useEffect(() => {
    const saved = localStorage.getItem('guppy-settings')
    if (saved) {
      try {
        const { temperature: t, maxTokens: mt } = JSON.parse(saved)
        setTemperature(t)
        setMaxTokens(mt)
      } catch {
        // Ignore parse errors
      }
    }
  }, [])

  // Clear success/error messages after 4 seconds
  useEffect(() => {
    if (apiSuccess) {
      const timeout = setTimeout(() => setApiSuccess(null), 4000)
      return () => clearTimeout(timeout)
    }
  }, [apiSuccess])

  useEffect(() => {
    if (apiError) {
      const timeout = setTimeout(() => setApiError(null), 4000)
      return () => clearTimeout(timeout)
    }
  }, [apiError])

  const toggleKeyVisibility = (provider: Provider) => {
    setVisibleKeys((prev) => ({
      ...prev,
      [provider]: !prev[provider],
    }))
  }

  const handleCredentialChange = (provider: Provider, value: string) => {
    setCredentialInputs((prev) => ({
      ...prev,
      [provider]: value,
    }))
    setApiError(null)
  }

  const handleSaveCredential = useCallback(
    async (provider: Provider) => {
      const apiKey = credentialInputs[provider]?.trim()
      if (!apiKey) {
        setApiError(`Please enter an API key for ${PROVIDERS[provider].label}`)
        return
      }

      setSavingProvider(provider)
      setApiError(null)
      setApiSuccess(null)

      try {
        await storeCredential(provider, apiKey)
        setCredentialInputs((prev) => ({
          ...prev,
          [provider]: '',
        }))
        setApiSuccess(`Successfully saved ${PROVIDERS[provider].label} credentials`)
      } catch (err) {
        setApiError(`Failed to save ${PROVIDERS[provider].label} credentials`)
        console.error('Save credential error:', err)
      } finally {
        setSavingProvider(null)
      }
    },
    [credentialInputs, storeCredential]
  )

  const handleDeleteClick = (provider: Provider) => {
    setDeleteConfirm({
      provider,
      visible: true,
    })
  }

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteConfirm.provider) return

    const provider = deleteConfirm.provider
    setDeletingProvider(provider)
    setDeleteConfirm({ provider: null, visible: false })
    setApiError(null)
    setApiSuccess(null)

    try {
      await deleteCredential(provider)
      setApiSuccess(`Deleted ${PROVIDERS[provider].label} credentials`)
    } catch (err) {
      setApiError(`Failed to delete ${PROVIDERS[provider].label} credentials`)
      console.error('Delete credential error:', err)
    } finally {
      setDeletingProvider(null)
    }
  }, [deleteConfirm.provider, deleteCredential])

  const handleSetActiveProvider = useCallback(
    async (provider: Provider) => {
      setSavingProvider(provider)
      setApiError(null)
      setApiSuccess(null)

      try {
        await setActiveProvider(provider)
        setApiSuccess(`Switched to ${PROVIDERS[provider].label}`)
      } catch (err) {
        setApiError(`Failed to switch to ${PROVIDERS[provider].label}`)
        console.error('Set provider error:', err)
      } finally {
        setSavingProvider(null)
      }
    },
    [setActiveProvider]
  )

  const handleSaveSettings = () => {
    localStorage.setItem('guppy-settings', JSON.stringify({ temperature, maxTokens }))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const isProviderConfigured = (provider: Provider): boolean => {
    if (provider === 'local') return true
    return settings?.credentials?.[provider]?.configured ?? false
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-headline font-bold text-on-surface">Settings</h1>
        <p className="text-on-surface-variant mt-2">
          Manage providers, credentials, and system diagnostics
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-outline">
        <button
          onClick={() => setActiveTab('providers')}
          className={cn(
            'px-4 py-2 font-medium text-sm transition-colors border-b-2 -mb-px',
            activeTab === 'providers'
              ? 'border-primary text-primary'
              : 'border-transparent text-on-surface-variant hover:text-on-surface'
          )}
        >
          Providers & Credentials
        </button>
        <button
          onClick={() => setActiveTab('diagnostics')}
          className={cn(
            'px-4 py-2 font-medium text-sm transition-colors border-b-2 -mb-px flex items-center gap-2',
            activeTab === 'diagnostics'
              ? 'border-primary text-primary'
              : 'border-transparent text-on-surface-variant hover:text-on-surface'
          )}
        >
          <Activity className="w-4 h-4" />
          System Diagnostics
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'providers' && (
        <>
          {/* Alert Messages */}
          {apiError && (
            <div className="p-4 rounded-lg bg-error/10 border border-error/20 text-error flex items-start gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Error</p>
                <p className="text-sm">{apiError}</p>
              </div>
            </div>
          )}

          {apiSuccess && (
            <div className="p-4 rounded-lg bg-success/10 border border-success/20 text-success flex items-start gap-3">
              <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Success</p>
                <p className="text-sm">{apiSuccess}</p>
              </div>
            </div>
          )}

          {/* Provider Selection & Credentials */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>AI Providers</CardTitle>
                  <CardDescription>Select and manage your API credentials</CardDescription>
                </div>
                {loading && (
                  <RefreshCw className="w-5 h-5 text-on-surface-variant animate-spin" />
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Provider Grid */}
              <div className="space-y-4">
                {Object.entries(PROVIDERS).map(([key, provider]) => {
                  const providerKey = key as Provider
                  const isConfigured = isProviderConfigured(providerKey)
                  const isActive = settings?.active_provider === providerKey
                  const isSaving = savingProvider === providerKey
                  const isDeleting = deletingProvider === providerKey
                  const hasInput = credentialInputs[providerKey]?.trim()

                  return (
                    <div
                      key={providerKey}
                      className={cn(
                        'p-6 rounded-lg border-2 transition-all duration-200',
                        isActive
                          ? 'border-primary bg-primary/5'
                          : isConfigured
                            ? 'border-success/30 bg-success/5'
                            : 'border-surface-container bg-surface-container-low'
                      )}
                    >
                      {/* Provider Header */}
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="text-on-surface">{provider.icon}</div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <p className="font-medium text-on-surface">{provider.label}</p>
                              {isConfigured && (
                                <span className="px-2 py-1 bg-success/20 text-success text-xs font-bold rounded flex items-center gap-1">
                                  <CheckCircle className="w-3 h-3" />
                                  Configured
                                </span>
                              )}
                              {isActive && (
                                <span className="px-2 py-1 bg-primary/20 text-primary text-xs font-bold rounded">
                                  Active
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-on-surface-variant mt-1">
                              {providerKey === 'local'
                                ? 'Use local Ollama models'
                                : `Add your ${provider.label} API key below`}
                            </p>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2">
                          {isConfigured && !isActive && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleSetActiveProvider(providerKey)}
                              disabled={isSaving}
                              className="text-xs"
                            >
                              {isSaving ? (
                                <RefreshCw className="w-3 h-3 animate-spin" />
                              ) : (
                                'Activate'
                              )}
                            </Button>
                          )}

                          {isConfigured && isActive && (
                            <div className="flex items-center gap-1 px-3 py-1.5 bg-primary text-white rounded-lg text-xs font-bold">
                              <CheckCircle className="w-3 h-3" />
                              Current
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Credential Input (Cloud Providers Only) */}
                      {providerKey !== 'local' && (
                        <div className="space-y-3 mb-4">
                          <div className="flex gap-2">
                            <div className="relative flex-1">
                              <Input
                                type={visibleKeys[providerKey] ? 'text' : 'password'}
                                placeholder={provider.placeholder}
                                value={credentialInputs[providerKey] || ''}
                                onChange={(e) => handleCredentialChange(providerKey, e.target.value)}
                                disabled={isSaving}
                                className="pr-10"
                              />
                              <button
                                onClick={() => toggleKeyVisibility(providerKey)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface transition-colors"
                                tabIndex={-1}
                              >
                                {visibleKeys[providerKey] ? (
                                  <EyeOff className="w-4 h-4" />
                                ) : (
                                  <Eye className="w-4 h-4" />
                                )}
                              </button>
                            </div>

                            {hasInput && (
                              <Button
                                size="sm"
                                onClick={() => handleSaveCredential(providerKey)}
                                disabled={isSaving}
                                variant={isSaving ? 'outline' : 'default'}
                              >
                                {isSaving ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Save className="w-4 h-4" />
                                )}
                              </Button>
                            )}
                          </div>

                          {/* Get Key Link */}
                          {!hasInput && !isConfigured && (
                            <a
                              href={provider.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-primary hover:underline flex items-center gap-1"
                            >
                              Get API key
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}

                          {/* Delete Button */}
                          {isConfigured && (
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteClick(providerKey)}
                              disabled={isDeleting || isSaving}
                              className="w-full text-xs"
                            >
                              {isDeleting ? (
                                <RefreshCw className="w-3 h-3 animate-spin mr-1" />
                              ) : (
                                <Trash2 className="w-3 h-3 mr-1" />
                              )}
                              {isDeleting ? 'Deleting...' : 'Delete Credentials'}
                            </Button>
                          )}

                          {/* Security Note */}
                          <div className="flex items-start gap-2 p-3 bg-surface-container rounded text-xs text-on-surface-variant">
                            <Lock className="w-3 h-3 flex-shrink-0 mt-0.5" />
                            <p>API keys are encrypted and stored securely. Never share your key.</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* Appearance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {resolvedTheme === 'dark' ? (
                  <Moon className="w-5 h-5" />
                ) : (
                  <Sun className="w-5 h-5" />
                )}
                Appearance
              </CardTitle>
              <CardDescription>Customize the look and feel</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-on-surface">Theme</p>
                  <p className="text-sm text-on-surface-variant">Switch between light and dark mode</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant={resolvedTheme === 'light' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => resolvedTheme === 'dark' && toggleTheme()}
                  >
                    <Sun className="w-4 h-4 mr-1" />
                    Light
                  </Button>
                  <Button
                    variant={resolvedTheme === 'dark' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => resolvedTheme === 'light' && toggleTheme()}
                  >
                    <Moon className="w-4 h-4 mr-1" />
                    Dark
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Model Parameters */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sliders className="w-5 h-5" />
                Model Parameters
              </CardTitle>
              <CardDescription>Default parameters for AI model interactions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label htmlFor="temperature" className="text-sm font-medium text-on-surface">
                    Temperature
                  </label>
                  <span className="text-sm font-bold text-primary">{temperature.toFixed(2)}</span>
                </div>
                <input
                  id="temperature"
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full h-2 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <p className="text-xs text-on-surface-variant">
                  Lower values (0.0-0.7) produce focused, deterministic outputs. Higher values
                  (0.7-2.0) increase creativity and randomness.
                </p>
              </div>

              <div className="space-y-3">
                <label htmlFor="max-tokens" className="text-sm font-medium text-on-surface">
                  Max Tokens
                </label>
                <Input
                  id="max-tokens"
                  type="number"
                  placeholder="4096"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(e.target.value)}
                  className="max-w-xs"
                />
                <p className="text-xs text-on-surface-variant">
                  Maximum length of generated responses. Higher values allow longer outputs.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSaveSettings} size="lg">
              <Save className="w-4 h-4 mr-2" />
              {saved ? 'Saved!' : 'Save Settings'}
            </Button>
          </div>
        </>
      )}

      {/* Diagnostics Tab */}
      {activeTab === 'diagnostics' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />
                System Health & Monitoring
              </CardTitle>
              <CardDescription>
                Real-time monitoring of circuit breakers, request queue, error metrics, and system performance
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ErrorBoundary fallback={
                <div className="flex items-center justify-center p-8 border border-error/20 rounded-lg bg-error/10">
                  <div className="text-center">
                    <AlertCircle className="w-8 h-8 text-error mx-auto mb-2" />
                    <p className="text-on-surface font-medium">Diagnostics Failed to Load</p>
                    <p className="text-sm text-on-surface-variant mt-1">
                      There was an error loading the diagnostics dashboard. Please refresh the page or try again later.
                    </p>
                  </div>
                </div>
              }>
                <DiagnosticDashboard expanded={true} />
              </ErrorBoundary>
            </CardContent>
          </Card>

          {/* Documentation Links */}
          <Card>
            <CardHeader>
              <CardTitle>Documentation</CardTitle>
              <CardDescription>Learn about error codes and best practices</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <a
                href="/docs/ERROR_CODE_REFERENCE.md"
                className="block p-3 border border-outline rounded-lg hover:bg-surface-container transition-colors"
              >
                <p className="font-medium text-on-surface">Error Code Reference</p>
                <p className="text-sm text-on-surface-variant mt-1">
                  Complete enumeration of all error codes with user messages and recovery actions
                </p>
              </a>
              <a
                href="/docs/ERROR_HANDLING_BEST_PRACTICES.md"
                className="block p-3 border border-outline rounded-lg hover:bg-surface-container transition-colors"
              >
                <p className="font-medium text-on-surface">Error Handling Best Practices</p>
                <p className="text-sm text-on-surface-variant mt-1">
                  Guidelines for handling errors, patterns, testing approaches, and debugging tips
                </p>
              </a>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm.visible && deleteConfirm.provider && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="max-w-md">
            <CardHeader>
              <CardTitle className="text-on-surface">Delete Credentials?</CardTitle>
              <CardDescription>
                This will permanently delete your {PROVIDERS[deleteConfirm.provider].label} API
                credentials.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-on-surface-variant">
                You can re-add them at any time. This action cannot be undone.
              </p>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setDeleteConfirm({ provider: null, visible: false })}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleConfirmDelete}
                  className="flex-1"
                >
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
