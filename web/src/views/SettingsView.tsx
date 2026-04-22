import { useEffect, useState } from 'react'
import { Save, CheckCircle, XCircle, ExternalLink, Moon, Sun, Sliders } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'
import api from '../api/client'

/**
 * Provider status interfaces
 * 
 * BACKEND INTEGRATION:
 * - GET /api/providers -> Get provider configuration status
 * - Settings are env-var driven and require server restart
 */
interface ProviderStatus {
  configured: boolean
  active_model: string
}

interface Providers {
  anthropic: ProviderStatus
  openai: ProviderStatus
  google: ProviderStatus
  local: ProviderStatus & { backend: string }
}

const PROVIDER_DOCS: Record<string, { label: string; env: string; url: string }> = {
  anthropic: { label: 'Anthropic', env: 'ANTHROPIC_API_KEY', url: 'https://console.anthropic.com/account/keys' },
  openai: { label: 'OpenAI', env: 'OPENAI_API_KEY', url: 'https://platform.openai.com/api-keys' },
  google: { label: 'Google', env: 'GOOGLE_API_KEY', url: 'https://aistudio.google.com/app/apikey' },
}

/**
 * SettingsView - Application configuration
 * 
 * BACKEND INTEGRATION:
 * - GET /api/providers - Get current provider configuration
 * - Settings are primarily env-var driven
 * - UI preferences stored in localStorage
 */
export default function SettingsView() {
  const [providers, setProviders] = useState<Providers | null>(null)
  const [saved, setSaved] = useState(false)
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState('4096')
  const { theme, toggleTheme, resolvedTheme } = useTheme()

  useEffect(() => {
    api.get('/providers').then((r) => setProviders(r.data)).catch(() => {})
  }, [])

  const handleSave = () => {
    // BACKEND: Settings could be sent to POST /api/settings
    // Currently stored in localStorage
    localStorage.setItem('guppy-settings', JSON.stringify({ temperature, maxTokens }))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground">
          Configure your Guppy assistant preferences
        </p>
      </div>

      {/* AI Providers */}
      <Card>
        <CardHeader>
          <CardTitle>AI Providers</CardTitle>
          <CardDescription>
            API keys are set in <code className="px-1 py-0.5 bg-muted rounded text-xs">.env</code> and require a server restart to take effect.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(PROVIDER_DOCS).map(([key, doc]) => {
            const status = providers?.[key as keyof typeof PROVIDER_DOCS]
            return (
              <div
                key={key}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border",
                  status?.configured ? "border-success/30 bg-success/5" : "border-border"
                )}
              >
                <div className="flex items-center gap-3">
                  {status?.configured ? (
                    <CheckCircle className="w-5 h-5 text-success" />
                  ) : (
                    <XCircle className="w-5 h-5 text-muted-foreground" />
                  )}
                  <div>
                    <p className="font-medium text-foreground">{doc.label}</p>
                    {status?.configured ? (
                      <p className="text-sm text-muted-foreground">
                        Active: <span className="text-foreground">{status.active_model}</span>
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Set <code className="px-1 py-0.5 bg-muted rounded text-xs">{doc.env}</code>
                      </p>
                    )}
                  </div>
                </div>
                {!status?.configured && (
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-sm text-primary hover:underline"
                  >
                    Get API Key
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            )
          })}

          {/* Local Provider */}
          <div
            className={cn(
              "flex items-center justify-between p-4 rounded-lg border",
              providers?.local?.configured ? "border-success/30 bg-success/5" : "border-border"
            )}
          >
            <div className="flex items-center gap-3">
              {providers?.local?.configured ? (
                <CheckCircle className="w-5 h-5 text-success" />
              ) : (
                <XCircle className="w-5 h-5 text-muted-foreground" />
              )}
              <div>
                <p className="font-medium text-foreground">Local</p>
                {providers?.local && (
                  <p className="text-sm text-muted-foreground">
                    Backend: <span className="text-foreground">{providers.local.backend}</span>
                  </p>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {resolvedTheme === 'dark' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
            Appearance
          </CardTitle>
          <CardDescription>Customize the look and feel</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-foreground">Theme</p>
              <p className="text-sm text-muted-foreground">Switch between light and dark mode</p>
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
              <label htmlFor="temperature" className="text-sm font-medium text-foreground">
                Temperature
              </label>
              <span className="text-sm text-muted-foreground">{temperature}</span>
            </div>
            <input
              id="temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <p className="text-xs text-muted-foreground">
              Lower values produce more focused outputs, higher values increase creativity
            </p>
          </div>

          <div className="space-y-3">
            <label htmlFor="max-tokens" className="text-sm font-medium text-foreground">
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
            <p className="text-xs text-muted-foreground">
              Maximum number of tokens in the model response
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} className="min-w-[120px]">
          <Save className="w-4 h-4 mr-2" />
          {saved ? 'Saved!' : 'Save Settings'}
        </Button>
      </div>
    </div>
  )
}
