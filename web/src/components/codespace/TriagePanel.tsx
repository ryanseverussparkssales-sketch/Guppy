/**
 * TriagePanel — Self-triage dashboard
 *
 * Shows recent dev-check runs (pass/fail), failure list, and lets
 * the user trigger a manual triage or view full output.
 *
 * API:
 *   GET  /api/codespace/triage/runs          — recent runs
 *   GET  /api/codespace/triage/runs/{id}     — single run detail
 *   POST /api/codespace/triage/trigger       — trigger now
 *   GET  /api/codespace/triage/status        — watchdog status
 */
import { useState, useEffect, useCallback } from 'react'
import {
  ShieldCheck, ShieldAlert, Zap, RefreshCw, ChevronDown, ChevronRight,
  Clock, X, CheckCircle2, AlertCircle, Eye, Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { useAppStore } from '@/store/appStore'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TriageRun {
  id: string
  triggered_at: string
  trigger: string
  status: 'queued' | 'running' | 'passed' | 'failed'
  failures: string[]
  duration_s: number | null
}

interface RunDetail extends TriageRun {
  output: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: TriageRun['status'] }) {
  if (status === 'passed')  return <CheckCircle2 className="w-4 h-4 text-success" />
  if (status === 'failed')  return <AlertCircle  className="w-4 h-4 text-error" />
  if (status === 'running') return <RefreshCw    className="w-4 h-4 text-primary animate-spin" />
  return <Clock className="w-4 h-4 text-on-surface-variant/50" />
}

function fmtDuration(s: number | null) {
  if (s === null) return ''
  if (s < 60) return `${s.toFixed(0)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

function relTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
}

// ── RunCard ───────────────────────────────────────────────────────────────────

function RunCard({ run, onViewDetail }: { run: TriageRun; onViewDetail: (id: string) => void }) {
  const [expanded, setExpanded]   = useState(false)
  const { setPendingDraftText }   = useAppStore()
  const hasFailures = run.failures.length > 0

  const analyzeWithAI = async () => {
    // Fetch the full output, then pre-fill Codespace chat
    try {
      const res = await api.get(`/api/codespace/triage/runs/${run.id}`)
      const output = res.data?.output ?? run.failures.join('\n')
      const prompt = `Analyze this Guppy dev-check failure and suggest a fix:\n\n\`\`\`\n${output.slice(0, 3000)}\n\`\`\``
      setPendingDraftText(prompt)
    } catch {
      const prompt = `Analyze this dev-check failure:\n\n${run.failures.join('\n')}`
      setPendingDraftText(prompt)
    }
  }

  return (
    <div className={cn(
      "bg-surface-container rounded-xl overflow-hidden border",
      run.status === 'passed' && "border-success/20",
      run.status === 'failed' && "border-error/20",
      (run.status === 'running' || run.status === 'queued') && "border-primary/20",
    )}>
      <div
        className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer hover:bg-surface-variant/20 transition-colors"
        onClick={() => hasFailures && setExpanded(!expanded)}
      >
        <StatusIcon status={run.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-xs font-semibold capitalize",
              run.status === 'passed' && "text-success",
              run.status === 'failed' && "text-error",
              (run.status === 'running' || run.status === 'queued') && "text-primary",
            )}>
              {run.status}
            </span>
            <span className="text-xs text-on-surface-variant/40">
              {relTime(run.triggered_at)}
            </span>
            {run.duration_s !== null && (
              <span className="text-xs text-on-surface-variant/30">{fmtDuration(run.duration_s)}</span>
            )}
            <span className="text-xs text-on-surface-variant/30 capitalize">{run.trigger}</span>
          </div>
          {run.failures.length > 0 && (
            <p className="text-xs text-error/80 truncate mt-0.5">{run.failures[0]}</p>
          )}
        </div>
        {run.status === 'failed' && (
          <button
            onClick={(e) => { e.stopPropagation(); analyzeWithAI() }}
            className="p-1 rounded hover:bg-secondary/10 text-on-surface-variant/40 hover:text-secondary transition-colors"
            title="Analyze failure with AI (opens Codespace chat)"
          >
            <Sparkles className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onViewDetail(run.id) }}
          className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors"
          title="View full output"
        >
          <Eye className="w-3.5 h-3.5" />
        </button>
        {hasFailures && (
          expanded
            ? <ChevronDown  className="w-3.5 h-3.5 text-on-surface-variant/40" />
            : <ChevronRight className="w-3.5 h-3.5 text-on-surface-variant/40" />
        )}
      </div>

      {/* Failure list */}
      {expanded && hasFailures && (
        <div className="border-t border-outline-variant/10 px-3 py-2 space-y-1 bg-error/5">
          {run.failures.map((f, i) => (
            <p key={i} className="text-xs text-error/80 font-mono leading-relaxed">{f}</p>
          ))}
        </div>
      )}
    </div>
  )
}

