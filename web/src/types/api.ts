/**
 * =============================================================================
 * GUPPY API TYPE DEFINITIONS
 * =============================================================================
 * 
 * This file contains all TypeScript interfaces for backend API communication.
 * Each type is documented with its corresponding API endpoint for easy backend
 * agent integration.
 * 
 * BACKEND INTEGRATION NOTES:
 * - All endpoints are prefixed with /api (proxied via vite.config.ts)
 * - WebSocket connection: ws://localhost:8081/ws
 * - Authentication: Token-based (see AuthResponse)
 * =============================================================================
 */

// =============================================================================
// COMMON TYPES
// =============================================================================

export interface ApiResponse<T> {
  data: T
  success: boolean
  error?: string
  timestamp: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

// =============================================================================
// AUTHENTICATION
// Endpoints: POST /api/auth/login, POST /api/auth/logout, GET /api/auth/status
// =============================================================================

export interface LoginRequest {
  username: string
  password: string
}

export interface AuthResponse {
  token: string
  user: User
  expiresAt: string
}

export interface User {
  id: string
  username: string
  role: "admin" | "user" | "viewer"
  createdAt: string
}

// =============================================================================
// INSTANCES
// Endpoints: GET /api/instances, GET /api/instances/:id, POST /api/instances,
//            PUT /api/instances/:id, DELETE /api/instances/:id
//            POST /api/instances/:id/start, POST /api/instances/:id/stop
// =============================================================================

export type InstanceStatus = "running" | "stopped" | "error" | "starting" | "stopping"

export interface Instance {
  /** Unique identifier for the instance */
  id: string
  /** Human-readable name */
  name: string
  /** Current operational status */
  status: InstanceStatus
  /** Model ID this instance is running */
  modelId: string
  /** Model name for display */
  modelName: string
  /** When the instance was created */
  createdAt: string
  /** Last activity timestamp */
  lastActive: string
  /** Resource usage metrics */
  metrics: InstanceMetrics
  /** Configuration settings */
  config: InstanceConfig
}

export interface InstanceMetrics {
  /** CPU usage percentage (0-100) */
  cpuUsage: number
  /** Memory usage in bytes */
  memoryUsage: number
  /** Total memory allocated in bytes */
  memoryTotal: number
  /** Number of requests processed */
  requestCount: number
  /** Average response time in ms */
  avgResponseTime: number
}

export interface InstanceConfig {
  /** Maximum tokens per response */
  maxTokens: number
  /** Temperature setting (0-2) */
  temperature: number
  /** Top-p sampling */
  topP: number
  /** System prompt */
  systemPrompt?: string
  /** Enabled tools/functions */
  enabledTools: string[]
}

export interface CreateInstanceRequest {
  name: string
  modelId: string
  config?: Partial<InstanceConfig>
}

// =============================================================================
// MODELS
// Endpoints: GET /api/models, GET /api/models/:id, POST /api/models/download,
//            DELETE /api/models/:id
// =============================================================================

export type ModelType = "llm" | "embedding" | "vision" | "audio" | "multimodal"
export type ModelProvider = "local" | "openai" | "anthropic" | "ollama" | "custom"

export interface Model {
  /** Unique identifier */
  id: string
  /** Display name */
  name: string
  /** Model provider/source */
  provider: ModelProvider
  /** Type of model */
  type: ModelType
  /** Model description */
  description: string
  /** Parameter count (e.g., "7B", "70B") */
  parameters: string
  /** Context window size */
  contextLength: number
  /** Whether model is downloaded/available */
  isAvailable: boolean
  /** Download progress (0-100) if downloading */
  downloadProgress?: number
  /** Size in bytes */
  size: number
  /** Model capabilities */
  capabilities: ModelCapabilities
}

export interface ModelCapabilities {
  chat: boolean
  completion: boolean
  functionCalling: boolean
  vision: boolean
  embedding: boolean
  streaming: boolean
}

export interface DownloadModelRequest {
  modelId: string
  source: string
}

// =============================================================================
// TOOLS
// Endpoints: GET /api/tools, GET /api/tools/:id, POST /api/tools,
//            PUT /api/tools/:id, DELETE /api/tools/:id
// =============================================================================

export interface Tool {
  /** Unique identifier */
  id: string
  /** Tool name (used in function calls) */
  name: string
  /** Human-readable description */
  description: string
  /** Tool category for grouping */
  category: string
  /** Whether tool is enabled globally */
  isEnabled: boolean
  /** JSON Schema for tool parameters */
  parameters: Record<string, unknown>
  /** Tool implementation type */
  type: "builtin" | "custom" | "mcp"
}

export interface CreateToolRequest {
  name: string
  description: string
  category: string
  parameters: Record<string, unknown>
  implementation: string
}

// =============================================================================
// CHAT / CONVERSATIONS
// Endpoints: GET /api/conversations, GET /api/conversations/:id,
//            POST /api/conversations, DELETE /api/conversations/:id
// WebSocket: ws://localhost:8081/ws (for streaming)
// =============================================================================

export type MessageRole = "user" | "assistant" | "system" | "tool"

export interface Conversation {
  id: string
  title: string
  instanceId: string
  createdAt: string
  updatedAt: string
  messageCount: number
}

export interface Message {
  id: string
  conversationId: string
  role: MessageRole
  content: string
  timestamp: string
  /** Tool calls made by assistant */
  toolCalls?: ToolCall[]
  /** Tool response (if role is "tool") */
  toolResult?: ToolResult
  /** Token usage for this message */
  tokens?: {
    prompt: number
    completion: number
  }
}

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

export interface ToolResult {
  toolCallId: string
  result: unknown
  error?: string
}

export interface SendMessageRequest {
  conversationId: string
  content: string
  /** Optional: override instance config for this message */
  config?: Partial<InstanceConfig>
}

// =============================================================================
// WEBSOCKET EVENTS
// Connection: ws://localhost:8081/ws
// =============================================================================

export type WebSocketEventType =
  | "connected"
  | "message_start"
  | "message_delta"
  | "message_complete"
  | "tool_call_start"
  | "tool_call_complete"
  | "error"
  | "instance_status"

export interface WebSocketEvent<T = unknown> {
  type: WebSocketEventType
  payload: T
  timestamp: string
}

export interface MessageDeltaPayload {
  conversationId: string
  messageId: string
  delta: string
}

export interface InstanceStatusPayload {
  instanceId: string
  status: InstanceStatus
  metrics?: InstanceMetrics
}

// =============================================================================
// SYSTEM STATUS
// Endpoints: GET /api/status, GET /api/status/health
// =============================================================================

export interface SystemStatus {
  /** Overall system health */
  health: "healthy" | "degraded" | "unhealthy"
  /** Backend version */
  version: string
  /** Uptime in seconds */
  uptime: number
  /** System resource usage */
  resources: {
    cpuUsage: number
    memoryUsage: number
    memoryTotal: number
    gpuUsage?: number
    gpuMemory?: number
  }
  /** Connected services status */
  services: {
    database: "connected" | "disconnected"
    modelServer: "connected" | "disconnected"
    websocket: "connected" | "disconnected"
  }
}

// =============================================================================
// SETTINGS
// Endpoints: GET /api/settings, PUT /api/settings
// =============================================================================

export interface Settings {
  /** Default model for new instances */
  defaultModelId: string
  /** Theme preference */
  theme: "light" | "dark" | "system"
  /** API keys (masked) */
  apiKeys: {
    openai?: string
    anthropic?: string
  }
  /** Default instance configuration */
  defaultConfig: InstanceConfig
}

export interface UpdateSettingsRequest {
  settings: Partial<Settings>
}
