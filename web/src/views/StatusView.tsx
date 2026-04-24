import { useEffect, useState, useCallback } from 'react'
import { Activity, Zap, Mic, Database, CheckCircle, XCircle, AlertCircle, RefreshCw, Cpu, Server } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import api from '../api/client'

/**
 * Status interfaces
 * 
 * BACKEND INTEGRATION:
 * - GET /api/status -> Full system status
 * - Returns health checks, service availability, and runtime info
 */
interface ReadinessCheck {
  state: string
  detail: string
}

interface StatusData {
  status?: string
  message?: string
  memory_available?: boolean
  voice_available?: boolean
  daemon_available?: boolean
  guppy_core_available?: boolean
  startup_readiness?: {
    overall: string
    checks: Record<string, ReadinessCheck>
  }
  local_runtime?: {
    state: string
    backend: string
    chat_ready: boolean
    models?: string[]
  }
}

/**
 * StatusView - System health and status monitoring
 * 
 * BACKEND INTEGRATION:
 * - GET /api/status - Fetch current system status
 * - Auto-refreshes every 30 seconds
 * - Shows service availability, startup checks, and runtime info
 */
export default function StatusView() {
  const [statusData, setStatusData] = useState<StatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true)
      const response = await api.get('/status')
      setStatusData(response.data)
      setLastFetch(new Date())
    } catch (error) {
      console.error('Failed to fetch status:', error)
      setStatusData({ status: 'error', message: 'Failed to fetch system status' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const isHealthy = statusData?.status === 'healthy'
  const checks = statusData?.startup_readiness?.checks ?? {}

  const serviceCards = [
    {
      key: 'api',
      icon: <Activity className="w-6 h-6" />,
      title: 'API Status',
      available: isHealthy,
      label: isHealthy ? 'Healthy' : 'Unhealthy',
      detail: statusData?.message || 'Checking...',
    },
    {
      key: 'core',
      icon: <Zap className="w-6 h-6" />,
      title: 'Guppy Core',
      available: statusData?.guppy_core_available ?? false,
      label: statusData?.guppy_core_available ? 'Available' : 'Unavailable',
      detail: statusData?.guppy_core_available ? 'Core services ready' : 'Limited functionality',
    },
    {
      key: 'memory',
      icon: <Database className="w-6 h-6" />,
      title: 'Memory',
      available: statusData?.memory_available ?? false,
      label: statusData?.memory_available ? 'Available' : 'Unavailable',
      detail: statusData?.memory_available ? 'Memory backend operational' : 'Memory features disabled',
    },
    {
      key: 'voice',
      icon: <Mic className="w-6 h-6" />,
      title: 'Voice System',
      available: statusData?.voice_available ?? false,
      label: statusData?.voice_available ? 'Available' : 'Not Available',
      detail: statusData?.voice_available ? 'Voice features enabled' : 'Voice features disabled',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">System Status</h1>
          <p className="text-muted-foreground">
            Monitor your Guppy system health and services
          </p>
        </div>
        <div className="flex items-center gap-4">
          {lastFetch && (
            <span className="text-sm text-muted-foreground">
              Updated {lastFetch.toLocaleTimeString()}
            </span>
          )}
          <Button variant="outline" onClick={fetchStatus} disabled={loading}>
            <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {loading && !statusData ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <RefreshCw className="w-8 h-8 animate-spin" />
            <p>Loading system status...</p>
          </div>
        </div>
      ) : (
        <>
          {/* Service Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {serviceCards.map((card) => (
              <Card key={card.key} className={cn(
                "transition-colors",
                card.available ? "border-success/30" : "border-warning/30"
              )}>
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className={cn(
                      "p-3 rounded-xl",
                      card.available ? "bg-success/10 text-success" : "bg-warning/10 text-warning"
                    )}>
                      {card.icon}
                    </div>
                    <Badge variant={card.available ? "success" : "warning"}>
                      {card.label}
                    </Badge>
                  </div>
                  <h3 className="font-semibold text-foreground mb-1">{card.title}</h3>
                  <p className="text-sm text-muted-foreground">{card.detail}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Startup Readiness Checks */}
          {Object.keys(checks).length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Server className="w-5 h-5 text-primary" />
                      Startup Readiness
                    </CardTitle>
                    <CardDescription>Component initialization status</CardDescription>
                  </div>
                  <Badge
                    variant={
                      statusData?.startup_readiness?.overall === 'READY'
                        ? 'success'
                        : statusData?.startup_readiness?.overall === 'PARTIAL'
                        ? 'warning'
                        : 'destructive'
                    }
                  >
                    {statusData?.startup_readiness?.overall ?? 'Unknown'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(checks).map(([name, check]) => (
                    <div
                      key={name}
                      className={cn(
                        "flex items-center gap-4 p-3 rounded-lg",
                        check.state === 'READY' && "bg-success/5",
                        (check.state === 'PARTIAL' || check.state === 'SKIPPED') && "bg-warning/5",
                        check.state !== 'READY' && check.state !== 'PARTIAL' && check.state !== 'SKIPPED' && "bg-destructive/5"
                      )}
                    >
                      <StateIcon state={check.state} />
                      <span className="font-medium text-foreground min-w-[120px]">{name}</span>
                      <Badge
                        variant={
                          check.state === 'READY' ? 'success'
                            : check.state === 'PARTIAL' || check.state === 'SKIPPED' ? 'warning'
                            : 'destructive'
                        }
                        className="text-xs"
                      >
                        {check.state}
                      </Badge>
                      <span className="text-sm text-muted-foreground flex-1">{check.detail}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Local Runtime */}
          {statusData?.local_runtime && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-primary" />
                  Local Runtime
                </CardTitle>
                <CardDescription>Local LLM backend status</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Backend</p>
                    <p className="font-semibold text-foreground">{statusData.local_runtime.backend}</p>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">State</p>
                    <p className="font-semibold text-foreground">{statusData.local_runtime.state}</p>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Chat Ready</p>
                    <Badge variant={statusData.local_runtime.chat_ready ? "success" : "secondary"}>
                      {statusData.local_runtime.chat_ready ? 'Yes' : 'No'}
                    </Badge>
                  </div>
                  {statusData.local_runtime.models && statusData.local_runtime.models.length > 0 && (
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <p className="text-xs text-muted-foreground mb-1">Models</p>
                      <p className="font-semibold text-foreground text-sm">
                        {statusData.local_runtime.models.join(', ')}
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

function StateIcon({ state }: { state: string }) {
  const s = (state || '').toUpperCase()
  if (s === 'READY') return <CheckCircle className="w-5 h-5 text-success" />
  if (s === 'PARTIAL' || s === 'OPTIONAL' || s === 'SKIPPED')
    return <AlertCircle className="w-5 h-5 text-warning" />
  return <XCircle className="w-5 h-5 text-destructive" />
}
