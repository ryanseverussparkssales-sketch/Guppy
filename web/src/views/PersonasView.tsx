/**
 * PersonasView — Persona Library
 *
 * Create and manage AI personas. Each persona defines the assistant's
 * name, purpose, voice, enabled tools, and theme preference.
 */

import { useState } from 'react'
import {
  Plus, Users, Mic, Wrench, Palette, Check, Trash2,
  Edit2, X, ChevronRight, Volume2, Monitor,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Persona {
  id: string
  name: string
  emoji: string
  color: string          // tailwind bg class
  purpose: string        // one-line description
  system_prompt: string  // full system prompt
  voice_id: string
  voice_provider: 'auto' | 'kokoro' | 'elevenlabs' | 'sapi'
  tools: string[]        // enabled tool IDs
  theme: 'system' | 'dark' | 'light'
  is_active: boolean
  created_at: string
}

// ── Defaults ──────────────────────────────────────────────────────────────────

const EMOJI_OPTIONS = ['🤖', '🧠', '🦊', '🐋', '⚡', '🔬', '🎯', '🛠️', '📐', '🌊']
const COLOR_OPTIONS = [
  { label: 'Indigo',  bg: 'bg-indigo-500',  ring: 'ring-indigo-400' },
  { label: 'Emerald', bg: 'bg-emerald-500', ring: 'ring-emerald-400' },
  { label: 'Amber',   bg: 'bg-amber-500',   ring: 'ring-amber-400' },
  { label: 'Rose',    bg: 'bg-rose-500',    ring: 'ring-rose-400' },
  { label: 'Cyan',    bg: 'bg-cyan-500',    ring: 'ring-cyan-400' },
  { label: 'Violet',  bg: 'bg-violet-500',  ring: 'ring-violet-400' },
  { label: 'Slate',   bg: 'bg-slate-500',   ring: 'ring-slate-400' },
]

const VOICE_OPTIONS = [
  { id: 'bm_lewis',   name: 'Lewis',  provider: 'kokoro',     label: 'British Male' },
  { id: 'bm_george',  name: 'George', provider: 'kokoro',     label: 'British Male' },
  { id: 'bf_emma',    name: 'Emma',   provider: 'kokoro',     label: 'British Female' },
  { id: 'af_alloy',   name: 'Alloy',  provider: 'kokoro',     label: 'American Female' },
  { id: 'am_adam',    name: 'Adam',   provider: 'kokoro',     label: 'American Male' },
  { id: 'af_heart',   name: 'Heart',  provider: 'kokoro',     label: 'American Female' },
  { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel', provider: 'elevenlabs', label: 'ElevenLabs' },
  { id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella',  provider: 'elevenlabs', label: 'ElevenLabs' },
]

const TOOL_OPTIONS = [
  { id: 'web_search',     name: 'Web Search',     icon: '🌐' },
  { id: 'code_execution', name: 'Code Execution', icon: '⚙️' },
  { id: 'file_read',      name: 'File Read',      icon: '📄' },
  { id: 'file_write',     name: 'File Write',     icon: '✏️' },
  { id: 'query_instance', name: 'Agent Dispatch', icon: '🤖' },
  { id: 'shell_execute',  name: 'Shell',          icon: '💻' },
]

const THEME_OPTIONS: { id: Persona['theme']; label: string; icon: React.ReactNode }[] = [
  { id: 'system', label: 'System', icon: <Monitor className="w-3.5 h-3.5" /> },
  { id: 'dark',   label: 'Dark',   icon: <span className="text-xs">●</span> },
  { id: 'light',  label: 'Light',  icon: <span className="text-xs">○</span> },
]

// ── Seed personas ─────────────────────────────────────────────────────────────

const SEED_PERSONAS: Persona[] = [
  {
    id: 'guppy-default',
    name: 'Guppy',
    emoji: '🤖',
    color: 'bg-indigo-500',
    purpose: 'Technical intelligence assistant for Ryan Sparks',
    system_prompt:
      'You are Guppy, a technical intelligence assistant for Ryan Sparks. You are precise, direct, and efficient — no filler, no unnecessary caveats. Think like a senior engineer, communicate like one.',
    voice_id: 'bm_lewis',
    voice_provider: 'auto',
    tools: ['web_search', 'code_execution', 'file_read', 'query_instance'],
    theme: 'system',
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'builder',
    name: 'Builder',
    emoji: '🛠️',
    color: 'bg-amber-500',
    purpose: 'Deep code review, architecture, and implementation',
    system_prompt:
      'You are a senior software architect and builder. Analyse code rigorously, propose concrete implementations, and default to showing code over explanation. Assume expert-level context.',
    voice_id: 'am_adam',
    voice_provider: 'auto',
    tools: ['code_execution', 'file_read', 'file_write', 'shell_execute'],
    theme: 'dark',
    is_active: false,
    created_at: new Date().toISOString(),
  },
  {
    id: 'researcher',
    name: 'Researcher',
    emoji: '🔬',
    color: 'bg-emerald-500',
    purpose: 'Deep research, synthesis, and structured analysis',
    system_prompt:
      'You are a rigorous research assistant. When given a topic, search broadly, synthesise accurately, and present structured findings with citations. Prioritise nuance over speed.',
    voice_id: 'bf_emma',
    voice_provider: 'auto',
    tools: ['web_search', 'file_read'],
    theme: 'system',
    is_active: false,
    created_at: new Date().toISOString(),
  },
]

// ── blank persona factory ──────────────────────────────────────────────────────

function blankPersona(): Omit<Persona, 'id' | 'created_at'> {
  return {
    name: '',
    emoji: '🤖',
    color: 'bg-indigo-500',
    purpose: '',
    system_prompt: '',
    voice_id: 'bm_lewis',
    voice_provider: 'auto',
    tools: [],
    theme: 'system',
    is_active: false,
  }
}

// ── main view ─────────────────────────────────────────────────────────────────

export default function PersonasView() {
  const [personas, setPersonas] = useState<Persona[]>(SEED_PERSONAS)
  const [editing, setEditing]   = useState<Persona | null>(null)
  const [isNew, setIsNew]       = useState(false)

  const openNew = () => {
    setEditing({
      id: `persona-${Date.now()}`,
      created_at: new Date().toISOString(),
      ...blankPersona(),
    })
    setIsNew(true)
  }

  const openEdit = (p: Persona) => { setEditing({ ...p }); setIsNew(false) }

  const setActive = (id: string) => {
    setPersonas(prev => prev.map(p => ({ ...p, is_active: p.id === id })))
    toast.success('Persona activated')
  }

  const deletePersona = (id: string) => {
    if (!window.confirm('Delete this persona?')) return
    setPersonas(prev => prev.filter(p => p.id !== id))
    toast.success('Persona deleted')
  }

  const savePersona = (p: Persona) => {
    if (!p.name.trim()) { toast.error('Name required'); return }
    setPersonas(prev =>
      isNew ? [p, ...prev] : prev.map(x => x.id === p.id ? p : x)
    )
    setEditing(null)
    toast.success(isNew ? 'Persona created' : 'Persona saved')
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-5 border-b border-border shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Personas</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Define how Guppy behaves — voice, tools, and purpose per context
          </p>
        </div>
        <button
          onClick={openNew}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-xl text-sm font-semibold hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Persona
        </button>
      </div>

      {/* Persona grid */}
      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {personas.map(p => (
            <PersonaCard
              key={p.id}
              persona={p}
              onActivate={() => setActive(p.id)}
              onEdit={() => openEdit(p)}
              onDelete={() => deletePersona(p.id)}
            />
          ))}

          {/* Create new card */}
          <button
            onClick={openNew}
            className="rounded-2xl border-2 border-dashed border-border hover:border-primary/40 hover:bg-primary/3 transition-colors flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground hover:text-primary"
          >
            <Plus className="w-6 h-6" />
            <span className="text-sm font-medium">New Persona</span>
          </button>
        </div>
      </div>

      {/* Edit modal */}
      {editing && (
        <PersonaEditor
          persona={editing}
          isNew={isNew}
          onChange={setEditing}
          onSave={savePersona}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

// ── Persona card ──────────────────────────────────────────────────────────────

function PersonaCard({
  persona: p, onActivate, onEdit, onDelete,
}: {
  persona: Persona
  onActivate: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const voice = VOICE_OPTIONS.find(v => v.id === p.voice_id)

  return (
    <div
      className={cn(
        'group relative rounded-2xl border bg-card p-5 flex flex-col gap-4 transition-all',
        p.is_active ? 'border-primary/40 shadow-sm' : 'border-border hover:border-primary/20'
      )}
    >
      {/* Active badge */}
      {p.is_active && (
        <div className="absolute top-4 right-4 flex items-center gap-1 text-[11px] font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
          <Check className="w-3 h-3" /> Active
        </div>
      )}

      {/* Avatar + name */}
      <div className="flex items-center gap-3">
        <div className={cn('w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0', p.color)}>
          {p.emoji}
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-foreground truncate">{p.name}</h3>
          <p className="text-xs text-muted-foreground truncate">{p.purpose}</p>
        </div>
      </div>

      {/* Metadata pills */}
      <div className="flex flex-wrap gap-1.5">
        {/* Voice */}
        <span className="flex items-center gap-1 text-[11px] bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
          <Volume2 className="w-2.5 h-2.5" />
          {voice?.name ?? p.voice_id}
        </span>
        {/* Tools */}
        <span className="flex items-center gap-1 text-[11px] bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
          <Wrench className="w-2.5 h-2.5" />
          {p.tools.length} tool{p.tools.length !== 1 ? 's' : ''}
        </span>
        {/* Theme */}
        <span className="flex items-center gap-1 text-[11px] bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
          <Palette className="w-2.5 h-2.5" />
          {p.theme}
        </span>
      </div>

      {/* System prompt preview */}
      {p.system_prompt && (
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          {p.system_prompt}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-1 border-t border-border/50">
        {!p.is_active && (
          <button
            onClick={onActivate}
            className="flex-1 text-xs font-semibold py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center justify-center gap-1"
          >
            <Users className="w-3.5 h-3.5" /> Activate
          </button>
        )}
        <button
          onClick={onEdit}
          className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <Edit2 className="w-4 h-4" />
        </button>
        {!p.is_active && (
          <button
            onClick={onDelete}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-destructive transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={onEdit}
          className="ml-auto p-1.5 rounded-lg text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

// ── Persona editor modal ──────────────────────────────────────────────────────

function PersonaEditor({
  persona, isNew, onChange, onSave, onClose,
}: {
  persona: Persona
  isNew: boolean
  onChange: (p: Persona) => void
  onSave: (p: Persona) => void
  onClose: () => void
}) {
  const set = <K extends keyof Persona>(k: K, v: Persona[K]) =>
    onChange({ ...persona, [k]: v })

  const toggleTool = (id: string) => {
    const tools = persona.tools.includes(id)
      ? persona.tools.filter(t => t !== id)
      : [...persona.tools, id]
    set('tools', tools)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-outline-variant rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant/30 shrink-0">
          <h2 className="font-semibold text-on-surface">{isNew ? 'New Persona' : `Edit · ${persona.name}`}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant">
            <X className="w-4 h-4 text-on-surface-variant" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* Identity */}
          <section className="space-y-3">
            <label className="text-sm font-medium text-on-surface">Identity</label>
            {/* Emoji + color row */}
            <div className="flex items-center gap-4">
              {/* Emoji picker */}
              <div className="flex flex-wrap gap-1.5 flex-1">
                {EMOJI_OPTIONS.map(e => (
                  <button
                    key={e}
                    onClick={() => set('emoji', e)}
                    className={cn(
                      'w-9 h-9 rounded-lg text-lg flex items-center justify-center transition-all',
                      persona.emoji === e ? 'bg-primary/20 ring-2 ring-primary scale-110' : 'bg-muted hover:bg-surface-variant'
                    )}
                  >{e}</button>
                ))}
              </div>
              {/* Color picker */}
              <div className="flex gap-1.5">
                {COLOR_OPTIONS.map(c => (
                  <button
                    key={c.bg}
                    onClick={() => set('color', c.bg)}
                    className={cn(
                      'w-7 h-7 rounded-full transition-all',
                      c.bg,
                      persona.color === c.bg ? `ring-2 ring-offset-2 ring-offset-surface ${c.ring}` : 'opacity-60 hover:opacity-100'
                    )}
                  />
                ))}
              </div>
            </div>

            {/* Name */}
            <input
              value={persona.name}
              onChange={e => set('name', e.target.value)}
              placeholder="Persona name"
              className="w-full px-3 py-2 rounded-xl bg-surface-variant border border-outline-variant text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
            />
            {/* Purpose */}
            <input
              value={persona.purpose}
              onChange={e => set('purpose', e.target.value)}
              placeholder="One-line purpose (e.g. Deep code review and architecture)"
              className="w-full px-3 py-2 rounded-xl bg-surface-variant border border-outline-variant text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
            />
          </section>

          {/* System prompt */}
          <section className="space-y-2">
            <label className="text-sm font-medium text-on-surface">System Prompt</label>
            <textarea
              value={persona.system_prompt}
              onChange={e => set('system_prompt', e.target.value)}
              placeholder="Describe how this persona thinks and communicates…"
              rows={5}
              className="w-full px-3 py-2 rounded-xl bg-surface-variant border border-outline-variant text-sm font-mono text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary resize-none leading-relaxed"
            />
          </section>

          {/* Voice */}
          <section className="space-y-3">
            <label className="text-sm font-medium text-on-surface flex items-center gap-2">
              <Mic className="w-4 h-4 text-muted-foreground" /> Voice
            </label>
            <div className="grid grid-cols-3 gap-2">
              {VOICE_OPTIONS.map(v => (
                <button
                  key={v.id}
                  onClick={() => { set('voice_id', v.id); set('voice_provider', v.provider as Persona['voice_provider']) }}
                  className={cn(
                    'p-2.5 rounded-xl border text-left transition-all',
                    persona.voice_id === v.id
                      ? 'border-primary bg-primary/8 text-primary'
                      : 'border-border hover:border-primary/40 text-foreground'
                  )}
                >
                  <span className="text-sm font-medium block">{v.name}</span>
                  <span className="text-[11px] text-muted-foreground">{v.label}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Tools */}
          <section className="space-y-3">
            <label className="text-sm font-medium text-on-surface flex items-center gap-2">
              <Wrench className="w-4 h-4 text-muted-foreground" /> Tools
            </label>
            <div className="grid grid-cols-2 gap-2">
              {TOOL_OPTIONS.map(t => {
                const enabled = persona.tools.includes(t.id)
                return (
                  <button
                    key={t.id}
                    onClick={() => toggleTool(t.id)}
                    className={cn(
                      'flex items-center gap-2.5 px-3 py-2.5 rounded-xl border text-sm transition-all text-left',
                      enabled
                        ? 'border-primary bg-primary/8 text-primary'
                        : 'border-border hover:border-primary/30 text-on-surface'
                    )}
                  >
                    <span className="text-base leading-none">{t.icon}</span>
                    <span className="font-medium">{t.name}</span>
                    {enabled && <Check className="w-3.5 h-3.5 ml-auto shrink-0" />}
                  </button>
                )
              })}
            </div>
          </section>

          {/* Theme */}
          <section className="space-y-3">
            <label className="text-sm font-medium text-on-surface flex items-center gap-2">
              <Palette className="w-4 h-4 text-muted-foreground" /> Theme
            </label>
            <div className="flex gap-2">
              {THEME_OPTIONS.map(t => (
                <button
                  key={t.id}
                  onClick={() => set('theme', t.id)}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-all',
                    persona.theme === t.id
                      ? 'border-primary bg-primary/8 text-primary'
                      : 'border-border hover:border-primary/30 text-on-surface'
                  )}
                >
                  {t.icon} {t.label}
                </button>
              ))}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-outline-variant/30 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-xl border border-outline-variant text-on-surface-variant hover:bg-surface-variant transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onSave(persona)}
            className="px-5 py-2 text-sm rounded-xl bg-primary text-white font-semibold hover:bg-primary/90 transition-colors"
          >
            {isNew ? 'Create Persona' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}
