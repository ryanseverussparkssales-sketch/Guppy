/**
 * DesktopView — Live desktop vision and control panel.
 *
 * Features:
 * - Live screenshot viewer (manual refresh + auto-refresh)
 * - Click on screenshot → sends click to the desktop
 * - Type text / send keyboard shortcuts
 * - Scroll & drag controls
 * - Vision OCR: ask a question about the current screen
 *
 * Backend: POST/GET /api/desktop/*
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Monitor, RefreshCw, MousePointer, Keyboard, Eye,
  Play, Square, ChevronUp, ChevronDown,
  Crosshair, Type, Zap, AlertCircle, Send, Bot,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api, { streamChat } from '../api/client'

interface ScreenInfo {
  width: number
  height: number
  cursor_x: number
  cursor_y: number
}

interface Screenshot {
  image: string        // base64 JPEG
  mime_type: string
  width: number
  height: number
  region: string
  timestamp: number
}

type Region = 'full' | 'top' | 'bottom' | 'left' | 'right' | 'active_window'
const REGIONS: Region[] = ['full', 'top', 'bottom', 'left', 'right', 'active_window']

export default function DesktopView() {
  const [screenshot, setScreenshot]     = useState<Screenshot | null>(null)
  const [screenInfo, setScreenInfo]     = useState<ScreenInfo | null>(null)
  const [loading, setLoading]           = useState(false)
  const [autoRefresh, setAutoRefresh]   = useState(false)
  const [region, setRegion]             = useState<Region>('full')
  const [clickMode, setClickMode]       = useState(false)
  const [lastAction, setLastAction]     = useState('')
  const [typeText, setTypeText]         = useState('')
  const [shortcut, setShortcut]         = useState('')
  const [ocrInstruction, setOcrInstruction] = useState('Describe what you see on the screen in detail.')
  const [ocrResult, setOcrResult]       = useState('')
  const [ocrLoading, setOcrLoading]     = useState(false)

  // Agent prompt bar
  const [agentPrompt, setAgentPrompt]   = useState('')
  const [agentResponse, setAgentResponse] = useState('')
  const [agentLoading, setAgentLoading] = useState(false)

  const imgRef      = useRef<HTMLImageElement>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Fetch screen info ─────────────────────────────────────────────────────
  const fetchInfo = useCallback(async () => {
    try {
      const res = await api.get('/api/desktop/info')
      setScreenInfo(res.data)
    } catch {
      // non-fatal
    }
  }, [])

  // ── Take screenshot ───────────────────────────────────────────────────────
  const takeScreenshot = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const res = await api.post('/api/desktop/screenshot', { region, quality: 80 })
      setScreenshot(res.data)
      if (!quiet) setLastAction(`Screenshot taken (${res.data.width}×${res.data.height})`)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Screenshot failed'
      if (!quiet) toast.error(msg)
      setLastAction(`Error: ${msg}`)
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [region])

  // ── Auto-refresh ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => takeScreenshot(true), 2000)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [autoRefresh, takeScreenshot])

  // Initial load
  useEffect(() => {
    takeScreenshot()
    fetchInfo()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Click on screenshot image → desktop click ─────────────────────────────
  const handleImageClick = async (e: React.MouseEvent<HTMLImageElement>) => {
    if (!clickMode || !screenshot || !imgRef.current) return
    const rect = imgRef.current.getBoundingClientRect()
    const relX = (e.clientX - rect.left) / rect.width
    const relY = (e.clientY - rect.top) / rect.height
    const x = Math.round(relX * screenshot.width)
    const y = Math.round(relY * screenshot.height)
    try {
      const res = await api.post('/api/desktop/click', { x, y })
      setLastAction(res.data.result)
      setTimeout(() => takeScreenshot(true), 300)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Click failed')
    }
  }

  // ── Type text ─────────────────────────────────────────────────────────────
  const handleType = async () => {
    if (!typeText.trim()) return
    try {
      const res = await api.post('/api/desktop/type', { text: typeText })
      setLastAction(res.data.result)
      setTypeText('')
      setTimeout(() => takeScreenshot(true), 200)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Type failed')
    }
  }

  // ── Keyboard shortcut ─────────────────────────────────────────────────────
  const handleShortcut = async (keys: string) => {
    const k = keys || shortcut
    if (!k.trim()) return
    try {
      const res = await api.post('/api/desktop/shortcut', { keys: k })
      setLastAction(res.data.result)
      setShortcut('')
      setTimeout(() => takeScreenshot(true), 200)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Shortcut failed')
    }
  }

  // ── Scroll ────────────────────────────────────────────────────────────────
  const handleScroll = async (direction: 'up' | 'down') => {
    try {
      const clicks = direction === 'up' ? 5 : -5
      const res = await api.post('/api/desktop/scroll', { clicks, x: 0, y: 0 })
      setLastAction(res.data.result)
      setTimeout(() => takeScreenshot(true), 200)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Scroll failed')
    }
  }

  // ── Vision OCR ────────────────────────────────────────────────────────────
  const handleReadScreen = async () => {
    setOcrLoading(true)
    setOcrResult('')
    try {
      const res = await api.post('/api/desktop/read-screen', {
        instruction: ocrInstruction,
        region,
        quality: 85,
      })
      setOcrResult(res.data.result)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Vision failed')
    } finally {
      setOcrLoading(false)
    }
  }

  // ── Quick shortcuts ───────────────────────────────────────────────────────
  const QUICK_SHORTCUTS = [
    { label: 'Copy',  keys: 'ctrl+c' },
    { label: 'Paste', keys: 'ctrl+v' },
    { label: 'Undo',  keys: 'ctrl+z' },
    { label: 'Win+D', keys: 'win+d' },
    { label: 'Alt+Tab', keys: 'alt+tab' },
    { label: 'Escape', keys: 'escape' },
    { label: 'Enter', keys: 'enter' },
    { label: 'PrtSc', keys: 'printscreen' },
  ]

  // ── Agent prompt ──────────────────────────────────────────────────────────
  const handleAgentPrompt = async () => {
    const prompt = agentPrompt.trim()
    if (!prompt || agentLoading) return
    setAgentLoading(true)
    setAgentResponse('')
    setAgentPrompt('')
    try {
      // Snapshot first so the AI has fresh context
      await takeScreenshot(true)
      let reply = ''
      await streamChat(
        { message: `[Desktop Control] ${prompt}` },
        (token) => { reply += token; setAgentResponse(reply) }
      )
    } catch (err: any) {
      toast.error(err?.message || 'Agent failed')
    } finally {
      setAgentLoading(false)
    }
  }

  return (
    <div className="flex h-full bg-background overflow-hidden">
      {/* ── Left panel: screenshot viewer ─────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="border-b border-border px-4 py-3 flex items-center gap-3 bg-surface flex-shrink-0">
          <Monitor className="w-5 h-5 text-primary" />
          <h1 className="font-semibold text-lg">Desktop Control</h1>

          {screenInfo && (
            <span className="text-xs text-on-surface-variant ml-2">
              {screenInfo.width}×{screenInfo.height} · cursor ({screenInfo.cursor_x}, {screenInfo.cursor_y})
            </span>
          )}

          <div className="ml-auto flex items-center gap-2">
            {/* Region selector */}
            <select
              value={region}
              onChange={e => setRegion(e.target.value as Region)}
              className="text-xs px-2 py-1 rounded border border-border bg-background text-on-background"
            >
              {REGIONS.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>

            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(v => !v)}
              title={autoRefresh ? 'Stop auto-refresh' : 'Auto-refresh every 2s'}
              className={cn(
                'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors',
                autoRefresh
                  ? 'bg-success/20 text-success border border-success/30'
                  : 'bg-surface-variant text-on-surface-variant hover:bg-surface-container'
              )}
            >
              {autoRefresh ? <Square className="w-3 h-3" /> : <Play className="w-3 h-3" />}
              {autoRefresh ? 'Live' : 'Live'}
            </button>

            {/* Manual refresh */}
            <button
              onClick={() => takeScreenshot()}
              disabled={loading}
              className="p-2 rounded-lg hover:bg-surface-container text-on-surface-variant transition-colors disabled:opacity-50"
              title="Refresh screenshot"
            >
              <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            </button>

            {/* Click mode toggle */}
            <button
              onClick={() => setClickMode(v => !v)}
              title={clickMode ? 'Click mode ON — click image to click desktop' : 'Enable click mode'}
              className={cn(
                'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors',
                clickMode
                  ? 'bg-warning/20 text-warning border-warning/40 animate-pulse'
                  : 'bg-surface-variant text-on-surface-variant border-border hover:border-primary/50'
              )}
            >
              <Crosshair className="w-3.5 h-3.5" />
              {clickMode ? 'Clicking' : 'Click'}
            </button>
          </div>
        </div>

        {/* Screenshot canvas */}
        <div className="flex-1 overflow-auto bg-black/5 p-3 flex items-center justify-center">
          {screenshot ? (
            <img
              ref={imgRef}
              src={`data:${screenshot.mime_type};base64,${screenshot.image}`}
              alt="Desktop screenshot"
              onClick={handleImageClick}
              className={cn(
                'max-w-full max-h-full object-contain rounded shadow-lg select-none',
                clickMode && 'cursor-crosshair ring-2 ring-warning/60'
              )}
            />
          ) : (
            <div className="text-center text-on-surface-variant space-y-3">
              <Monitor className="w-16 h-16 mx-auto opacity-30" />
              <p className="text-sm">{loading ? 'Capturing screen…' : 'No screenshot yet'}</p>
            </div>
          )}
        </div>

        {/* Status bar */}
        {lastAction && (
          <div className="border-t border-border px-4 py-1.5 text-xs text-on-surface-variant bg-surface flex-shrink-0 truncate">
            {lastAction}
          </div>
        )}

        {/* Agent prompt bar */}
        <div className="border-t border-border bg-surface flex-shrink-0">
          {agentResponse && (
            <div className="px-4 py-3 border-b border-border text-sm text-on-surface bg-surface-container-low max-h-36 overflow-y-auto whitespace-pre-wrap leading-relaxed">
              <span className="text-xs font-semibold text-primary flex items-center gap-1 mb-1">
                <Bot className="w-3 h-3" /> Guppy
              </span>
              {agentResponse}
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-2">
            <Bot className="w-4 h-4 text-primary flex-shrink-0" />
            <input
              value={agentPrompt}
              onChange={e => setAgentPrompt(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAgentPrompt() } }}
              placeholder="Tell Guppy what to do on screen…"
              disabled={agentLoading}
              className="flex-1 text-sm bg-transparent outline-none text-on-surface placeholder:text-on-surface-variant/50 disabled:opacity-50"
            />
            <button
              onClick={handleAgentPrompt}
              disabled={!agentPrompt.trim() || agentLoading}
              className="p-1.5 rounded-lg bg-primary text-white disabled:opacity-40 hover:bg-primary/90 transition-colors flex-shrink-0"
            >
              {agentLoading
                ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                : <Send className="w-3.5 h-3.5" />
              }
            </button>
          </div>
        </div>
      </div>

      {/* ── Right panel: controls ──────────────────────────────────────────── */}
      <div className="w-72 border-l border-border flex flex-col bg-surface overflow-y-auto flex-shrink-0">

        {/* Mouse controls */}
        <section className="p-4 border-b border-border space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-on-surface">
            <MousePointer className="w-4 h-4 text-primary" />
            Mouse
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleScroll('up')}
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-surface-variant text-on-surface-variant hover:bg-surface-container text-xs transition-colors"
            >
              <ChevronUp className="w-3.5 h-3.5" /> Scroll Up
            </button>
            <button
              onClick={() => handleScroll('down')}
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-surface-variant text-on-surface-variant hover:bg-surface-container text-xs transition-colors"
            >
              <ChevronDown className="w-3.5 h-3.5" /> Scroll Down
            </button>
          </div>
          {clickMode && (
            <p className="text-xs text-warning bg-warning/10 px-2 py-1.5 rounded">
              Click mode active — click the screenshot to send clicks to the desktop.
            </p>
          )}
        </section>

        {/* Type text */}
        <section className="p-4 border-b border-border space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-on-surface">
            <Type className="w-4 h-4 text-primary" />
            Type Text
          </div>
          <textarea
            value={typeText}
            onChange={e => setTypeText(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleType() }
            }}
            placeholder="Text to type on desktop…"
            rows={3}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background text-on-background resize-none focus:outline-none focus:border-primary"
          />
          <button
            onClick={handleType}
            disabled={!typeText.trim()}
            className={cn(
              'w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              typeText.trim()
                ? 'bg-primary text-white hover:bg-primary/90'
                : 'bg-surface-variant text-on-surface-variant cursor-not-allowed'
            )}
          >
            Send Text
          </button>
        </section>

        {/* Keyboard shortcuts */}
        <section className="p-4 border-b border-border space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-on-surface">
            <Keyboard className="w-4 h-4 text-primary" />
            Shortcuts
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {QUICK_SHORTCUTS.map(s => (
              <button
                key={s.keys}
                onClick={() => handleShortcut(s.keys)}
                className="px-2 py-1.5 rounded text-xs bg-surface-variant text-on-surface-variant hover:bg-surface-container transition-colors truncate"
                title={s.keys}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={shortcut}
              onChange={e => setShortcut(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleShortcut(shortcut) }}
              placeholder="ctrl+shift+t"
              className="flex-1 px-2 py-1.5 text-xs rounded border border-border bg-background text-on-background focus:outline-none focus:border-primary"
            />
            <button
              onClick={() => handleShortcut(shortcut)}
              disabled={!shortcut.trim()}
              className={cn(
                'px-3 py-1.5 rounded text-xs font-medium transition-colors',
                shortcut.trim()
                  ? 'bg-primary text-white hover:bg-primary/90'
                  : 'bg-surface-variant text-on-surface-variant cursor-not-allowed'
              )}
            >
              <Zap className="w-3.5 h-3.5" />
            </button>
          </div>
        </section>

        {/* Vision / OCR */}
        <section className="p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-on-surface">
            <Eye className="w-4 h-4 text-primary" />
            Vision / OCR
          </div>
          <textarea
            value={ocrInstruction}
            onChange={e => setOcrInstruction(e.target.value)}
            placeholder="What do you want to know about the screen?"
            rows={3}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background text-on-background resize-none focus:outline-none focus:border-primary"
          />
          <button
            onClick={handleReadScreen}
            disabled={ocrLoading}
            className={cn(
              'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              ocrLoading
                ? 'bg-surface-variant text-on-surface-variant cursor-not-allowed'
                : 'bg-primary text-white hover:bg-primary/90'
            )}
          >
            {ocrLoading
              ? <><RefreshCw className="w-4 h-4 animate-spin" /> Analyzing…</>
              : <><Eye className="w-4 h-4" /> Analyze Screen</>
            }
          </button>
          {ocrResult && (
            <div className="text-xs bg-surface-container rounded-lg p-3 whitespace-pre-wrap max-h-64 overflow-y-auto text-on-surface leading-relaxed">
              {ocrResult}
            </div>
          )}
        </section>

        {/* Danger zone */}
        <section className="p-4 border-t border-border mt-auto">
          <p className="text-xs text-on-surface-variant/70 flex items-center gap-1.5">
            <AlertCircle className="w-3 h-3" />
            Desktop control acts on the host machine. Use with care.
          </p>
        </section>
      </div>
    </div>
  )
}
