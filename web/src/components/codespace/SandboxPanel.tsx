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

// ── TerminalOutput ────────────────────────────────────────────────────────────

function TerminalOutput({
  sandboxId,
  onClose,
}: {
  sandboxId: string
  onClose: () => void
}) {
  const [command, setCommand]   = useState('')
  const [lines, setLines]       = useState<string[]>([])
  const [running, setRunning]   = useState(false)
  const bottomRef               = useRef<HTMLDivElement>(null)
  const abortRef                = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const exec = async () => {
    if (!command.trim() || running) return
    const cmd = command.trim()
    setCommand('')
    setLines((l) => [...l, `$ ${cmd}`])
    setRunning(true)
    abortRef.current = new AbortController()

    try {
      const token = localStorage.getItem('accessToken') || ''
      const res = await fetch(`/api/codespace/sandbox/${sandboxId}/exec`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
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
            setLines((l) => [...l, evt.slice(6)])
          }
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        setLines((l) => [...l, `[error: ${e?.message ?? e}]`])
      }
    } finally {
      setRunning(false)
      abortRef.current = null
    }
  }

  const interrupt = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    setLines((l) => [...l, '^C'])
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

      {/* Output area */}
      <div className="flex-1 overflow-y-auto bg-surface-container-low p-3 font-mono text-xs text-on-surface/80 space-y-0.5">
        {lines.length === 0 && (
          <p className="text-on-surface-variant/40">Ready. Type a command below.</p>
        )}
        {lines.map((line, i) => (
          <div key={i} className={cn(
            "leading-relaxed whitespace-pre-wrap",
            line.startsWith('$') && "text-primary font-semibold",
            line.startsWith('[error') && "text-error",
          )}>
            {line}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input row */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-outline-variant/20 bg-surface-container flex-shrink-0">
        <span className="text-primary font-mono text-xs font-semibold">$</span>
        <input
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && exec()}
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
        <TerminalOutput sandboxId={activeTerminal} onClose={() => setTerminal(null)} />
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
