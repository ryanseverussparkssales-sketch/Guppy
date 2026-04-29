/**
 * BackendSelector — per-surface backend/model picker
 *
 * Reads and writes /api/surface/config/{surface}.
 * Shows a compact chip in the surface header that opens a dropdown.
 * Surfaces: companion | workspace | codespace
 */
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Cpu, Cloud, Zap, RotateCcw } from 'lucide-react'
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
  // llamacpp backends
  { backend: 'llamacpp', model: 'llamacpp-minicpm',   mode: 'local', label: 'MiniCPM (Vision+Voice)', description: 'llamacpp · 9GB · voice+vision native' },
  { backend: 'llamacpp', model: 'llamacpp-rocinante', mode: 'local', label: 'Rocinante 12B',           description: 'llamacpp · 10GB · uncensored creative' },
  { backend: 'llamacpp', model: 'llamacpp-hermes4',   mode: 'local', label: 'Hermes 4 14B',            description: 'llamacpp · 11GB · tools + uncensored' },
  { backend: 'llamacpp', model: 'llamacpp-hermes3',   mode: 'local', label: 'Hermes 3 8B',             description: 'llamacpp · 9GB · fast tools + uncensored' },
  { backend: 'llamacpp', model: 'llamacpp-qwen3',     mode: 'local', label: 'Qwen3 35B MoE',           description: 'llamacpp · 19GB · deep reasoning' },
  { backend: 'llamacpp', model: 'llamacpp-xlam',      mode: 'local', label: 'xLAM 8B',                 description: 'llamacpp · 5GB · tool-call specialist' },
  { backend: 'llamacpp', model: 'llamacpp-pepe',      mode: 'local', label: 'Pepe 8B',                 description: 'llamacpp · 8.5GB · fast chat' },
  { backend: 'llamacpp', model: 'llamacpp-dispatch',  mode: 'local', label: 'Dispatch 3B',             description: 'llamacpp · 2.5GB · ultra-fast orchestrator' },
  // Ollama models
  { backend: 'ollama', model: 'guppy-fast',  mode: 'local', label: 'Guppy Fast (7B)',  description: 'Ollama · 5GB · quick queries' },
  { backend: 'ollama', model: 'guppy',       mode: 'local', label: 'Guppy (32B)',      description: 'Ollama · 20GB · complex tasks' },
  { backend: 'ollama', model: 'guppy-code',  mode: 'code',  label: 'Guppy Code (14B)', description: 'Ollama · 9GB · code specialist' },
  { backend: 'ollama', model: 'guppy-teach', mode: 'local', label: 'Guppy Teach (32B)', description: 'Ollama · 20GB · Socratic teaching' },
  // Cloud
  { backend: 'cloud', model: 'claude', mode: 'claude', label: 'Claude (Anthropic)', description: 'Cloud API · max capability' },
  { backend: 'cloud', model: 'auto',   mode: 'auto',   label: 'Auto (Cloud)',       description: 'Cloud API · best available model' },
]

const BACKEND_ICONS: Record<string, React.ReactNode> = {
  llamacpp: <Cpu className="w-3 h-3" />,
  ollama:   <Zap className="w-3 h-3" />,
  cloud:    <Cloud className="w-3 h-3" />,
}

interface BackendSelectorProps {
  surface: 'companion' | 'workspace' | 'codespace'
  compact?: boolean
}

export function BackendSelector({ surface, compact = false }: BackendSelectorProps) {
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
            {(['llamacpp', 'ollama', 'cloud'] as const).map((backend) => {
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
