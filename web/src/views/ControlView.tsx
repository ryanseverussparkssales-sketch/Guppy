/**
 * Control Panel — Operator settings + Model Health.
 *
 * Three sections:
 *   1. Cloud Access — toggles for paid/free cloud routing
 *   2. Conversation Partner — radio cards selecting the active partner model
 *   3. Model Health — read-only status grid for every core model
 */
import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Cpu, Cloud, CloudOff, CheckCircle2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
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

function ModelRow({ m }: { m: ModelStatus }) {
  const isCpu = m.vram_gb === 0
  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-2.5 rounded-xl border',
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
      <div className="flex-shrink-0">
        {m.alive ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-green-400/70" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-on-surface-variant/20" />
        )}
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
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [settingsRes, backendsRes] = await Promise.all([
        api.get('/api/control/operator-settings'),
        api.get('/api/backends/llamacpp').catch(() => ({ data: [] })),
      ])
      setSettings(settingsRes.data)
      const raw: any[] = backendsRes.data ?? []
      setModels(
        raw.map(b => ({
          key: b.name,
          label: b.label,
          port: b.port,
          alive: b.alive,
          vram_gb: b.vram_gb,
          note: b.note,
          auto_start: b.auto_start,
        })),
      )
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, 10_000)
    return () => clearInterval(id)
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

  const alive = models.filter(m => m.alive).length

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
                <ModelRow key={m.key} m={m} />
              ))}
            </div>
          )}
        </section>

      </div>
    </div>
  )
}
