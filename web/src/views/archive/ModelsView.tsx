import { useEffect, useState } from 'react'
import { Download, Trash2, RefreshCw, CheckCircle, XCircle, Brain, Cloud, Cpu, Activity, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

const _BACKEND_LABELS: Record<string, string> = {
  ollama:              'Ollama',
  lmstudio:            'LM Studio',
  lemonade:            'Lemonade',
  local_harness:       'Local Harness',
  'llamacpp-gemma':    'Gemma 4 Heretic',
  'llamacpp-qwen3':    'Qwen3 Uncensored',
  'llamacpp-pepe':     'Pepe 8B',
  'llamacpp-minicpm':  'MiniCPM-o 4.5',
  'llamacpp-dispatch': 'Qwen2.5-Omni 3B',
}

/**
 * Model and Provider interfaces
 * 
 * BACKEND INTEGRATION:
 * - GET /api/providers -> Get all provider status and models
 * - POST /api/models/pull -> Pull a new local model { name: string }
 * - GET /api/models/pull/:jobId -> Check pull job status
 * - DELETE /api/models/:id -> Delete a local model
 */
interface PullStatus {
  status: string
  progress: number
  done: boolean
  detail?: string
  error?: string
}

interface ProviderInfo {
  configured: boolean
  active_model: string
  models: { id: string; name: string; tier: string; backend?: string }[]
  backend?: string
  backends?: Record<string, { alive: boolean; label?: string }>
}

interface ProvidersPayload {
  anthropic: ProviderInfo
  openai: ProviderInfo
  google: ProviderInfo
  cohere: ProviderInfo
  mistral: ProviderInfo
  local: ProviderInfo & { backend: string; backends: Record<string, { alive: boolean; label?: string }> }
}

type Tab = 'local' | 'anthropic' | 'openai' | 'google' | 'cohere' | 'mistral'

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'local',     label: 'Local',       icon: <Cpu className="w-4 h-4" /> },
  { id: 'anthropic', label: 'Anthropic',   icon: <Cloud className="w-4 h-4" /> },
  { id: 'openai',    label: 'OpenAI',      icon: <Cloud className="w-4 h-4" /> },
  { id: 'google',    label: 'Google',      icon: <Cloud className="w-4 h-4" /> },
  { id: 'cohere',    label: 'Cohere',      icon: <Cloud className="w-4 h-4" /> },
  { id: 'mistral',   label: 'Mistral AI',  icon: <Cloud className="w-4 h-4" /> },
]

/**
 * ModelsView - Manage LLM models and providers
 * 
 * BACKEND INTEGRATION:
 * - GET /api/providers - Get provider status and available models
 * - POST /api/models/pull - Start pulling a local model
 * - GET /api/models/pull/:jobId - Poll pull job progress
 * - DELETE /api/models/:id - Remove a local model
 */
