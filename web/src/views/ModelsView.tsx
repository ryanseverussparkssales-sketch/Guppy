import { useEffect, useState } from 'react'
import { Download, Trash2, RefreshCw, CheckCircle, XCircle, Brain, Cloud, Cpu } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import api from '../api/client'

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

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'local', label: 'Local', icon: <Cpu className="w-4 h-4" /> },
  { id: 'anthropic', label: 'Anthropic', icon: <Cloud className="w-4 h-4" /> },
  { id: 'openai', label: 'OpenAI', icon: <Cloud className="w-4 h-4" /> },
  { id: 'google', label: 'Google', icon: <Cloud className="w-4 h-4" /> },
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

  const getTierColor = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'premium': return 'bg-amber-500/10 text-amber-500 border-amber-500/20'
      case 'standard': return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
      case 'basic': return 'bg-slate-500/10 text-slate-400 border-slate-500/20'
      default: return 'bg-muted text-muted-foreground'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Models</h1>
          <p className="text-muted-foreground">
            Manage LLM providers and available models
          </p>
        </div>
        <Button variant="outline" onClick={fetchProviders} disabled={loading}>
          <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive">
          {error}
        </div>
      )}

      {/* Provider Tabs */}
      <div className="flex items-center gap-2 p-1 bg-muted/50 rounded-lg w-fit">
        {TABS.map((tab) => {
          const info = providers?.[tab.id]
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {info && (
                info.configured
                  ? <CheckCircle className="w-4 h-4 text-success" />
                  : <XCircle className="w-4 h-4 text-muted-foreground" />
              )}
              {tab.icon}
              {tab.label}
              {info && (
                <Badge variant="secondary" className="ml-1 text-xs">
                  {info.models.length}
                </Badge>
              )}
            </button>
          )
        })}
      </div>

      {/* Content */}
      {loading && !providers ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <RefreshCw className="w-8 h-8 animate-spin" />
            <p>Loading providers...</p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Local Tab */}
          {activeTab === 'local' && providers && (
            <>
              {/* Backend Status */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Local Backend Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-muted-foreground">
                      Active: <span className="font-medium text-foreground">{providers.local.backend}</span>
                    </span>
                    <div className="flex items-center gap-2">
                      {Object.entries(providers.local.backends || {}).map(([name, b]) => (
                        <Badge
                          key={name}
                          variant={b.alive ? "success" : "secondary"}
                          className="text-xs"
                        >
                          {name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Pull Model */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Pull New Model</CardTitle>
                  <CardDescription>
                    Download a model from Ollama registry (e.g., llama3.2:3b)
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-2">
                    <Input
                      placeholder="Model name (e.g., llama3.2:3b)"
                      value={pullName}
                      onChange={(e) => setPullName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handlePull()}
                      className="flex-1"
                    />
                    <Button onClick={handlePull} disabled={!pullName.trim()}>
                      <Download className="w-4 h-4 mr-2" />
                      Pull
                    </Button>
                  </div>

                  {pullStatus && !pullStatus.done && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">
                          {pullStatus.status} {pullStatus.detail && `- ${pullStatus.detail}`}
                        </span>
                        <span className="font-medium">{pullStatus.progress.toFixed(0)}%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-300"
                          style={{ width: `${pullStatus.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {pullStatus?.done && pullStatus?.error && (
                    <p className="text-sm text-destructive">Pull failed: {pullStatus.error}</p>
                  )}
                  {pullStatus?.done && !pullStatus?.error && (
                    <p className="text-sm text-success">Pull complete!</p>
                  )}
                </CardContent>
              </Card>

              {/* Local Models Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {providers.local.models.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    isActive={providers.local.active_model === model.id}
                    onDelete={() => handleDelete(model.id)}
                    deleting={deleting === model.id}
                    tierColor={getTierColor(model.tier)}
                    showDelete
                  />
                ))}
                {providers.local.models.length === 0 && (
                  <Card className="col-span-full">
                    <CardContent className="flex flex-col items-center justify-center h-32 text-center">
                      <Brain className="w-8 h-8 text-muted-foreground mb-2" />
                      <p className="text-muted-foreground">No local models found. Pull one above.</p>
                    </CardContent>
                  </Card>
                )}
              </div>
            </>
          )}

          {/* Cloud Provider Tabs */}
          {activeTab !== 'local' && providers && (
            <>
              {!providers[activeTab].configured && (
                <Card className="border-warning/20 bg-warning/5">
                  <CardContent className="flex items-center gap-4 py-4">
                    <XCircle className="w-6 h-6 text-warning" />
                    <div>
                      <p className="font-medium text-foreground">Not configured</p>
                      <p className="text-sm text-muted-foreground">
                        Add{' '}
                        <code className="px-1 py-0.5 bg-muted rounded text-xs">
                          {activeTab === 'anthropic' && 'ANTHROPIC_API_KEY'}
                          {activeTab === 'openai' && 'OPENAI_API_KEY'}
                          {activeTab === 'google' && 'GOOGLE_API_KEY'}
                        </code>{' '}
                        to your <code className="px-1 py-0.5 bg-muted rounded text-xs">.env</code> and restart the server.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {providers[activeTab].models.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    isActive={providers[activeTab].active_model === model.id}
                    tierColor={getTierColor(model.tier)}
                  />
                ))}
                {providers[activeTab].models.length === 0 && providers[activeTab].configured && (
                  <Card className="col-span-full">
                    <CardContent className="flex flex-col items-center justify-center h-32 text-center">
                      <Cloud className="w-8 h-8 text-muted-foreground mb-2" />
                      <p className="text-muted-foreground">No models available.</p>
                    </CardContent>
                  </Card>
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
  model: { id: string; name: string; tier: string }
  isActive: boolean
  onDelete?: () => void
  deleting?: boolean
  tierColor: string
  showDelete?: boolean
}

function ModelCard({ model, isActive, onDelete, deleting, tierColor, showDelete }: ModelCardProps) {
  return (
    <Card className={cn(
      "transition-colors",
      isActive && "border-primary"
    )}>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <Brain className={cn(
              "w-5 h-5",
              isActive ? "text-primary" : "text-muted-foreground"
            )} />
            <span className="font-medium text-foreground">{model.name || model.id}</span>
          </div>
          <Badge className={cn("text-xs border", tierColor)}>
            {model.tier}
          </Badge>
        </div>

        <p className="text-xs text-muted-foreground font-mono mb-3">{model.id}</p>

        <div className="flex items-center justify-between">
          {isActive && (
            <Badge variant="success" className="text-xs">Active</Badge>
          )}
          {showDelete && onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDelete}
              disabled={deleting}
              className="ml-auto text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              {deleting ? 'Deleting...' : 'Remove'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
