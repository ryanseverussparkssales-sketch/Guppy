/**
 * SettingsView — 5-tab consolidated control centre.
 * Tabs: Cloud · Credentials · Voice · Tools · Personas
 */
import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import {
  Cloud, Key, Mic, Wrench, Users, Eye, EyeOff,
  Save, Trash2, RefreshCw, CheckCircle, ExternalLink,
  Sun, Moon, Monitor, ToggleLeft, ToggleRight, Lock,
  Plug, Check, Edit2, X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { useSettings } from '@/hooks/useSettings'
import { useTheme } from '@/hooks/useTheme'
import VoicesView from './VoicesView'
import MCPView from './MCPView'

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = 'cloud' | 'credentials' | 'voice' | 'tools' | 'personas'

interface CredRow { key: string; label: string; placeholder: string; url?: string; hint?: string }

interface PersonaPreset {
  label: string; model: string; description: string; system_prompt: string
  tag?: string; tagColor?: string
}

// ── Credential definitions ─────────────────────────────────────────────────────

const CLOUD_AI_CREDS: CredRow[] = [
  { key: 'anthropic', label: 'Anthropic (paid)', placeholder: 'sk-ant-…', url: 'https://console.anthropic.com/account/keys', hint: 'Claude Sonnet/Opus — used for cloud fallback and Codespace' },
  { key: 'cohere',    label: 'Cohere (free tier)', placeholder: 'Free key from dashboard.cohere.com', url: 'https://dashboard.cohere.com/api-keys', hint: 'Command R free tier — no credit card required' },
  { key: 'mistral',   label: 'Mistral (free tier)', placeholder: 'Free key from console.mistral.ai', url: 'https://console.mistral.ai/api-keys', hint: 'Mistral Small free tier' },
]

const SERVICE_CREDS: CredRow[] = [
  { key: 'elevenlabs', label: 'ElevenLabs (TTS)', placeholder: 'el_…', url: 'https://elevenlabs.io/app/settings/api-keys', hint: 'High-quality neural TTS voices' },
  { key: 'deepgram',   label: 'Deepgram (STT)',   placeholder: 'dg_…', url: 'https://console.deepgram.com/', hint: 'Real-time speech-to-text' },
  { key: 'hubspot',    label: 'HubSpot CRM',       placeholder: 'pat-…', url: 'https://app.hubspot.com/settings/integrations/api-key', hint: 'Contact + deal sync' },
  { key: 'quo',        label: 'Quo (VoIP)',         placeholder: 'API key from app.quo.com', url: 'https://app.quo.com', hint: 'Outbound calling + call logs' },
  { key: 'google',     label: 'Google (Calendar + Gmail)', placeholder: 'OAuth credentials JSON path or refresh token', hint: 'Set GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN in .env' },
]

// ── Tab config ─────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'cloud',       label: 'Cloud',       icon: <Cloud className="w-4 h-4" /> },
  { id: 'credentials', label: 'Credentials', icon: <Key className="w-4 h-4" /> },
  { id: 'voice',       label: 'Voice',       icon: <Mic className="w-4 h-4" /> },
  { id: 'tools',       label: 'Tools',       icon: <Wrench className="w-4 h-4" /> },
  { id: 'personas',    label: 'Personas',    icon: <Users className="w-4 h-4" /> },
]

// ── Main component ─────────────────────────────────────────────────────────────

export default function SettingsView() {
  const [tab, setTab] = useState<Tab>('cloud')
  return (
    <div className="h-full flex flex-col max-w-4xl">
      {/* Header */}
      <div className="px-6 pt-6 pb-0">
        <h1 className="text-2xl font-bold text-on-surface mb-4">Settings</h1>
        <div className="flex gap-0 border-b border-outline-variant/20">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                tab === t.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-on-surface-variant/60 hover:text-on-surface',
              )}
            >
              {t.icon}{t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto px-6 py-6">
        {tab === 'cloud'       && <CloudTab />}
        {tab === 'credentials' && <CredentialsTab />}
        {tab === 'voice'       && <VoicesView />}
        {tab === 'tools'       && <ToolsTab />}
        {tab === 'personas'    && <PersonasTab />}
      </div>
    </div>
  )
}

// ── Cloud Tab ─────────────────────────────────────────────────────────────────

