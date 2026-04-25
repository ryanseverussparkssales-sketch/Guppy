import { useState, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import {
  Plus, Trash2, ChevronUp, ChevronDown,
  Eye, EyeOff, Save, BookOpen, Loader2, X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  useBooklet, useBookletCompiled,
  useUpdateBookletSection, useAddBookletSection,
  useDeleteBookletSection, useReorderBookletSections,
} from '@/api/queries'
import type { BookletSection } from '@/api/schemas'

// ── Mode badge ────────────────────────────────────────────────────────────────

const MODE_META = {
  always:   { label: 'Always',   color: 'bg-primary/10 text-primary border-primary/20' },
  retrieve: { label: 'Retrieve', color: 'bg-warning/10 text-warning border-warning/20' },
  off:      { label: 'Off',      color: 'bg-muted text-on-surface-variant border-outline-variant' },
}

function ModeBadge({ mode, onClick }: { mode: BookletSection['mode']; onClick?: (e: React.MouseEvent) => void }) {
  const m = MODE_META[mode]
  return (
    <button
      onClick={onClick}
      className={cn('px-2 py-0.5 rounded-full text-xs border font-medium transition-opacity hover:opacity-80', m.color)}
    >
      {m.label}
    </button>
  )
}

// ── Add section modal ─────────────────────────────────────────────────────────

function AddSectionModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('')
  const [id, setId] = useState('')
  const [idTouched, setIdTouched] = useState(false)
  const add = useAddBookletSection()

  const derivedId = title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 64)
  const effectiveId = idTouched ? id : derivedId

  const handleSubmit = async () => {
    if (!effectiveId || !title) return
    try {
      await add.mutateAsync({ id: effectiveId, title, mode: 'always' })
      toast.success('Section added')
      onClose()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Failed to add section')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-surface border border-outline-variant rounded-xl shadow-2xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-on-surface">New Section</h3>
          <button onClick={onClose}><X className="w-4 h-4 text-on-surface-variant" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-on-surface-variant mb-1 block">Title</label>
            <input
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Communication Style"
              className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs text-on-surface-variant mb-1 block">ID (slug)</label>
            <input
              value={effectiveId}
              onChange={e => { setId(e.target.value); setIdTouched(true) }}
              placeholder="auto-generated"
              className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm font-mono text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
            />
          </div>
        </div>
        <div className="flex gap-2 mt-5 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-outline-variant text-on-surface-variant hover:bg-surface-variant">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={!title || !effectiveId || add.isPending}
            className="px-4 py-2 text-sm rounded-lg bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
          >
            {add.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
            Add Section
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main view ─────────────────────────────────────────────────────────────────

export default function InstructionsView() {
  const booklet       = useBooklet()
  const compiled      = useBookletCompiled()
  const updateSection = useUpdateBookletSection()
  const deleteSection = useDeleteBookletSection()
  const reorder       = useReorderBookletSections()

  const sections: BookletSection[] = booklet.data ?? []
  const [selectedId, setSelectedId]     = useState<string | null>(null)
  const [draftContent, setDraftContent] = useState('')
  const [draftTitle, setDraftTitle]     = useState('')
  const [dirty, setDirty]               = useState(false)
  const [showPreview, setShowPreview]   = useState(false)
  const [showAdd, setShowAdd]           = useState(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const selected = sections.find(s => s.id === selectedId) ?? null

  // Initialise draft when selection changes
  useEffect(() => {
    if (selected) {
      setDraftContent(selected.content)
      setDraftTitle(selected.title)
      setDirty(false)
    }
  }, [selectedId, selected?.content, selected?.title])

  // Auto-select first section on load
  useEffect(() => {
    if (!selectedId && sections.length > 0) {
      setSelectedId(sections[0].id)
    }
  }, [sections])

  // Auto-save with debounce
  useEffect(() => {
    if (!dirty || !selected) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await updateSection.mutateAsync({
          id: selected.id,
          title: draftTitle,
          content: draftContent,
        })
        setDirty(false)
      } catch {
        toast.error('Auto-save failed')
      }
    }, 1200)
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [dirty, draftContent, draftTitle])

  const saveNow = async () => {
    if (!selected || !dirty) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    try {
      await updateSection.mutateAsync({ id: selected.id, title: draftTitle, content: draftContent })
      setDirty(false)
      toast.success('Saved')
    } catch {
      toast.error('Save failed')
    }
  }

  const cycleMode = async (section: BookletSection) => {
    const next: Record<string, BookletSection['mode']> = { always: 'retrieve', retrieve: 'off', off: 'always' }
    try {
      await updateSection.mutateAsync({ id: section.id, mode: next[section.mode] })
    } catch {
      toast.error('Failed to update mode')
    }
  }

  const moveSection = async (id: string, direction: 'up' | 'down') => {
    const ids = sections.map(s => s.id)
    const i = ids.indexOf(id)
    if (direction === 'up' && i === 0) return
    if (direction === 'down' && i === ids.length - 1) return
    const swapIdx = direction === 'up' ? i - 1 : i + 1;
    [ids[i], ids[swapIdx]] = [ids[swapIdx], ids[i]]
    try { await reorder.mutateAsync(ids) } catch { toast.error('Reorder failed') }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this section?')) return
    try {
      await deleteSection.mutateAsync(id)
      if (selectedId === id) setSelectedId(sections.find(s => s.id !== id)?.id ?? null)
      toast.success('Section deleted')
    } catch {
      toast.error('Delete failed')
    }
  }

  const alwaysCount = sections.filter(s => s.mode === 'always').length

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Left panel: section list ── */}
      <aside className="w-72 flex-shrink-0 border-r border-outline-variant flex flex-col bg-surface-container-low">
        <div className="flex items-center justify-between px-4 py-4 border-b border-outline-variant">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-primary" />
            <span className="font-semibold text-sm text-on-surface">Instructions</span>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant hover:text-primary transition-colors"
            title="Add section"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {booklet.isPending && (
            <div className="flex items-center justify-center py-12 text-on-surface-variant">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          )}
          {sections.map((section, idx) => (
            <div
              key={section.id}
              onClick={() => setSelectedId(section.id)}
              className={cn(
                'group flex items-start gap-2 px-3 py-3 cursor-pointer transition-colors border-l-2',
                selectedId === section.id
                  ? 'bg-surface-variant border-primary'
                  : 'border-transparent hover:bg-surface-variant/50'
              )}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-on-surface truncate">{section.title}</p>
                <p className="text-xs text-on-surface-variant truncate mt-0.5">
                  {section.content.slice(0, 60).replace(/\n/g, ' ')}…
                </p>
                <div className="mt-1.5">
                  <ModeBadge mode={section.mode} onClick={e => { e.stopPropagation(); cycleMode(section) }} />
                </div>
              </div>
              <div className="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5">
                <button onClick={e => { e.stopPropagation(); moveSection(section.id, 'up') }} disabled={idx === 0}
                  className="p-0.5 rounded hover:bg-surface disabled:opacity-20">
                  <ChevronUp className="w-3 h-3 text-on-surface-variant" />
                </button>
                <button onClick={e => { e.stopPropagation(); moveSection(section.id, 'down') }} disabled={idx === sections.length - 1}
                  className="p-0.5 rounded hover:bg-surface disabled:opacity-20">
                  <ChevronDown className="w-3 h-3 text-on-surface-variant" />
                </button>
                <button onClick={e => { e.stopPropagation(); handleDelete(section.id) }}
                  className="p-0.5 rounded hover:bg-surface text-on-surface-variant hover:text-coral">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="px-4 py-3 border-t border-outline-variant">
          <p className="text-xs text-on-surface-variant">
            <span className="text-primary font-medium">{alwaysCount}</span> of {sections.length} sections active in every chat
          </p>
        </div>
      </aside>

      {/* ── Right panel: editor ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {selected ? (
          <>
            {/* Toolbar */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-outline-variant bg-surface flex-shrink-0">
              <div className="flex items-center gap-3 min-w-0">
                <input
                  value={draftTitle}
                  onChange={e => { setDraftTitle(e.target.value); setDirty(true) }}
                  className="font-semibold text-on-surface bg-transparent border-none outline-none text-base w-full"
                />
                <ModeBadge mode={selected.mode} onClick={() => cycleMode(selected)} />
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                {dirty && (
                  <span className="text-xs text-on-surface-variant">Unsaved</span>
                )}
                {updateSection.isPending && (
                  <Loader2 className="w-4 h-4 animate-spin text-on-surface-variant" />
                )}
                <button
                  onClick={() => { setShowPreview(!showPreview); if (!showPreview) compiled.refetch() }}
                  className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors',
                    showPreview
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-outline-variant text-on-surface-variant hover:bg-surface-variant'
                  )}
                >
                  {showPreview ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  {showPreview ? 'Edit' : 'Preview'}
                </button>
                <button
                  onClick={saveNow}
                  disabled={!dirty || updateSection.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-40 transition-colors"
                >
                  <Save className="w-3.5 h-3.5" />
                  Save
                </button>
              </div>
            </div>

            {/* Editor or Preview */}
            {showPreview ? (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-3xl mx-auto">
                  <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-4">
                    Compiled System Prompt — what Guppy receives at session start
                  </h3>
                  {compiled.isFetching ? (
                    <div className="flex items-center gap-2 text-on-surface-variant">
                      <Loader2 className="w-4 h-4 animate-spin" /> Loading…
                    </div>
                  ) : (
                    <pre className="whitespace-pre-wrap font-mono text-xs text-on-surface bg-surface-container p-4 rounded-xl border border-outline-variant leading-relaxed">
                      {compiled.data?.compiled ?? '(no active sections)'}
                    </pre>
                  )}
                </div>
              </div>
            ) : (
              <textarea
                value={draftContent}
                onChange={e => { setDraftContent(e.target.value); setDirty(true) }}
                placeholder="Write this section in plain text or markdown…"
                className="flex-1 p-6 font-mono text-sm text-on-surface bg-surface resize-none outline-none placeholder:text-on-surface-variant/40 leading-relaxed"
                spellCheck={false}
              />
            )}

            {/* Footer hint */}
            {!showPreview && (
              <div className="px-6 py-2 border-t border-outline-variant bg-surface-container-low flex-shrink-0">
                <p className="text-xs text-on-surface-variant">
                  Markdown supported · Auto-saves after 1.2 s · Click mode badge to change how this section is used
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-on-surface-variant">
            <div className="text-center">
              <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">Select a section to edit</p>
              <button onClick={() => setShowAdd(true)} className="mt-3 text-sm text-primary hover:underline">
                + Add your first section
              </button>
            </div>
          </div>
        )}
      </div>

      {showAdd && <AddSectionModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}
