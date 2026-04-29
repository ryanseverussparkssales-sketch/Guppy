/**
 * PersonaModelPicker — Companion surface model switcher
 *
 * Shows the 7-model stack as cards: always-on (Hermes3), persona alternatives
 * (Pepe, Rocinante, MiniCPM), workers (Hermes4, Llama70B), and cloud.
 * Polls /api/backends/llamacpp for live/cold status. One-click to:
 *   - Switch active companion model (writes to surface_config)
 *   - Wake a cold model (calls /api/backends/llamacpp/{name}/start)
 */
import { useState, useEffect, useCallback } from 'react'
import { Zap, ZapOff, RefreshCw, Check, Cpu, Cloud } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import api from '@/api/client'

interface ModelCard {
  key: string        // llamacpp-hermes3, llamacpp-pepe, etc. (or 'cloud')
  label: string
  tag: string        // chip label: "Main", "Humor", "Creative", etc.
  tagColor: string   // tailwind bg class for the tag chip
  description: string
  port?: number      // undefined = cloud/non-local
  vramGb?: number
  cpuOnly?: boolean
}

const PERSONA_MODELS: ModelCard[] = [
  {
    key: 'llamacpp-hermes3',
    label: 'Hermes 3',
    tag: 'Main Chat',
    tagColor: 'bg-primary/20 text-primary',
    description: '8B · fast · uncensored · always-on companion voice',
    port: 8087,
    vramGb: 9,
  },
  {
    key: 'llamacpp-pepe',
    label: 'Pepe',
    tag: 'Humor',
    tagColor: 'bg-amber-500/20 text-amber-400',
    description: '8B · internet personality · reddit energy · unfiltered',
    port: 8082,
    vramGb: 8.5,
  },
  {
    key: 'llamacpp-rocinante',
    label: 'Rocinante',
    tag: 'Creative',
    tagColor: 'bg-purple-500/20 text-purple-400',
    description: '12B · roleplay · writing partner · narrative depth',
    port: 8088,
    vramGb: 10,
  },
  {
    key: 'llamacpp-minicpm',
    label: 'MiniCPM Vision',
    tag: 'Vision',
    tagColor: 'bg-rose-500/20 text-rose-400',
    description: '4.5B omni · sees your screen · private · vision + voice',
    port: 8084,
    vramGb: 9,
  },
  {
    key: 'llamacpp-chat',
    label: 'Llama 3.3 70B',
    tag: 'Deep Think',
    tagColor: 'bg-cyan-500/20 text-cyan-400',
    description: '70B · CPU-only · no VRAM · slow but thorough',
    port: 8090,
    vramGb: 0,
    cpuOnly: true,
  },
  {
    key: 'cloud',
    label: 'Claude (cloud)',
    tag: 'Cloud',
    tagColor: 'bg-secondary/20 text-secondary',
    description: 'Sonnet · full capabilities · uses API key',
  },
]

interface BackendStatus {
  name: string
  alive: boolean
}