function CloudTab() {
  const { settings, fetchSettings, storeCredential, deleteCredential } = useSettings()
  const { activeTheme, setTheme, themes } = useTheme()
  const [inputs, setInputs]   = useState<Record<string, string>>({})
  const [visible, setVisible] = useState<Record<string, boolean>>({})
  const [saving, setSaving]   = useState<string | null>(null)

  useEffect(() => { fetchSettings() }, [fetchSettings])

  const configured = (key: string) =>
    key === 'local' ? true : (settings?.credentials?.[key]?.configured ?? false)

  const save = async (key: string) => {
    const val = inputs[key]?.trim()
    if (!val) return
    setSaving(key)
    try {
      await storeCredential(key as any, val)
      setInputs(p => ({ ...p, [key]: '' }))
      toast.success('Saved')
    } catch { toast.error('Save failed') }
    finally { setSaving(null) }
  }

  const remove = async (key: string) => {
    setSaving(key)
    try {
      await deleteCredential(key as any)
      toast.success('Removed')
    } catch { toast.error('Remove failed') }
    finally { setSaving(null) }
  }

  return (
    <div className="space-y-8">
      {/* AI cloud providers */}
      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/50">
          AI Cloud Providers
        </h2>
        {CLOUD_AI_CREDS.map(row => (
          <CredentialRow
            key={row.key}
            row={row}
            configured={configured(row.key)}
            saving={saving === row.key}
            value={inputs[row.key] || ''}
            visible={!!visible[row.key]}
            onValue={v => setInputs(p => ({ ...p, [row.key]: v }))}
            onToggleVisible={() => setVisible(p => ({ ...p, [row.key]: !p[row.key] }))}
            onSave={() => save(row.key)}
            onRemove={() => remove(row.key)}
          />
        ))}
      </section>

      {/* Appearance */}
      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant/50">
          Appearance
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {themes.map(t => (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              className={cn(
                'flex items-center gap-2 p-2.5 rounded-xl border-2 text-left transition-all',
                activeTheme === t.id
                  ? 'border-primary bg-primary/5'
                  : 'border-outline-variant/20 hover:border-outline-variant/50',
              )}
            >
              <div className="flex rounded overflow-hidden w-7 h-7 border border-outline-variant/30 flex-shrink-0">
                <div style={{ background: t.preview[1] }} className="w-1/2" />
                <div style={{ background: t.preview[0] }} className="w-1/2" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-on-surface truncate">{t.label}</p>
                {activeTheme === t.id && <p className="text-[10px] text-primary font-bold">Active</p>}
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

// ── Credentials Tab ────────────────────────────────────────────────────────────

function CredentialsTab() {
  const { settings, fetchSettings, storeCredential, deleteCredential } = useSettings()
  const [inputs, setInputs]   = useState<Record<string, string>>({})
  const [visible, setVisible] = useState<Record<string, boolean>>({})
  const [saving, setSaving]   = useState<string | null>(null)

  useEffect(() => { fetchSettings() }, [fetchSettings])

  const configured = (key: string) =>
    settings?.credentials?.[key]?.configured ?? false

  const save = async (key: string) => {
    const val = inputs[key]?.trim()
    if (!val) return
    setSaving(key)
    try {
      await storeCredential(key as any, val)
      setInputs(p => ({ ...p, [key]: '' }))
      toast.success('Saved')
    } catch { toast.error('Save failed') }
    finally { setSaving(null) }
  }

  const remove = async (key: string) => {
    setSaving(key)
    try {
      await deleteCredential(key as any)
      toast.success('Removed')
    } catch { toast.error('Remove failed') }
    finally { setSaving(null) }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-on-surface-variant/50 mb-4">
        Service API keys stored locally in your Guppy data directory.
      </p>
      {SERVICE_CREDS.map(row => (
        <CredentialRow
          key={row.key}
          row={row}
          configured={configured(row.key)}
          saving={saving === row.key}
          value={inputs[row.key] || ''}
          visible={!!visible[row.key]}
          onValue={v => setInputs(p => ({ ...p, [row.key]: v }))}
          onToggleVisible={() => setVisible(p => ({ ...p, [row.key]: !p[row.key] }))}
          onSave={() => save(row.key)}
          onRemove={() => remove(row.key)}
        />
      ))}
    </div>
  )
}

// ── Shared credential row ──────────────────────────────────────────────────────

function CredentialRow({
  row, configured, saving, value, visible,
  onValue, onToggleVisible, onSave, onRemove,
}: {
  row: CredRow
  configured: boolean
  saving: boolean
  value: string
  visible: boolean
  onValue: (v: string) => void
  onToggleVisible: () => void
  onSave: () => void
  onRemove: () => void
}) {
  return (
    <div className={cn(
      'rounded-xl border p-4 transition-all',
      configured
        ? 'border-green-500/20 bg-green-500/5'
        : 'border-outline-variant/15 bg-surface-container/30',
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-medium text-on-surface">{row.label}</span>
            {configured && (
              <span className="flex items-center gap-0.5 text-[10px] text-green-400">
                <CheckCircle className="w-3 h-3" />configured
              </span>
            )}
          </div>
          {row.hint && <p className="text-[11px] text-on-surface-variant/50">{row.hint}</p>}
        </div>
        {row.url && (
          <a href={row.url} target="_blank" rel="noreferrer"
            className="flex-shrink-0 text-on-surface-variant/30 hover:text-primary transition-colors">
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>

      <div className="flex gap-2 mt-3">
        <div className="relative flex-1">
          <input
            type={visible ? 'text' : 'password'}
            placeholder={configured ? '••••••••••••' : row.placeholder}
            value={value}
            onChange={e => onValue(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && value && onSave()}
            className="w-full text-sm bg-surface-container border border-outline-variant/20 rounded-lg px-3 py-2 pr-9 text-on-surface placeholder:text-on-surface-variant/30 focus:outline-none focus:border-primary/40"
          />
          <button onClick={onToggleVisible}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant/40 hover:text-on-surface-variant transition-colors">
            {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
        {value && (
          <button onClick={onSave} disabled={saving}
            className="flex items-center gap-1 text-xs px-3 py-2 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50">
            {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
          </button>
        )}
        {configured && !value && (
          <button onClick={onRemove} disabled={saving}
            className="flex items-center gap-1 text-xs px-3 py-2 rounded-lg border border-red-400/20 text-red-400/70 hover:bg-red-400/10 transition-colors disabled:opacity-50">
            {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
          </button>
        )}
      </div>

      <div className="flex items-center gap-1 mt-2">
        <Lock className="w-2.5 h-2.5 text-on-surface-variant/25" />
        <p className="text-[10px] text-on-surface-variant/30">Stored locally. Never sent to third parties.</p>
      </div>
    </div>
  )
}

// ── Tools Tab ─────────────────────────────────────────────────────────────────

function ToolsTab() {
  const [subTab, setSubTab] = useState<'functions' | 'mcp'>('functions')
  const [tools, setTools]     = useState<any[]>([])
  const [toggling, setToggling] = useState<string | null>(null)

  const fetchTools = useCallback(async () => {
    try {
      const res = await api.get('/api/tools')
      setTools(res.data ?? [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { fetchTools() }, [fetchTools])

  const toggle = async (tool: any) => {
    setToggling(tool.id)
    try {
      const endpoint = tool.isEnabled ? 'disable' : 'enable'
      await api.post(`/api/tools/${tool.id}/${endpoint}`)
      setTools(prev => prev.map(t => t.id === tool.id ? { ...t, isEnabled: !t.isEnabled } : t))
    } catch { toast.error('Toggle failed') }
    finally { setToggling(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-outline-variant/20">
        {[
          { id: 'functions', label: 'Functions', icon: <Wrench className="w-3.5 h-3.5" /> },
          { id: 'mcp',       label: 'MCP Servers', icon: <Plug className="w-3.5 h-3.5" /> },
        ].map(t => (
          <button key={t.id} onClick={() => setSubTab(t.id as any)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors -mb-px',
              subTab === t.id ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant/60 hover:text-on-surface',
            )}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {subTab === 'mcp' && <MCPView />}

      {subTab === 'functions' && (
        <div className="space-y-2">
          {tools.length === 0 && (
            <p className="text-sm text-on-surface-variant/50 py-4 text-center">No tools configured — backend connection required.</p>
          )}
          {tools.map(tool => (
            <div key={tool.id}
              className="flex items-center justify-between px-4 py-3 rounded-xl border border-outline-variant/15 bg-surface-container/30">
              <div>
                <p className="text-sm font-medium text-on-surface">{tool.name}</p>
                <p className="text-[11px] text-on-surface-variant/50">{tool.description}</p>
              </div>
              <button
                onClick={() => toggle(tool)}
                disabled={toggling === tool.id}
                className={cn(
                  'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-all',
                  tool.isEnabled
                    ? 'border-green-500/30 text-green-400 bg-green-500/10 hover:bg-green-500/20'
                    : 'border-outline-variant/20 text-on-surface-variant/50 hover:border-primary/30 hover:text-primary',
                )}
              >
                {toggling === tool.id
                  ? <RefreshCw className="w-3 h-3 animate-spin" />
                  : tool.isEnabled
                    ? <><ToggleRight className="w-3.5 h-3.5" />On</>
                    : <><ToggleLeft className="w-3.5 h-3.5" />Off</>
                }
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Personas Tab ──────────────────────────────────────────────────────────────

const PERSONA_TAG_COLORS: Record<string, string> = {
  sharp:    'bg-primary/15 text-primary',
  humor:    'bg-amber-500/15 text-amber-400',
  creative: 'bg-purple-500/15 text-purple-400',
  voice:    'bg-rose-500/15 text-rose-400',
  thinking: 'bg-cyan-500/15 text-cyan-400',
}

const MODEL_LABELS: Record<string, string> = {
  'llamacpp-hermes3': 'Hermes 3 8B',
  'llamacpp-pepe':    'Pepe 8B',
  'llamacpp-rocinante': 'Rocinante 12B',
  'llamacpp-minicpm': 'MiniCPM Vision 4.5B',
  'llamacpp-chat':    'Llama 3.3 70B (CPU)',
  'auto':             'Cloud (Claude)',
}

function PersonasTab() {
  const [presets, setPresets]     = useState<Record<string, PersonaPreset>>({})
  const [activePreset, setActive] = useState<string>('sharp')
  const [editing, setEditing]     = useState<string | null>(null)
  const [draft, setDraft]         = useState('')
  const [saving, setSaving]       = useState<string | null>(null)
  const [loading, setLoading]     = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/companion/personality')
      setPresets(res.data.presets ?? {})
      setActive(res.data.active_preset ?? 'sharp')
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const activate = async (key: string) => {
    setSaving(key)
    try {
      await api.put('/api/companion/personality', { preset: key })
      setActive(key)
      toast.success(`Switched to ${presets[key]?.label ?? key}`)
    } catch { toast.error('Switch failed') }
    finally { setSaving(null) }
  }

  const savePrompt = async (key: string) => {
    setSaving(key)
    try {
      await api.patch(`/api/companion/personality/${key}`, { system_prompt: draft })
      setPresets(prev => ({ ...prev, [key]: { ...prev[key], system_prompt: draft } }))
      setEditing(null)
      toast.success('Prompt saved')
    } catch { toast.error('Save failed') }
    finally { setSaving(null) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-40">
      <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
    </div>
  )

  return (
    <div className="space-y-3">
      <p className="text-xs text-on-surface-variant/50">
        Each persona locks to a specific local model. Edit the system prompt to shape voice and personality.
      </p>
      {Object.entries(presets).map(([key, preset]) => {
        const isActive  = activePreset === key
        const isEditing = editing === key
        const tagCls    = PERSONA_TAG_COLORS[key] ?? 'bg-surface-container text-on-surface-variant'
        const modelLabel = MODEL_LABELS[preset.model] ?? preset.model

        return (
          <div key={key}
            className={cn(
              'rounded-xl border p-4 transition-all',
              isActive
                ? 'border-primary/30 bg-primary/5'
                : 'border-outline-variant/15 bg-surface-container/30',
            )}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-on-surface">{preset.label}</span>
                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full font-medium', tagCls)}>
                    {key}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-container border border-outline-variant/20 text-on-surface-variant/50 font-mono">
                    🔒 {modelLabel}
                  </span>
                  {isActive && (
                    <span className="flex items-center gap-0.5 text-[10px] text-primary font-semibold">
                      <Check className="w-3 h-3" />active
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-on-surface-variant/50 mt-0.5">{preset.description}</p>
              </div>

              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => { setEditing(isEditing ? null : key); setDraft(preset.system_prompt) }}
                  className="p-1.5 rounded-lg text-on-surface-variant/40 hover:text-on-surface-variant hover:bg-surface-container transition-all"
                  title="Edit system prompt"
                >
                  {isEditing ? <X className="w-3.5 h-3.5" /> : <Edit2 className="w-3.5 h-3.5" />}
                </button>
                {!isActive && (
                  <button
                    onClick={() => activate(key)}
                    disabled={saving === key}
                    className="text-xs px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
                  >
                    {saving === key ? <RefreshCw className="w-3 h-3 animate-spin" /> : 'Activate'}
                  </button>
                )}
              </div>
            </div>

            {isEditing && (
              <div className="mt-3 space-y-2">
                <textarea
                  value={draft}
                  onChange={e => setDraft(e.target.value)}
                  rows={6}
                  className="w-full text-xs bg-surface-container border border-outline-variant/20 rounded-lg px-3 py-2 text-on-surface placeholder:text-on-surface-variant/30 focus:outline-none focus:border-primary/40 resize-y font-mono leading-relaxed"
                />
                <div className="flex justify-end gap-2">
                  <button onClick={() => setEditing(null)}
                    className="text-xs px-3 py-1.5 rounded-lg border border-outline-variant/20 text-on-surface-variant/60 hover:text-on-surface transition-colors">
                    Cancel
                  </button>
                  <button
                    onClick={() => savePrompt(key)}
                    disabled={saving === key}
                    className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {saving === key ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                    Save prompt
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
