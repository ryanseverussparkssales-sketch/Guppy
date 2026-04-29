import { Brain, TrendingDown, Activity, RefreshCw, AlertCircle } from 'lucide-react'
import { useStatus, useMetrics } from '@/api/queries'

const navigate = (view: string) =>
  window.dispatchEvent(new CustomEvent('guppy:navigate', { detail: { view } }))

export default function DashboardView() {
  const statusQ  = useStatus()
  const metricsQ = useMetrics()

  const status  = statusQ.data
  const metrics = metricsQ.data
  const isLoading = statusQ.isPending || metricsQ.isPending

  const res       = status?.resource_envelope?.metrics
  const cpuPct    = res?.cpu_pct    ?? 0
  const ramPct    = res?.ram_pct    ?? 0
  const totalRam  = res?.total_ram_gb ? `${Math.round(res.total_ram_gb)}GB` : '—'
  const latency   = metrics?.average_latency_ms?.toFixed(1) ?? '—'
  const models    = status?.local_runtime?.models ?? []
  const isHealthy = status?.status === 'healthy' || status?.status === 'degraded'
  const statusLabel = status?.status === 'healthy' ? 'Optimal'
    : status?.status === 'degraded' ? 'Degraded'
    : isLoading ? 'Loading…'
    : 'Unknown'

  const requests = metrics?.requests_total ?? 0
  const errors   = metrics?.errors_total   ?? 0

  return (
    <div className="px-12 py-8 max-w-7xl mx-auto">
      {/* ── Header bento ─────────────────────────────────────────────────── */}
      <section className="grid grid-cols-12 gap-6 mb-12">
        {/* Main status */}
        <div className="col-span-8 bg-surface-container-lowest rounded-xl p-8 ghost-border shadow-soft flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-xs uppercase tracking-widest font-bold text-secondary mb-2 block">
                Real-time Infrastructure
              </span>
              <h2 className="text-4xl font-headline font-bold text-on-surface mb-4">
                System Status: {statusLabel}
              </h2>
              <p className="text-on-surface-variant leading-relaxed max-w-lg">
                {models.length > 0
                  ? `${models.length} model${models.length !== 1 ? 's' : ''} initialized for local inference.`
                  : 'Local model registry not reachable — check Ollama.'}
                {' '}
                {requests.toLocaleString()} requests served
                {errors > 0 ? `, ${errors} error${errors !== 1 ? 's' : ''}` : ' with no errors'}.
              </p>
            </div>
            <button
              type="button"
              title="Refresh"
              className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors"
              onClick={() => { statusQ.refetch(); metricsQ.refetch() }}
            >
              <RefreshCw size={16} className={(statusQ.isFetching || metricsQ.isFetching) ? 'animate-spin' : ''} />
            </button>
          </div>
          <div className="mt-8 flex gap-8">
            <div>
              <p className="text-xs text-on-surface-variant font-bold mb-1 uppercase tracking-wider">Avg Latency</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-body font-bold text-primary">{latency}ms</span>
                {errors === 0 && (
                  <span className="text-xs text-primary-container font-bold flex items-center gap-1">
                    <TrendingDown className="w-3 h-3" /> clean
                  </span>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs text-on-surface-variant font-bold mb-1 uppercase tracking-wider">RAM Usage</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-body font-bold text-on-surface">{ramPct.toFixed(0)}%</span>
                <span className="text-xs text-on-surface-variant/50 font-bold">OF {totalRam}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Architecture pulse */}
        <div className="col-span-4 bg-primary text-white rounded-xl p-8 relative overflow-hidden flex flex-col justify-between">
          <div className="relative z-10">
            <Activity className="w-10 h-10 opacity-50 mb-4" />
            <h3 className="text-2xl font-headline italic">Architecture Pulse</h3>
            <p className="text-white/70 text-sm mt-2">
              {status?.local_runtime?.backend ?? 'ollama'} runtime ·{' '}
              {status?.local_runtime?.chat_state ?? 'warming'}
            </p>
          </div>
          <div className="relative h-24 w-full flex items-end gap-1 z-10 mt-4">
            {[50, 65, 75, requests > 0 ? 100 : 60, 80, 65, 50, errors > 0 ? 30 : 85].map((h, i) => (
              <div
                key={i}
                className="flex-1 bg-white/30 rounded-t-sm"
                style={{ height: `${h}%`, opacity: 0.2 + i * 0.1 }}
              />
            ))}
          </div>
          <div className="absolute inset-0 signature-gradient opacity-10" />
        </div>
      </section>

      {/* ── Models ───────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-8">
        <h3 className="text-xl font-headline font-bold text-on-surface">Local Models</h3>
        <button
          type="button"
          onClick={() => navigate('models')}
          className="px-3 py-1 text-xs font-bold text-on-surface-variant hover:text-on-surface transition-colors"
        >
          Manage →
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-on-surface-variant">Loading…</div>
      ) : models.length === 0 ? (
        <div className="flex items-center gap-3 p-6 rounded-xl bg-surface-container text-on-surface-variant mb-12">
          <AlertCircle size={20} />
          <span>No local models found. Make sure Ollama is running on port 11434.</span>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-4 mb-12">
          {models.slice(0, 6).map((modelName, i) => (
            <ModelCard
              key={modelName}
              name={modelName}
              isPrimary={i === 0}
              role={
                modelName.includes('code') ? 'Code'
                : modelName.includes('vision') ? 'Vision'
                : modelName.includes('embed') ? 'Embeddings'
                : modelName.includes('vault') ? 'Vault'
                : modelName.includes('teach') ? 'Teaching'
                : modelName.includes('fast') ? 'Fast'
                : 'General'
              }
            />
          ))}
          {models.length > 6 && (
            <div className="col-span-6 xl:col-span-4 flex items-center justify-center p-6 rounded-xl bg-surface-container text-on-surface-variant text-sm">
              +{models.length - 6} more · <button type="button" onClick={() => navigate('models')} className="ml-1 text-primary hover:underline">View all</button>
            </div>
          )}
        </div>
      )}

      {/* ── Bottom row ───────────────────────────────────────────────────── */}
      <section className="grid grid-cols-12 gap-6">
        {/* Stats */}
        <div className="col-span-8 bg-surface-container rounded-xl p-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-lg font-headline font-bold text-on-surface">Resource Utilization</h3>
              <p className="text-xs text-on-surface-variant">
                Profile: {status?.resource_envelope ? (status.resource_envelope as any).profile ?? 'standard' : 'standard'}
              </p>
            </div>
          </div>
          <div className="h-48 w-full bg-surface-container-low rounded-lg relative overflow-hidden flex items-end px-4 gap-4">
            {/* CPU bar */}
            <div className="flex flex-col items-center gap-1 flex-1">
              <span className="text-xs text-on-surface-variant">CPU</span>
              <div className="w-full bg-surface-container rounded-t-sm flex flex-col justify-end" style={{ height: '140px' }}>
                <div
                  className="bg-primary/40 border-t-2 border-primary rounded-t-sm transition-all"
                  style={{ height: `${cpuPct}%` }}
                />
              </div>
              <span className="text-xs font-bold text-primary">{cpuPct.toFixed(0)}%</span>
            </div>
            {/* RAM bar */}
            <div className="flex flex-col items-center gap-1 flex-1">
              <span className="text-xs text-on-surface-variant">RAM</span>
              <div className="w-full bg-surface-container rounded-t-sm flex flex-col justify-end" style={{ height: '140px' }}>
                <div
                  className="bg-secondary/40 border-t-2 border-secondary rounded-t-sm transition-all"
                  style={{ height: `${ramPct}%` }}
                />
              </div>
              <span className="text-xs font-bold text-secondary">{ramPct.toFixed(0)}%</span>
            </div>
            {/* Requests bar (normalised to max 100% display) */}
            <div className="flex flex-col items-center gap-1 flex-1">
              <span className="text-xs text-on-surface-variant">Req</span>
              <div className="w-full bg-surface-container rounded-t-sm flex flex-col justify-end" style={{ height: '140px' }}>
                <div
                  className="bg-primary/20 border-t-2 border-primary/60 rounded-t-sm"
                  style={{ height: `${Math.min(requests / 10, 100)}%` }}
                />
              </div>
              <span className="text-xs font-bold text-on-surface">{requests}</span>
            </div>
            {/* Errors bar */}
            <div className="flex flex-col items-center gap-1 flex-1">
              <span className="text-xs text-on-surface-variant">Err</span>
              <div className="w-full bg-surface-container rounded-t-sm flex flex-col justify-end" style={{ height: '140px' }}>
                <div
                  className={`border-t-2 rounded-t-sm ${errors > 0 ? 'bg-coral/40 border-coral' : 'bg-surface-container border-outline-variant'}`}
                  style={{ height: errors > 0 ? `${Math.min(errors * 10, 100)}%` : '2px' }}
                />
              </div>
              <span className={`text-xs font-bold ${errors > 0 ? 'text-coral' : 'text-on-surface-variant'}`}>{errors}</span>
            </div>
          </div>
        </div>

        {/* System workspace */}
        <div className="col-span-4 bg-surface-container-lowest rounded-xl p-6 ghost-border">
          <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-4">System Workspace</h4>

          <div className="space-y-4 mb-6">
            <ResourceBar label="CPU LOAD" pct={cpuPct} color="secondary" />
            <ResourceBar label="MEMORY"   pct={ramPct}  color="secondary" />
          </div>

          <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-4">Quick Actions</h4>
          <div className="space-y-2">
            <QuickAction label="Open Chat"    onClick={() => navigate('assistant')} />
            <QuickAction label="Browse Models" onClick={() => navigate('models')} />
            <QuickAction label="Admin Panel"  onClick={() => navigate('admin')} />
          </div>
        </div>
      </section>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface ModelCardProps { name: string; role: string; isPrimary?: boolean }

function ModelCard({ name, role, isPrimary }: ModelCardProps) {
  return (
    <div className="col-span-6 xl:col-span-4 group">
      <div className="bg-surface-container-lowest p-6 rounded-xl ghost-border transition-all duration-300 hover:shadow-soft-lg hover:-translate-y-1">
        <div className="flex justify-between items-start mb-4">
          <div className="p-3 bg-surface-container-low rounded-lg text-primary">
            <Brain className="w-5 h-5" />
          </div>
          <span className={isPrimary ? 'badge-active' : 'badge-ready'}>{isPrimary ? 'Primary' : role}</span>
        </div>
        <h4 className="text-base font-headline font-bold text-on-surface mb-1 truncate" title={name}>{name}</h4>
        <p className="text-on-surface-variant text-xs mb-4">{role} model · Ollama</p>
        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent('guppy:navigate', { detail: { view: 'models' } }))}
          className={`w-full mt-2 py-2 font-bold text-xs rounded transition-all uppercase tracking-wider ${
            isPrimary
              ? 'signature-gradient text-white shadow-md'
              : 'bg-surface-container-low text-on-surface hover:bg-primary hover:text-white'
          }`}
        >
          {isPrimary ? 'Configure' : 'Details'}
        </button>
      </div>
    </div>
  )
}

interface ResourceBarProps { label: string; pct: number; color: 'primary' | 'secondary' }

function ResourceBar({ label, pct, color }: ResourceBarProps) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-on-surface-variant">{label}</span>
        <span className={`text-sm font-bold text-${color}`}>{pct.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
        <div className={`h-full bg-${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

interface QuickActionProps { label: string; onClick: () => void }

function QuickAction({ label, onClick }: QuickActionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center justify-between p-3 rounded-lg border border-outline-variant/10 hover:bg-surface-container transition-colors text-left group"
    >
      <span className="text-sm text-on-surface">{label}</span>
      <span className="text-on-surface-variant group-hover:text-primary transition-colors">→</span>
    </button>
  )
}
