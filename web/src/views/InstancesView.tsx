import { useEffect, useRef, useState } from 'react'
import { Server, Play, Square, Settings, MoreHorizontal, RefreshCw, X } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import api from '../api/client'

/**
 * Instance data structure
 * 
 * BACKEND INTEGRATION:
 * - GET /api/instances -> List all instances
 * - POST /api/instances -> Create new instance
 * - POST /api/instances/:name/start -> Start instance
 * - POST /api/instances/:name/stop -> Stop instance
 * - DELETE /api/instances/:name -> Delete instance
 */
interface Instance {
  name: string
  description?: string
  type?: string
  mode?: string
  persona?: string
  status?: 'running' | 'stopped' | 'error' | 'starting'
  enabled?: boolean
  uptime?: string
  lastActive?: string
}

/**
 * InstancesView - Manage Guppy instances
 * 
 * BACKEND INTEGRATION:
 * - GET /api/instances - Fetch all instances with status
 * - POST /api/instances - Create new instance { name, description, type, mode }
 * - POST /api/instances/:name/start - Start a stopped instance
 * - POST /api/instances/:name/stop - Stop a running instance
 * - DELETE /api/instances/:name - Remove an instance
 */
export default function InstancesView() {
  const [instances, setInstances] = useState<Instance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newInstanceName, setNewInstanceName] = useState('')
  const [creating, setCreating] = useState(false)
  const nameInputRef = useRef<HTMLInputElement>(null)

  const fetchInstances = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/instances')
      const instanceData = response.data.instances || []
      setInstances(Array.isArray(instanceData) ? instanceData : [])
      setError(null)
    } catch (err: any) {
      console.error('Failed to fetch instances:', err)
      setError('Unable to load instances')
      setInstances([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInstances()
  }, [])

  const handleStartInstance = async (name: string) => {
    try {
      await api.post(`/api/instances/${name}/start`)
      fetchInstances()
    } catch (err) {
      console.error('Failed to start instance:', err)
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
      fetchInstances()
    } catch {
      toast.error('Failed to create instance')
    } finally {
      setCreating(false)
    }
  }

  const handleStopInstance = async (name: string) => {
    try {
      await api.post(`/api/instances/${name}/stop`)
      fetchInstances()
    } catch (err) {
      console.error('Failed to stop instance:', err)
    }
  }

  const getStatusVariant = (status?: string): "success" | "destructive" | "warning" | "secondary" => {
    switch (status) {
      case 'running': return 'success'
      case 'stopped': return 'secondary'
      case 'error': return 'destructive'
      case 'starting': return 'warning'
      default: return 'secondary'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Instances</h1>
          <p className="text-muted-foreground">
            Manage your Guppy assistant instances
          </p>
        </div>
        <Button variant="outline" onClick={fetchInstances} disabled={loading}>
          <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <RefreshCw className="w-8 h-8 animate-spin" />
            <p>Loading instances...</p>
          </div>
        </div>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64">
            <p className="text-destructive font-medium">{error}</p>
            <Button variant="outline" className="mt-4" onClick={fetchInstances}>
              Try Again
            </Button>
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
              Instances are defined in <code className="text-xs bg-muted px-1 rounded">config/instances.json</code>. Restart the API after editing.
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
              statusVariant={getStatusVariant(instance.status)}
            />
          ))}
        </div>
      )}

      {/* Create Instance Modal */}
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
    </div>
  )
}

interface InstanceCardProps {
  instance: Instance
  onStart: () => void
  onStop: () => void
  statusVariant: "success" | "destructive" | "warning" | "secondary"
}

function InstanceCard({ instance, onStart, onStop, statusVariant }: InstanceCardProps) {
  const isRunning = instance.status === 'running'

  return (
    <Card className="group hover:border-primary/50 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center",
              isRunning ? "bg-success/10" : "bg-muted"
            )}>
              <Server className={cn(
                "w-5 h-5",
                isRunning ? "text-success" : "text-muted-foreground"
              )} />
            </div>
            <div>
              <CardTitle className="text-base">{instance.name}</CardTitle>
              {instance.type && (
                <p className="text-xs text-muted-foreground">{instance.type}</p>
              )}
            </div>
          </div>
          <Badge variant={statusVariant}>
            {instance.status || 'unknown'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {instance.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {instance.description}
          </p>
        )}

        {/* Instance metadata */}
        <div className="flex flex-wrap gap-2 text-xs">
          {instance.mode && (
            <span className="px-2 py-1 bg-muted rounded-md">
              Mode: {instance.mode}
            </span>
          )}
          {instance.persona && (
            <span className="px-2 py-1 bg-muted rounded-md">
              Persona: {instance.persona}
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-border">
          {isRunning ? (
            <Button variant="outline" size="sm" onClick={onStop} className="flex-1">
              <Square className="w-3 h-3 mr-2" />
              Stop
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={onStart} className="flex-1">
              <Play className="w-3 h-3 mr-2" />
              Start
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            title="Instance settings"
            onClick={() => toast.info(`Settings for "${instance.name}" coming in Phase 3`)}
          >
            <Settings className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            title="More options"
            onClick={() => toast.info(`More options for "${instance.name}" coming soon`)}
          >
            <MoreHorizontal className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
