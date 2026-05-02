/**
 * Control Panel — service lifecycle, operator settings, and model health.
 *
 * Sections:
 *   1. Service Controls — API/Web UI on/off/reset/health
 *   2. Cloud Access — toggles for paid/free cloud routing
 *   3. Conversation Partner — radio cards selecting the active partner model
 *   4. Model Health — status and lifecycle controls for local model servers
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  RefreshCw,
  Cpu,
  Cloud,
  CloudOff,
  CheckCircle2,
  XCircle,
  Globe2,
  Power,
  PowerOff,
  RotateCcw,
  Server,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Tooltip } from '@/components/ui/tooltip'
import api from '@/api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OperatorSettings {
  cloud_paid_enabled: boolean
  cloud_free_enabled: boolean
  conversation_partner: string
}

interface ModelStatus {
  key: string
  label: string
  port: number
  alive: boolean
  vram_gb: number
  note: string
  auto_start: boolean
}

interface BackendStatus {
  name: string
  label: string
  port: number
  alive: boolean
  vram_gb: number
  note: string
  auto_start?: boolean
}

interface ServiceStatus {
  key: string
  service_name: string
  label: string
  description: string
  state: 'running' | 'stopped'
  port: number | null
  health: 'up' | 'down' | 'degraded' | 'unknown'
  latency_ms: number | null
  health_detail: string
}

type ControlAction = 'on' | 'off' | 'reset' | 'health'

// ---------------------------------------------------------------------------
// Partner card definitions
// ---------------------------------------------------------------------------

const PARTNER_OPTIONS = [
  {
    role: 'conversation.default',
    label: 'Hermes 3',
    sub: 'Fast chat · uncensored',
    description: 'Default conversation model. Snappy, tool-capable.',
  },
  {
    role: 'conversation.partner.writing',
    label: 'Rocinante',
    sub: 'Writing · roleplay',
    description: 'Creative writing and long-form roleplay partner.',
  },
  {
    role: 'conversation.partner.study',
    label: 'Pepe',
    sub: 'Study · funny',
    description: 'Study sessions and casual, humorous assistance.',
  },
  {
    role: 'conversation.partner.vision',
    label: 'MiniCPM',
    sub: 'Vision · private',
    description: 'Vision + speech model. On-device, no cloud.',
  },
]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Toggle({
  label,
  sublabel,
  checked,
  onChange,
  icon,
}: {
  label: string
  sublabel: string
  checked: boolean
  onChange: (v: boolean) => void
  icon: React.ReactNode
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl border transition-all text-left w-full',
        checked
          ? 'border-primary/30 bg-primary/8 text-on-surface'
          : 'border-outline-variant/20 bg-surface-container/30 text-on-surface-variant/60',
      )}
    >
      <div
        className={cn(
          'flex-shrink-0 p-2 rounded-lg transition-colors',
          checked ? 'bg-primary/15 text-primary' : 'bg-surface-container text-on-surface-variant/40',
        )}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-on-surface-variant/50 mt-0.5">{sublabel}</p>
      </div>
      <div
        className={cn(
          'flex-shrink-0 w-11 h-6 rounded-full relative transition-colors',
          checked ? 'bg-primary' : 'bg-outline-variant/30',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
            checked && 'translate-x-5',
          )}
        />
      </div>
    </button>
  )
}

function PartnerCard({
  option,
  selected,
  onSelect,
}: {
  option: (typeof PARTNER_OPTIONS)[0]
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'p-4 rounded-xl border text-left transition-all w-full',
        selected
          ? 'border-primary/40 bg-primary/8 ring-1 ring-primary/20'
          : 'border-outline-variant/15 bg-surface-container/30 hover:bg-surface-container/50',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className={cn('text-sm font-semibold', selected ? 'text-primary' : 'text-on-surface')}>
            {option.label}
          </p>
          <p className="text-[11px] text-on-surface-variant/50 mt-0.5">{option.sub}</p>
        </div>
        <div
          className={cn(
            'w-4 h-4 rounded-full border-2 flex-shrink-0 mt-0.5 transition-colors',
            selected ? 'border-primary bg-primary' : 'border-outline-variant/40 bg-transparent',
          )}
        />
      </div>
      <p className="text-[11px] text-on-surface-variant/40 mt-2 leading-relaxed">
        {option.description}
      </p>
    </button>
  )
}

function IconButton({
  label,
  disabled,
  onClick,
  children,
  tone = 'neutral',
}: {
  label: string
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
  tone?: 'neutral' | 'danger' | 'primary'
}) {
  return (
    <Tooltip content={label} side="top">
      <button
        type="button"
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
        className={cn(
          'w-8 h-8 rounded-lg border flex items-center justify-center transition-colors disabled:opacity-40 disabled:cursor-default',
          tone === 'primary' &&
            'border-primary/25 bg-primary/10 text-primary hover:bg-primary/15',
          tone === 'danger' &&
            'border-red-500/20 bg-red-500/10 text-red-400 hover:bg-red-500/15',
          tone === 'neutral' &&
            'border-outline-variant/15 bg-surface-container/40 text-on-surface-variant hover:bg-surface-container/70',
        )}
      >
        {children}
      </button>
    </Tooltip>
  )
}

function ServiceCard({
  service,
  busyAction,
  lastCheck,
  onAction,
}: {
  service: ServiceStatus
  busyAction?: ControlAction
  lastCheck?: string
  onAction: (key: string, action: ControlAction) => void
}) {
  const isWeb = service.key === 'web-ui'
  const isUp = service.health === 'up' || service.state === 'running'
  const healthText = lastCheck || service.health || 'unknown'
  const healthTone = healthText === 'up' || healthText === 'online' || healthText === 'already_running'

  return (
    <div
      className={cn(
        'p-4 rounded-xl border bg-surface-container/25 flex flex-col gap-3',
        isUp ? 'border-green-500/20' : 'border-outline-variant/15',
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
            isUp ? 'bg-green-500/10 text-green-400' : 'bg-surface-container text-on-surface-variant/45',
          )}
        >
          {isWeb ? <Globe2 className="w-4 h-4" /> : <Server className="w-4 h-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-on-surface truncate">{service.label}</p>
            {service.port && (
              <span className="text-[10px] text-on-surface-variant/35">:{service.port}</span>
            )}
          </div>
          <p className="text-[11px] text-on-surface-variant/45 mt-0.5 truncate">
            {service.description}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[11px]">
        <span
          className={cn(
            'px-2 py-0.5 rounded-full font-medium',
            healthTone
              ? 'bg-green-500/10 text-green-400'
              : healthText === 'error' || healthText === 'timed_out'
                ? 'bg-red-500/10 text-red-400'
                : healthText === 'starting' || healthText === 'restart_scheduled' || healthText === 'shutdown_scheduled'
                  ? 'bg-amber-500/10 text-amber-400'
                  : 'bg-outline-variant/10 text-on-surface-variant/45',
          )}
        >
          {healthText}
        </span>
        {service.latency_ms !== null && (
          <span className="text-on-surface-variant/35">{service.latency_ms}ms</span>
        )}
        <span className="text-on-surface-variant/30 truncate">{service.health_detail}</span>
      </div>

      <div className="flex items-center gap-1.5">
        <IconButton
          label={isUp ? 'Turn off' : 'Turn on'}
          disabled={Boolean(busyAction)}
          onClick={() => onAction(service.key, isUp ? 'off' : 'on')}
          tone={isUp ? 'danger' : 'primary'}
        >
          {busyAction === 'on' || busyAction === 'off' ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : isUp ? (
            <PowerOff className="w-3.5 h-3.5" />
          ) : (
            <Power className="w-3.5 h-3.5" />
          )}
        </IconButton>
        <IconButton
          label="Reset"
          disabled={Boolean(busyAction)}
          onClick={() => onAction(service.key, 'reset')}
        >
          {busyAction === 'reset' ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RotateCcw className="w-3.5 h-3.5" />
          )}
        </IconButton>
        <IconButton
          label="Check health"
          disabled={Boolean(busyAction)}
          onClick={() => onAction(service.key, 'health')}
        >
          {busyAction === 'health' ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Activity className="w-3.5 h-3.5" />
          )}
        </IconButton>
      </div>
    </div>
  )
}

function ModelRow({
  m,
  busyAction,
  lastCheck,
  onAction,
}: {
  m: ModelStatus
  busyAction?: ControlAction
  lastCheck?: string
  onAction: (key: string, action: ControlAction) => void
}) {
  const isCpu = m.vram_gb === 0
  const checkText = lastCheck || (m.alive ? 'online' : 'offline')
  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-2.5 rounded-xl border',
        m.alive
          ? 'border-green-500/20 bg-green-500/5'
          : 'border-outline-variant/15 bg-surface-container/20',
      )}
    >
      <div className="flex-shrink-0">
        {isCpu ? (
          <Cpu
            className={cn(
              'w-3.5 h-3.5',
              m.alive ? 'text-cyan-400' : 'text-on-surface-variant/25',
            )}
          />
        ) : (
          <span
            className={cn(
              'block w-2.5 h-2.5 rounded-full',
              m.alive
                ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.6)]'
                : 'bg-on-surface-variant/20',
            )}
          />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-on-surface">{m.label}</span>
          <span className="text-[10px] text-on-surface-variant/30">:{m.port}</span>
          {m.auto_start && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary/70">
              always-on
            </span>
          )}
        </div>
        <p className="text-[11px] text-on-surface-variant/35 truncate">{m.note}</p>
      </div>
      <span className="text-[10px] text-on-surface-variant/25 flex-shrink-0 hidden sm:block">
        {m.vram_gb > 0 ? `${m.vram_gb} GB` : 'CPU'}
      </span>
      <span
        className={cn(
          'text-[10px] px-2 py-0.5 rounded-full flex-shrink-0',
          checkText === 'online' || checkText === 'up' || checkText === 'already_running'
            ? 'bg-green-500/10 text-green-400'
            : checkText === 'error' || checkText === 'timed_out'
              ? 'bg-red-500/10 text-red-400'
              : checkText === 'starting' || checkText === 'restart_scheduled'
                ? 'bg-amber-500/10 text-amber-400'
                : 'bg-outline-variant/10 text-on-surface-variant/35',
        )}
      >
        {checkText}
      </span>
      <div className="flex-shrink-0 hidden sm:block">
        {m.alive ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-green-400/70" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-on-surface-variant/20" />
        )}
      </div>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <IconButton
          label={m.alive ? 'Turn off' : 'Turn on'}
          disabled={Boolean(busyAction)}
          onClick={() => onAction(m.key, m.alive ? 'off' : 'on')}
          tone={m.alive ? 'danger' : 'primary'}
        >
          {busyAction === 'on' || busyAction === 'off' ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : m.alive ? (
            <PowerOff className="w-3.5 h-3.5" />
          ) : (
            <Power className="w-3.5 h-3.5" />
          )}
        </IconButton>
        <IconButton
          label="Reset"
          disabled={Boolean(busyAction)}
          onClick={() => onAction(m.key, 'reset')}
        >
          {busyAction === 'reset' ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RotateCcw className="w-3.5 h-3.5" />
          )}
        </IconButton>
        <IconButton
          label="Check health"
          disabled={Boolean(busyAction)}
          onClick={() => onAction(m.key, 'health')}
        >
          {busyAction === 'health' ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Activity className="w-3.5 h-3.5" />
          )}
        </IconButton>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export default function ControlView() {
  const [settings, setSettings] = useState<OperatorSettings>({
    cloud_paid_enabled: true,
    cloud_free_enabled: false,
    conversation_partner: 'conversation.default',
  })
  const [models, setModels] = useState<ModelStatus[]>([])
  const [services, setServices] = useState<ServiceStatus[]>([])
  const [serviceChecks, setServiceChecks] = useState<Record<string, string>>({})
  const [modelChecks, setModelChecks] = useState<Record<string, string>>({})
  const [serviceBusy, setServiceBusy] = useState<string | null>(null)
  const [modelBusy, setModelBusy] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [settingsRes, backendsRes, servicesRes] = await Promise.all([
        api.get('/api/control/operator-settings'),
        api.get('/api/backends/llamacpp').catch(() => ({ data: [] })),
        api.get('/api/control/services').catch(() => ({ data: [] })),
      ])
      setSettings(settingsRes.data)
      const raw = Array.isArray(backendsRes.data)
        ? (backendsRes.data as BackendStatus[])
        : []
      setModels(
        raw.map(b => ({
          key: b.name,
          label: b.label,
          port: b.port,
          alive: b.alive,
          vram_gb: b.vram_gb,
          note: b.note,
          auto_start: Boolean(b.auto_start),
        })),
      )
      setServices(servicesRes.data ?? [])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => {
      void fetchAll()
    }, 0)
    const id = window.setInterval(() => {
      void fetchAll()
    }, 10_000)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(id)
    }
  }, [fetchAll])

  const patch = useCallback(async (update: Partial<OperatorSettings>) => {
    setSaving(true)
    try {
      const res = await api.put('/api/control/operator-settings', update)
      setSettings(res.data)
    } catch {
      // ignore — keep optimistic state
    } finally {
      setSaving(false)
    }
  }, [])

  const serviceAction = useCallback(async (key: string, action: ControlAction) => {
    const busyKey = `${key}:${action}`
    setServiceBusy(busyKey)
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 30_000)
    try {
      const res =
        action === 'health'
          ? await api.get(`/api/control/services/${key}/health`, { signal: controller.signal })
          : await api.post(`/api/control/services/${key}/${action}`, undefined, { signal: controller.signal })
      const data = res.data ?? {}
      const status =
        data.health?.health ||
        data.status ||
        data.result?.status ||
        data.health ||
        'ok'
      setServiceChecks(prev => ({ ...prev, [key]: String(status) }))
      await fetchAll()
    } catch (err: unknown) {
      const label = (err as { name?: string })?.name === 'AbortError' ? 'timed_out' : 'error'
      setServiceChecks(prev => ({ ...prev, [key]: label }))
    } finally {
      window.clearTimeout(timer)
      setServiceBusy(null)
    }
  }, [fetchAll])

  const modelAction = useCallback(async (key: string, action: ControlAction) => {
    const busyKey = `${key}:${action}`
    setModelBusy(busyKey)
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 30_000)
    try {
      const res =
        action === 'health'
          ? await api.get(`/api/control/models/${key}/health`, { signal: controller.signal })
          : await api.post(`/api/control/models/${key}/${action}`, undefined, { signal: controller.signal })
      const data = res.data ?? {}
      const status =
        data.health?.status ||
        data.status ||
        (data.health?.alive ? 'online' : '') ||
        'ok'
      setModelChecks(prev => ({ ...prev, [key]: String(status) }))
      await fetchAll()
    } catch (err: unknown) {
      const label = (err as { name?: string })?.name === 'AbortError' ? 'timed_out' : 'error'
      setModelChecks(prev => ({ ...prev, [key]: label }))
    } finally {
      window.clearTimeout(timer)
      setModelBusy(null)
    }
  }, [fetchAll])

  const alive = models.filter(m => m.alive).length
  const servicesUp = services.filter(s => s.health === 'up' || s.state === 'running').length

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <RefreshCw className="w-5 h-5 text-on-surface-variant/40 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-on-surface p-6">
      <div className="max-w-2xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Operator Controls</h1>
            <p className="text-sm text-on-surface-variant/50 mt-0.5">
              {services.length > 0 && `${servicesUp} / ${services.length} services up · `}
              {alive} / {models.length} models live
            </p>
          </div>
          <button
            onClick={fetchAll}
            className="text-on-surface-variant/40 hover:text-on-surface-variant transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', saving && 'animate-spin')} />
          </button>
        </div>

        {/* 0. Service Controls */}
        <section>
          <h2 className="text-xs font-semibold text-on-surface-variant/50 uppercase tracking-wider mb-3">
            Service Controls
          </h2>
          {services.length === 0 ? (
            <p className="text-sm text-on-surface-variant/40 italic">Service controls unavailable.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {services.map(service => (
                <ServiceCard
                  key={service.key}
                  service={service}
                  busyAction={
                    serviceBusy?.startsWith(`${service.key}:`)
                      ? (serviceBusy.split(':')[1] as ControlAction)
                      : undefined
                  }
                  lastCheck={serviceChecks[service.key]}
                  onAction={serviceAction}
                />
              ))}
            </div>
          )}
        </section>

        {/* 1. Cloud Access */}
        <section>
          <h2 className="text-xs font-semibold text-on-surface-variant/50 uppercase tracking-wider mb-3">
            Cloud Access
          </h2>
          <div className="space-y-2">
            <Toggle
              label="Paid Cloud"
              sublabel="Claude (Anthropic) · GPT-4 (OpenAI) — requires API key"
              checked={settings.cloud_paid_enabled}
              onChange={v => patch({ cloud_paid_enabled: v })}
              icon={<Cloud className="w-4 h-4" />}
            />
            <Toggle
              label="Free Cloud"
              sublabel="Mistral · Cohere free tier — no cost, rate-limited"
              checked={settings.cloud_free_enabled}
              onChange={v => patch({ cloud_free_enabled: v })}
              icon={<CloudOff className="w-4 h-4" />}
            />
          </div>
        </section>

        {/* 2. Conversation Partner */}
        <section>
          <h2 className="text-xs font-semibold text-on-surface-variant/50 uppercase tracking-wider mb-3">
            Conversation Partner
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {PARTNER_OPTIONS.map(opt => (
              <PartnerCard
                key={opt.role}
                option={opt}
                selected={settings.conversation_partner === opt.role}
                onSelect={() =>
                  settings.conversation_partner !== opt.role &&
                  patch({ conversation_partner: opt.role })
                }
              />
            ))}
          </div>
        </section>

        {/* 3. Model Health */}
        <section>
          <h2 className="text-xs font-semibold text-on-surface-variant/50 uppercase tracking-wider mb-3">
            Model Health
          </h2>
          {models.length === 0 ? (
            <p className="text-sm text-on-surface-variant/40 italic">No models registered.</p>
          ) : (
            <div className="space-y-1.5">
              {models.map(m => (
                <ModelRow
                  key={m.key}
                  m={m}
                  busyAction={
                    modelBusy?.startsWith(`${m.key}:`)
                      ? (modelBusy.split(':')[1] as ControlAction)
                      : undefined
                  }
                  lastCheck={modelChecks[m.key]}
                  onAction={modelAction}
                />
              ))}
            </div>
          )}
        </section>

      </div>
    </div>
  )
}
