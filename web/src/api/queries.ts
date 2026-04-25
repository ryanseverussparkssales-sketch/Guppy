/**
 * TanStack Query hooks for all server data.
 *
 * Convention:
 *   useXxx()        — read (useQuery)
 *   useXxxMutation()— write (useMutation)
 *
 * All responses are validated through Zod schemas before returning,
 * so callers get typed data with no casting needed.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query'
import api from './client'
import {
  SettingsSchema,        type Settings,
  ProvidersSchema,       type Providers,
  ToolSchema,            type Tool,
  MCPServerSchema,       type MCPServer,
  MetricsSchema,         type Metrics,
  StatusSchema,          type Status,
  LogsSchema,            type Logs,
  TelemetryReportSchema, type TelemetryReport,
  PullStatusSchema,      type PullStatus,
  BookletSectionSchema,  type BookletSection,
  BookletCompiledSchema,
} from './schemas'

// ── Query keys ───────────────────────────────────────────────────────────────

export const QK = {
  settings:   ['settings']   as const,
  providers:  ['providers']  as const,
  tools:      ['tools']      as const,
  mcpServers: ['mcpServers'] as const,
  metrics:    ['metrics']    as const,
  status:     ['status']     as const,
  logs:       ['logs']       as const,
  telemetry:  ['telemetry']  as const,
  booklet:    ['booklet']    as const,
  bookletCompiled: ['bookletCompiled'] as const,
  pullJob:    (id: string) => ['pullJob', id] as const,
  mcpTools:   (id: string) => ['mcpTools', id] as const,
} as const

// ── Settings ─────────────────────────────────────────────────────────────────

export function useSettings(opts?: Partial<UseQueryOptions<Settings>>) {
  return useQuery<Settings>({
    queryKey: QK.settings,
    queryFn:  async () => SettingsSchema.parse((await api.get('/api/settings')).data),
    staleTime: 30_000,
    ...opts,
  })
}

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { temperature?: number; max_tokens?: number; active_provider?: string }) =>
      api.put('/api/settings', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.settings }),
  })
}

export function useStoreCredential() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, api_key }: { provider: string; api_key: string }) =>
      api.post('/api/settings/credentials', { provider, api_key }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.settings }),
  })
}

export function useDeleteCredential() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: string) => api.delete(`/api/settings/credentials/${provider}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.settings }),
  })
}

export function useSetActiveProvider() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: string) => api.post('/api/settings/provider', { provider }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.settings }),
  })
}

// ── Providers / Models ───────────────────────────────────────────────────────

export function useProviders(opts?: Partial<UseQueryOptions<Providers>>) {
  return useQuery<Providers>({
    queryKey: QK.providers,
    queryFn:  async () => ProvidersSchema.parse((await api.get('/providers')).data),
    staleTime: 15_000,
    ...opts,
  })
}

export function useSetActiveModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, model_id }: { provider: string; model_id: string }) =>
      api.post(`/providers/${provider}/active-model`, { model_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.providers }),
  })
}

export function usePullModel() {
  return useMutation({
    mutationFn: (name: string) => api.post('/api/models/pull', { name }),
  })
}

export function usePullStatus(jobId: string | null) {
  return useQuery<PullStatus>({
    queryKey: QK.pullJob(jobId ?? ''),
    queryFn:  async () =>
      PullStatusSchema.parse((await api.get(`/api/models/pull/${jobId}`)).data),
    enabled:          !!jobId,
    refetchInterval:  (q) => (q.state.data?.done ? false : 1000),
    staleTime:        0,
  })
}

export function useDeleteModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (modelId: string) => api.delete(`/api/models/${modelId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.providers }),
  })
}

// ── Tools ────────────────────────────────────────────────────────────────────

export function useTools(opts?: Partial<UseQueryOptions<Tool[]>>) {
  return useQuery<Tool[]>({
    queryKey: QK.tools,
    queryFn:  async () => {
      const data = (await api.get('/api/tools')).data
      return (Array.isArray(data) ? data : []).map((t: unknown) => ToolSchema.parse(t))
    },
    staleTime: 60_000,
    ...opts,
  })
}

export function useSetToolEnabled() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ toolId, enabled }: { toolId: string; enabled: boolean }) =>
      api.post(`/api/tools/${toolId}/${enabled ? 'enable' : 'disable'}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.tools }),
  })
}

// ── MCP Servers ──────────────────────────────────────────────────────────────

export function useMCPServers(opts?: Partial<UseQueryOptions<MCPServer[]>>) {
  return useQuery<MCPServer[]>({
    queryKey: QK.mcpServers,
    queryFn:  async () => {
      const data = (await api.get('/api/mcp/servers')).data
      return (Array.isArray(data) ? data : []).map((s: unknown) => MCPServerSchema.parse(s))
    },
    staleTime: 30_000,
    ...opts,
  })
}

export function useSetMCPEnabled() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ serverId, enabled }: { serverId: string; enabled: boolean }) =>
      api.post(`/api/mcp/servers/${serverId}/${enabled ? 'enable' : 'disable'}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.mcpServers }),
  })
}

export function useAddMCPServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      id: string; name: string; description: string
      command: string; args: string[]; envVars: Record<string, string>
    }) => api.post('/api/mcp/servers', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.mcpServers }),
  })
}

export function useDeleteMCPServer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (serverId: string) => api.delete(`/api/mcp/servers/${serverId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.mcpServers }),
  })
}

export function useTestMCPServer() {
  return useMutation({
    mutationFn: (serverId: string) => api.post(`/api/mcp/servers/${serverId}/test`),
  })
}

export function useMCPServerTools(serverId: string) {
  return useQuery({
    queryKey: QK.mcpTools(serverId),
    queryFn:  async () => (await api.get(`/api/mcp/servers/${serverId}/tools`)).data.tools ?? [],
    staleTime: 60_000,
    enabled: !!serverId,
  })
}

// ── Admin / Ops ──────────────────────────────────────────────────────────────

export function useMetrics() {
  return useQuery<Metrics>({
    queryKey: QK.metrics,
    queryFn:  async () => MetricsSchema.parse((await api.get('/metrics')).data),
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}

export function useStatus() {
  return useQuery<Status>({
    queryKey: QK.status,
    queryFn:  async () => StatusSchema.parse((await api.get('/status')).data),
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}

export function useLogs() {
  return useQuery<Logs>({
    queryKey: QK.logs,
    queryFn:  async () => LogsSchema.parse((await api.get('/logs/recent?limit=50')).data),
    staleTime: 0,
    enabled: false, // only fetch on demand via refetch()
  })
}

export function useTelemetry() {
  return useQuery<TelemetryReport>({
    queryKey: QK.telemetry,
    queryFn:  async () =>
      TelemetryReportSchema.parse((await api.get('/telemetry/report?since_minutes=60')).data),
    staleTime: 0,
    enabled: false,
  })
}

export function useRepairToken() {
  return useQuery<string | null>({
    queryKey: ['repairToken'],
    queryFn:  async () => {
      const r = await api.get('/repair-token/refresh')
      return r.data.repair_token ?? null
    },
    staleTime: Infinity,
    enabled: false,
    retry: false,
  })
}

// ── Instructions Booklet ─────────────────────────────────────────────────────

export function useBooklet(opts?: Partial<UseQueryOptions<BookletSection[]>>) {
  return useQuery<BookletSection[]>({
    queryKey: QK.booklet,
    queryFn: async () => {
      const data = (await api.get('/api/booklet/sections')).data
      return (Array.isArray(data) ? data : []).map((s: unknown) => BookletSectionSchema.parse(s))
    },
    staleTime: 30_000,
    ...opts,
  })
}

export function useBookletCompiled() {
  return useQuery({
    queryKey: QK.bookletCompiled,
    queryFn: async () => BookletCompiledSchema.parse((await api.get('/api/booklet/compiled')).data),
    enabled: false,
    staleTime: 0,
  })
}

export function useUpdateBookletSection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; title?: string; content?: string; mode?: string }) =>
      api.patch(`/api/booklet/sections/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.booklet }),
  })
}

export function useAddBookletSection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { id: string; title: string; content?: string; mode?: string }) =>
      api.post('/api/booklet/sections', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.booklet }),
  })
}

export function useDeleteBookletSection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/booklet/sections/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.booklet }),
  })
}

export function useReorderBookletSections() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) => api.post('/api/booklet/sections/reorder', { ids }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.booklet }),
  })
}

export function useRunRepair() {
  return useMutation({
    mutationFn: ({ action, dryRun, token }: { action: string; dryRun: boolean; token: string }) =>
      api.post('/repair', { action, dry_run: dryRun }, { headers: { 'X-Repair-Token': token } }),
  })
}
