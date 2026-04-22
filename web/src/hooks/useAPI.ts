/**
 * useAPI Hook
 * Shared API client for the backup web UI.
 *
 * This client now targets the live local backend contract:
 * - GET /instances
 * - GET /status
 * - POST /chat
 */

import { useCallback, useState } from "react";
import axios, { AxiosError, AxiosInstance } from "axios";
import {
  APIError,
  APIResponse,
  ErrorSeverity,
  Model,
  RuntimeStatus,
  Workspace,
  WorkspaceType,
} from "@/types/api";

interface APIHookConfig {
  baseURL?: string;
  timeout?: number;
}

interface APIHookState {
  loading: boolean;
  error: APIError | null;
  data: any | null;
}

function buildAPIError(
  code: string,
  message: string,
  severity: ErrorSeverity,
  details?: Record<string, unknown>
): APIError {
  return {
    code,
    message,
    severity,
    details,
    timestamp: new Date().toISOString(),
  };
}

export function coerceAPIError(
  error: unknown,
  fallbackCode: string,
  fallbackMessage: string,
  severity: ErrorSeverity = ErrorSeverity.ERROR
): APIError {
  if (error && typeof error === "object") {
    const candidate = error as Partial<APIError>;
    if (
      typeof candidate.code === "string" &&
      typeof candidate.message === "string" &&
      typeof candidate.severity === "string"
    ) {
      return {
        code: candidate.code,
        message: candidate.message,
        severity: candidate.severity as ErrorSeverity,
        details: candidate.details,
        timestamp: candidate.timestamp || new Date().toISOString(),
      };
    }
  }

  if (error instanceof Error) {
    return buildAPIError(fallbackCode, error.message || fallbackMessage, severity);
  }

  return buildAPIError(fallbackCode, fallbackMessage, severity);
}

function resolveBaseURL(explicitBaseURL?: string): string {
  if (explicitBaseURL?.trim()) {
    return explicitBaseURL.trim().replace(/\/+$/, "");
  }

  const envBaseURL = String(import.meta.env.VITE_GUPPY_API_BASE_URL || "").trim();
  if (envBaseURL) {
    return envBaseURL.replace(/\/+$/, "");
  }

  const port = String(import.meta.env.VITE_GUPPY_API_PORT || "8081").trim() || "8081";
  return `http://127.0.0.1:${port}`;
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "::1";
}

function summarizeModelSize(modelId: string): string {
  const match = modelId.match(/(\d+(?:\.\d+)?)b/i);
  return match ? `${match[1]}B` : "unknown";
}

function normalizeWorkspaceType(value: unknown): WorkspaceType {
  const raw = String(value || "").trim().toLowerCase();
  if (
    raw === "shared_instance" ||
    raw === "read_only_instance" ||
    raw === "builder_instance" ||
    raw === "admin_instance"
  ) {
    return raw;
  }
  return "user_instance";
}

function normalizeWorkspaceStatus(value: unknown): Workspace["status"] {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "error" || raw === "failed") {
    return "error";
  }
  if (raw === "active" || raw === "running" || raw === "ready") {
    return "active";
  }
  return "inactive";
}

function mapInstanceToWorkspace(instance: Record<string, any>): Workspace {
  const id = String(instance.name || instance.id || "");
  const createdAt = String(instance.created_at || new Date().toISOString());
  const updatedAt = String(instance.last_updated || createdAt);

  return {
    id,
    name: id,
    description: String(instance.description || ""),
    type: normalizeWorkspaceType(instance.type),
    status: normalizeWorkspaceStatus(instance.status),
    createdAt,
    updatedAt,
    settings: {
      mode: String(instance.mode || "auto"),
      persona: String(instance.persona || "guppy"),
      voice: String(instance.voice || "default"),
      enabled: Boolean(instance.enabled ?? true),
      modelCurrentlyUsing: String(instance.model_currently_using || "auto"),
    },
  };
}

