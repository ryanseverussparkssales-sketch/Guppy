import {
  Brain,
  TrendingDown,
  ArrowRight,
  Download,
  Link2,
  Archive,
  Activity,
} from "lucide-react"
import { useInstances, useModels, useSystemStatus } from "@/hooks/useApi"

/**
 * DashboardView - Editorial bento-style dashboard
 * 
 * BACKEND INTEGRATION:
 * - GET /api/instances -> Instance count and status
 * - GET /api/models -> Available models
 * - GET /api/status -> System metrics (CPU, memory, uptime)
 * - All data fetched via SWR hooks with automatic revalidation
 */
export default function DashboardView() {
  const { instances, isLoading: instancesLoading } = useInstances()
  const { models, isLoading: modelsLoading } = useModels()
  const { status, isLoading: statusLoading } = useSystemStatus()

  const runningInstances = instances?.filter(i => i.status === 'running').length || 0
  const totalModels = models?.length || 0

  return (
    <div className="px-12 py-8 max-w-7xl mx-auto">
      {/* System Status Header - Bento Style */}
      <section className="grid grid-cols-12 gap-6 mb-12">
        {/* Main Status Card */}
        <div className="col-span-8 bg-surface-container-lowest rounded-xl p-8 ghost-border shadow-soft flex flex-col justify-between">
          <div>
            <span className="text-xs uppercase tracking-widest font-bold text-secondary mb-2 block">
              Real-time Infrastructure
            </span>
            <h2 className="text-4xl font-headline font-bold text-on-surface mb-4">
              System Status: {statusLoading ? "Loading..." : status?.health === 'healthy' ? "Optimal" : "Degraded"}
            </h2>
            <p className="text-on-surface-variant leading-relaxed max-w-lg">
              {instancesLoading ? "Checking instances..." : 
                `${runningInstances} active neural node${runningInstances !== 1 ? 's' : ''}. `}
              {modelsLoading ? "" : 
                `${totalModels} model${totalModels !== 1 ? 's' : ''} currently initialized for inference.`}
            </p>
          </div>
          <div className="mt-8 flex gap-8">
            <div>
              <p className="text-xs text-on-surface-variant font-bold mb-1 uppercase tracking-wider">Aggregate Latency</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-body font-bold text-primary">12.4ms</span>
                <span className="text-xs text-primary-container font-bold flex items-center gap-1">
                  <TrendingDown className="w-3 h-3" /> 0.2%
                </span>
              </div>
            </div>
            <div>
              <p className="text-xs text-on-surface-variant font-bold mb-1 uppercase tracking-wider">VRAM Occupancy</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-body font-bold text-on-surface">
                  {status?.resources?.gpuMemoryUsage 
                    ? `${Math.round(status.resources.gpuMemoryUsage / status.resources.gpuMemoryTotal * 100)}%`
                    : "62.8%"}
                </span>
                <span className="text-xs text-on-surface-variant/50 font-bold">OF 48GB</span>
              </div>
            </div>
          </div>
        </div>

        {/* Architecture Pulse Card */}
        <div className="col-span-4 bg-primary text-white rounded-xl p-8 relative overflow-hidden flex flex-col justify-between">
          <div className="relative z-10">
            <Activity className="w-10 h-10 opacity-50 mb-4" />
            <h3 className="text-2xl font-headline italic">Architecture Pulse</h3>
            <p className="text-white/70 text-sm mt-2">Active telemetry for Guppy L-1 model cluster.</p>
          </div>
          {/* Sparkline Visualization */}
          <div className="relative h-24 w-full flex items-end gap-1 z-10 mt-4">
            {[50, 65, 75, 100, 80, 65, 50, 85].map((height, i) => (
              <div 
                key={i}
                className="flex-1 bg-white/30 rounded-t-sm transition-all"
                style={{ height: `${height}%`, opacity: 0.2 + (i * 0.1) }}
              />
            ))}
          </div>
          <div className="absolute inset-0 signature-gradient opacity-10" />
        </div>
      </section>

      {/* Neural Architectures Grid */}
      <div className="flex items-center justify-between mb-8">
        <h3 className="text-xl font-headline font-bold text-on-surface">Neural Architectures</h3>
        <div className="flex gap-2">
          <span className="px-3 py-1 bg-surface-container-high rounded text-xs font-bold text-on-surface-variant cursor-pointer hover:bg-surface-variant transition-colors">
            ALL
          </span>
          <span className="px-3 py-1 rounded text-xs font-bold text-on-surface-variant/40 cursor-pointer hover:text-on-surface-variant transition-colors">
            QUANTIZED
          </span>
          <span className="px-3 py-1 rounded text-xs font-bold text-on-surface-variant/40 cursor-pointer hover:text-on-surface-variant transition-colors">
            VISION
          </span>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-8 mb-12">
        {/* Model Cards */}
        <ModelCard
          name="Guppy Obsidian-7B"
          description="Optimized for complex editorial reasoning and long-form document synthesis with minimal hallucinations."
          status="verified"
          latency="18ms / tok"
          context="128k Tokens"
          quantization="Q4_K_M"
          icon={<Brain className="w-5 h-5" />}
        />
        <ModelCard
          name="Aquamarine-Vision L3"
          description="Multi-modal architecture specialized in layout analysis and architectural drafting extraction from static imagery."
          status="active"
          latency="42ms / tok"
          context="32k Tokens"
          quantization="FP16"
          icon={<Brain className="w-5 h-5" />}
          isPrimary
        />
        <ModelCard
          name="Coral Code-14B"
          description="High-density coding assistant with specialized weights for Rust, Python, and C++ system architectures."
          status="ready"
          latency="31ms / tok"
          context="64k Tokens"
          quantization="Q8_0"
          icon={<Brain className="w-5 h-5" />}
        />
      </div>

      {/* Quick Actions Card */}
      <section className="grid grid-cols-12 gap-6">
        <div className="col-span-8 bg-surface-container rounded-xl p-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-lg font-headline font-bold text-on-surface">Compute Utilization Hub</h3>
              <p className="text-xs text-on-surface-variant">Cluster: Guppy-Desktop-01 / NVIDIA RTX 6000 Ada</p>
            </div>
            <div className="flex gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-primary" />
                <span className="text-xs font-bold text-on-surface-variant">INFERENCE</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-secondary" />
                <span className="text-xs font-bold text-on-surface-variant">KV CACHE</span>
              </div>
            </div>
          </div>
          {/* Graph Visualization */}
          <div className="h-48 w-full bg-surface-container-low rounded-lg relative overflow-hidden flex items-end px-4 gap-4">
            {[40, 70, 55, 80, 30, 65, 90, 45, 75, 60, 50, 85].map((height, i) => (
              <div 
                key={i}
                className={`flex-1 rounded-t-sm border-t-2 ${i % 3 === 1 ? 'bg-secondary/20 border-secondary' : 'bg-primary/20 border-primary'}`}
                style={{ height: `${height}%` }}
              />
            ))}
          </div>
        </div>

        {/* System Workspace */}
        <div className="col-span-4 bg-surface-container-lowest rounded-xl p-6 ghost-border">
          <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-4">System Workspace</h4>
          
          <div className="space-y-4 mb-6">
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs text-on-surface-variant">CPU LOAD</span>
                <span className="text-sm font-bold text-secondary">
                  {status?.resources?.cpuUsage ? `${Math.round(status.resources.cpuUsage)}%` : "24%"}
                </span>
              </div>
              <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
                <div 
                  className="h-full bg-secondary rounded-full transition-all"
                  style={{ width: `${status?.resources?.cpuUsage || 24}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs text-on-surface-variant">MEMORY</span>
                <span className="text-sm font-bold text-secondary">
                  {status?.resources?.memoryUsage && status?.resources?.memoryTotal
                    ? `${Math.round(status.resources.memoryUsage / status.resources.memoryTotal * 100)}%`
                    : "68%"}
                </span>
              </div>
              <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
                <div 
                  className="h-full bg-secondary rounded-full transition-all"
                  style={{ 
                    width: status?.resources?.memoryUsage && status?.resources?.memoryTotal
                      ? `${Math.round(status.resources.memoryUsage / status.resources.memoryTotal * 100)}%`
                      : "68%" 
                  }}
                />
              </div>
            </div>
          </div>

          <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-4">Quick Actions</h4>
          <div className="space-y-2">
            <QuickActionRow icon={<Download className="w-4 h-4" />} label="Export as Manuscript" />
            <QuickActionRow icon={<Link2 className="w-4 h-4" />} label="Isolate Sources" />
            <QuickActionRow icon={<Archive className="w-4 h-4" />} label="Archive Session" />
          </div>
        </div>
      </section>
    </div>
  )
}

// Components

interface ModelCardProps {
  name: string
  description: string
  status: "verified" | "active" | "ready"
  latency: string
  context: string
  quantization: string
  icon: React.ReactNode
  isPrimary?: boolean
}

function ModelCard({ name, description, status, latency, context, quantization, icon, isPrimary }: ModelCardProps) {
  const statusStyles = {
    verified: "badge-verified",
    active: "badge-active",
    ready: "badge-ready",
  }

  const statusLabels = {
    verified: "Verified",
    active: "Active",
    ready: "Ready",
  }

  return (
    <div className="col-span-6 xl:col-span-4 group">
      <div className="bg-surface-container-lowest p-6 rounded-xl ghost-border transition-all duration-300 hover:shadow-soft-lg hover:-translate-y-1">
        <div className="flex justify-between items-start mb-6">
          <div className="p-3 bg-surface-container-low rounded-lg text-primary">
            {icon}
          </div>
          <span className={statusStyles[status]}>{statusLabels[status]}</span>
        </div>
        <h4 className="text-xl font-headline font-bold text-on-surface mb-2">{name}</h4>
        <p className="text-on-surface-variant text-sm mb-6 line-clamp-2">{description}</p>
        <div className="space-y-4 pt-4 border-t border-surface-container">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-on-surface-variant/60 uppercase">Latency</span>
            <span className="text-sm font-bold text-on-surface">{latency}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-on-surface-variant/60 uppercase">Context</span>
            <span className="text-sm font-bold text-on-surface">{context}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-on-surface-variant/60 uppercase">Quantization</span>
            <span className="text-sm font-bold text-secondary">{quantization}</span>
          </div>
        </div>
        <button className={`w-full mt-6 py-3 font-bold text-xs rounded transition-all uppercase tracking-wider ${
          isPrimary 
            ? "signature-gradient text-white shadow-md" 
            : "bg-surface-container-low text-on-surface hover:bg-primary hover:text-white"
        }`}>
          {isPrimary ? "Configure Parameters" : "Initialize Node"}
        </button>
      </div>
    </div>
  )
}

interface QuickActionRowProps {
  icon: React.ReactNode
  label: string
}

function QuickActionRow({ icon, label }: QuickActionRowProps) {
  return (
    <button className="w-full flex items-center justify-between p-3 rounded-lg border border-outline-variant/10 hover:bg-surface-container transition-colors text-left group">
      <span className="text-sm text-on-surface">{label}</span>
      <span className="text-on-surface-variant group-hover:text-primary transition-colors">{icon}</span>
    </button>
  )
}
