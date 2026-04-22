import { useEffect, useState } from 'react'
import { Download, Trash2, RefreshCw, CheckCircle, XCircle } from 'lucide-react'
import api from '../api/client'
import './ModelsView.css'

interface ModelEntry {
  id: string
  name: string
  tier: string
  provider: string
  configured: boolean
}

interface ProviderInfo {
  configured: boolean
  active_model: string
  models: { id: string; name: string; tier: string }[]
  backend?: string
  backends?: Record<string, { alive: boolean }>
}

interface ProvidersPayload {
  anthropic: ProviderInfo
  openai: ProviderInfo
  google: ProviderInfo
  local: ProviderInfo & { backend: string; backends: Record<string, { alive: boolean }> }
}

type Tab = 'local' | 'anthropic' | 'openai' | 'google'

export default function ModelsView() {
  const [providers, setProviders] = useState<ProvidersPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<Tab>('local')
  const [pullName, setPullName] = useState('')
  const [pullJobId, setPullJobId] = useState<string | null>(null)
  const [pullStatus, setPullStatus] = useState<Record<string, unknown> | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchProviders = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/providers')
      setProviders(res.data)
    } catch (e) {
      setError('Failed to load provider status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProviders()
  }, [])

  // Poll pull job progress
  useEffect(() => {
    if (!pullJobId) return
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/models/pull/${pullJobId}`)
        setPullStatus(res.data)
        if (res.data.done) {
          clearInterval(interval)
          fetchProviders()
        }
      } catch {
        clearInterval(interval)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [pullJobId])

  const handlePull = async () => {
    if (!pullName.trim()) return
    try {
      const res = await api.post('/api/models/pull', { name: pullName.trim() })
      setPullJobId(res.data.job_id)
      setPullStatus({ status: 'queued', progress: 0, done: false })
      setPullName('')
    } catch {
      setError('Failed to start pull')
    }
  }

  const handleDelete = async (modelId: string) => {
    if (!confirm(`Delete model "${modelId}"?`)) return
    setDeleting(modelId)
    try {
      await api.delete(`/api/models/${modelId}`)
      fetchProviders()
    } catch {
      setError(`Failed to delete ${modelId}`)
    } finally {
      setDeleting(null)
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'local',     label: 'Local' },
    { id: 'anthropic', label: 'Anthropic' },
    { id: 'openai',    label: 'OpenAI' },
    { id: 'google',    label: 'Google' },
  ]

  const StatusIcon = ({ ok }: { ok: boolean }) =>
    ok
      ? <CheckCircle size={16} className="status-ok" />
      : <XCircle size={16} className="status-off" />

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Models</h2>
        <button type="button" className="btn btn-secondary" onClick={fetchProviders} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>

      {error && <div className="models-error">{error}</div>}

      <div className="models-tabs">
        {tabs.map((t) => {
          const info = providers?.[t.id]
          return (
            <button
              type="button"
              key={t.id}
              className={`models-tab ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {info && <StatusIcon ok={info.configured} />}
              {t.label}
              {info && (
                <span className="models-tab-count">{info.models.length}</span>
              )}
            </button>
          )
        })}
      </div>

      {loading && !providers ? (
        <div className="models-loading">Loading...</div>
      ) : (
        <div className="models-content">
          {activeTab === 'local' && providers && (
            <div>
              <div className="models-backend-bar">
                <span>Backend: <strong>{providers.local.backend}</strong></span>
                {Object.entries(providers.local.backends || {}).map(([name, b]) => (
                  <span key={name} className={`backend-badge ${b.alive ? 'alive' : 'dead'}`}>
                    {name}
                  </span>
                ))}
              </div>

              <div className="models-pull-row">
                <input
                  type="text"
                  className="models-pull-input"
                  placeholder="Model name to pull (e.g. llama3.2:3b)"
                  value={pullName}
                  onChange={(e) => setPullName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handlePull()}
                />
                <button type="button" className="btn btn-primary" onClick={handlePull} disabled={!pullName.trim()}>
                  <Download size={16} />
                  Pull
                </button>
              </div>

              {pullStatus && !pullStatus.done && (
                <div className="models-pull-progress">
                  <div className="pull-progress-label">
                    {String(pullStatus.status)} — {String(pullStatus.detail || '')}
                  </div>
                  <div className="pull-progress-bar">
                    <div
                      className="pull-progress-fill"
                      // @ts-expect-error CSS custom property
                      style={{ '--progress': `${pullStatus.progress}%` }}
                    />
                  </div>
                </div>
              )}
              {pullStatus?.done && pullStatus?.error && (
                <div className="models-error">Pull failed: {String(pullStatus.error)}</div>
              )}
              {pullStatus?.done && !pullStatus?.error && (
                <div className="models-success">Pull complete</div>
              )}

              <div className="grid">
                {providers.local.models.map((m) => (
                  <div key={m.id} className="card model-card">
                    <div className="model-card-header">
                      <span className="model-name">{m.id}</span>
                      <span className={`model-tier tier-${m.tier}`}>{m.tier}</span>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary model-delete-btn"
                      onClick={() => handleDelete(m.id)}
                      disabled={deleting === m.id}
                    >
                      <Trash2 size={14} />
                      {deleting === m.id ? 'Deleting…' : 'Remove'}
                    </button>
                  </div>
                ))}
                {providers.local.models.length === 0 && (
                  <div className="empty-state">
                    <p>No local models found. Pull one above.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab !== 'local' && providers && (
            <div>
              {!providers[activeTab].configured && (
                <div className="models-unconfigured">
                  <XCircle size={20} />
                  <div>
                    <strong>Not configured.</strong> Add{' '}
                    {activeTab === 'anthropic' && <code>ANTHROPIC_API_KEY</code>}
                    {activeTab === 'openai'    && <code>OPENAI_API_KEY</code>}
                    {activeTab === 'google'    && <code>GOOGLE_API_KEY</code>}
                    {' '}to your <code>.env</code> and restart the server.
                  </div>
                </div>
              )}
              <div className="grid">
                {providers[activeTab].models.map((m) => (
                  <div key={m.id} className={`card model-card ${providers[activeTab].active_model === m.id ? 'model-active' : ''}`}>
                    <div className="model-card-header">
                      <span className="model-name">{m.name}</span>
                      <span className={`model-tier tier-${m.tier}`}>{m.tier}</span>
                    </div>
                    <span className="model-id">{m.id}</span>
                    {providers[activeTab].active_model === m.id && (
                      <span className="model-active-badge">active</span>
                    )}
                  </div>
                ))}
                {providers[activeTab].models.length === 0 && providers[activeTab].configured && (
                  <div className="empty-state"><p>No models available.</p></div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
