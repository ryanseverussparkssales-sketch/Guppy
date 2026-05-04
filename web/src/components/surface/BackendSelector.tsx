/**
 * BackendSelector — per-surface backend/model picker
 *
 * Reads and writes /api/surface/config/{surface}.
 * Default: compact chip in the surface header that opens a dropdown.
 * simple={true}: 2-button Local/Cloud toggle for Companion (single primary model).
 * Surfaces: companion | workspace | codespace
 */
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Cpu, Cloud, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface SurfaceConfig {
  surface: string
  backend: string
  model: string
  fallback_model?: string
  mode: string
  tool_policy: string
}

interface BackendOption {
  backend: string
  model: string
  mode: string
  label: string
  description: string
}

const BACKEND_OPTIONS: BackendOption[] = [
  // ── Local — llama.cpp (GPU/CPU) ───────────────────────────────────────────
  { backend: 'llamacpp', model: 'llamacpp-hermes4',   mode: 'local', label: 'Hermes 4.3 36B',          description: 'llamacpp · 21.8GB VRAM · primary — all surfaces' },
  { backend: 'llamacpp', model: 'llamacpp-chat',      mode: 'local', label: 'Llama 3.3 70B (CPU)',     description: 'llamacpp · 42GB RAM · 0 VRAM · flagship chat' },
  { backend: 'llamacpp', model: 'llamacpp-hermes3',   mode: 'local', label: 'Hermes 3 8B',             description: 'llamacpp · 9GB VRAM · on-demand fallback' },
  { backend: 'llamacpp', model: 'llamacpp-rocinante', mode: 'local', label: 'Rocinante 12B',           description: 'llamacpp · 10GB VRAM · on-demand / roleplay' },
  { backend: 'llamacpp', model: 'llamacpp-qwen3',     mode: 'local', label: 'Qwen3 35B MoE',           description: 'llamacpp · 19GB VRAM · deep reasoning' },
  { backend: 'llamacpp', model: 'llamacpp-xlam',      mode: 'local', label: 'xLAM 8B',                 description: 'llamacpp · 5GB VRAM · tool-call specialist' },
  { backend: 'llamacpp', model: 'llamacpp-pepe',      mode: 'local', label: 'Pepe 8B',                 description: 'llamacpp · 8.5GB VRAM · fast chat' },
  { backend: 'llamacpp', model: 'llamacpp-minicpm',   mode: 'local', label: 'MiniCPM (Vision+Voice)',  description: 'llamacpp · 9GB VRAM · vision+speech' },
  { backend: 'llamacpp', model: 'llamacpp-dispatch',  mode: 'local', label: 'Dispatch 3B',             description: 'llamacpp · 2GB VRAM · text router' },
  { backend: 'llamacpp', model: 'llamacpp-phi4-mini', mode: 'local', label: 'Phi-4-mini (Dispatch)',   description: 'llamacpp · 2.5GB VRAM · JSON tool_call orchestrator' },
  // ── Cloud — Anthropic ─────────────────────────────────────────────────────
  { backend: 'cloud', model: 'auto',                      mode: 'auto',   label: 'Auto (Smart Route)',        description: 'Auto-routes by task type · local-first' },
  { backend: 'cloud', model: 'claude',                    mode: 'claude', label: 'Claude Sonnet 4.6',         description: 'Anthropic · max capability · tool-capable' },
  { backend: 'cloud', model: 'claude-haiku-4-5-20251001', mode: 'claude', label: 'Claude Haiku 4.5',          description: 'Anthropic · fast + cheap · tool-capable' },
  // ── Cloud — Groq (free tier, GroqChip hardware) ───────────────────────────
  { backend: 'cloud', model: 'llama-3.3-70b-versatile',   mode: 'cloud',  label: 'Llama 3.3 70B (Groq)',      description: 'Groq · free tier · ~300 tok/s · GROQ_API_KEY' },
  { backend: 'cloud', model: 'llama-3.1-8b-instant',      mode: 'cloud',  label: 'Llama 3.1 8B (Groq)',       description: 'Groq · free tier · ultra-fast · GROQ_API_KEY' },
  { backend: 'cloud', model: 'gemma2-9b-it',              mode: 'cloud',  label: 'Gemma2 9B (Groq)',           description: 'Groq · free tier · fast · GROQ_API_KEY' },
  { backend: 'cloud', model: 'qwen-qwq-32b',              mode: 'cloud',  label: 'Qwen QwQ 32B (Groq)',        description: 'Groq · free tier · reasoning · GROQ_API_KEY' },
  { backend: 'cloud', model: 'deepseek-r1-distill-llama-70b', mode: 'cloud', label: 'DeepSeek R1 70B (Groq)', description: 'Groq · free tier · strong reasoning · GROQ_API_KEY' },
  // ── Cloud — Google Gemini (free tier) ─────────────────────────────────────
  { backend: 'cloud', model: 'gemini-2.0-flash',          mode: 'cloud',  label: 'Gemini 2.0 Flash',           description: 'Google · free tier · fast + capable · GOOGLE_API_KEY' },
  { backend: 'cloud', model: 'gemini-1.5-flash',          mode: 'cloud',  label: 'Gemini 1.5 Flash',           description: 'Google · free tier · GOOGLE_API_KEY' },
  { backend: 'cloud', model: 'gemini-2.5-flash-preview-04-17', mode: 'cloud', label: 'Gemini 2.5 Flash',       description: 'Google · preview · latest · GOOGLE_API_KEY' },
  // ── Cloud — OpenRouter (aggregates 200+ models) ───────────────────────────
  { backend: 'cloud', model: 'openrouter/meta-llama/llama-3.3-70b-instruct:free', mode: 'cloud', label: 'Llama 3.3 70B (OpenRouter·free)',  description: 'OpenRouter · free · no key required · OPENROUTER_API_KEY' },
  { backend: 'cloud', model: 'openrouter/qwen/qwq-32b:free',                      mode: 'cloud', label: 'Qwen QwQ 32B (OpenRouter·free)',   description: 'OpenRouter · free · reasoning · OPENROUTER_API_KEY' },
  { backend: 'cloud', model: 'openrouter/google/gemini-flash-1.5',                mode: 'cloud', label: 'Gemini Flash (OpenRouter)',         description: 'OpenRouter · OPENROUTER_API_KEY' },
  // ── Cloud — Mistral / Cohere ──────────────────────────────────────────────
  { backend: 'cloud', model: 'mistral-small-latest',        mode: 'cloud', label: 'Mistral Small',              description: 'Mistral · MISTRAL_API_KEY' },
  { backend: 'cloud', model: 'command-r7b-12-2024',         mode: 'cloud', label: 'Cohere Command R7B',         description: 'Cohere · COHERE_API_KEY' },
]

