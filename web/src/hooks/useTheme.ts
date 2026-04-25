import { useState, useCallback, useEffect } from 'react'
import { THEMES, type ThemeDefinition, applyTheme, getStoredTheme } from '@/themes'

export type { ThemeDefinition }
export { THEMES }

/**
 * Hook for reading and switching the active theme.
 *
 * Themes are implemented as CSS [data-theme] attribute overrides on <html>.
 * Tailwind utilities (bg-primary, text-on-surface, etc.) automatically
 * reflect the active theme's CSS custom properties — no JS required.
 */
export function useTheme() {
  const [activeTheme, setActiveThemeState] = useState<string>(getStoredTheme)

  // Sync across tabs
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'guppy-theme' && e.newValue) {
        setActiveThemeState(e.newValue)
        applyTheme(e.newValue)
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const setTheme = useCallback((id: string) => {
    applyTheme(id)
    setActiveThemeState(id)
  }, [])

  const toggleDark = useCallback(() => {
    setTheme(activeTheme === 'dark' ? 'default' : 'dark')
  }, [activeTheme, setTheme])

  const isDark = activeTheme === 'dark'

  // Legacy compat — SettingsView uses resolvedTheme / toggleTheme
  const resolvedTheme: 'light' | 'dark' = isDark ? 'dark' : 'light'
  const toggleTheme = toggleDark

  return {
    activeTheme,
    setTheme,
    toggleDark,
    isDark,
    themes: THEMES,
    resolvedTheme,
    toggleTheme,
  }
}
