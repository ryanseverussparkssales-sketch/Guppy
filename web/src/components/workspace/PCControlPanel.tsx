/**
 * PCControlPanel — Desktop vision + control UI
 *
 * Surfaces the /api/desktop/* endpoints in the Workspace PC tab.
 * Screenshot + vision analysis are always available.
 * Click/type/shortcut/scroll require GUPPY_DESKTOP_CONTROL=1 on the server.
 */
import { useState } from 'react'
import { Monitor, Eye, MousePointer, Keyboard, ChevronDown, Loader2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiPost(path: string, body: object) {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || resp.statusText)
  }
  return resp.json()
}

// ── Screenshot viewer ─────────────────────────────────────────────────────────

function ScreenshotViewer() {
  const [imgSrc, setImgSrc] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [region, setRegion] = useState('full')
  const [error, setError] = useState<string | null>(null)

  const takeScreenshot = async () => {
    setLoading(true)
    setError(null)
    setAnswer(null)
    try {
      const data = await apiPost('/api/desktop/screenshot', { region, quality: 80 })
      setImgSrc(`data:image/jpeg;base64,${data.image}`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const askVision = async () => {
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await apiPost('/api/desktop/read-screen', {
        instruction: question.trim(),
        region,
        quality: 80,
      })
      setAnswer(data.result)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={region}
          onChange={e => setRegion(e.target.value)}
          className="text-xs bg-surface-container border border-outline-variant/30 rounded-lg px-2 py-1.5 text-on-surface"
        >
          {['full', 'active_window', 'top', 'bottom', 'left', 'right'].map(r => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <button
          onClick={takeScreenshot}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Monitor className="w-3 h-3" />}
          Capture
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-error bg-error/5 rounded-lg px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {error}
        </div>
      )}

      {imgSrc && (
        <div className="rounded-xl overflow-hidden border border-outline-variant/20 bg-black">
          <img src={imgSrc} alt="Desktop screenshot" className="w-full object-contain max-h-72" />
        </div>
      )}

      <div className="flex gap-2">
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && askVision()}
          placeholder='Ask vision: "What error is shown?" or "What is open?"'
          className="flex-1 text-xs bg-surface-container border border-outline-variant/30 rounded-lg px-3 py-1.5 text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/40"
        />
        <button
          onClick={askVision}
          disabled={loading || !question.trim()}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-secondary/10 text-secondary hover:bg-secondary/20 transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
          Ask
        </button>
      </div>

      {answer && (
        <div className="text-xs text-on-surface bg-surface-container rounded-lg px-3 py-2 leading-relaxed whitespace-pre-wrap">
          {answer}
        </div>
      )}
    </div>
  )
}

// ── Control panel (click / type / shortcut / scroll) ─────────────────────────

function ControlPanel() {
  const [clickDesc, setClickDesc] = useState('')
  const [typeText, setTypeText] = useState('')
  const [shortcut, setShortcut] = useState('')
  const [scrollDir, setScrollDir] = useState<'up' | 'down'>('down')
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const run = async (path: string, body: object, label: string) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await apiPost(path, body)
      setResult(data.result || label + ' done')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-on-surface-variant/50">
        Requires <code className="font-mono bg-surface-container px-1 rounded">GUPPY_DESKTOP_CONTROL=1</code>
      </p>

      {/* Click by description */}
      <div className="flex gap-2">
        <input
          value={clickDesc}
          onChange={e => setClickDesc(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && clickDesc.trim() && run('/api/desktop/click-element', { description: clickDesc.trim() }, 'Click')}
          placeholder='Click element: "Submit button", "search bar"…'
          className="flex-1 text-xs bg-surface-container border border-outline-variant/30 rounded-lg px-3 py-1.5 text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/40"
        />
        <button
          onClick={() => clickDesc.trim() && run('/api/desktop/click-element', { description: clickDesc.trim() }, 'Click')}
          disabled={loading || !clickDesc.trim()}
          className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-variant/50 text-on-surface transition-colors disabled:opacity-50"
        >
          <MousePointer className="w-3 h-3" /> Click
        </button>
      </div>

      {/* Type */}
      <div className="flex gap-2">
        <input
          value={typeText}
          onChange={e => setTypeText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && typeText.trim() && run('/api/desktop/type', { text: typeText }, 'Type')}
          placeholder="Type text…"
          className="flex-1 text-xs bg-surface-container border border-outline-variant/30 rounded-lg px-3 py-1.5 text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/40"
        />
        <button
          onClick={() => typeText.trim() && run('/api/desktop/type', { text: typeText }, 'Type')}
          disabled={loading || !typeText.trim()}
          className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-variant/50 text-on-surface transition-colors disabled:opacity-50"
        >
          <Keyboard className="w-3 h-3" /> Type
        </button>
      </div>

      {/* Shortcut */}
      <div className="flex gap-2">
        <input
          value={shortcut}
          onChange={e => setShortcut(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && shortcut.trim() && run('/api/desktop/shortcut', { keys: shortcut.trim() }, 'Shortcut')}
          placeholder='Shortcut: ctrl+c, win+d, alt+tab…'
          className="flex-1 text-xs bg-surface-container border border-outline-variant/30 rounded-lg px-3 py-1.5 text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/40"
        />
        <button
          onClick={() => shortcut.trim() && run('/api/desktop/shortcut', { keys: shortcut.trim() }, 'Shortcut')}
          disabled={loading || !shortcut.trim()}
          className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-variant/50 text-on-surface transition-colors disabled:opacity-50"
        >
          ⌨ Send
        </button>
      </div>

      {/* Scroll */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-on-surface-variant/60">Scroll</span>
        <button
          onClick={() => setScrollDir(d => d === 'up' ? 'down' : 'up')}
          className="text-xs flex items-center gap-1 px-2 py-1 rounded-lg bg-surface-container border border-outline-variant/20"
        >
          <ChevronDown className={cn("w-3 h-3 transition-transform", scrollDir === 'up' && "rotate-180")} />
          {scrollDir}
        </button>
        {[3, 5, 10].map(n => (
          <button
            key={n}
            onClick={() => run('/api/desktop/scroll', { clicks: scrollDir === 'up' ? n : -n }, 'Scroll')}
            disabled={loading}
            className="text-xs px-2 py-1 rounded-lg bg-surface-container-high hover:bg-surface-variant/50 text-on-surface transition-colors disabled:opacity-50"
          >
            {n}
          </button>
        ))}
      </div>

      {loading && <div className="text-xs text-on-surface-variant/50 flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin" /> Executing…</div>}
      {result && <div className="text-xs text-emerald-600 bg-emerald-500/5 rounded-lg px-3 py-2">{result}</div>}
      {error  && <div className="flex items-start gap-2 text-xs text-error bg-error/5 rounded-lg px-3 py-2"><AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{error}</div>}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export function PCControlPanel() {
  const [tab, setTab] = useState<'vision' | 'control'>('vision')

  return (
    <div className="p-4 border-t border-outline-variant/15">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Desktop Control</h2>
        <div className="flex rounded-lg overflow-hidden border border-outline-variant/20 text-xs">
          {(['vision', 'control'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-3 py-1 transition-colors capitalize",
                tab === t
                  ? "bg-primary/15 text-primary"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-variant/30"
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === 'vision'  && <ScreenshotViewer />}
      {tab === 'control' && <ControlPanel />}
    </div>
  )
}