// Simple toggle options for Companion (local vs cloud only)
const SIMPLE_TOGGLE_OPTIONS: BackendOption[] = [
  { backend: 'llamacpp', model: 'llamacpp-hermes4',      mode: 'local', label: 'Local',  description: 'Hermes 4.3 36B · 21.8GB VRAM' },
  { backend: 'cloud',    model: 'claude-haiku-4-5-20251001', mode: 'claude', label: 'Haiku', description: 'Claude Haiku · fast + cheap' },
]

const BACKEND_ICONS: Record<string, React.ReactNode> = {
  llamacpp: <Cpu className="w-3 h-3" />,
  cloud:    <Cloud className="w-3 h-3" />,
}

interface BackendSelectorProps {
  surface: 'companion' | 'workspace' | 'codespace'
  compact?: boolean
  simple?: boolean
}

export function BackendSelector({ surface, compact = false, simple = false }: BackendSelectorProps) {
  const [config, setConfig]   = useState<SurfaceConfig | null>(null)
  const [open, setOpen]       = useState(false)
  const [saving, setSaving]   = useState(false)
  const dropdownRef           = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get(`/api/surface/config/${surface}`)
      .then((r) => setConfig(r.data))
      .catch(() => {})
  }, [surface])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const selectOption = async (opt: BackendOption) => {
    if (!config) return
    setSaving(true)
    try {
      const res = await api.put(`/api/surface/config/${surface}`, {
        backend: opt.backend,
        model: opt.model,
        mode: opt.mode,
      })
      setConfig(res.data)
    } catch { /* ignore */ }
    finally {
      setSaving(false)
      setOpen(false)
    }
  }

  const resetToDefault = async () => {
    setSaving(true)
    try {
      await api.post(`/api/surface/config/${surface}/reset`)
      const res = await api.get(`/api/surface/config/${surface}`)
      setConfig(res.data)
    } catch { /* ignore */ }
    finally {
      setSaving(false)
      setOpen(false)
    }
  }

  const currentOpt = BACKEND_OPTIONS.find(
    (o) => o.model === config?.model && o.backend === config?.backend
  )
  const label = currentOpt?.label ?? config?.model ?? '…'
  const icon  = config ? BACKEND_ICONS[config.backend] : null

  // ── Simple local/cloud toggle (Companion) ──────────────────────────────────
  if (simple) {
    const isCloud = config?.backend === 'cloud'
    return (
      <div className="flex items-center rounded-lg overflow-hidden border border-outline-variant/30 text-xs font-medium">
        {SIMPLE_TOGGLE_OPTIONS.map((opt) => {
          const active = opt.backend === 'cloud' ? isCloud : !isCloud
          return (
            <button
              type="button"
              key={opt.model}
              onClick={() => selectOption(opt)}
              disabled={saving}
              title={opt.description}
              className={cn(
                'flex items-center gap-1 px-2.5 py-1 transition-colors',
                active
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-container text-on-surface-variant hover:bg-surface-variant',
                saving && 'opacity-50 cursor-not-allowed'
              )}
            >
              {opt.backend === 'cloud' ? <Cloud className="w-3 h-3" /> : <Cpu className="w-3 h-3" />}
              {opt.label}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 rounded-lg transition-colors text-xs font-medium",
          compact ? "px-2 py-1" : "px-3 py-1.5",
          "bg-surface-variant hover:bg-surface-container text-on-surface-variant hover:text-on-surface border border-outline-variant/30"
        )}
        title="Backend selector"
      >
        {icon}
        {!compact && <span>{label}</span>}
        {compact && <span className="max-w-[80px] truncate">{config?.backend ?? '…'}</span>}
        <ChevronDown className={cn("w-3 h-3 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-72 bg-surface border border-outline-variant/30 rounded-xl shadow-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-outline-variant/10">
            <p className="text-xs font-semibold text-on-surface capitalize">{surface} Backend</p>
            <p className="text-xs text-on-surface-variant/50">
              Select model and inference backend
            </p>
          </div>

          <div className="max-h-80 overflow-y-auto custom-scrollbar">
            {(['llamacpp', 'cloud'] as const).map((backend) => {
              const opts = BACKEND_OPTIONS.filter((o) => o.backend === backend)
              return (
                <div key={backend}>
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-variant/30">
                    {BACKEND_ICONS[backend]}
                    <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                      {backend}
                    </span>
                  </div>
                  {opts.map((opt) => {
                    const isActive = opt.model === config?.model && opt.backend === config?.backend
                    return (
                      <button
                        key={opt.model}
                        onClick={() => selectOption(opt)}
                        disabled={saving}
                        className={cn(
                          "w-full flex items-start gap-3 px-3 py-2 text-left text-sm hover:bg-surface-variant/50 transition-colors",
                          isActive && "bg-primary/10"
                        )}
                      >
                        <div className="flex-1 min-w-0">
                          <p className={cn("font-medium truncate", isActive ? "text-primary" : "text-on-surface")}>
                            {opt.label}
                            {isActive && ' ✓'}
                          </p>
                          <p className="text-xs text-on-surface-variant/60 truncate">{opt.description}</p>
                        </div>
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </div>

          <div className="border-t border-outline-variant/10 px-3 py-2">
            <button
              onClick={resetToDefault}
              className="flex items-center gap-1.5 text-xs text-on-surface-variant/60 hover:text-on-surface transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              Reset to surface default
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