function mapStatusToModels(statusPayload: Record<string, any>): Model[] {
  const localRuntime = (statusPayload.local_runtime || {}) as Record<string, any>;
  const availableModels = Array.isArray(localRuntime.models) ? localRuntime.models : [];
  const roleModels =
    localRuntime.role_models && typeof localRuntime.role_models === "object"
      ? localRuntime.role_models
      : {};
  const availableRoles = Array.isArray(localRuntime.available_roles)
    ? new Set(localRuntime.available_roles.map((value: unknown) => String(value)))
    : new Set<string>();

  return availableModels.map((modelName: unknown) => {
    const id = String(modelName || "");
    const role = Object.entries(roleModels).find(([, value]) => String(value) === id)?.[0] || "";
    return {
      id,
      name: id,
      provider: String(localRuntime.backend || "local"),
      size: summarizeModelSize(id),
      status: role && !availableRoles.has(role) ? "missing" : "available",
      metadata: {
        role,
        chatModel: String(localRuntime.chat_model || ""),
        detail: String(localRuntime.detail || ""),
      },
    };
  });
}

function mapStatusToRuntimeStatus(statusPayload: Record<string, any>): RuntimeStatus {
  const localRuntime = (statusPayload.local_runtime || {}) as Record<string, any>;
  const resourceEnvelope = (statusPayload.resource_envelope || {}) as Record<string, any>;
  const metrics = (resourceEnvelope.metrics || {}) as Record<string, any>;
  const startedAt = String(resourceEnvelope.ts || "");
  const uptime = startedAt ? Math.max(0, Date.now() - Date.parse(startedAt)) / 1000 : 0;
  const rawStatus = String(statusPayload.status || "").trim().toLowerCase();
  const normalizedStatus: RuntimeStatus["status"] =
    rawStatus === "healthy" || rawStatus === "ok"
      ? "healthy"
      : rawStatus === "offline"
        ? "offline"
        : rawStatus === "error"
          ? "error"
          : "degraded";

  return {
    status: normalizedStatus,
    uptime,
    activeModel: String(localRuntime.chat_model || ""),
    backend: String(localRuntime.backend || "local"),
    detail: String(localRuntime.detail || ""),
    availableModels: Array.isArray(localRuntime.models)
      ? localRuntime.models.map((item: unknown) => String(item))
      : [],
    memory:
      typeof metrics.available_ram_gb === "number" && typeof metrics.total_ram_gb === "number"
        ? {
            used: Math.max(0, metrics.total_ram_gb - metrics.available_ram_gb),
            total: metrics.total_ram_gb,
          }
        : undefined,
    health: {
      api: rawStatus !== "error",
      models: Array.isArray(localRuntime.models) && localRuntime.models.length > 0,
      runtime: Boolean(localRuntime.chat_ready),
    },
  };
}

class GuppyAPIClient {
  private client: AxiosInstance;
  private baseURL: string;
  private authToken: string | null = null;
  private authBootstrapPromise: Promise<string | null> | null = null;