export function PersonaModelPicker({
  currentModel,
  onSwitch,
}: {
  currentModel: string
  onSwitch: (key: string) => void
}) {
  const [statuses, setStatuses] = useState<Record<string, boolean>>({})
  const [waking, setWaking]     = useState<string | null>(null)
  const [switching, setSwitching] = useState<string | null>(null)

  const fetchStatuses = useCallback(async () => {
    try {
      const res = await api.get('/api/backends/llamacpp')
      const map: Record<string, boolean> = {}
      for (const s of res.data as BackendStatus[]) {
        map[s.name] = s.alive
      }
      setStatuses(map)
    } catch { /* non-critical */ }
  }, [])

  useEffect(() => {
    fetchStatuses()
    const id = setInterval(fetchStatuses, 10000)
    return () => clearInterval(id)
  }, [fetchStatuses])

  const handleSelect = async (key: string) => {
    if (key === currentModel) return
    setSwitching(key)
    try {
      // Map to the backend model key the surface_config expects
      const modelKey = key === 'cloud' ? 'auto' : key
      await api.put('/api/surface/config/companion', { model: modelKey, fallback_model: 'auto' })
      onSwitch(key)
    } catch { /* surface_config write failed — still call onSwitch so UI updates */ }
    finally { setSwitching(null) }
  }

  const handleWake = async (e: React.MouseEvent, key: string) => {
    e.stopPropagation()
    setWaking(key)
    try {
      await api.post(`/api/backends/llamacpp/${key}/start`)
      // Poll until alive (max 90 s)
      for (let i = 0; i < 18; i++) {
        await new Promise(r => setTimeout(r, 5000))
        await fetchStatuses()
        if (statuses[key]) break
      }
    } catch { /* ignore — status poll will reflect reality */ }
    finally { setWaking(null) }
  }

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between px-0.5 mb-2">
        <span className="text-[11px] font-semibold text-on-surface-variant/50 uppercase tracking-wider">
          Active voice
        </span>
        <button
          onClick={fetchStatuses}
          className="text-on-surface-variant/30 hover:text-on-surface-variant/60 transition-colors"
          title="Refresh status"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

      {PERSONA_MODELS.map((m) => {
        const isActive  = currentModel === m.key || (m.key === 'cloud' && currentModel === 'auto')
        const isAlive   = m.key === 'cloud' ? true : (statuses[m.key] ?? false)
        const isWaking  = waking === m.key
        const isSwitching = switching === m.key

        return (
          <motion.button
            key={m.key}
            onClick={() => handleSelect(m.key)}
            whileTap={{ scale: 0.98 }}
            className={cn(
              'w-full text-left rounded-xl border px-3 py-2.5 transition-all duration-150',
              'flex items-start gap-2.5 group',
              isActive
                ? 'border-primary/40 bg-primary/8 shadow-sm'
                : 'border-outline-variant/20 bg-surface-container/40 hover:bg-surface-container hover:border-outline-variant/40',
            )}
          >
            {/* Live/cold dot */}
            <div className="flex-shrink-0 mt-1">
              {m.key === 'cloud' ? (
                <Cloud className="w-3.5 h-3.5 text-secondary/60" />
              ) : m.cpuOnly ? (
                <Cpu className={cn('w-3.5 h-3.5', isAlive ? 'text-cyan-400' : 'text-on-surface-variant/30')} />
              ) : (
                <span className={cn(
                  'block w-2 h-2 rounded-full mt-0.5',
                  isAlive ? 'bg-green-400 shadow-[0_0_4px_rgba(74,222,128,0.6)]' : 'bg-on-surface-variant/20',
                )} />
              )}
            </div>

            {/* Label + description */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className={cn(
                  'text-sm font-medium',
                  isActive ? 'text-primary' : 'text-on-surface',
                )}>
                  {m.label}
                </span>
                <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full font-medium', m.tagColor)}>
                  {m.tag}
                </span>
                {isAlive && !isActive && (
                  <span className="text-[10px] text-green-400/70">live</span>
                )}
              </div>
              <p className="text-[11px] text-on-surface-variant/50 mt-0.5 leading-snug">
                {m.description}
              </p>
            </div>

            {/* Right side: active check | wake button | switching spinner */}
            <div className="flex-shrink-0 flex items-center gap-1.5 mt-0.5">
              <AnimatePresence mode="wait">
                {isSwitching ? (
                  <motion.div key="spin" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <RefreshCw className="w-3.5 h-3.5 text-primary animate-spin" />
                  </motion.div>
                ) : isActive ? (
                  <motion.div key="check" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                    <Check className="w-3.5 h-3.5 text-primary" />
                  </motion.div>
                ) : !isAlive && m.key !== 'cloud' ? (
                  <motion.button
                    key="wake"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    onClick={(e) => handleWake(e, m.key)}
                    disabled={!!isWaking}
                    className={cn(
                      'text-[10px] px-2 py-0.5 rounded-lg border transition-colors',
                      isWaking
                        ? 'border-primary/30 text-primary/50 cursor-not-allowed'
                        : 'border-outline-variant/30 text-on-surface-variant/40 hover:border-primary/40 hover:text-primary',
                    )}
                    title="Start this model"
                  >
                    {isWaking ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                  </motion.button>
                ) : (
                  <ZapOff className="w-3 h-3 text-on-surface-variant/20 opacity-0 group-hover:opacity-100 transition-opacity" />
                )}
              </AnimatePresence>
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}
