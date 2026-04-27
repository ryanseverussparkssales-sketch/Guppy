/**
 * Zod schemas for all API responses.
 * Import the inferred types (e.g. `Settings`) instead of writing interfaces by hand.
 * Parse with `schema.parse(res.data)` on the way in — runtime validation + TS types for free.
 */
import { z } from 'zod'

// ── Settings ────────────────────────────────────────────────────────────────

export const CredentialStatusSchema = z.object({
  anthropic: z.object({ configured: z.boolean() }),
  openai:    z.object({ configured: z.boolean() }),
  google:    z.object({ configured: z.boolean() }),
  cohere:    z.object({ configured: z.boolean() }).optional(),
  mistral:   z.object({ configured: z.boolean() }).optional(),
})

export const ModelParamsSchema = z.object({
  temperature: z.number().min(0).max(2),
  max_tokens:  z.number().int().positive(),
})

export const SettingsSchema = z.object({
  active_provider: z.enum(['local', 'anthropic', 'openai', 'google', 'cohere', 'mistral']),
  credentials:     CredentialStatusSchema,
  model_params:    ModelParamsSchema,
})

export type Settings         = z.infer<typeof SettingsSchema>
export type CredentialStatus = z.infer<typeof CredentialStatusSchema>
export type ModelParams      = z.infer<typeof ModelParamsSchema>

// ── Providers / Models ───────────────────────────────────────────────────────

export const ModelEntrySchema = z.object({
  id:   z.string(),
  name: z.string(),
  tier: z.string(),
})

export const ProviderInfoSchema = z.object({
  configured:   z.boolean(),
  active_model: z.string(),
  models:       z.array(ModelEntrySchema),
  backend:      z.string().optional(),
  backends:     z.record(z.string(), z.object({ alive: z.boolean(), label: z.string().optional() })).optional(),
})

export const ProvidersSchema = z.object({
  anthropic: ProviderInfoSchema,
  openai:    ProviderInfoSchema,
  google:    ProviderInfoSchema,
  local:     ProviderInfoSchema,
})

export type ProviderInfo = z.infer<typeof ProviderInfoSchema>
export type Providers    = z.infer<typeof ProvidersSchema>
export type ModelEntry   = z.infer<typeof ModelEntrySchema>

// ── Tools ────────────────────────────────────────────────────────────────────

export const ToolSchema = z.object({
  id:          z.string(),
  name:        z.string(),
  description: z.string(),
  category:    z.string(),
  type:        z.string(),
  parameters:  z.record(z.string(), z.unknown()),
  isEnabled:   z.boolean(),
})

export type Tool = z.infer<typeof ToolSchema>

// ── MCP Servers ──────────────────────────────────────────────────────────────

export const MCPServerSchema = z.object({
  id:          z.string(),
  name:        z.string(),
  description: z.string(),
  command:     z.string(),
  args:        z.array(z.string()),
  envVars:     z.record(z.string(), z.string()),
  isEnabled:   z.boolean(),
  isPreset:    z.boolean(),
})

export type MCPServer = z.infer<typeof MCPServerSchema>

// ── Admin / Ops ──────────────────────────────────────────────────────────────

export const MetricsSchema = z.object({
  started_at:         z.string(),
  requests_total:     z.number(),
  errors_total:       z.number(),
  slow_requests:      z.number(),
  average_latency_ms: z.number(),
  path_counts:        z.record(z.string(), z.number()),
  status_counts:      z.record(z.string(), z.number()),
})

export const ReadinessCheckSchema = z.object({
  state:  z.string(),
  detail: z.string(),
}).passthrough()

export const StatusSchema = z.object({
  status:            z.string(),
  memory_available:  z.boolean(),
  voice_available:   z.boolean(),
  daemon_available:  z.boolean(),
  startup_readiness: z.object({
    overall: z.string(),
    checks:  z.record(z.string(), ReadinessCheckSchema),
  }).optional(),
  local_runtime: z.object({
    state:       z.string(),
    backend:     z.string(),
    chat_ready:  z.boolean(),
    models:      z.array(z.string()).optional(),
  }).optional(),
  resource_envelope: z.record(z.string(), z.unknown()).optional(),
})

export const LogEventSchema = z.object({
  ts:      z.string().optional(),
  stream:  z.string().optional(),
  event:   z.string().optional(),
  level:   z.string().optional(),
  payload: z.record(z.string(), z.unknown()).optional(),
}).passthrough()

export const LogsSchema = z.object({
  session_events:     z.array(LogEventSchema),
  agent_performance:  z.array(LogEventSchema),
  integration_events: z.array(LogEventSchema),
})

export const TelemetryReportSchema = z.object({
  report: z.object({
    total_events:    z.number(),
    streams:         z.record(z.string(), z.number()),
    levels:          z.record(z.string(), z.number()),
    top_events:      z.array(z.object({ event: z.string(), count: z.number() })),
    active_sessions: z.number(),
    latency_ms:      z.object({ avg: z.number(), p95: z.number(), max: z.number() }).optional(),
  }),
})

export type Metrics         = z.infer<typeof MetricsSchema>
export type Status          = z.infer<typeof StatusSchema>
export type LogEvent        = z.infer<typeof LogEventSchema>
export type Logs            = z.infer<typeof LogsSchema>
export type TelemetryReport = z.infer<typeof TelemetryReportSchema>

// ── Voices ───────────────────────────────────────────────────────────────────

export const VoiceSchema = z.object({
  id:       z.string(),
  name:     z.string(),
  provider: z.string(),
  gender:   z.string().optional(),
  preview:  z.string().optional(),
}).passthrough()

export type Voice = z.infer<typeof VoiceSchema>

// ── Instructions Booklet ─────────────────────────────────────────────────────

export const BookletSectionSchema = z.object({
  id:         z.string(),
  title:      z.string(),
  content:    z.string(),
  mode:       z.enum(['always', 'retrieve', 'off']),
  sort_order: z.number(),
})

export const BookletCompiledSchema = z.object({
  compiled: z.string(),
})

export type BookletSection  = z.infer<typeof BookletSectionSchema>
export type BookletCompiled = z.infer<typeof BookletCompiledSchema>

// ── Pull job ─────────────────────────────────────────────────────────────────

export const PullStatusSchema = z.object({
  status:   z.string(),
  progress: z.number(),
  done:     z.boolean(),
  detail:   z.string().optional(),
  error:    z.string().optional(),
})

export type PullStatus = z.infer<typeof PullStatusSchema>