  constructor(config: APIHookConfig = {}) {
    this.baseURL = resolveBaseURL(config.baseURL);
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        "Content-Type": "application/json",
      },
    });

    this.client.interceptors.request.use(async (requestConfig) => {
      const token = await this.ensureAuthToken();
      if (token) {
        requestConfig.headers = requestConfig.headers || {};
        requestConfig.headers.Authorization = `Bearer ${token}`;
      }
      return requestConfig;
    });

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as (typeof error.config & {
          _guppyRetried?: boolean;
        }) | null;

        if (error.response?.status === 401 && originalRequest && !originalRequest._guppyRetried) {
          originalRequest._guppyRetried = true;
          this.authToken = null;
          const refreshedToken = await this.ensureAuthToken(true);
          if (refreshedToken) {
            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `Bearer ${refreshedToken}`;
            return this.client.request(originalRequest);
          }
        }

        return Promise.reject(
          buildAPIError(
            error.code || "REQUEST_FAILED",
            error.message || "Request failed",
            ErrorSeverity.ERROR,
            {
              status: error.response?.status,
              data: error.response?.data as unknown,
            }
          )
        );
      }
    );
  }

  private absoluteURL(path: string): string {
    return `${this.baseURL}${path}`;
  }

  private async requestBootstrapToken(
    path: string,
    payload: Record<string, unknown>
  ): Promise<string | null> {
    const response = await axios.post(this.absoluteURL(path), payload, {
      timeout: 5000,
      headers: {
        "Content-Type": "application/json",
      },
    });

    return String((response.data || {}).access_token || "").trim() || null;
  }

  private async acquireAuthToken(): Promise<string | null> {
    const envBearer = String(import.meta.env.VITE_GUPPY_BEARER_TOKEN || "").trim();
    if (envBearer) {
      return envBearer;
    }

    const envApiKey = String(import.meta.env.VITE_GUPPY_API_KEY || "").trim();
    if (envApiKey) {
      try {
        return await this.requestBootstrapToken("/auth/token", { api_key: envApiKey });
      } catch {
        // Fall through to other auth paths.
      }
    }

    const envTurnstileToken = String(import.meta.env.VITE_GUPPY_TURNSTILE_TOKEN || "").trim();
    const hostname =
      typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";
    const fallbackTurnstileToken =
      envTurnstileToken || (isLoopbackHost(hostname) ? "local-dev" : "");

    if (fallbackTurnstileToken) {
      try {
        return await this.requestBootstrapToken("/auth/verify", {
          token: fallbackTurnstileToken,
        });
      } catch {
        return null;
      }
    }

    return null;
  }

  private async ensureAuthToken(forceRefresh = false): Promise<string | null> {
    if (!forceRefresh && this.authToken) {
      return this.authToken;
    }

    if (!forceRefresh && this.authBootstrapPromise) {
      return this.authBootstrapPromise;
    }

    this.authBootstrapPromise = this.acquireAuthToken()
      .then((token) => {
        this.authToken = token;
        return token;
      })
      .finally(() => {
        this.authBootstrapPromise = null;
      });

    return this.authBootstrapPromise;
  }

  async listWorkspaces(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/instances");
      const payload = response.data || {};
      const workspaces = Array.isArray(payload.instances)
        ? payload.instances.map((instance: Record<string, any>) => mapInstanceToWorkspace(instance))
        : [];

      return {
        success: true,
        data: {
          workspaces,
          activeWorkspaceId: String(payload.active_instance || ""),
          warnings: Array.isArray(payload.warnings) ? payload.warnings : [],
        },
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(error, "WORKSPACE_LIST_FAILED", "Failed to fetch workspaces"),
      };
    }
  }

  async createWorkspace(config: any): Promise<APIResponse> {
    try {
      const response = await this.client.post("/instances", config);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(error, "WORKSPACE_CREATE_FAILED", "Failed to create workspace"),
      };
    }
  }

  async updateWorkspace(id: string, config: any): Promise<APIResponse> {
    try {
      const response = await this.client.post("/instances", {
        name: config.name || id,
        description: config.description || "",
        type: config.type || "user_instance",
        persona: config.persona || "guppy",
        mode: config.mode || "auto",
        voice: config.voice || "default",
        enabled: config.enabled ?? true,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(error, "WORKSPACE_UPDATE_FAILED", "Failed to update workspace"),
      };
    }
  }

  async deleteWorkspace(id: string): Promise<APIResponse> {
    try {
      const response = await this.client.delete(`/instances/${id}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(error, "WORKSPACE_DELETE_FAILED", "Failed to delete workspace"),
      };
    }
  }

  async listModels(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/status");
      return {
        success: true,
        data: mapStatusToModels(response.data || {}),
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(error, "MODELS_LIST_FAILED", "Failed to fetch models"),
      };
    }
  }

  async getRuntimeStatus(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/status");
      return {
        success: true,
        data: mapStatusToRuntimeStatus(response.data || {}),
        metadata: {
          raw: response.data,
        },
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(
          error,
          "RUNTIME_STATUS_FAILED",
          "Failed to get runtime status",
          ErrorSeverity.WARNING
        ),
      };
    }
  }

  async setActiveModel(modelId: string): Promise<APIResponse> {
    return {
      success: false,
      error: buildAPIError(
        "MODEL_SELECT_UNSUPPORTED",
        `The live local backend does not expose a direct model activation route for ${modelId}.`,
        ErrorSeverity.WARNING
      ),
    };
  }

  async sendMessage(workspaceId: string, message: string, context?: any): Promise<APIResponse> {
    try {
      const response = await this.client.post("/chat", {
        message,
        session_id: context?.sessionId,
        mode: context?.mode,
        persona: context?.persona,
        history: Array.isArray(context?.history) ? context.history : undefined,
      });

      return {
        success: true,
        data: {
          workspaceId,
          response: String(response.data?.response || ""),
          sessionId: response.data?.session_id || null,
        },
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(error, "MESSAGE_SEND_FAILED", "Failed to send message"),
      };
    }
  }

  async getConversationHistory(workspaceId: string, limit = 50): Promise<APIResponse> {
    return {
      success: true,
      data: [],
      metadata: {
        workspaceId,
        limit,
        unsupported: true,
      },
    };
  }

  async getLibrary(workspaceId: string): Promise<APIResponse> {
    return {
      success: true,
      data: [],
      metadata: {
        workspaceId,
        unsupported: true,
      },
    };
  }

  async saveArtifact(
    workspaceId: string,
    content: string,
    artifactType: string
  ): Promise<APIResponse> {
    return {
      success: false,
      error: buildAPIError(
        "ARTIFACT_SAVE_UNSUPPORTED",
        `Artifact save is not exposed on the live local backend for ${workspaceId}/${artifactType}.`,
        ErrorSeverity.WARNING,
        { contentLength: content.length }
      ),
    };
  }

  async getSettings(scope = "user"): Promise<APIResponse> {
    return {
      success: true,
      data: {},
      metadata: {
        scope,
        unsupported: true,
      },
    };
  }

  async updateSettings(scope: string, settings: any): Promise<APIResponse> {
    return {
      success: true,
      data: settings,
      metadata: {
        scope,
        unsupported: true,
      },
    };
  }

  async healthCheck(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/status");
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: coerceAPIError(
          error,
          "HEALTH_CHECK_FAILED",
          "API health check failed",
          ErrorSeverity.CRITICAL
        ),
      };
    }
  }
}

let globalClient: GuppyAPIClient | null = null;

export function getAPIClient(config?: APIHookConfig): GuppyAPIClient {
  if (!globalClient) {
    globalClient = new GuppyAPIClient(config);
  }
  return globalClient;
}

export function useAPI<T = any>(
  fn: (client: GuppyAPIClient) => Promise<APIResponse<T>>,
  dependencies: any[] = []
) {
  const [state, setState] = useState<APIHookState>({
    loading: false,
    error: null,
    data: null,
  });

  const execute = useCallback(async () => {
    setState({ loading: true, error: null, data: null });
    try {
      const client = getAPIClient();
      const response = await fn(client);
      if (response.success) {
        setState({ loading: false, error: null, data: response.data });
      } else {
        setState({
          loading: false,
          error:
            response.error ||
            buildAPIError("UNKNOWN_ERROR", "An unknown error occurred", ErrorSeverity.ERROR),
          data: null,
        });
      }
    } catch (error) {
      setState({
        loading: false,
        error: coerceAPIError(error, "REQUEST_ERROR", "An error occurred"),
        data: null,
      });
    }
  }, dependencies);

  return { ...state, execute };
}

export default useAPI;
