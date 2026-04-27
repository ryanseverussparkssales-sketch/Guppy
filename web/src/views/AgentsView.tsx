/**
 * AgentsView — Agent Routing, Multi-Agent Chains, Custom Agents
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Cpu, Cloud, Activity, Zap, DollarSign, Lock,
  CheckCircle, XCircle, RefreshCw, ChevronDown, ChevronUp,
  Users, ArrowRight, Layers, Play, X, Loader2, Copy,
  Plus, Pencil, Trash2, GitBranch, History, Bot,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useProviders } from '@/api/queries'
import api from '@/api/client'

const _API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

// ── Budget modes ──────────────────────────────────────────────────────────────

const BUDGET_MODES = [
  { id: 'local_only',  label: 'Local Only',   description: 'All requests routed to LM Studio / Ollama. No cloud calls.',         icon: <Lock className="w-5 h-5" />,       color: 'text-success' },
  { id: 'free_tier',   label: 'Free Tier',    description: 'Prefer local; fall back to cloud free-tier when unavailable.',        icon: <DollarSign className="w-5 h-5" />, color: 'text-info' },
  { id: 'balanced',    label: 'Balanced',     description: 'Simple queries local. Complex / reasoning tasks route to cloud.',     icon: <Layers className="w-5 h-5" />,     color: 'text-primary' },
  { id: 'cloud_first', label: 'Cloud First',  description: 'Prefer cloud models for quality. Local only as fallback.',            icon: <Cloud className="w-5 h-5" />,      color: 'text-secondary' },
]

const MODEL_ROLES: Record<string, { label: string; color: string }> = {
  // Ollama / Guppy models
  'guppy-fast':           { label: 'Fast Butler',    color: 'bg-success/10 text-success' },
  'guppy-code':           { label: 'Code Review',    color: 'bg-info/10 text-info' },
  'guppy':                { label: 'Full Tasks',     color: 'bg-primary/10 text-primary' },
  'guppy-teach':          { label: 'Teaching',       color: 'bg-secondary/10 text-secondary' },
  'vault-scraper':        { label: 'Vault Agent',    color: 'bg-warning/10 text-warning' },
  // llama.cpp (local GPU — ROCm)
  'assistant-pepe-8b':    { label: 'Fast Chat',      color: 'bg-emerald-600/10 text-emerald-400' },
  'qwen3-35b-uncensored': { label: 'Agentic / Heavy', color: 'bg-purple-600/10 text-purple-400' },
  'gemma-4-heretic-ara':  { label: 'Vision · Fast',  color: 'bg-orange-500/10 text-orange-400' },
  'minicpm-o-4.5':        { label: 'Omni (V+A)',     color: 'bg-pink-500/10 text-pink-400' },
  'qwen2.5-omni-3b':      { label: 'Dispatcher',     color: 'bg-cyan-500/10 text-cyan-400' },
}

const TASK_ROUTES_BY_MODE: Record<string, { task: string; route: string; local: boolean }[]> = {
  local_only:  [
    { task: 'Simple query', route: 'local / guppy-fast',  local: true },
    { task: 'Code review',  route: 'local / guppy-code',  local: true },
    { task: 'Complex task', route: 'local / guppy',       local: true },
    { task: 'Teaching',     route: 'local / guppy-teach', local: true },
    { task: 'Fallback',     route: 'local / guppy-fast',  local: true },
  ],
  free_tier: [
    { task: 'Simple query', route: 'local / guppy-fast',               local: true },
    { task: 'Code review',  route: 'local / guppy-code',               local: true },
    { task: 'Complex task', route: 'local / guppy',                    local: true },
    { task: 'Teaching',     route: 'local / guppy-teach',              local: true },
    { task: 'Fallback',     route: 'anthropic / claude-haiku (free)',  local: false },
  ],
  balanced: [
    { task: 'Simple query', route: 'pepe 8B (llamacpp)',              local: true },
    { task: 'Agentic / Files', route: 'qwen3 35B (llamacpp) → Claude', local: true },
    { task: 'Code review',  route: 'local / guppy-code',              local: true },
    { task: 'Complex task', route: 'anthropic / claude-sonnet-4-6',   local: false },
    { task: 'Teaching',     route: 'anthropic / claude-haiku-4-5',    local: false },
    { task: 'Fallback',     route: 'anthropic / claude-haiku-4-5',    local: false },
  ],
  cloud_first: [
    { task: 'Simple query', route: 'anthropic / claude-haiku-4-5',   local: false },
    { task: 'Code review',  route: 'anthropic / claude-sonnet-4-6',  local: false },
    { task: 'Complex task', route: 'anthropic / claude-sonnet-4-6',  local: false },
    { task: 'Teaching',     route: 'anthropic / claude-haiku-4-5',   local: false },
    { task: 'Fallback',     route: 'local / guppy',                  local: true },
  ],
}

// ── Chain templates ───────────────────────────────────────────────────────────

interface ChainTemplate {
  label: string
  templateId: string
  description: string
  isParallel?: boolean
  from?: string
  to?: string
}

const CHAIN_TEMPLATES: ChainTemplate[] = [
  { from: 'guppy-fast', to: 'guppy-code', label: 'Query → Code Review',       templateId: 'query_to_code',         description: 'Fast triage, then expert code generation' },
  { from: 'guppy-fast', to: 'guppy',      label: 'Triage → Deep Analysis',    templateId: 'triage_to_analysis',    description: 'Bullet-point triage, then thorough analysis' },
  { from: 'guppy',      to: 'guppy-teach',label: 'Analysis → Teaching',       templateId: 'analysis_to_teach',     description: 'Full analysis, then Socratic explanation' },
  { isParallel: true,                      label: 'Parallel Perspectives',      templateId: 'parallel_perspectives', description: 'Fast + deep agents run simultaneously, then synthesized' },
]

// ── Pipeline state types ──────────────────────────────────────────────────────

interface ParallelAgentState {
  role: string
  model: string
  status: 'pending' | 'running' | 'done'
  output: string
}

interface PipelineStepState {
  role: string
  model: string
  status: 'pending' | 'running' | 'done'
  output: string
  isParallel?: boolean
  parallelAgents?: ParallelAgentState[]
}

interface PipelineRunState {
  id: string
  template: string
  label: string
  steps: PipelineStepState[]
  currentStep: number
  status: 'running' | 'done' | 'error'
  error?: string
}

// ── Custom agent type ─────────────────────────────────────────────────────────

interface Agent {
  id: string
  name: string
  model: string
  system_prompt: string
  tools: string[]
  color: string
  created_at: string
  builtin: boolean
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useQueueHealth() {
  return useQuery({
    queryKey: ['queueHealth'],
    queryFn: async () => (await api.get('/api/queue/status')).data,
    refetchInterval: 5000,
    staleTime: 0,
    retry: false,
  })
}

function useRoutingMode() {
  return useQuery<string>({
    queryKey: ['routingMode'],
    queryFn: async () => (await api.get('/api/settings')).data?.routing_mode ?? 'balanced',
    staleTime: 30_000,
    retry: false,
  })
}

function useSaveRoutingMode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mode: string) => api.put('/api/settings', { routing_mode: mode }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routingMode'] }),
  })
}

function useAgents() {
  return useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: async () => (await api.get('/api/agents')).data,
    staleTime: 30_000,
  })
}

function usePipelineHistory() {
  return useQuery({
    queryKey: ['pipelineHistory'],
    queryFn: async () => (await api.get('/api/pipeline/history?limit=10')).data,
    staleTime: 10_000,
    retry: false,
  })
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AgentsView() {
  const qc = useQueryClient()
  const { data: providers, isLoading: providersLoading } = useProviders()
  const { data: queueHealth, isLoading: queueLoading } = useQueueHealth()
  const { data: savedMode } = useRoutingMode()
  const { data: agents } = useAgents()
  const { data: pipelineHistory } = usePipelineHistory()
  const saveModeMut = useSaveRoutingMode()

  const [activeMode, setActiveMode] = useState<string>(savedMode ?? 'balanced')
  const [showRouting, setShowRouting] = useState(true)
  const [showHistory, setShowHistory] = useState(false)

  if (savedMode && savedMode !== activeMode && !saveModeMut.isPending) {
    setActiveMode(savedMode)
  }

  // ── Pipeline execution state ─────────────────────────────────────────────
  const [pipelineInput, setPipelineInput] = useState('')
  const [promptDialogChain, setPromptDialogChain] = useState<ChainTemplate | null>(null)
  const [runningPipeline, setRunningPipeline] = useState<PipelineRunState | null>(null)
  const esRef = useRef<EventSource | null>(null)

  // ── Agent edit state ─────────────────────────────────────────────────────
  const [agentDialog, setAgentDialog] = useState<{ mode: 'create' | 'edit'; agent?: Agent } | null>(null)
  const [agentForm, setAgentForm] = useState({ name: '', model: 'guppy', system_prompt: '', color: 'bg-primary/10 text-primary' })

  const createAgentMut = useMutation({
    mutationFn: (data: typeof agentForm) => api.post('/api/agents', data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents'] }); setAgentDialog(null); toast.success('Agent created') },
    onError: () => toast.error('Failed to create agent'),
  })
  const updateAgentMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<typeof agentForm> }) => api.put(`/api/agents/${id}`, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents'] }); setAgentDialog(null); toast.success('Agent updated') },
    onError: () => toast.error('Failed to update agent'),
  })
  const deleteAgentMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/agents/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents'] }); toast.success('Agent deleted') },
    onError: () => toast.error('Cannot delete built-in agents'),
  })

  const openCreateAgent = () => {
    setAgentForm({ name: '', model: 'guppy', system_prompt: '', color: 'bg-primary/10 text-primary' })
    setAgentDialog({ mode: 'create' })
  }
  const openEditAgent = (agent: Agent) => {
    setAgentForm({ name: agent.name, model: agent.model, system_prompt: agent.system_prompt, color: agent.color })
    setAgentDialog({ mode: 'edit', agent })
  }
  const submitAgentForm = () => {
    if (!agentForm.name.trim()) return
    if (agentDialog?.mode === 'create') {
      createAgentMut.mutate(agentForm)
    } else if (agentDialog?.agent) {
      updateAgentMut.mutate({ id: agentDialog.agent.id, data: agentForm })
    }
  }

  // ── Pipeline event handler ───────────────────────────────────────────────
  const handlePipelineEvent = useCallback((data: any) => {
    setRunningPipeline(prev => {
      if (!prev) return null
      const steps = [...prev.steps]

      if (data.type === 'step_start') {
        steps[data.step] = { ...steps[data.step], role: data.role, model: data.model, status: 'running' }
        return { ...prev, steps, currentStep: data.step }
      }
      if (data.type === 'token') {
        steps[data.step] = { ...steps[data.step], output: steps[data.step].output + data.token }
        return { ...prev, steps }
      }
      if (data.type === 'step_done') {
        steps[data.step] = { ...steps[data.step], status: 'done' }
        return { ...prev, steps }
      }
      if (data.type === 'parallel_start') {
        steps[data.step] = {
          ...steps[data.step],
          isParallel: true,
          status: 'running',
          role: 'parallel',
          parallelAgents: data.agents.map((a: any) => ({ ...a, status: 'running', output: '' })),
        }
        return { ...prev, steps, currentStep: data.step }
      }
      if (data.type === 'parallel_token') {
        const pa = [...(steps[data.step].parallelAgents ?? [])]
        if (pa[data.agent]) pa[data.agent] = { ...pa[data.agent], output: pa[data.agent].output + data.token }
        steps[data.step] = { ...steps[data.step], parallelAgents: pa }
        return { ...prev, steps }
      }
      if (data.type === 'parallel_agent_done') {
        const pa = [...(steps[data.step].parallelAgents ?? [])]
        if (pa[data.agent]) pa[data.agent] = { ...pa[data.agent], status: 'done' }
        steps[data.step] = { ...steps[data.step], parallelAgents: pa }
        return { ...prev, steps }
      }
      if (data.type === 'tool_call') {
        // Append a brief tool-call note to the step output
        const note = `\n\n[Tool: ${data.tool}]\n${data.result_preview ?? ''}\n`
        steps[data.step] = { ...steps[data.step], output: steps[data.step].output + note }
        return { ...prev, steps }
      }
      if (data.type === 'done' || data.type === 'eof') {
        esRef.current?.close()
        const finalSteps = steps.map(s => ({ ...s, status: s.status === 'running' ? 'done' as const : s.status }))
        return { ...prev, status: 'done', steps: finalSteps }
      }
      if (data.type === 'error') {
        esRef.current?.close()
        return { ...prev, status: 'error', error: data.message }
      }
      return prev
    })
  }, [])

  useEffect(() => () => esRef.current?.close(), [])

  // ── Dialog keyboard handling (Escape to close) ───────────────────────────
  // IMPORTANT: we attach to `window`, never to a DOM ref, so there is
  // no "null.addEventListener" race if the dialog hasn't painted yet.
  // The dependency array includes both dialog states so the listener is
  // registered/removed whenever either dialog opens or closes.
  useEffect(() => {
    const isOpen = !!(agentDialog || promptDialogChain)
    if (!isOpen) return   // no dialog → nothing to do

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (agentDialog)      setAgentDialog(null)
      if (promptDialogChain) setPromptDialogChain(null)
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [agentDialog, promptDialogChain])

  const startPipelineMut = useMutation({
    mutationFn: (payload: { template: string; input: string }) => api.post('/api/pipeline', payload),
    onSuccess: (res) => {
      const { pipeline_id, template, label } = res.data
      const isParallel = template === 'parallel_perspectives'
      setRunningPipeline({
        id: pipeline_id, template, label,
        steps: [
          { role: '', model: '', status: 'pending', output: '', isParallel, parallelAgents: isParallel ? [] : undefined },
          { role: '', model: '', status: 'pending', output: '' },
        ],
        currentStep: 0,
        status: 'running',
      })
      setPromptDialogChain(null)
      setPipelineInput('')
      qc.invalidateQueries({ queryKey: ['pipelineHistory'] })

      const es = new EventSource(`${_API_BASE}/api/pipeline/${pipeline_id}/stream`)
      esRef.current = es
      es.onmessage = (e) => { try { handlePipelineEvent(JSON.parse(e.data)) } catch { /* */ } }
      es.onerror = () => es.close()
    },
    onError: () => toast.error('Failed to start pipeline — is LM Studio running?'),
  })

  const handleModeChange = async (modeId: string) => {
    setActiveMode(modeId)
    try {
      await saveModeMut.mutateAsync(modeId)
      toast.success(`Routing mode: ${BUDGET_MODES.find(m => m.id === modeId)?.label}`)
    } catch { toast.error('Failed to save routing mode') }
  }

  const localBackends = (providers as any)?.local?.backends ?? {}
  const localModels = (providers as any)?.local?.models ?? []
  const routes = TASK_ROUTES_BY_MODE[activeMode] ?? TASK_ROUTES_BY_MODE.balanced
  const cloudProviders = ['anthropic', 'openai', 'google', 'cohere', 'mistral'] as const

  return (
    <div className="px-12 py-8 max-w-7xl mx-auto space-y-10">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-widest font-bold text-secondary mb-2 block">Agent Control Center</span>
          <h1 className="text-3xl font-headline font-bold text-on-surface">Agents & Routing</h1>
        </div>
        <button
          onClick={() => qc.invalidateQueries({ queryKey: ['providers', 'queueHealth', 'agents'] })}
          className="flex items-center gap-2 px-4 py-2 bg-surface-container-lowest rounded-lg ghost-border text-on-surface hover:shadow-soft transition-all"
        >
          <RefreshCw className={cn('w-4 h-4', providersLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Budget Mode Selector */}
      <section>
        <h2 className="text-xs uppercase tracking-widest font-bold text-on-surface-variant mb-4">Budget Mode</h2>
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {BUDGET_MODES.map((mode) => (
            <button
              key={mode.id}
              onClick={() => handleModeChange(mode.id)}
              className={cn(
                'p-5 rounded-xl text-left ghost-border transition-all duration-200',
                activeMode === mode.id
                  ? 'bg-primary/10 ring-2 ring-primary shadow-soft'
                  : 'bg-surface-container-lowest hover:bg-surface-container hover:shadow-soft'
              )}
            >
              <div className={cn('mb-3', mode.color)}>{mode.icon}</div>
              <p className="font-headline font-bold text-on-surface mb-1">{mode.label}</p>
              <p className="text-xs text-on-surface-variant leading-relaxed">{mode.description}</p>
              {activeMode === mode.id && (
                <div className="mt-3 flex items-center gap-1.5 text-xs font-bold text-primary">
                  <CheckCircle className="w-3.5 h-3.5" />Active
                </div>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* Routing Rules */}
      <section className="bg-surface-container-lowest rounded-xl ghost-border">
        <button
          onClick={() => setShowRouting(!showRouting)}
          className="w-full flex items-center justify-between p-5 text-left"
        >
          <div className="flex items-center gap-3">
            <ArrowRight className="w-5 h-5 text-primary" />
            <h2 className="font-headline font-bold text-on-surface">Routing Rules</h2>
            <span className="text-xs text-on-surface-variant capitalize">— {activeMode.replace('_', ' ')}</span>
          </div>
          {showRouting ? <ChevronUp className="w-4 h-4 text-on-surface-variant" /> : <ChevronDown className="w-4 h-4 text-on-surface-variant" />}
        </button>
        {showRouting && (
          <div className="px-5 pb-5">
            <div className="rounded-lg overflow-hidden border border-outline-variant/30">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-container">
                    <th className="text-left px-4 py-2.5 text-xs uppercase tracking-widest text-on-surface-variant font-bold">Task</th>
                    <th className="text-left px-4 py-2.5 text-xs uppercase tracking-widest text-on-surface-variant font-bold">Route</th>
                    <th className="px-4 py-2.5 text-xs uppercase tracking-widest text-on-surface-variant font-bold text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {routes.map((row, i) => (
                    <tr key={i} className={cn('border-t border-outline-variant/20', i % 2 !== 0 && 'bg-surface-container/30')}>
                      <td className="px-4 py-3 text-on-surface font-medium">{row.task}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {row.local ? <Cpu className="w-3.5 h-3.5 text-success" /> : <Cloud className="w-3.5 h-3.5 text-secondary" />}
                          <span className="font-mono text-xs text-on-surface-variant">{row.route}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full', row.local ? 'bg-success/10 text-success' : 'bg-secondary/10 text-secondary')}>
                          {row.local ? 'Free' : 'Tokens'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Status columns */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-5 space-y-6">

          {/* Local Backends */}
          <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
            <div className="flex items-center gap-3 mb-5">
              <Cpu className="w-5 h-5 text-primary" />
              <h2 className="font-headline font-bold text-on-surface">Local Backends</h2>
            </div>
            {providersLoading ? (
              <div className="flex items-center gap-2 text-on-surface-variant text-sm"><RefreshCw className="w-4 h-4 animate-spin" />Probing…</div>
            ) : Object.keys(localBackends).length === 0 ? (
              <p className="text-sm text-on-surface-variant">No backends detected.</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(localBackends).map(([name, b]: [string, any]) => (
                  <div key={name} className="flex items-center justify-between p-3 bg-surface-container rounded-lg">
                    <div className="flex items-center gap-2.5">
                      {b.alive ? <span className="w-2 h-2 rounded-full bg-success animate-pulse" /> : <span className="w-2 h-2 rounded-full bg-error/40" />}
                      <span className="font-medium text-on-surface capitalize">{name}</span>
                    </div>
                    <span className={cn('text-xs font-bold', b.alive ? 'text-success' : 'text-on-surface-variant')}>
                      {b.alive ? 'Online' : 'Offline'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Queue Health */}
          <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
            <div className="flex items-center gap-3 mb-5">
              <Activity className="w-5 h-5 text-primary" />
              <h2 className="font-headline font-bold text-on-surface">Queue Health</h2>
            </div>
            {queueLoading ? (
              <div className="flex items-center gap-2 text-on-surface-variant text-sm"><RefreshCw className="w-4 h-4 animate-spin" />Loading…</div>
            ) : queueHealth ? (
              <div className="space-y-3">
                {[
                  ['Status', <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full capitalize', (queueHealth as any).status === 'healthy' ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning')}>{(queueHealth as any).status}</span>],
                  ['Executing', <span className="font-bold text-on-surface">{(queueHealth as any).metrics.executing_count}</span>],
                  ['Completed', <span className="font-bold text-on-surface">{(queueHealth as any).metrics.success_count}</span>],
                  ['Failed', <span className="font-bold text-on-surface">{(queueHealth as any).metrics.failed_count}</span>],
                  ['Avg Latency', <span className="font-bold text-on-surface">{(queueHealth as any).metrics.avg_latency_ms > 0 ? `${(queueHealth as any).metrics.avg_latency_ms.toFixed(0)}ms` : '—'}</span>],
                ].map(([label, val], i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-sm text-on-surface-variant">{label}</span>
                    {val}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-on-surface-variant">Queue service unavailable.</p>
            )}
          </section>
        </div>

        <div className="col-span-7 space-y-6">

          {/* Local Agents */}
          <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
            <div className="flex items-center gap-3 mb-5">
              <Users className="w-5 h-5 text-primary" />
              <h2 className="font-headline font-bold text-on-surface">Local Agents</h2>
              <span className="text-xs text-on-surface-variant ml-auto">
                Active: <span className="font-bold text-secondary">{(providers as any)?.local?.backend ?? '—'}</span>
              </span>
            </div>
            {localModels.length === 0 ? (
              <div className="text-center py-8 text-on-surface-variant">
                <Cpu className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No local models loaded. Start LM Studio or Ollama.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {localModels.map((model: any) => {
                  const role = MODEL_ROLES[model.id] ?? { label: 'General', color: 'bg-surface-container text-on-surface-variant' }
                  const isActive = (providers as any)?.local?.active_model === model.id
                  const isOffline = model.alive === false
                  return (
                    <div key={model.id} className={cn(
                      'flex items-center justify-between p-3 rounded-lg border transition-all',
                      isActive ? 'border-primary/30 bg-primary/5'
                      : isOffline ? 'border-outline-variant/10 bg-surface-container/20 opacity-60'
                      : 'border-outline-variant/20 bg-surface-container/50'
                    )}>
                      <div className="flex items-center gap-3">
                        {isActive
                          ? <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                          : isOffline
                            ? <span className="w-2 h-2 rounded-full bg-slate-600" />
                            : <span className="w-2 h-2 rounded-full bg-success/60" />}
                        <div>
                          <p className={cn('font-medium', isOffline ? 'text-on-surface-variant' : 'text-on-surface')}>
                            {model.name || model.id}
                          </p>
                          <p className="text-xs font-mono text-on-surface-variant truncate max-w-xs">{model.id}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full', role.color)}>{role.label}</span>
                        {isActive && <span className="text-xs font-bold text-primary">Active</span>}
                        {isOffline && <span className="text-xs text-slate-500">offline</span>}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {/* Cloud Providers */}
          <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
            <div className="flex items-center gap-3 mb-5">
              <Cloud className="w-5 h-5 text-secondary" />
              <h2 className="font-headline font-bold text-on-surface">Cloud Providers</h2>
            </div>
            <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
              {cloudProviders.map((p) => {
                const info = (providers as any)?.[p]
                return (
                  <div key={p} className="p-3 rounded-lg bg-surface-container/50 border border-outline-variant/20">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-on-surface capitalize">{p}</span>
                      {info?.configured ? <CheckCircle className="w-4 h-4 text-success" /> : <XCircle className="w-4 h-4 text-on-surface-variant/40" />}
                    </div>
                    <p className="text-xs text-on-surface-variant">
                      {info?.configured ? `${info.models?.length ?? 0} model${info.models?.length === 1 ? '' : 's'}` : 'No API key'}
                    </p>
                    {info?.active_model && <p className="text-xs font-mono text-primary mt-1 truncate">{info.active_model}</p>}
                  </div>
                )
              })}
            </div>
            <p className="text-xs text-on-surface-variant mt-3">
              Add keys in{' '}
              <button onClick={() => window.dispatchEvent(new CustomEvent('guppy:navigate', { detail: { view: 'settings' } }))} className="text-primary underline">
                Settings → Providers
              </button>
            </p>
          </section>
        </div>
      </div>

      {/* My Agents */}
      <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
        <div className="flex items-center gap-3 mb-5">
          <Bot className="w-5 h-5 text-secondary" />
          <h2 className="font-headline font-bold text-on-surface">My Agents</h2>
          <span className="text-xs text-on-surface-variant ml-auto">{agents?.length ?? 0} agent{agents?.length !== 1 ? 's' : ''}</span>
          <button
            onClick={openCreateAgent}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg text-xs font-bold transition-all"
          >
            <Plus className="w-3.5 h-3.5" />New Agent
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {(agents ?? []).map((agent) => (
            <div key={agent.id} className="p-4 rounded-xl bg-surface-container border border-outline-variant/20 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full', agent.color)}>{agent.name}</span>
                  <span className="text-xs font-mono text-on-surface-variant">{agent.model}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => openEditAgent(agent)} className="p-1.5 rounded hover:bg-surface-container-high text-on-surface-variant transition-all">
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  {!agent.builtin && (
                    <button onClick={() => deleteAgentMut.mutate(agent.id)} className="p-1.5 rounded hover:bg-error/10 text-on-surface-variant hover:text-error transition-all">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed line-clamp-3">
                {agent.system_prompt || <span className="italic">No system prompt</span>}
              </p>
              {agent.builtin && <span className="text-xs text-on-surface-variant/50 italic">Built-in</span>}
            </div>
          ))}
        </div>
      </section>

      {/* Multi-Agent Chains */}
      <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
        <div className="flex items-center gap-3 mb-4">
          <Zap className="w-5 h-5 text-secondary" />
          <h2 className="font-headline font-bold text-on-surface">Multi-Agent Chains</h2>
          <span className="ml-2 text-xs bg-success/10 text-success px-2 py-0.5 rounded-full font-bold">Live</span>
        </div>
        <p className="text-sm text-on-surface-variant mb-5">
          Chain local agents for complex workflows. Output from each step is context for the next — fully local, no cloud required.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {CHAIN_TEMPLATES.map((chain) => (
            <div key={chain.templateId} className="flex flex-col gap-3 p-4 bg-surface-container rounded-xl border border-outline-variant/20">
              <div className="flex items-center gap-2">
                {chain.isParallel ? (
                  <div className="flex items-center gap-1">
                    <span className={cn('text-xs font-bold px-2 py-0.5 rounded', MODEL_ROLES['guppy-fast']?.color)}>guppy-fast</span>
                    <GitBranch className="w-3.5 h-3.5 text-on-surface-variant rotate-180" />
                    <span className={cn('text-xs font-bold px-2 py-0.5 rounded', MODEL_ROLES['guppy']?.color)}>guppy</span>
                  </div>
                ) : (
                  <>
                    <span className={cn('text-xs font-bold px-2 py-0.5 rounded', MODEL_ROLES[chain.from!]?.color ?? 'bg-surface-container text-on-surface-variant')}>{chain.from}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-on-surface-variant shrink-0" />
                    <span className={cn('text-xs font-bold px-2 py-0.5 rounded', MODEL_ROLES[chain.to!]?.color ?? 'bg-surface-container text-on-surface-variant')}>{chain.to}</span>
                  </>
                )}
              </div>
              <div>
                <p className="font-medium text-on-surface text-sm">{chain.label}</p>
                <p className="text-xs text-on-surface-variant mt-0.5">{chain.description}</p>
              </div>
              <button
                onClick={() => { setPromptDialogChain(chain); setPipelineInput('') }}
                disabled={startPipelineMut.isPending}
                className="mt-auto flex items-center justify-center gap-2 px-3 py-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg text-xs font-bold transition-all disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />Run Chain
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Live pipeline result panel */}
      {runningPipeline && (
        <section className="bg-surface-container-lowest rounded-xl p-6 ghost-border">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              {runningPipeline.status === 'running' ? <Loader2 className="w-5 h-5 text-primary animate-spin" /> : runningPipeline.status === 'done' ? <CheckCircle className="w-5 h-5 text-success" /> : <XCircle className="w-5 h-5 text-error" />}
              <h2 className="font-headline font-bold text-on-surface">{runningPipeline.label}</h2>
              <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full capitalize', runningPipeline.status === 'running' ? 'bg-primary/10 text-primary' : runningPipeline.status === 'done' ? 'bg-success/10 text-success' : 'bg-error/10 text-error')}>
                {runningPipeline.status}
              </span>
            </div>
            <button onClick={() => { esRef.current?.close(); setRunningPipeline(null) }} className="p-2 rounded-lg hover:bg-surface-container text-on-surface-variant transition-all">
              <X className="w-4 h-4" />
            </button>
          </div>

          {runningPipeline.status === 'error' && (
            <div className="mb-4 p-3 bg-error/10 text-error rounded-lg text-sm">{runningPipeline.error}</div>
          )}

          <div className={cn('grid gap-5', runningPipeline.steps.length === 2 ? 'grid-cols-2' : 'grid-cols-1')}>
            {runningPipeline.steps.map((step, i) => (
              <div key={i} className="space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  {step.status === 'pending' && <span className="w-2 h-2 rounded-full bg-on-surface-variant/30" />}
                  {step.status === 'running' && <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />}
                  {step.status === 'done' && <CheckCircle className="w-3.5 h-3.5 text-success" />}
                  <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
                    Step {i + 1}{step.role ? ` — ${step.role}` : ''}
                  </span>
                  {step.model && (
                    <span className={cn('text-xs px-1.5 py-0.5 rounded font-bold', MODEL_ROLES[step.model]?.color ?? 'bg-surface-container text-on-surface-variant')}>
                      {step.model}
                    </span>
                  )}
                </div>

                {/* Parallel agents layout */}
                {step.isParallel && step.parallelAgents && step.parallelAgents.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    {step.parallelAgents.map((pa, ai) => (
                      <div key={ai} className="bg-surface-container rounded-lg p-3 max-h-40 overflow-y-auto">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          {pa.status === 'running' && <Loader2 className="w-3 h-3 text-primary animate-spin" />}
                          {pa.status === 'done' && <CheckCircle className="w-3 h-3 text-success" />}
                          <span className="text-xs font-bold text-on-surface-variant">{pa.role}</span>
                          <span className={cn('text-xs px-1.5 rounded font-bold ml-auto', MODEL_ROLES[pa.model]?.color ?? 'bg-surface-container text-on-surface-variant')}>{pa.model}</span>
                        </div>
                        <pre className="text-xs text-on-surface whitespace-pre-wrap font-sans">
                          {pa.output || ' '}
                          {pa.status === 'running' && <span className="inline-block w-1.5 h-3.5 bg-primary ml-0.5 animate-pulse align-text-bottom" />}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : null}

                {/* Sequential or synthesis output */}
                {(!step.isParallel || step.status === 'done') && (
                  <div className="relative bg-surface-container rounded-lg p-4 min-h-[100px] max-h-72 overflow-y-auto">
                    {step.status === 'pending' && <p className="text-sm text-on-surface-variant/50 italic">Waiting…</p>}
                    {(step.status === 'running' || step.status === 'done') && step.output && (
                      <>
                        <pre className="text-sm text-on-surface whitespace-pre-wrap font-sans leading-relaxed">
                          {step.output}
                          {step.status === 'running' && <span className="inline-block w-2 h-4 bg-primary ml-0.5 animate-pulse align-text-bottom" />}
                        </pre>
                        {step.status === 'done' && (
                          <button onClick={() => { navigator.clipboard.writeText(step.output); toast.success('Copied') }} className="absolute top-2 right-2 p-1.5 rounded bg-surface-container-high/80 hover:bg-surface-container-highest text-on-surface-variant transition-all">
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Pipeline history */}
      <section className="bg-surface-container-lowest rounded-xl ghost-border">
        <button onClick={() => setShowHistory(!showHistory)} className="w-full flex items-center justify-between p-5 text-left">
          <div className="flex items-center gap-3">
            <History className="w-5 h-5 text-primary" />
            <h2 className="font-headline font-bold text-on-surface">Pipeline History</h2>
            {pipelineHistory && <span className="text-xs text-on-surface-variant">{(pipelineHistory as any[]).length} runs</span>}
          </div>
          {showHistory ? <ChevronUp className="w-4 h-4 text-on-surface-variant" /> : <ChevronDown className="w-4 h-4 text-on-surface-variant" />}
        </button>
        {showHistory && (
          <div className="px-5 pb-5 space-y-3">
            {!(pipelineHistory as any[])?.length ? (
              <p className="text-sm text-on-surface-variant">No pipeline runs yet.</p>
            ) : (
              (pipelineHistory as any[]).map((run: any) => (
                <div key={run.id} className="p-4 bg-surface-container rounded-xl border border-outline-variant/20">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={cn('w-2 h-2 rounded-full', run.status === 'done' ? 'bg-success' : run.status === 'error' ? 'bg-error' : 'bg-primary animate-pulse')} />
                      <span className="font-medium text-on-surface text-sm">{run.label}</span>
                    </div>
                    <span className="text-xs text-on-surface-variant">
                      {run.finished_at ? `${((run.finished_at - run.started_at)).toFixed(1)}s` : 'running'}
                    </span>
                  </div>
                  <p className="text-xs text-on-surface-variant truncate">{run.input}</p>
                  {run.error && <p className="text-xs text-error mt-1">{run.error}</p>}
                </div>
              ))
            )}
          </div>
        )}
      </section>

      {/* Pipeline input prompt dialog */}
      {promptDialogChain && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) setPromptDialogChain(null) }}>
          <div className="w-full max-w-lg mx-4 bg-surface-container-lowest rounded-2xl shadow-xl p-6 ghost-border space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-widest font-bold text-secondary">Run Chain</p>
                <h3 className="font-headline font-bold text-on-surface text-xl">{promptDialogChain.label}</h3>
              </div>
              <button onClick={() => setPromptDialogChain(null)} className="p-2 rounded-lg hover:bg-surface-container text-on-surface-variant transition-all"><X className="w-4 h-4" /></button>
            </div>
            <div className="flex items-center gap-2 text-xs text-on-surface-variant bg-surface-container rounded-lg px-3 py-2">
              {promptDialogChain.isParallel ? (
                <span>guppy-fast + guppy running in parallel, then synthesized</span>
              ) : (
                <>
                  <span className={cn('font-bold px-1.5 py-0.5 rounded', MODEL_ROLES[promptDialogChain.from!]?.color)}>{promptDialogChain.from}</span>
                  <ArrowRight className="w-3 h-3" />
                  <span className={cn('font-bold px-1.5 py-0.5 rounded', MODEL_ROLES[promptDialogChain.to!]?.color)}>{promptDialogChain.to}</span>
                  <span className="ml-1">{promptDialogChain.description}</span>
                </>
              )}
            </div>
            <textarea
              autoFocus
              value={pipelineInput}
              onChange={e => setPipelineInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) startPipelineMut.mutate({ template: promptDialogChain.templateId, input: pipelineInput.trim() }) }}
              placeholder="What should the chain work on?"
              className="w-full h-28 resize-none rounded-xl bg-surface-container p-3 text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:ring-2 ring-primary/40"
            />
            <div className="flex justify-end gap-3">
              <button onClick={() => setPromptDialogChain(null)} className="px-4 py-2 rounded-lg text-sm text-on-surface-variant hover:bg-surface-container transition-all">Cancel</button>
              <button
                onClick={() => startPipelineMut.mutate({ template: promptDialogChain.templateId, input: pipelineInput.trim() })}
                disabled={!pipelineInput.trim() || startPipelineMut.isPending}
                className="flex items-center gap-2 px-5 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold hover:opacity-90 transition-all disabled:opacity-50"
              >
                {startPipelineMut.isPending ? <><Loader2 className="w-4 h-4 animate-spin" />Starting…</> : <><Play className="w-4 h-4" />Launch</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Agent create/edit dialog */}
      {agentDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) setAgentDialog(null) }}>
          <div className="w-full max-w-lg mx-4 bg-surface-container-lowest rounded-2xl shadow-xl p-6 ghost-border space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-headline font-bold text-on-surface text-xl">{agentDialog.mode === 'create' ? 'New Agent' : 'Edit Agent'}</h3>
              <button onClick={() => setAgentDialog(null)} className="p-2 rounded-lg hover:bg-surface-container text-on-surface-variant transition-all"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-1 block">Name</label>
                <input autoFocus value={agentForm.name} onChange={e => setAgentForm(f => ({ ...f, name: e.target.value }))} placeholder="My Specialist Agent" className="w-full bg-surface-container rounded-lg p-2.5 text-sm text-on-surface outline-none focus:ring-2 ring-primary/40" />
              </div>
              <div>
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-1 block">Model</label>
                <select value={agentForm.model} onChange={e => setAgentForm(f => ({ ...f, model: e.target.value }))} className="w-full bg-surface-container rounded-lg p-2.5 text-sm text-on-surface outline-none focus:ring-2 ring-primary/40">
                  {/* llamacpp (local GPU) — always shown, status-aware */}
                  {localModels.filter((m: any) => (m.backend as string | undefined)?.startsWith('llamacpp')).length > 0 && (
                    <optgroup label="llamacpp · local GPU">
                      {localModels
                        .filter((m: any) => (m.backend as string | undefined)?.startsWith('llamacpp'))
                        .map((m: any) => (
                          <option key={m.id} value={m.id}>
                            {m.name || m.id}{m.alive === false ? ' (offline)' : ''}
                          </option>
                        ))}
                    </optgroup>
                  )}
                  {/* Ollama models */}
                  {localModels.filter((m: any) => !(m.backend as string | undefined)?.startsWith('llamacpp')).length > 0 && (
                    <optgroup label="Ollama">
                      {localModels
                        .filter((m: any) => !(m.backend as string | undefined)?.startsWith('llamacpp'))
                        .map((m: any) => (
                          <option key={m.id} value={m.id}>{m.name || m.id}</option>
                        ))}
                    </optgroup>
                  )}
                  {/* Fallback hardcoded list when providers haven't loaded yet */}
                  {localModels.length === 0 && (
                    <>
                      <option value="assistant-pepe-8b">Assistant Pepe 8B</option>
                      <option value="guppy-fast">Guppy Fast</option>
                      <option value="guppy-code">Guppy Code</option>
                      <option value="guppy">Guppy</option>
                      <option value="guppy-teach">Guppy Teach</option>
                    </>
                  )}
                </select>
              </div>
              <div>
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-1 block">System Prompt</label>
                <textarea value={agentForm.system_prompt} onChange={e => setAgentForm(f => ({ ...f, system_prompt: e.target.value }))} placeholder="You are a specialized agent that…" rows={5} className="w-full resize-none bg-surface-container rounded-lg p-2.5 text-sm text-on-surface outline-none focus:ring-2 ring-primary/40" />
              </div>
              <div>
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-1 block">Badge Color</label>
                <div className="flex flex-wrap gap-2">
                  {['bg-primary/10 text-primary','bg-success/10 text-success','bg-info/10 text-info','bg-secondary/10 text-secondary','bg-warning/10 text-warning','bg-error/10 text-error'].map(c => (
                    <button key={c} onClick={() => setAgentForm(f => ({ ...f, color: c }))} className={cn('px-3 py-1 rounded-full text-xs font-bold ring-2 transition-all', c, agentForm.color === c ? 'ring-on-surface' : 'ring-transparent')}>
                      Sample
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setAgentDialog(null)} className="px-4 py-2 rounded-lg text-sm text-on-surface-variant hover:bg-surface-container transition-all">Cancel</button>
              <button
                onClick={submitAgentForm}
                disabled={!agentForm.name.trim() || createAgentMut.isPending || updateAgentMut.isPending}
                className="flex items-center gap-2 px-5 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold hover:opacity-90 transition-all disabled:opacity-50"
              >
                {createAgentMut.isPending || updateAgentMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {agentDialog.mode === 'create' ? 'Create' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