// ── OutputModal ───────────────────────────────────────────────────────────────

function OutputModal({ runId, onClose }: { runId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/api/codespace/triage/runs/${runId}`)
      .then((r) => setDetail(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [runId])

  return (
    <div className="absolute inset-0 bg-surface z-10 flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-outline-variant/20 flex-shrink-0">
        {detail && <StatusIcon status={detail.status} />}
        <span className="text-xs font-medium text-on-surface flex-1">
          Triage output {detail ? `— ${detail.status}` : ''}
        </span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-3">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : !detail ? (
          <p className="text-xs text-error/70">Could not load run detail.</p>
        ) : (
          <pre className="text-xs font-mono text-on-surface/80 whitespace-pre-wrap leading-relaxed">
            {detail.output || '(no output)'}
          </pre>
        )}
      </div>
    </div>
  )
}

// ── TriagePanel ───────────────────────────────────────────────────────────────

export function TriagePanel() {
  const [runs, setRuns]             = useState<TriageRun[]>([])
  const [loading, setLoading]       = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [watchdog, setWatchdog]     = useState<boolean | null>(null)
  const [detailRunId, setDetailRunId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [runsRes, statusRes] = await Promise.all([
        api.get('/api/codespace/triage/runs?limit=30'),
        api.get('/api/codespace/triage/status'),
      ])
      setRuns(Array.isArray(runsRes.data) ? runsRes.data : [])
      setWatchdog(statusRes.data?.watchdog_running ?? null)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Poll for running state
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === 'running' || r.status === 'queued')
    if (!hasRunning) return
    const t = setTimeout(load, 3000)
    return () => clearTimeout(t)
  }, [runs, load])

  const trigger = async () => {
    setTriggering(true)
    try {
      await api.post('/api/codespace/triage/trigger')
      setTimeout(load, 500)
    } catch { /* ignore */ } finally {
      setTriggering(false)
    }
  }

  const lastRun = runs[0]
  const passRate = runs.length > 0
    ? Math.round((runs.filter((r) => r.status === 'passed').length / runs.filter((r) => r.status !== 'queued' && r.status !== 'running').length || 1) * 100)
    : null

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {/* Output modal */}
      {detailRunId && (
        <OutputModal runId={detailRunId} onClose={() => setDetailRunId(null)} />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {lastRun?.status === 'passed'
          ? <ShieldCheck className="w-4 h-4 text-success" />
          : lastRun?.status === 'failed'
          ? <ShieldAlert className="w-4 h-4 text-error" />
          : <ShieldCheck className="w-4 h-4 text-on-surface-variant/40" />
        }
        <span className="text-sm font-semibold text-on-surface">Self-Triage</span>
        {passRate !== null && (
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded-full font-medium",
            passRate >= 90 ? "bg-success/10 text-success" : "bg-warning/10 text-warning"
          )}>
            {passRate}% pass
          </span>
        )}
        <div className={cn(
          "ml-auto w-2 h-2 rounded-full",
          watchdog === null ? "bg-on-surface-variant/30" : watchdog ? "bg-success" : "bg-on-surface-variant/20"
        )} />
        <span className="text-xs text-on-surface-variant/40">
          {watchdog === null ? '…' : watchdog ? 'Watchdog on' : 'No watchdog'}
        </span>
      </div>

      {/* Trigger button */}
      <button
        onClick={trigger}
        disabled={triggering || runs.some((r) => r.status === 'running')}
        className="flex items-center justify-center gap-2 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium flex-shrink-0"
      >
        {triggering ? (
          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Zap className="w-3.5 h-3.5" />
        )}
        Run dev-check now
      </button>

      {/* Runs list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 min-h-0">
        {loading && runs.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : runs.length === 0 ? (
          <div className="text-center py-10">
            <ShieldCheck className="w-10 h-10 text-on-surface-variant/15 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant/40">No triage runs yet</p>
            <p className="text-xs text-on-surface-variant/30 mt-1">
              Trigger one above or wait for the watchdog to detect changes
            </p>
          </div>
        ) : (
          runs.map((run) => (
            <RunCard key={run.id} run={run} onViewDetail={setDetailRunId} />
          ))
        )}
      </div>

      {/* Refresh */}
      <button
        onClick={load}
        className="flex items-center justify-center gap-1.5 text-xs text-on-surface-variant/40 hover:text-on-surface transition-colors flex-shrink-0"
      >
        <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
        Refresh
      </button>
    </div>
  )
}
