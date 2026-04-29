/**
 * AvatarPresence — animated companion avatar orb (Phase 5)
 *
 * States: idle | listening | thinking | speaking
 *
 * idle      → breathing gradient orb, soft pulse
 * listening → three expanding rings, error-red waveform
 * thinking  → three dots orbiting the orb
 * speaking  → 11-bar waveform with audio-realistic amplitude envelope
 */
import { cn } from '@/lib/utils'

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking'

interface AvatarPresenceProps {
  state: AvatarState
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

// ── Size tokens ───────────────────────────────────────────────────────────────

const SIZE = {
  sm: { wrap: 'w-10 h-10',   letter: 'text-base',  barW: 'w-0.5', barH: 18, orbit: 8,  ring1: '-inset-1',   ring2: '-inset-2',   ring3: '-inset-3.5', dot: 'w-1.5 h-1.5' },
  md: { wrap: 'w-16 h-16',   letter: 'text-2xl',   barW: 'w-1',   barH: 30, orbit: 13, ring1: '-inset-1.5', ring2: '-inset-3',   ring3: '-inset-5',   dot: 'w-2 h-2'     },
  lg: { wrap: 'w-28 h-28',   letter: 'text-4xl',   barW: 'w-1.5', barH: 52, orbit: 22, ring1: '-inset-2',   ring2: '-inset-4',   ring3: '-inset-7',   dot: 'w-2.5 h-2.5' },
} as const

// ── Waveform — 11 bars with a bell-curve amplitude envelope ──────────────────

const BARS = 11
const ENVELOPE = Array.from({ length: BARS }, (_, i) => {
  const t = (i / (BARS - 1)) * Math.PI
  return 0.30 + 0.70 * Math.sin(t)        // 30%–100% of max height
})
const BAR_DUR = [0.55, 0.48, 0.62, 0.44, 0.58, 0.50, 0.53, 0.46, 0.60, 0.47, 0.56]
const BAR_DEL = [0.00, 0.07, 0.14, 0.06, 0.11, 0.03, 0.09, 0.15, 0.04, 0.12, 0.08]

// ── OrbitDots — three dots spinning around the orb center ────────────────────

function OrbitDots({ orbit, dotCls, color }: { orbit: number; dotCls: string; color: string }) {
  return (
    <div
      className="absolute inset-0 rounded-full"
      style={{ animation: 'spin 2.4s linear infinite' }}
    >
      {[0, 120, 240].map((deg) => (
        <div
          key={deg}
          className={cn('absolute top-1/2 left-1/2 rounded-full', dotCls, color)}
          style={{
            transform: `rotate(${deg}deg) translateX(${orbit}px) rotate(-${deg}deg) translate(-50%, -50%)`,
          }}
        />
      ))}
    </div>
  )
}

// ── AvatarPresence ────────────────────────────────────────────────────────────

export function AvatarPresence({ state, size = 'md', className }: AvatarPresenceProps) {
  const s = SIZE[size]
  const isWaveform = state === 'listening' || state === 'speaking'

  const orbBg: Record<AvatarState, string> = {
    idle:      'bg-primary/10',
    listening: 'bg-error/15',
    thinking:  'bg-secondary/15',
    speaking:  'bg-primary/20',
  }

  const ringColor: Record<'listening' | 'speaking', string> = {
    listening: 'bg-error',
    speaking:  'bg-primary',
  }

  return (
    <div className={cn('flex flex-col items-center gap-3 select-none', className)}>

      {/* ── Outer group (orb + rings) ── */}
      <div className="relative flex items-center justify-center">

        {/* Expanding pulse rings — listening & speaking */}
        {isWaveform && (
          <>
            <div className={cn('absolute rounded-full animate-ping opacity-[0.08]', ringColor[state as 'listening' | 'speaking'], s.ring3)}
                 style={{ animationDuration: '1.9s' }} />
            <div className={cn('absolute rounded-full animate-ping opacity-[0.12]', ringColor[state as 'listening' | 'speaking'], s.ring2)}
                 style={{ animationDuration: '1.3s', animationDelay: '0.2s' }} />
            <div className={cn('absolute rounded-full animate-pulse opacity-[0.18]', ringColor[state as 'listening' | 'speaking'], s.ring1)}
                 style={{ animationDuration: '1s' }} />
          </>
        )}

        {/* Thinking halo */}
        {state === 'thinking' && (
          <div className={cn('absolute rounded-full bg-secondary/10 animate-pulse', s.ring2)}
               style={{ animationDuration: '1.6s' }} />
        )}

        {/* ── The Orb ── */}
        <div className={cn(
          'relative rounded-full flex items-center justify-center transition-all duration-500 overflow-hidden',
          s.wrap,
          orbBg[state],
          state === 'idle'   && 'animate-pulse',
          isWaveform         && 'scale-105',
        )} style={{
          animationDuration: state === 'idle' ? '3s' : undefined,
          boxShadow: state === 'speaking'  ? '0 0 22px 5px rgba(99,102,241,0.22)' :
                     state === 'listening' ? '0 0 18px 4px rgba(239,68,68,0.20)' :
                     state === 'thinking'  ? '0 0 16px 3px rgba(168,85,247,0.18)' : 'none',
        }}>

          {/* Content: waveform | orbiting dots | idle letter */}
          {isWaveform ? (
            <div className="flex items-center gap-px justify-center w-full h-full px-2">
              {ENVELOPE.map((amp, i) => (
                <div
                  key={i}
                  className={cn('rounded-full flex-shrink-0', s.barW,
                    state === 'listening' ? 'bg-error/75' : 'bg-primary/85'
                  )}
                  style={{
                    height:   `${Math.round(amp * s.barH)}px`,
                    animation: `bounce ${BAR_DUR[i]}s ease-in-out ${BAR_DEL[i]}s infinite alternate`,
                  }}
                />
              ))}
            </div>
          ) : state === 'thinking' ? (
            <OrbitDots orbit={s.orbit} dotCls={s.dot} color="bg-secondary/65" />
          ) : (
            <span className={cn('font-bold text-primary/55', s.letter)}>G</span>
          )}
        </div>

        {/* Thinking center anchor dot */}
        {state === 'thinking' && (
          <div className="absolute w-2 h-2 rounded-full bg-secondary/40 animate-pulse"
               style={{ animationDuration: '0.9s' }} />
        )}
      </div>

      {/* ── State label ── */}
      <p className={cn(
        'text-xs font-medium tracking-wide transition-colors duration-300',
        state === 'idle'      && 'text-on-surface-variant/40',
        state === 'listening' && 'text-error',
        state === 'thinking'  && 'text-secondary',
        state === 'speaking'  && 'text-primary',
      )}>
        {state === 'idle'      ? 'Ready'
       : state === 'listening' ? 'Listening…'
       : state === 'thinking'  ? 'Thinking…'
       :                         'Speaking…'}
      </p>
    </div>
  )
}
