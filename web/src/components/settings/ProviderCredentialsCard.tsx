import {
  Eye, EyeOff, CheckCircle, AlertCircle, Trash2, RefreshCw, Save, Cpu, Cloud, Lock, ExternalLink,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { type Provider } from '@/store'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type Settings } from '@/api/schemas'
import { useProviderCredentials } from '@/hooks/useProviderCredentials'

interface ProviderConfig {
  label: string
  icon: React.ReactNode
  url: string
  placeholder: string
}

const PROVIDERS: Record<Provider, ProviderConfig> = {
  local:     { label: 'Local',          icon: <Cpu className="w-5 h-5" />,   url: '',                                           placeholder: 'No API key needed' },
  anthropic: { label: 'Anthropic Claude', icon: <Cloud className="w-5 h-5" />, url: 'https://console.anthropic.com/account/keys', placeholder: 'sk-ant-...' },
  openai:    { label: 'OpenAI',          icon: <Cloud className="w-5 h-5" />, url: 'https://platform.openai.com/api-keys',        placeholder: 'sk-...' },
  google:    { label: 'Google Gemini',   icon: <Cloud className="w-5 h-5" />, url: 'https://aistudio.google.com/app/apikey',      placeholder: 'AIza...' },
  cohere:    { label: 'Cohere',          icon: <Cloud className="w-5 h-5" />, url: 'https://dashboard.cohere.com/api-keys',       placeholder: '...' },
  mistral:   { label: 'Mistral AI',      icon: <Cloud className="w-5 h-5" />, url: 'https://console.mistral.ai/api-keys',         placeholder: '...' },
}

interface Props {
  settings: Settings | undefined
  isLoading: boolean
}

export function ProviderCredentialsCard({ settings, isLoading }: Props) {
  const creds = useProviderCredentials()

  return (
    <>
      {creds.apiError && (
        <div className="p-4 rounded-lg bg-error/10 border border-error/20 text-error flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Error</p>
            <p className="text-sm">{creds.apiError}</p>
          </div>
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>AI Providers</CardTitle>
              <CardDescription>Select and manage your API credentials</CardDescription>
            </div>
            {isLoading && <RefreshCw className="w-5 h-5 text-on-surface-variant animate-spin" />}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(PROVIDERS).map(([key, provider]) => {
            const pk = key as Provider
            const isConfigured = creds.isProviderConfigured(pk)
            const isActive = settings?.active_provider === pk
            const isSaving = creds.savingProviders.has(pk)
            const isDeleting = creds.deletingProviders.has(pk)
            const hasInput = creds.credentialInputs[pk]?.trim()

            return (
              <div
                key={pk}
                className={cn(
                  'p-6 rounded-lg border-2 transition-all duration-200',
                  isActive
                    ? 'border-primary bg-primary/5'
                    : isConfigured
                      ? 'border-success/30 bg-success/5'
                      : 'border-surface-container bg-surface-container-low'
                )}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="text-on-surface">{provider.icon}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-on-surface">{provider.label}</p>
                        {isConfigured && (
                          <span className="px-2 py-1 bg-success/20 text-success text-xs font-bold rounded flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> Configured
                          </span>
                        )}
                        {isActive && (
                          <span className="px-2 py-1 bg-primary/20 text-primary text-xs font-bold rounded">Active</span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-1">
                        {pk === 'local' ? 'Use local Ollama models' : `Add your ${provider.label} API key below`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {isConfigured && !isActive && (
                      <Button size="sm" variant="outline" onClick={() => creds.handleSetActiveProvider(pk)} disabled={isSaving} className="text-xs">
                        {isSaving ? <RefreshCw className="w-3 h-3 animate-spin" /> : 'Activate'}
                      </Button>
                    )}
                    {isConfigured && isActive && (
                      <div className="flex items-center gap-1 px-3 py-1.5 bg-primary text-white rounded-lg text-xs font-bold">
                        <CheckCircle className="w-3 h-3" /> Current
                      </div>
                    )}
                  </div>
                </div>

                {pk !== 'local' && (
                  <div className="space-y-3 mb-4">
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <Input
                          type={creds.visibleKeys[pk] ? 'text' : 'password'}
                          placeholder={provider.placeholder}
                          value={creds.credentialInputs[pk] || ''}
                          onChange={(e) => creds.handleCredentialChange(pk, e.target.value)}
                          disabled={isSaving}
                          className="pr-10"
                        />
                        <button
                          onClick={() => creds.toggleKeyVisibility(pk)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface transition-colors"
                          tabIndex={-1}
                        >
                          {creds.visibleKeys[pk] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      {hasInput && (
                        <Button size="sm" onClick={() => creds.handleSaveCredential(pk)} disabled={isSaving} variant={isSaving ? 'outline' : 'default'}>
                          {isSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        </Button>
                      )}
                    </div>
                    {!hasInput && !isConfigured && (
                      <a href={provider.url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1">
                        Get API key <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {isConfigured && (
                      <Button size="sm" variant="destructive" onClick={() => creds.handleDeleteClick(pk)} disabled={isDeleting || isSaving} className="w-full text-xs">
                        {isDeleting ? <RefreshCw className="w-3 h-3 animate-spin mr-1" /> : <Trash2 className="w-3 h-3 mr-1" />}
                        {isDeleting ? 'Deleting...' : 'Delete Credentials'}
                      </Button>
                    )}
                    <div className="flex items-start gap-2 p-3 bg-surface-container rounded text-xs text-on-surface-variant">
                      <Lock className="w-3 h-3 flex-shrink-0 mt-0.5" />
                      <p>API keys are stored locally in your Guppy data directory. Never share your key.</p>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* Delete confirmation modal */}
      {creds.deleteConfirm.visible && creds.deleteConfirm.provider && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="max-w-md">
            <CardHeader>
              <CardTitle className="text-on-surface">Delete Credentials?</CardTitle>
              <CardDescription>
                This will permanently delete your {PROVIDERS[creds.deleteConfirm.provider].label} API credentials.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-on-surface-variant">You can re-add them at any time.</p>
              <div className="flex gap-3">
                <Button variant="outline" onClick={creds.handleCancelDelete} className="flex-1">Cancel</Button>
                <Button variant="destructive" onClick={creds.handleConfirmDelete} className="flex-1">Delete</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
