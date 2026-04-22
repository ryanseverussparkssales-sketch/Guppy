/**
 * useAPI Hook
 * Provides Axios client for communicating with Guppy API
 * Used by web UI (and can be used by desktop UI)
 */

import { useState, useCallback, useEffect } from "react";
import axios, { AxiosInstance, AxiosError } from "axios";
import { APIResponse, APIError, ErrorSeverity } from "@/types/api";

interface APIHookConfig {
  baseURL?: string;
  timeout?: number;
}

interface APIHookState {
  loading: boolean;
  error: APIError | null;
  data: any | null;
}

class GuppyAPIClient {
  /**
   * Shared Axios client for all API calls
   */
  private client: AxiosInstance;

  constructor(config: APIHookConfig = {}) {
    this.client = axios.create({
      baseURL: config.baseURL || "http://localhost:8000/api",
      timeout: config.timeout || 30000,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Add response interceptor for consistent error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        const apiError: APIError = {
          code: error.code || "REQUEST_FAILED",
          message: error.message || "An error occurred",
          severity: ErrorSeverity.ERROR,
          details: {
            status: error.response?.status,
            data: error.response?.data,
          },
        };
        return Promise.reject(apiError);
      }
    );
  }

  // ─── Workspace API ────────────────────────────────────

  async listWorkspaces(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/workspaces/");
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "WORKSPACE_LIST_FAILED",
          message: "Failed to fetch workspaces",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async createWorkspace(config: any): Promise<APIResponse> {
    try {
      const response = await this.client.post("/workspaces/", config);
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "WORKSPACE_CREATE_FAILED",
          message: "Failed to create workspace",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async updateWorkspace(id: string, config: any): Promise<APIResponse> {
    try {
      const response = await this.client.put(`/workspaces/${id}`, config);
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "WORKSPACE_UPDATE_FAILED",
          message: "Failed to update workspace",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async deleteWorkspace(id: string): Promise<APIResponse> {
    try {
      const response = await this.client.delete(`/workspaces/${id}`);
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "WORKSPACE_DELETE_FAILED",
          message: "Failed to delete workspace",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  // ─── Models API ───────────────────────────────────────

  async listModels(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/models/");
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "MODELS_LIST_FAILED",
          message: "Failed to fetch models",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async getRuntimeStatus(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/models/runtime-status");
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "RUNTIME_STATUS_FAILED",
          message: "Failed to get runtime status",
          severity: ErrorSeverity.WARNING,
        },
      };
    }
  }

  async setActiveModel(modelId: string): Promise<APIResponse> {
    try {
      const response = await this.client.post(`/models/${modelId}/activate`);
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "MODEL_SELECT_FAILED",
          message: "Failed to set active model",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  // ─── Assistant API ────────────────────────────────────

  async sendMessage(
    workspaceId: string,
    message: string,
    context?: any
  ): Promise<APIResponse> {
    try {
      const response = await this.client.post("/assistant/message", {
        workspace_id: workspaceId,
        message,
        context,
      });
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "MESSAGE_SEND_FAILED",
          message: "Failed to send message",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async getConversationHistory(
    workspaceId: string,
    limit: number = 50
  ): Promise<APIResponse> {
    try {
      const response = await this.client.get(
        `/assistant/${workspaceId}/history?limit=${limit}`
      );
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "HISTORY_FETCH_FAILED",
          message: "Failed to fetch conversation history",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  // ─── Library API ──────────────────────────────────────

  async getLibrary(workspaceId: string): Promise<APIResponse> {
    try {
      const response = await this.client.get(`/library/${workspaceId}`);
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "LIBRARY_FETCH_FAILED",
          message: "Failed to fetch library",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async saveArtifact(
    workspaceId: string,
    content: string,
    artifactType: string
  ): Promise<APIResponse> {
    try {
      const response = await this.client.post(`/library/${workspaceId}`, {
        content,
        artifact_type: artifactType,
      });
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "ARTIFACT_SAVE_FAILED",
          message: "Failed to save artifact",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  // ─── Settings API ─────────────────────────────────────

  async getSettings(scope: string = "user"): Promise<APIResponse> {
    try {
      const response = await this.client.get(`/settings/?scope=${scope}`);
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "SETTINGS_FETCH_FAILED",
          message: "Failed to fetch settings",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  async updateSettings(
    scope: string,
    settings: any
  ): Promise<APIResponse> {
    try {
      const response = await this.client.put("/settings/", {
        scope,
        ...settings,
      });
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "SETTINGS_UPDATE_FAILED",
          message: "Failed to update settings",
          severity: ErrorSeverity.ERROR,
        },
      };
    }
  }

  // ─── Health Check ────────────────────────────────────

  async healthCheck(): Promise<APIResponse> {
    try {
      const response = await this.client.get("/health");
      return response.data;
    } catch (error: any) {
      return {
        success: false,
        error: error instanceof APIError ? error : {
          code: "HEALTH_CHECK_FAILED",
          message: "API health check failed",
          severity: ErrorSeverity.CRITICAL,
        },
      };
    }
  }
}

// Global client instance
let globalClient: GuppyAPIClient | null = null;

export function getAPIClient(config?: APIHookConfig): GuppyAPIClient {
  if (!globalClient) {
    globalClient = new GuppyAPIClient(config);
  }
  return globalClient;
}

// React hook for API calls
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
          error: response.error || {
            code: "UNKNOWN_ERROR",
            message: "An unknown error occurred",
            severity: ErrorSeverity.ERROR,
          },
          data: null,
        });
      }
    } catch (error: any) {
      setState({
        loading: false,
        error: error instanceof APIError ? error : {
          code: "REQUEST_ERROR",
          message: error.message || "An error occurred",
          severity: ErrorSeverity.ERROR,
        },
        data: null,
      });
    }
  }, dependencies);

  return { ...state, execute };
}

export default useAPI;
