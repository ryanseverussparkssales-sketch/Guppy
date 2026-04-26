import { Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { useTheme } from '@/hooks/useTheme'

export function AppearanceCard() {
  const { resolvedTheme, activeTheme, setTheme, themes } = useTheme()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {resolvedTheme === 'dark' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          Appearance
        </CardTitle>
        <CardDescription>
          Choose a theme — drop V0 packs into <code className="text-xs font-mono">web/src/themes/</code> to add more
        </CardDescription>
      </CardHeader>
      <CardContent>
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
              <div className="flex shrink-0 rounded overflow-hidden w-8 h-8 border border-outline-variant">
                <div style={{ background: t.preview[1] }} className="w-1/2" />
                <div style={{ background: t.preview[0] }} className="w-1/2" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-on-surface truncate">{t.label}</p>
                {activeTheme === t.id && (
                  <p className="text-[10px] text-primary font-bold uppercase tracking-wide">Active</p>
                )}
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
