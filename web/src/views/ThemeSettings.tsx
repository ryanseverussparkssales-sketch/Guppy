import { Palette } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'
import { cn } from '@/lib/utils'

export default function ThemeSettings() {
  const { activeTheme, setTheme, themes, resolvedTheme } = useTheme()

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Palette className="w-5 h-5 text-primary" />
          <h2 className="text-xl font-headline font-bold text-on-surface">Theme</h2>
        </div>
        <p className="text-sm text-on-surface-variant">
          Currently <span className="font-medium text-on-surface">{resolvedTheme}</span>.
          Drop V0 theme CSS files into <code className="text-xs font-mono bg-surface-container px-1 py-0.5 rounded">web/src/themes/</code> to add more.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {themes.map((t) => (
          <button
            key={t.id}
            onClick={() => setTheme(t.id)}
            className={cn(
              'flex items-center gap-3 p-3 rounded-lg border-2 text-left transition-all',
              activeTheme === t.id
                ? 'border-primary bg-primary/5'
                : 'border-outline-variant hover:border-outline'
            )}
          >
            <div className="flex shrink-0 rounded overflow-hidden w-10 h-10 border border-outline-variant">
              <div style={{ background: t.preview[1] }} className="w-1/2" />
              <div style={{ background: t.preview[0] }} className="w-1/2" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-on-surface truncate">{t.label}</p>
              <p className="text-xs text-on-surface-variant truncate">{t.description}</p>
              {activeTheme === t.id && (
                <p className="text-[10px] text-primary font-bold uppercase tracking-wide mt-0.5">Active</p>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
