/**
 * SandboxPanel — Docker sandbox manager
 *
 * Lists running Guppy sandboxes, lets the user create new ones,
 * and executes commands inside them with live SSE-streamed output.
 *
 * API:
 *   GET    /api/codespace/sandbox
 *   POST   /api/codespace/sandbox            { name?, image? }
 *   POST   /api/codespace/sandbox/{id}/exec  { command }
 *   DELETE /api/codespace/sandbox/{id}
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Box, Plus, Trash2, Terminal, RefreshCw, Play, X, AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import type { Terminal as XTerminal } from '@xterm/xterm'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Sandbox {
  id: string
  name: string
  image: string
  status: string
  created_at: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusColor(status: string) {
  if (status.toLowerCase().startsWith('up')) return 'text-success'
  if (status.toLowerCase().includes('exit')) return 'text-error/70'
  return 'text-on-surface-variant/50'
}

// ── XTermOutput ───────────────────────────────────────────────────────────────

function XTermOutput({
  sandboxId,
  onClose,
}: {
  sandboxId: string
  onClose: () => void
}) {
  const containerRef                 = useRef<HTMLDivElement>(null)
  const termRef                      = useRef<XTerminal | null>(null)
  const fitRef                       = useRef<{ fit: () => void } | null>(null)
  const [command, setCommand]        = useState('')
  const [running, setRunning]        = useState(false)
  const abortRef                     = useRef<AbortController | null>(null)
  const inputRef                     = useRef<HTMLInputElement>(null)

  // Lazy-load xterm (keeps initial bundle small)
  useEffect(() => {
    let term: XTerminal
    let resizeOb: ResizeObserver | undefined

    const init = async () => {
      const { Terminal } = await import('@xterm/xterm')
      const { FitAddon }  = await import('@xterm/addon-fit')
      const { WebLinksAddon } = await import('@xterm/addon-web-links')

      // Import xterm CSS once
      await import('@xterm/xterm/css/xterm.css')

      term = new Terminal({
        theme: {
          background: 'transparent',
          foreground: '#d4d4d8',
          cursor: '#a1a1aa',
          selectionBackground: '#3f3f46',
          black:   '#18181b', brightBlack:   '#71717a',
          red:     '#f87171', brightRed:     '#fca5a5',
          green:   '#4ade80', brightGreen:   '#86efac',
          yellow:  '#facc15', brightYellow:  '#fde047',
          blue:    '#60a5fa', brightBlue:    '#93c5fd',
          magenta: '#c084fc', brightMagenta: '#d8b4fe',
          cyan:    '#22d3ee', brightCyan:    '#67e8f9',
          white:   '#d4d4d8', brightWhite:   '#f4f4f5',
        },
        fontFamily: '"Cascadia Code", "Fira Code", "JetBrains Mono", monospace',
        fontSize: 12,
        cursorBlink: true,
        convertEol: true,
        scrollback: 2000,
        allowProposedApi: false,
      })
      const fit   = new FitAddon()
      const links = new WebLinksAddon()
      term.loadAddon(fit)
      term.loadAddon(links)

      if (containerRef.current) {
        term.open(containerRef.current)
        fit.fit()
      }
      termRef.current = term
      fitRef.current  = fit
      term.writeln('\x1b[1;36m── Guppy Sandbox Terminal ──\x1b[0m')
      term.writeln(`\x1b[2mContainer: ${sandboxId.slice(0, 12)}\x1b[0m`)
      term.writeln('')

      resizeOb = new ResizeObserver(() => { try { fit.fit() } catch { /* ignore */ } })
      if (containerRef.current?.parentElement) {
        resizeOb.observe(containerRef.current.parentElement)
      }
    }

    init()
    return () => {
      resizeOb?.disconnect()
      term?.dispose()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sandboxId])

  const exec = async () => {
    const cmd = command.trim()
    if (!cmd || running) return
    setCommand('')
    setRunning(true)
    const term = termRef.current
    term?.writeln(`\x1b[1;32m$ ${cmd}\x1b[0m`)
    abortRef.current = new AbortController()

    try {
      const token = localStorage.getItem('accessToken') || ''
      const res = await fetch(`/api/codespace/sandbox/${sandboxId}/exec`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ command: cmd }),
        signal: abortRef.current.signal,
      })
      if (!res.body) throw new Error('No body')

      const reader = res.body.getReader()
      const dec    = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const events = buf.split('\n\n')
        buf = events.pop() ?? ''
        for (const evt of events) {
          if (evt.startsWith('event: done')) {
            setRunning(false)
          } else if (evt.startsWith('data: ')) {
            term?.writeln(evt.slice(6))
          }
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        term?.writeln(`\x1b[1;31m[error: ${e?.message ?? e}]\x1b[0m`)
      }
    } finally {
      setRunning(false)
      abortRef.current = null
      term?.writeln('')
      inputRef.current?.focus()
    }
  }

  const interrupt = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    termRef.current?.writeln('^C')
  }

  return (
    <div className="absolute inset-0 bg-surface z-10 flex flex-col">
      {/* Terminal header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-surface-container border-b border-outline-variant/20 flex-shrink-0">
        <Terminal className="w-4 h-4 text-on-surface-variant" />
        <span className="text-xs font-mono text-on-surface flex-1 truncate">{sandboxId.slice(0, 12)}</span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 hover:text-on-surface transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* xterm output */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 bg-[#09090b] px-2 py-1 overflow-hidden"
      />

      {/* Input row */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-outline-variant/20 bg-surface-container flex-shrink-0">
        <span className="text-primary font-mono text-xs font-semibold">$</span>
        <input
          ref={inputRef}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') exec()
            if (e.key === 'c' && e.ctrlKey) interrupt()
          }}
          placeholder="command…"
          disabled={running}
          className="flex-1 bg-transparent text-xs font-mono text-on-surface outline-none placeholder-on-surface-variant/40"
          autoFocus
        />
        {running ? (
          <button
            onClick={interrupt}
            className="p-1.5 rounded-lg bg-error/10 text-error hover:bg-error/20 transition-colors"
            title="Interrupt (Ctrl+C)"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button
            onClick={exec}
            disabled={!command.trim()}
            className="p-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-30 transition-colors"
            title="Run"
          >
            <Play className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}

// ── CreateForm ─────────────────────────────────────────────────────────────────

function CreateForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen]       = useState(false)
  const [name, setName]       = useState('')
  const [image, setImage]     = useState('python:3.12-slim')
  const [creating, setCreating] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const create = async () => {
    setCreating(true)
    setError(null)
    try {
      await api.post('/api/codespace/sandbox', { name: name.trim(), image: image.trim() })
      setName(''); setOpen(false); onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Failed to create sandbox')
    } finally {
      setCreating(false)
    }
  }

  if (!open) return (
    <button
      onClick={() => setOpen(true)}
      className="w-full flex items-center justify-center gap-2 text-xs text-on-surface-variant/60 hover:text-primary transition-colors py-2.5 border border-dashed border-outline-variant/30 rounded-xl hover:border-primary/30"
    >
      <Plus className="w-3.5 h-3.5" /> New Sandbox
    </button>
  )

  return (
    <div className="bg-surface-container rounded-xl p-3 space-y-2.5 border border-primary/20">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name (optional)"
        className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface placeholder-on-surface-variant/40"
      />
      <div className="flex gap-2">
        <select
          value={image}
          onChange={(e) => setImage(e.target.value)}
          className="flex-1 text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        >
          <option value="python:3.12-slim">Python 3.12 slim</option>
          <option value="python:3.12">Python 3.12</option>
          <option value="node:20-slim">Node 20 slim</option>
          <option value="ubuntu:24.04">Ubuntu 24.04</option>
          <option value="alpine:latest">Alpine</option>
        </select>
      </div>
      {error && <p className="text-xs text-error/80">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={create}
          disabled={creating}
          className="flex-1 text-xs bg-primary text-on-primary rounded-lg py-1.5 hover:bg-primary/90 disabled:opacity-40 transition-colors flex items-center justify-center gap-1.5"
        >
          {creating ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          {creating ? 'Creating…' : 'Create'}
        </button>
        <button onClick={() => { setOpen(false); setError(null) }} className="px-3 text-xs text-on-surface-variant/60 hover:text-on-surface">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── SandboxPanel ───────────────────────────────────────────────────────────────

export function SandboxPanel() {
  const [sandboxes, setSandboxes]     = useState<Sandbox[]>([])
  const [dockerAvail, setDockerAvail] = useState<boolean | null>(null)
  const [loading, setLoading]         = useState(true)
  const [activeTerminal, setTerminal] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/codespace/sandbox')
      setDockerAvail(res.data?.docker_available ?? true)
      setSandboxes(res.data?.sandboxes ?? [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const remove = async (id: string) => {
    try {
      await api.delete(`/api/codespace/sandbox/${id}`)
      setSandboxes((s) => s.filter((x) => x.id !== id))
      if (activeTerminal === id) setTerminal(null)
    } catch { /* ignore */ }
  }

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {/* Terminal overlay */}
      {activeTerminal && (
        <XTermOutput sandboxId={activeTerminal} onClose={() => setTerminal(null)} />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Box className="w-4 h-4 text-on-surface-variant" />
        <span className="text-sm font-semibold text-on-surface">Sandboxes</span>
        <div className={cn(
          "ml-auto w-2 h-2 rounded-full",
          dockerAvail === null ? "bg-on-surface-variant/30"
          : dockerAvail ? "bg-success" : "bg-error/60"
        )} />
        <span className="text-xs text-on-surface-variant/40">
          {dockerAvail === null ? '…' : dockerAvail ? 'Docker' : 'No Docker'}
        </span>
        <button
          onClick={load}
          className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Docker unavailable banner */}
      {dockerAvail === false && (
        <div className="flex items-start gap-2 bg-warning/10 border border-warning/20 rounded-xl px-3 py-2.5 text-xs text-warning">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            Docker is not running on this host. Install Docker Desktop or start the
            Docker daemon to use sandboxed code execution.
          </span>
        </div>
      )}

      {/* Sandbox list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : sandboxes.length === 0 ? (
          <div className="text-center py-8">
            <Box className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No sandboxes running</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">Create one below</p>
          </div>
        ) : (
          sandboxes.map((s) => (
            <div
              key={s.id}
              className="bg-surface-container rounded-xl px-3 py-2.5 flex items-center gap-2 group"
            >
              <div className="w-8 h-8 rounded-lg bg-tertiary/15 flex items-center justify-center flex-shrink-0">
                <Box className="w-4 h-4 text-tertiary/70" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-on-surface truncate">{s.name}</p>
                <p className="text-xs text-on-surface-variant/50 truncate">{s.image}</p>
                <p className={cn("text-xs", statusColor(s.status))}>{s.status}</p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => setTerminal(s.id)}
                  className="p-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                  title="Open terminal"
                >
                  <Terminal className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => remove(s.id)}
                  className="p-1.5 rounded-lg hover:bg-error/10 text-on-surface-variant/40 hover:text-error transition-colors"
                  title="Remove sandbox"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create form */}
      {dockerAvail !== false && (
        <div className="flex-shrink-0">
          <CreateForm onCreated={load} />
        </div>
      )}
    </div>
  )
}
