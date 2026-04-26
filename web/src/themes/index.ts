/**
 * Theme Registry
 *
 * Each theme is a CSS file that overrides @theme CSS custom properties
 * under a [data-theme="id"] selector. Tailwind utilities pick up the
 * overrides automatically at runtime — no rebuild needed.
 *
 * HOW TO ADD A V0-GENERATED THEME
 * ─────────────────────────────────
 * 1. Drop your CSS file into this directory (e.g. `cyber.css`)
 * 2. Import it below
 * 3. Add an entry to THEMES
 * 4. Done — the theme switcher surfaces it automatically
 *
 * CSS file format:
 *   [data-theme="my-theme"] {
 *     --color-primary: #...;
 *     --color-surface: #...;
 *     --font-family-headline: 'My Font', serif;
 *     --color-gradient-start: #...;
 *     --color-gradient-end: #...;
 *     ... (any subset of the @theme tokens)
 *   }
 */

import './dark.css'
import './occult.css'
import './gonzo.css'
import './rockmag.css'
// import './cyber.css'
// import './forest.css'
// import './ocean.css'

export interface ThemeDefinition {
  id: string
  label: string
  description: string
  /** Representative swatch colors shown in the picker (primary, surface) */
  preview: [string, string]
}

export const THEMES: ThemeDefinition[] = [
  {
    id: 'default',
    label: 'Atoll Editorial',
    description: 'Warm parchment surfaces, teal primary, coral accent',
    preview: ['#006a6a', '#fbf9f4'],
  },
  {
    id: 'dark',
    label: 'Dark',
    description: 'Deep slate surfaces, bright teal primary',
    preview: ['#4cc9c9', '#0f1415'],
  },
  {
    id: 'occult',
    label: 'Liber Designatum',
    description: 'Abyss-black, gold primary, crimson accent — occult editorial',
    preview: ['#C8A84B', '#020103'],
  },
  {
    id: 'gonzo',
    label: 'Fear & Loathing',
    description: 'Void-black, acid-green primary, blood-red secondary — gonzo dark',
    preview: ['#B8E04A', '#0A0804'],
  },
  {
    id: 'rockmag',
    label: 'Creem × Rolling Stone',
    description: 'Newsprint cream, rust primary, goldenrod accent — vintage rock press',
    preview: ['#C4420A', '#F5F0E8'],
  },
  // { id: 'cyber', label: 'Cyber', description: '...', preview: ['#...', '#...'] },
]

const STORAGE_KEY = 'guppy-theme'

export function getStoredTheme(): string {
  return localStorage.getItem(STORAGE_KEY) ?? 'default'
}

export function applyTheme(id: string): void {
  const el = document.documentElement
  if (id === 'default') {
    el.removeAttribute('data-theme')
  } else {
    el.setAttribute('data-theme', id)
  }
  localStorage.setItem(STORAGE_KEY, id)
}

export function initTheme(): void {
  applyTheme(getStoredTheme())
}
