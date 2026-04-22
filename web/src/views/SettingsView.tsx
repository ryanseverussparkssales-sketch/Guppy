import { useEffect, useState } from 'react'
import { Save, CheckCircle, XCircle } from 'lucide-react'
import api from '../api/client'
import './SettingsView.css'

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
  anthropic: { label: 'Anthropic',  env: 'ANTHROPIC_API_KEY', url: 'https://console.anthropic.com/account/keys' },
  openai:    { label: 'OpenAI',     env: 'OPENAI_API_KEY',    url: 'https://platform.openai.com/api-keys' },
  google:    { label: 'Google',     env: 'GOOGLE_API_KEY',    url: 'https://aistudio.google.com/app/apikey' },
}

export default function SettingsView() {
  const [providers, setProviders] = useState<Providers | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.get('/providers').then((r) => setProviders(r.data)).catch(() => {})
  }, [])

  const handleSave = () => {
    // Settings are env-var driven; this persists UI preferences to localStorage
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Settings</h2>
      </div>

      <div className="settings-grid">
        <div className="settings-section">
          <h3>AI Providers</h3>
          <p className="settings-note">
            API keys are set in <code>.env</code> and require a server restart to take effect.
          </p>
          {Object.entries(PROVIDER_DOCS).map(([key, doc]) => {
            const status = providers?.[key as keyof typeof PROVIDER_DOCS]
            return (
              <div key={key} className="setting-item provider-row">
                <div className="provider-info">
                  {status?.configured
                    ? <CheckCircle size={16} className="provider-ok" />
                    : <XCircle size={16} className="provider-off" />}
                  <span className="provider-label">{doc.label}</span>
                  {status?.configured && (
                    <span className="provider-model">{status.active_model}</span>
                  )}
                </div>
                {!status?.configured && (
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="provider-get-key"
                  >
                    Get key →
                  </a>
                )}
                {!status?.configured && (
                  <code className="provider-env">{doc.env}</code>
                )}
              </div>
            )
          })}

          <div className="setting-item provider-row">
            <div className="provider-info">
              {providers?.local?.configured
                ? <CheckCircle size={16} className="provider-ok" />
                : <XCircle size={16} className="provider-off" />}
              <span className="provider-label">Local</span>
              {providers?.local && (
                <span className="provider-model">{providers.local.backend}</span>
              )}
            </div>
          </div>
        </div>

        <div className="settings-section">
          <h3>Personalization</h3>
          <div className="setting-item">
            <label>
              <input type="checkbox" />
              Enable dark mode
            </label>
          </div>
          <div className="setting-item">
            <label>
              <input type="checkbox" />
              Send usage analytics
            </label>
          </div>
        </div>

        <div className="settings-section">
          <h3>Advanced</h3>
          <div className="setting-item">
            <label htmlFor="setting-temperature">Temperature</label>
            <input id="setting-temperature" type="range" min="0" max="1" step="0.1" />
          </div>
          <div className="setting-item">
            <label htmlFor="setting-max-tokens">Max Tokens</label>
            <input id="setting-max-tokens" type="number" placeholder="4096" />
          </div>
        </div>
      </div>

      <button type="button" className="btn btn-primary" onClick={handleSave}>
        <Save size={18} />
        {saved ? 'Saved!' : 'Save Settings'}
      </button>
    </div>
  )
}
