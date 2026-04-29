/**
 * AvatarPresence — animated companion avatar orb
 *
 * States: idle | listening | thinking | speaking
 * Shows animated waveform bars during listening/speaking.
 * The orb pulses on active states.
 */
import { cn } from '@/lib/utils'

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking'

interface AvatarPresenceProps {
  state: AvatarState
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE_MAP = {
  sm: { orb: 'w-10 h-10', text: 'text-base', bars: 'h-5', barW: 'w-0.5' },
  md: { orb: 'w-16 h-16', text: 'text-2xl', bars: 'h-8', barW: 'w-1' },
  lg: { orb: 'w-24 h-24', text: 'text-3xl', bars: 'h-12', barW: 'w-1.5' },
}

const WAVEFORM_BARS = 7

export function AvatarPresence({ state, size = 'md', className }: AvatarPresenceProps) {
  const s = SIZE_MAP[size]
  const isActive = state !== 'idle'

  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      {/* Orb */}
      <div className={cn(
        "relative rounded-full flex items-center justify-center transition-all duration-500",
        s.orb,
        state === 'idle'      && "bg-primary/15 shadow-none",
        state === 'listening' && "bg-error/20 shadow-lg shadow-error/20 scale-105",
        state === 'thinking'  && "bg-secondary/20 shadow-lg shadow-secondary/20",
        state === 'speaking'  && "bg-primary/25 shadow-xl shadow-primary/30 scale-105",
      )}>
        {/* Pulse ring */}
        {isActive && (
          <div className={cn(
            "absolute inset-0 rounded-full animate-ping opacity-20",
            state === 'listening' && "bg-error",
            state === 'thinking'  && "bg-secondary",
            state === 'speaking'  && "bg-primary",
          )} />
        )}

        {/* Inner content */}
        {(state === 'listening' || state === 'speaking') ? (
          /* Waveform bars */
          <div className={cn("flex items-center gap-0.5", s.bars)}>
            {Array.from({ length: WAVEFORM_BARS }).map((_, i) => (
              <div
                key={i}
                className={cn(
                  "rounded-full animate-bounce",
                  s.barW,
                  state === 'listening' ? "bg-error" : "bg-primary",
                )}
                style={{
                  animationDelay:    `${i * 0.08}s`,
                  animationDuration: `${0.5 + (i % 3) * 0.1}s`,
                  height:            `${30 + Math.sin(i * 1.2) * 40}%`,
                }}
              />
            ))}
          </div>
        ) : state === 'thinking' ? (
          /* Spinning ring */
          <div className="w-6 h-6 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
        ) : (
          /* Logo / letter */
          <span className={cn("font-bold text-primary/70 select-none", s.text)}>G</span>
        )}
      </div>

      {/* State label */}
      <p className={cn(
        "text-xs font-medium tracking-wide transition-colors duration-300",
        state === 'idle'      && "text-on-surface-variant/40",
        state === 'listening' && "text-error",
        state === 'thinking'  && "text-secondary",
        state === 'speaking'  && "text-primary",
      )}>
        {state === 'idle'      && 'Ready'}
        {state === 'listening' && 'Listening…'}
        {state === 'thinking'  && 'Thinking…'}
        {state === 'speaking'  && 'Speaking…'}
      </p>
    </div>
  )
}