export default function ModelsView() {
  const [providers, setProviders] = useState<ProvidersPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<Tab>('local')
  const [pullName, setPullName] = useState('')
  const [pullJobId, setPullJobId] = useState<string | null>(null)
  const [pullStatus, setPullStatus] = useState<PullStatus | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [activating, setActivating] = useState<string | null>(null)
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

  const handleActivate = async (provider: Tab, modelId: string) => {
    setActivating(modelId)
    try {
      await api.post(`/providers/${provider}/active-model`, { model_id: modelId })
      setProviders((prev) => {
        if (!prev) return prev
        return { ...prev, [provider]: { ...prev[provider], active_model: modelId } }
      })
    } catch {
      setError(`Failed to activate ${modelId}`)
    } finally {
      setActivating(null)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'verified':
      case 'active':
        return 'badge-verified'
      case 'premium':
        return 'badge-active'
      case 'ready':
      default:
        return 'badge-ready'
    }
  }

  return (
    <div className="px-12 py-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <span className="text-xs uppercase tracking-widest font-bold text-secondary mb-2 block">
            Neural Architecture Registry
          </span>
          <h1 className="text-3xl font-headline font-bold text-on-surface">Model Fleet</h1>
        </div>
        <button 
          onClick={fetchProviders} 
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-surface-container-lowest rounded-lg ghost-border text-on-surface hover:shadow-soft transition-all"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-error/10 border border-error/20 text-error mb-6">
          {error}
        </div>
      )}

      {/* Provider Tabs */}
      <div className="flex items-center gap-1 mb-8">
        {TABS.map((tab) => {
          const info = providers?.[tab.id]
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-200",
                activeTab === tab.id
                  ? "bg-primary text-white shadow-md"
                  : "text-on-surface-variant hover:bg-surface-container"
              )}
            >
              {info && (
                info.configured
                  ? <CheckCircle className="w-4 h-4" />
                  : <XCircle className="w-4 h-4 opacity-50" />
              )}
              {tab.icon}
              {tab.label}
              {info && (
                <span className={cn(
                  "px-2 py-0.5 rounded text-xs ml-1",
                  activeTab === tab.id ? "bg-white/20" : "bg-surface-container-high"
                )}>
                  {info.models.length}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Content */}
      {loading && !providers ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3 text-on-surface-variant">
            <RefreshCw className="w-8 h-8 animate-spin" />
            <p className="font-headline italic">Loading neural architectures...</p>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Local Tab */}
          {activeTab === 'local' && providers && (
            <>
              {/* Backend Status */}
              <div className="grid grid-cols-12 gap-6">
                <div className="col-span-8 bg-surface-container-lowest rounded-xl p-6 ghost-border">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <Activity className="w-5 h-5 text-primary" />
                      <h3 className="font-headline font-bold text-on-surface">Local Backend Status</h3>
                    </div>
                    <span className="text-sm text-on-surface-variant">
                      Active: <span className="font-bold text-secondary">{providers.local.backend}</span>
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    {Object.entries(providers.local.backends || {}).map(([name, b]) => (
                      <span
                        key={name}
                        title={name}
                        className={cn(
                          "px-3 py-1.5 rounded-full text-xs font-bold",
                          b.alive
                            ? "bg-primary/10 text-primary"
                            : "bg-surface-container text-on-surface-variant/50"
                        )}
                      >
                        {b.alive && <span className="inline-block w-2 h-2 rounded-full bg-primary mr-2 animate-pulse" />}
                        {b.label ?? name}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Pull Model Card */}
                <div className="col-span-4 bg-surface-container-lowest rounded-xl p-6 ghost-border">
                  <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-4">
                    Pull New Model
                  </h4>
                  <div className="flex gap-2 mb-4">
                    <input
                      placeholder="e.g., llama3.2:3b"
                      value={pullName}
                      onChange={(e) => setPullName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handlePull()}
                      className="flex-1 bg-surface-container px-4 py-2.5 rounded-lg text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <button 
                      onClick={handlePull} 
                      disabled={!pullName.trim()}
                      className={cn(
                        "px-4 py-2.5 rounded-lg font-bold text-sm transition-all",
                        pullName.trim()
                          ? "signature-gradient text-white shadow-md"
                          : "bg-surface-container text-on-surface-variant"
                      )}
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>

                  {pullStatus && !pullStatus.done && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-on-surface-variant">{pullStatus.status}</span>
                        <span className="font-bold text-secondary">{pullStatus.progress.toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
                        <div
                          className="h-full bg-secondary rounded-full transition-all duration-300"
                          style={{ width: `${pullStatus.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {pullStatus?.done && pullStatus?.error && (
                    <p className="text-xs text-error">Pull failed: {pullStatus.error}</p>
                  )}
                  {pullStatus?.done && !pullStatus?.error && (
                    <p className="text-xs text-primary font-bold">Pull complete!</p>
                  )}
                </div>
              </div>

              {/* Local Models Grid */}
              <div>
                <h3 className="text-xl font-headline font-bold text-on-surface mb-6">Available Architectures</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {providers.local.models.map((model) => (
                    <ModelCard
                      key={model.id}
                      model={model}
                      isActive={providers.local.active_model === model.id}
                      onDelete={() => handleDelete(model.id)}
                      onActivate={() => handleActivate('local', model.id)}
                      deleting={deleting === model.id}
                      activating={activating === model.id}
                      statusBadge={getStatusBadge(model.tier)}
                      showDelete
                    />
                  ))}
                  {providers.local.models.length === 0 && (
                    <div className="col-span-full bg-surface-container-lowest rounded-xl p-12 ghost-border text-center">
                      <Brain className="w-12 h-12 text-on-surface-variant/40 mx-auto mb-4" />
                      <p className="font-headline italic text-on-surface-variant">No local models found. Pull one above.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Cloud Provider Tabs */}
          {activeTab !== 'local' && providers && (
            <>
              {!providers[activeTab].configured && (
                <div className="bg-secondary/10 border border-secondary/20 rounded-xl p-6 flex items-center gap-4">
                  <Settings className="w-8 h-8 text-secondary flex-shrink-0" />
                  <div>
                    <p className="font-headline font-bold text-on-surface">Provider Not Configured</p>
                    <p className="text-sm text-on-surface-variant mt-1">
                      Add your API key in{' '}
                      <button
                        onClick={() => window.dispatchEvent(new CustomEvent('guppy:navigate', { detail: { view: 'settings' } }))}
                        className="text-primary underline hover:no-underline"
                      >
                        Settings → Providers &amp; Credentials
                      </button>
                      .
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {providers[activeTab].models.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    isActive={providers[activeTab].active_model === model.id}
                    onActivate={() => handleActivate(activeTab, model.id)}
                    activating={activating === model.id}
                    statusBadge={getStatusBadge(model.tier)}
                  />
                ))}
                {providers[activeTab].models.length === 0 && providers[activeTab].configured && (
                  <div className="col-span-full bg-surface-container-lowest rounded-xl p-12 ghost-border text-center">
                    <Cloud className="w-12 h-12 text-on-surface-variant/40 mx-auto mb-4" />
                    <p className="font-headline italic text-on-surface-variant">No models available.</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

interface ModelCardProps {
  model: { id: string; name: string; tier: string; backend?: string }
  isActive: boolean
  onDelete?: () => void
  onActivate?: () => void
  deleting?: boolean
  activating?: boolean
  statusBadge: string
  showDelete?: boolean
}

function ModelCard({ model, isActive, onDelete, onActivate, deleting, activating, statusBadge, showDelete }: ModelCardProps) {
  return (
    <div className={cn(
      "bg-surface-container-lowest rounded-xl p-6 ghost-border transition-all duration-300 hover:shadow-soft-lg hover:-translate-y-1",
      isActive && "ring-2 ring-primary"
    )}>
      <div className="flex items-start justify-between mb-4">
        <div className="p-3 bg-surface-container-low rounded-lg text-primary">
          <Brain className="w-5 h-5" />
        </div>
        <span className={statusBadge}>{model.tier}</span>
      </div>

      <h4 className="text-xl font-headline font-bold text-on-surface mb-2">{model.name || model.id}</h4>
      <p className="text-xs text-on-surface-variant font-mono mb-1 truncate">{model.id}</p>
      {model.backend && (
        <p className="text-xs text-secondary font-bold mb-3">{_BACKEND_LABELS[model.backend] ?? model.backend}</p>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-surface-container">
        {isActive ? (
          <span className="badge-verified">Active</span>
        ) : (
          <button
            onClick={onActivate}
            disabled={activating}
            className={cn(
              "text-xs px-3 py-1 rounded-lg font-medium transition-all",
              activating
                ? "bg-surface-container text-on-surface-variant"
                : "bg-primary/10 text-primary hover:bg-primary/20"
            )}
          >
            {activating ? (
              <span className="flex items-center gap-1"><RefreshCw className="w-3 h-3 animate-spin" /> Activating…</span>
            ) : 'Activate'}
          </button>
        )}

        {showDelete && onDelete && (
          <button
            onClick={onDelete}
            disabled={deleting}
            className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-error transition-colors"
          >
            <Trash2 className="w-3 h-3" />
            {deleting ? 'Deleting...' : 'Remove'}
          </button>
        )}
      </div>
    </div>
  )
}
