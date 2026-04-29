import { useEffect, useRef, useState } from 'react'
import { Server, Play, Square, Settings, MoreHorizontal, RefreshCw, X, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import api from '../api/client'

interface Connector {
  id: string
  label: string
  category: string
  auth_state: string
}

interface Governance {
  auth_mode?: string
  auth_mode_label?: string
  policy_note?: string
  capabilities?: Record<string, boolean>
}

interface Instance {
  name: string
  description?: string
  type?: string
  mode?: string
  persona?: string
  voice?: string
  status?: 'running' | 'stopped' | 'error' | 'starting' | 'active'
  enabled?: boolean
  uptime?: string
  lastActive?: string
  message_count?: number
  connectors?: Connector[]
  governance?: Governance
}

export default function InstancesView() {
  const [instances, setInstances] = useState<Instance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newInstanceName, setNewInstanceName] = useState('')
  const [creating, setCreating] = useState(false)
  const [configInstance, setConfigInstance] = useState<Instance | null>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)

  const fetchInstances = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/instances')
      const instanceData = response.data.instances || []
      setInstances(Array.isArray(instanceData) ? instanceData : [])
      setError(null)
    } catch (err: unknown) {
      console.error('Failed to fetch instances:', err)
      setError('Unable to load instances')
      setInstances([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchInstances() }, [])

  const handleStartInstance = async (name: string) => {
    try {
      await api.post(`/api/instances/${name}/start`)
      fetchInstances()
    } catch (err) {
      console.error('Failed to start instance:', err)
      toast.error(`Failed to start "${name}"`)
    }
  }

  const handleStopInstance = async (name: string) => {
    try {
      await api.post(`/api/instances/${name}/stop`)
      fetchInstances()
    } catch (err) {
      console.error('Failed to stop instance:', err)
      toast.error(`Failed to stop "${name}"`)
    }
  }

  const handleViewLogs = async (name: string) => {
    try {
      const r = await api.get(`/api/instances/${name}/logs`)
      const entries: unknown[] = Array.isArray(r.data?.logs) ? r.data.logs : []
      if (entries.length === 0) {
        toast.info(`No logs for "${name}"`)
      } else {
        toast.info(`${entries.length} log entries — check Admin › Activity for details`)
      }
    } catch {
      toast.error('Could not fetch logs')
    }
  }

  const handleCreateInstance = async () => {
    const name = newInstanceName.trim()
    if (!name) return
    setCreating(true)
    try {
      await api.post('/api/instances', { name })
      toast.success(`Instance "${name}" created`)
      setShowCreateModal(false)
      setNewInstanceName('')
      fetchInstances()
    } catch {
      toast.error('Failed to create instance')
    } finally {
      setCreating(false)
    }
  }

  const getStatusVariant = (status?: string): 'success' | 'destructive' | 'warning' | 'secondary' => {
    if (status === 'running' || status === 'active') return 'success'
    if (status === 'error') return 'destructive'
    if (status === 'starting') return 'warning'
    return 'secondary'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Instances</h1>
          <p className="text-muted-foreground">Manage your Guppy assistant instances</p>
        </div>
        <Button variant="outline" onClick={fetchInstances} disabled={loading}>
          <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <RefreshCw className="w-8 h-8 animate-spin" />
            <p>Loading instances…</p>
          </div>
        </div>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64">
            <p className="text-destructive font-medium">{error}</p>
            <Button variant="outline" className="mt-4" onClick={fetchInstances}>Try Again</Button>
          </CardContent>
        </Card>
      ) : instances.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64 text-center">
            <div className="w-16 h-16 mb-4 rounded-2xl bg-muted flex items-center justify-center">
              <Server className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">No instances configured</h3>
            <p className="text-muted-foreground mb-4 max-w-sm">
              Instances are defined in{' '}
              <code className="text-xs bg-muted px-1 rounded">config/instances.json</code>.
              Restart the API after editing.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {instances.map((instance) => (
            <InstanceCard
              key={instance.name}
              instance={instance}
              onStart={() => handleStartInstance(instance.name)}
              onStop={() => handleStopInstance(instance.name)}
              onViewLogs={() => handleViewLogs(instance.name)}
              onViewConfig={() => setConfigInstance(instance)}
              statusVariant={getStatusVariant(instance.status)}
            />
          ))}
        </div>
      )}

      {/* ── Create modal ───────────────────────────────────────────────── */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowCreateModal(false)} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg p-6 w-full max-w-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">New Instance</h2>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowCreateModal(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>
            <input
              ref={nameInputRef}
              type="text"
              value={newInstanceName}
              onChange={(e) => setNewInstanceName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateInstance()}
              placeholder="Instance name"
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-foreground text-sm outline-none focus:ring-2 focus:ring-primary mb-4"
            />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowCreateModal(false)}>Cancel</Button>
              <Button onClick={handleCreateInstance} disabled={creating || !newInstanceName.trim()}>
                {creating ? 'Creating…' : 'Create'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Config/settings modal ──────────────────────────────────────── */}
      {configInstance && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setConfigInstance(null)} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">{configInstance.name} — Configuration</h2>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setConfigInstance(null)}>
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="space-y-4 text-sm">
              {/* Core fields */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  ['Type',    configInstance.type],
                  ['Mode',    configInstance.mode],
                  ['Persona', configInstance.persona],
                  ['Voice',   configInstance.voice],
                  ['Messages', String(configInstance.message_count ?? 0)],
                ].filter(([, v]) => v).map(([k, v]) => (
                  <div key={k} className="p-3 rounded-lg bg-muted/50">
                    <p className="text-xs text-muted-foreground mb-0.5">{k}</p>
                    <p className="font-medium text-foreground">{v}</p>
                  </div>
                ))}
              </div>

              {/* Capabilities */}
              {configInstance.governance?.capabilities && (
                <div>
                  <p className="font-semibold text-foreground mb-2">Capabilities</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(configInstance.governance.capabilities).map(([cap, allowed]) => (
                      <Badge key={cap} variant={allowed ? 'success' : 'secondary'}>
                        {allowed ? '✓' : '✗'} {cap}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Policy note */}
              {configInstance.governance?.policy_note && (
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Policy</p>
                  <p className="text-foreground">{configInstance.governance.policy_note}</p>
                </div>
              )}

              {/* Connectors */}
              {configInstance.connectors && configInstance.connectors.length > 0 && (
                <div>
                  <p className="font-semibold text-foreground mb-2">Connectors</p>
                  <div className="space-y-2">
                    {configInstance.connectors.map((c) => (
                      <div key={c.id} className="flex items-center justify-between p-2 rounded-lg bg-muted/30">
                        <span className="text-foreground">{c.label}</span>
                        <Badge variant={c.auth_state === 'connected' ? 'success' : c.auth_state === 'partial' ? 'warning' : 'secondary'}>
                          {c.auth_state}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-xs text-muted-foreground pt-2">
                Instance config is read from <code className="bg-muted px-1 rounded">config/instances.json</code>. Edit the file and restart the API to change settings.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface InstanceCardProps {
  instance: Instance
  onStart: () => void
  onStop: () => void
  onViewLogs: () => void
  onViewConfig: () => void
  statusVariant: 'success' | 'destructive' | 'warning' | 'secondary'
}

function InstanceCard({ instance, onStart, onStop, onViewLogs, onViewConfig, statusVariant }: InstanceCardProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const isRunning = instance.status === 'running' || instance.status === 'active'

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  return (
    <Card className="group hover:border-primary/50 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', isRunning ? 'bg-success/10' : 'bg-muted')}>
              <Server className={cn('w-5 h-5', isRunning ? 'text-success' : 'text-muted-foreground')} />
            </div>
            <div>
              <CardTitle className="text-base">{instance.name}</CardTitle>
              {instance.type && <p className="text-xs text-muted-foreground">{instance.type}</p>}
            </div>
          </div>
          <Badge variant={statusVariant}>{instance.status || 'unknown'}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {instance.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">{instance.description}</p>
        )}
        <div className="flex flex-wrap gap-2 text-xs">
          {instance.mode    && <span className="px-2 py-1 bg-muted rounded-md">Mode: {instance.mode}</span>}
          {instance.persona && <span className="px-2 py-1 bg-muted rounded-md">Persona: {instance.persona}</span>}
        </div>

        <div className="flex items-center gap-2 pt-2 border-t border-border">
          {isRunning ? (
            <Button variant="outline" size="sm" onClick={onStop} className="flex-1">
              <Square className="w-3 h-3 mr-2" /> Stop
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={onStart} className="flex-1">
              <Play className="w-3 h-3 mr-2" /> Start
            </Button>
          )}

          {/* Settings gear — opens config modal */}
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Instance config" onClick={onViewConfig}>
            <Settings className="w-4 h-4" />
          </Button>

          {/* More options — inline mini-menu */}
          <div className="relative" ref={menuRef}>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="More options"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <MoreHorizontal className="w-4 h-4" />
            </Button>
            {menuOpen && (
              <div className="absolute right-0 bottom-10 z-20 w-40 bg-card border border-border rounded-lg shadow-lg overflow-hidden">
                <button
                  type="button"
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  onClick={() => { setMenuOpen(false); onViewLogs() }}
                >
                  <ChevronRight className="w-3 h-3" /> View Logs
                </button>
                <button
                  type="button"
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  onClick={() => { setMenuOpen(false); onViewConfig() }}
                >
                  <ChevronRight className="w-3 h-3" /> View Config
                </button>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
