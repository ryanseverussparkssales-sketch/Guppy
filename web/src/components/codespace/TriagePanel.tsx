/**
 * TriagePanel — Self-triage dashboard + self-improvement review
 *
 * Shows recent dev-check runs (pass/fail), failure list, and lets
 * the user trigger a manual triage, view full output, or request
 * an AI-generated fix proposal (diff viewer with Accept/Reject).
 *
 * API:
 *   GET  /api/codespace/triage/runs                   — recent runs
 *   GET  /api/codespace/triage/runs/{id}              — single run detail
 *   POST /api/codespace/triage/trigger                — trigger now
 *   GET  /api/codespace/triage/status                 — watchdog status
 *   POST /api/codespace/triage/runs/{id}/propose-fix  — request AI fix
 *   GET  /api/codespace/proposals/{id}                — proposal detail
 *   POST /api/codespace/proposals/{id}/apply          — apply to branch
 *   POST /api/codespace/proposals/{id}/reject         — reject proposal
 */
import { useState, useEffect, useCallback } from 'react'
import {
  ShieldCheck, ShieldAlert, Zap, RefreshCw, ChevronDown, ChevronRight,
  Clock, X, CheckCircle2, AlertCircle, Eye, Sparkles, GitBranch,
  CheckCheck, XCircle, FlaskConical, Send,
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

interface FixProposal {
  id: string
  run_id: string
  created_at: string
  status: 'proposed' | 'applied' | 'apply_failed' | 'rejected' | 'no_fix'
  summary: string
  diff: string
  branch_name?: string
  test_status?: 'passed' | 'failed'
  test_output?: string
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

// ── DiffView ──────────────────────────────────────────────────────────────────

function DiffView({ diff }: { diff: string }) {
  if (!diff) return (
    <p className="text-xs text-on-surface-variant/40 italic px-2 py-4 text-center">
      No diff generated
    </p>
  )
  const lines = diff.split('\n')
  return (
    <pre className="text-xs font-mono whitespace-pre leading-relaxed overflow-x-auto">
      {lines.map((line, i) => {
        let cls = 'text-on-surface/70'
        let bg  = ''
        if (line.startsWith('+++') || line.startsWith('---')) {
          cls = 'text-on-surface-variant/60 font-semibold'
        } else if (line.startsWith('@@')) {
          cls = 'text-tertiary'
          bg  = 'bg-tertiary/5'
        } else if (line.startsWith('+')) {
          cls = 'text-success'
          bg  = 'bg-success/5'
        } else if (line.startsWith('-')) {
          cls = 'text-error'
          bg  = 'bg-error/5'
        }
        return (
          <div key={i} className={cn('px-2 min-w-max', bg, cls)}>
            {line || ' '}
          </div>
        )
      })}
    </pre>
  )
}

// ── ProposalModal ─────────────────────────────────────────────────────────────

function ProposalModal({ runId, onClose }: { runId: string; onClose: () => void }) {
  const [proposal, setProposal]     = useState<FixProposal | null>(null)
  const [generating, setGenerating] = useState(true)
  const [applying, setApplying]     = useState(false)
  const [rejecting, setRejecting]   = useState(false)
  const [forwarding, setForwarding] = useState(false)
  const [forwarded, setForwarded]   = useState(false)
  const [error, setError]           = useState('')

  // On mount: POST to generate proposal, then load it
  useEffect(() => {
    let cancelled = false
    setGenerating(true)
    setError('')

    api.post(`/api/codespace/triage/runs/${runId}/propose-fix`)
      .then((r) => {
        if (!cancelled) setProposal(r.data)
      })
      .catch((e) => {
        if (!cancelled) setError(e?.response?.data?.detail ?? 'Failed to generate proposal')
      })
      .finally(() => {
        if (!cancelled) setGenerating(false)
      })

    return () => { cancelled = true }
  }, [runId])

  const apply = async () => {
    if (!proposal) return
    setApplying(true)
    setError('')
    try {
      const r = await api.post(`/api/codespace/proposals/${proposal.id}/apply`)
      setProposal((p) => p ? {
        ...p,
        status:      r.data?.ok ? 'applied' : 'apply_failed',
        branch_name: r.data?.branch,
        test_status: r.data?.test_status,
        test_output: r.data?.test_output,
      } : p)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err?.response?.data?.detail ?? 'Apply failed')
    } finally {
      setApplying(false)
    }
  }

  const reject = async () => {
    if (!proposal) return
    setRejecting(true)
    try {
      await api.post(`/api/codespace/proposals/${proposal.id}/reject`)
      setProposal((p) => p ? { ...p, status: 'rejected' } : p)
    } catch { /* ignore */ } finally {
      setRejecting(false)
    }
  }

  const forwardToWorkspace = async () => {
    if (!proposal) return
    setForwarding(true)
    try {
      await api.post('/api/codespace/forward-to-workspace', {
        title: `Apply fix: ${proposal.summary.slice(0, 80)}`,
        content: proposal.diff || proposal.summary,
        source_type: 'triage',
      })
      setForwarded(true)
    } catch { /* ignore */ } finally {
      setForwarding(false)
    }
  }

  const statusLabel: Record<FixProposal['status'], string> = {
    proposed:    'Ready to apply',
    applied:     'Applied to branch',
    apply_failed:'Apply failed',
    rejected:    'Rejected',
    no_fix:      'No fix found',
  }

  const statusColor: Record<FixProposal['status'], string> = {
    proposed:    'text-primary',
    applied:     'text-success',
    apply_failed:'text-error',
    rejected:    'text-on-surface-variant/50',
    no_fix:      'text-on-surface-variant/50',
  }

  return (
    <div className="absolute inset-0 bg-surface z-20 flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-outline-variant/20 flex-shrink-0">
        <GitBranch className="w-4 h-4 text-secondary" />
        <span className="text-xs font-semibold text-on-surface flex-1">AI Fix Proposal</span>
        {proposal && !generating && (
          <span className={cn('text-xs font-medium', statusColor[proposal.status])}>
            {statusLabel[proposal.status]}
          </span>
        )}
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto">
        {generating ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-on-surface-variant/50">
            <RefreshCw className="w-6 h-6 animate-spin text-secondary" />
            <p className="text-xs">Asking AI for a fix proposal…</p>
            <p className="text-xs text-on-surface-variant/30">This may take up to 2 minutes</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 px-4">
            <AlertCircle className="w-8 h-8 text-error/50" />
            <p className="text-xs text-error/80 text-center">{error}</p>
          </div>
        ) : !proposal ? (
          <p className="text-xs text-error/70 p-4">No proposal data received.</p>
        ) : (
          <div className="flex flex-col gap-0">
            {/* Summary bar */}
            <div className="px-3 py-2.5 border-b border-outline-variant/10 bg-surface-container-low/50 flex-shrink-0">
              <p className="text-xs text-on-surface font-medium">{proposal.summary}</p>
              {proposal.branch_name && (
                <p className="text-xs text-on-surface-variant/50 mt-0.5 font-mono">
                  branch: {proposal.branch_name}
                </p>
              )}
            </div>

            {/* Diff */}
            {proposal.status !== 'no_fix' && (
              <div className="border-b border-outline-variant/10 bg-surface-container">
                <div className="px-3 py-1.5 bg-surface-container-high/50 border-b border-outline-variant/10">
                  <span className="text-xs font-semibold text-on-surface-variant/60 uppercase tracking-wider">Proposed diff</span>
                </div>
                <DiffView diff={proposal.diff} />
              </div>
            )}

            {/* Test results (after apply) */}
            {proposal.test_status && (
              <div className="border-b border-outline-variant/10">
                <div className="px-3 py-1.5 bg-surface-container-high/50 border-b border-outline-variant/10 flex items-center gap-2">
                  <FlaskConical className="w-3.5 h-3.5 text-on-surface-variant/50" />
                  <span className="text-xs font-semibold text-on-surface-variant/60 uppercase tracking-wider">
                    Dev-check result
                  </span>
                  <span className={cn(
                    'text-xs font-semibold ml-auto',
                    proposal.test_status === 'passed' ? 'text-success' : 'text-error'
                  )}>
                    {proposal.test_status === 'passed' ? '✓ Passed' : '✗ Failed'}
                  </span>
                </div>
                {proposal.test_output && (
                  <pre className="text-xs font-mono text-on-surface/70 whitespace-pre-wrap px-3 py-2 max-h-48 overflow-y-auto">
                    {proposal.test_output}
                  </pre>
                )}
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="px-3 py-2">
                <p className="text-xs text-error/80">{error}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer actions */}
      {proposal && !generating && proposal.status === 'proposed' && (
        <div className="flex items-center gap-2 px-3 py-2.5 border-t border-outline-variant/15 bg-surface-container-low/30 flex-shrink-0">
          <button
            type="button"
            onClick={apply}
            disabled={applying || rejecting}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs rounded-xl bg-success/10 text-success hover:bg-success/15 disabled:opacity-40 transition-colors font-medium"
          >
            {applying ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Applying… (runs tests)
              </>
            ) : (
              <>
                <CheckCheck className="w-3.5 h-3.5" />
                Apply to branch
              </>
            )}
          </button>
          <button
            type="button"
            onClick={reject}
            disabled={applying || rejecting}
            className="flex items-center gap-1.5 py-2 px-3 text-xs rounded-xl bg-error/8 text-error/70 hover:bg-error/12 disabled:opacity-40 transition-colors font-medium"
          >
            {rejecting ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <XCircle className="w-3.5 h-3.5" />
            )}
            Reject
          </button>
          <button
            type="button"
            onClick={forwardToWorkspace}
            disabled={forwarding || forwarded}
            className="flex items-center gap-1.5 py-2 px-3 text-xs rounded-xl bg-secondary/10 text-secondary hover:bg-secondary/15 disabled:opacity-40 transition-colors font-medium"
            title="Send fix proposal to Workspace as a task"
          >
            {forwarding ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : forwarded ? (
              <CheckCircle2 className="w-3.5 h-3.5" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            {forwarded ? 'Sent' : 'Workspace'}
          </button>
        </div>
      )}

      {/* Applied — show branch info + forward button */}
      {proposal && !generating && proposal.status === 'applied' && (
        <div className="px-3 py-2.5 border-t border-outline-variant/15 bg-success/5 flex-shrink-0 flex items-center gap-2">
          <p className="text-xs text-success font-medium flex-1 text-center">
            ✓ Patch applied to branch <span className="font-mono">{proposal.branch_name}</span>
            {proposal.test_status === 'passed' ? ' — tests pass' : proposal.test_status === 'failed' ? ' — tests failed' : ''}
          </p>
          <button
            type="button"
            onClick={forwardToWorkspace}
            disabled={forwarding || forwarded}
            className="flex items-center gap-1 py-1.5 px-2.5 text-xs rounded-xl bg-secondary/10 text-secondary hover:bg-secondary/15 disabled:opacity-40 transition-colors font-medium flex-shrink-0"
            title="Send fix proposal to Workspace as a task"
          >
            {forwarding ? <RefreshCw className="w-3 h-3 animate-spin" /> : forwarded ? <CheckCircle2 className="w-3 h-3" /> : <Send className="w-3 h-3" />}
            {forwarded ? 'Sent' : 'Workspace'}
          </button>
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

// ── RunCard ───────────────────────────────────────────────────────────────────

function RunCard({
  run,
  onViewDetail,
  onProposeFix,
}: {
  run: TriageRun
  onViewDetail: (id: string) => void
  onProposeFix: (id: string) => void
}) {
  const [expanded, setExpanded]       = useState(false)
  const [forwarding, setForwarding]   = useState(false)
  const [forwarded, setForwarded]     = useState(false)
  const { setPendingDraftText }       = useAppStore()
  const hasFailures = run.failures.length > 0

  const forwardFinding = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setForwarding(true)
    try {
      await api.post('/api/codespace/forward-to-workspace', {
        title: `Triage finding: ${run.failures[0]?.slice(0, 80) ?? run.id}`,
        content: run.failures.join('\n'),
        source_type: 'triage',
      })
      setForwarded(true)
    } catch { /* ignore */ } finally {
      setForwarding(false)
    }
  }

  const analyzeWithAI = async () => {
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
          <>
            {/* AI chat analysis */}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); analyzeWithAI() }}
              className="p-1 rounded hover:bg-secondary/10 text-on-surface-variant/40 hover:text-secondary transition-colors"
              title="Analyze failure with AI (opens Codespace chat)"
            >
              <Sparkles className="w-3.5 h-3.5" />
            </button>
            {/* Propose fix — self-improvement */}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onProposeFix(run.id) }}
              className="p-1 rounded hover:bg-tertiary/10 text-on-surface-variant/40 hover:text-tertiary transition-colors"
              title="Propose AI fix (diff + branch)"
            >
              <GitBranch className="w-3.5 h-3.5" />
            </button>
            {/* Send finding to Workspace */}
            <button
              type="button"
              onClick={forwardFinding}
              disabled={forwarding || forwarded}
              className="p-1 rounded hover:bg-secondary/10 disabled:opacity-40 transition-colors"
              title="Send triage finding to Workspace as a task"
            >
              {forwarding ? (
                <RefreshCw className="w-3.5 h-3.5 text-secondary animate-spin" />
              ) : forwarded ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-success" />
              ) : (
                <Send className="w-3.5 h-3.5 text-on-surface-variant/40 hover:text-secondary" />
              )}
            </button>
          </>
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

// ── TriagePanel ───────────────────────────────────────────────────────────────

export function TriagePanel() {
  const [runs, setRuns]               = useState<TriageRun[]>([])
  const [loading, setLoading]         = useState(true)
  const [triggering, setTriggering]   = useState(false)
  const [watchdog, setWatchdog]       = useState<boolean | null>(null)
  const [detailRunId, setDetailRunId] = useState<string | null>(null)
  const [proposeRunId, setProposeRunId] = useState<string | null>(null)

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

  // Poll while a run is active
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
  const completedRuns = runs.filter((r) => r.status !== 'queued' && r.status !== 'running')
  const passRate = completedRuns.length > 0
    ? Math.round((completedRuns.filter((r) => r.status === 'passed').length / completedRuns.length) * 100)
    : null

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {/* Output modal (z-10) */}
      {detailRunId && !proposeRunId && (
        <OutputModal runId={detailRunId} onClose={() => setDetailRunId(null)} />
      )}

      {/* Proposal modal (z-20, above output modal) */}
      {proposeRunId && (
        <ProposalModal runId={proposeRunId} onClose={() => setProposeRunId(null)} />
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
            <RunCard
              key={run.id}
              run={run}
              onViewDetail={setDetailRunId}
              onProposeFix={setProposeRunId}
            />
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
