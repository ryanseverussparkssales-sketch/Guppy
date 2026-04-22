/**
 * useAppState - Global state management hook using Zustand
 * Manages app state for the backup web UI.
 */

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import {
  AppActions,
  AppState,
  LibraryItem,
  Message,
  Model,
  Workspace,
} from "@/types/api";
import { coerceAPIError, getAPIClient } from "@/hooks/useAPI";

interface StoreState extends AppState, AppActions {}

export const useAppStore = create<StoreState>()(
  immer((set, get) => ({
    isAuthenticated: false,
    workspaces: [],
    models: [],
    messages: [],
    libraryItems: [],
    settings: {
      theme: "system",
      layout: "default",
      notifications: true,
      autoSave: true,
      language: "en",
    },
    workspacesLoading: false,
    modelsLoading: false,
    messagesLoading: false,
    libraryLoading: false,
    settingsLoading: false,
    sidebarOpen: true,
    activeTab: "assistant",
    isOnline: true,

    fetchWorkspaces: async () => {
      set((state) => {
        state.workspacesLoading = true;
        state.workspacesError = undefined;
      });

      try {
        const client = getAPIClient();
        const response = await client.listWorkspaces();
        if (!response.success) {
          throw response.error;
        }

        const payload = (response.data || {}) as {
          workspaces?: Workspace[];
          activeWorkspaceId?: string;
        };
        const workspaces = Array.isArray(payload.workspaces) ? payload.workspaces : [];
        const activeWorkspace =
          workspaces.find((workspace) => workspace.id === payload.activeWorkspaceId) ||
          get().activeWorkspace ||
          workspaces[0];

        set((state) => {
          state.workspaces = workspaces;
          state.activeWorkspace = activeWorkspace;
          state.workspacesLoading = false;
        });
      } catch (error) {
        set((state) => {
          state.workspacesError = coerceAPIError(
            error,
            "WORKSPACE_FETCH_FAILED",
            "Failed to fetch workspaces"
          );
          state.workspacesLoading = false;
        });
      }
    },

    createWorkspace: async (config) => {
      try {
        const client = getAPIClient();
        const response = await client.createWorkspace(config);
        if (!response.success) {
          throw response.error;
        }
        await get().fetchWorkspaces();
      } catch (error) {
        set((state) => {
          state.workspacesError = coerceAPIError(
            error,
            "WORKSPACE_CREATE_FAILED",
            "Failed to create workspace"
          );
        });
        throw error;
      }
    },

    updateWorkspace: async (id, config) => {
      try {
        const client = getAPIClient();
        const response = await client.updateWorkspace(id, config);
        if (!response.success) {
          throw response.error;
        }
        await get().fetchWorkspaces();
      } catch (error) {
        set((state) => {
          state.workspacesError = coerceAPIError(
            error,
            "WORKSPACE_UPDATE_FAILED",
            "Failed to update workspace"
          );
        });
        throw error;
      }
    },

    deleteWorkspace: async (id) => {
      try {
        const client = getAPIClient();
        const response = await client.deleteWorkspace(id);
        if (!response.success) {
          throw response.error;
        }
        await get().fetchWorkspaces();
      } catch (error) {
        set((state) => {
          state.workspacesError = coerceAPIError(
            error,
            "WORKSPACE_DELETE_FAILED",
            "Failed to delete workspace"
          );
        });
        throw error;
      }
    },

    setActiveWorkspace: (workspace) => {
      set((state) => {
        state.activeWorkspace = workspace;
      });
    },

    fetchModels: async () => {
      set((state) => {
        state.modelsLoading = true;
        state.modelsError = undefined;
      });

      try {
        const client = getAPIClient();
        const response = await client.listModels();
        if (!response.success) {
          throw response.error;
        }

        const models = Array.isArray(response.data) ? (response.data as Model[]) : [];
        const activeModelId = get().runtimeStatus?.activeModel || "";
        const activeModel =
          models.find((model) => model.id === activeModelId) || get().activeModel || models[0];

        set((state) => {
          state.models = models;
          state.activeModel = activeModel;
          state.modelsLoading = false;
        });
      } catch (error) {
        set((state) => {
          state.modelsError = coerceAPIError(
            error,
            "MODELS_FETCH_FAILED",
            "Failed to fetch models"
          );
          state.modelsLoading = false;
        });
      }
    },

    getRuntimeStatus: async () => {
      try {
        const client = getAPIClient();
        const response = await client.getRuntimeStatus();
        if (!response.success) {
          throw response.error;
        }

        const runtimeStatus = response.data || {
          status: "offline",
          uptime: 0,
        };

        set((state) => {
          state.runtimeStatus = runtimeStatus as any;
          if (state.models.length > 0 && runtimeStatus.activeModel) {
            const activeModel = state.models.find(
              (model) => model.id === runtimeStatus.activeModel
            );
            if (activeModel) {
              state.activeModel = activeModel;
            }
          }
        });
      } catch (error) {
        set((state) => {
          state.modelsError = coerceAPIError(
            error,
            "RUNTIME_STATUS_FAILED",
            "Failed to get runtime status"
          );
        });
      }
    },

    setActiveModel: async (model) => {
      try {
        const client = getAPIClient();
        const response = await client.setActiveModel(model.id);
        if (!response.success) {
          throw response.error;
        }

        set((state) => {
          state.activeModel = model;
        });
      } catch (error) {
        set((state) => {
          state.modelsError = coerceAPIError(
            error,
            "MODEL_SELECT_FAILED",
            "Failed to set active model"
          );
        });
        throw error;
      }
    },

    sendMessage: async (content) => {
      const workspace = get().activeWorkspace;
      if (!workspace) {
        throw new Error("No active workspace");
      }

      const history = get()
        .messages.slice(-12)
        .filter((message) => message.role === "user" || message.role === "assistant")
        .map((message) => ({
          role: message.role,
          content: message.content,
        }));

      const userMessage: Message = {
        id: `msg-${Date.now()}`,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };

      set((state) => {
        state.messages.push(userMessage);
        state.messagesLoading = true;
        state.messagesError = undefined;
      });

      try {
        const client = getAPIClient();
        const response = await client.sendMessage(workspace.id, content, { history });
        if (!response.success) {
          throw response.error;
        }

        const assistantMessage: Message = {
          id: `msg-${Date.now() + 1}`,
          role: "assistant",
          content: String(response.data?.response || "").trim() || "No response received.",
          timestamp: new Date().toISOString(),
        };

        set((state) => {
          state.messages.push(assistantMessage);
          state.messagesLoading = false;
        });
      } catch (error) {
        set((state) => {
          state.messagesError = coerceAPIError(
            error,
            "MESSAGE_SEND_FAILED",
            "Failed to send message"
          );
          state.messagesLoading = false;
        });
        throw error;
      }
    },

    getConversationHistory: async (workspaceId) => {
      set((state) => {
        state.messagesLoading = true;
      });

      try {
        const client = getAPIClient();
        const response = await client.getConversationHistory(workspaceId);
        if (!response.success) {
          throw response.error;
        }

        const messages = Array.isArray(response.data) ? (response.data as Message[]) : [];
        set((state) => {
          state.messages = messages;
          state.messagesLoading = false;
        });
      } catch (error) {
        set((state) => {
          state.messagesError = coerceAPIError(
            error,
            "HISTORY_FETCH_FAILED",
            "Failed to fetch conversation history"
          );
          state.messagesLoading = false;
        });
      }
    },

    clearConversation: () => {
      set((state) => {
        state.messages = [];
      });
    },

    fetchLibraryItems: async (workspaceId) => {
      set((state) => {
        state.libraryLoading = true;
        state.libraryError = undefined;
      });

      try {
        const client = getAPIClient();
        const response = await client.getLibrary(workspaceId);
        if (!response.success) {
          throw response.error;
        }

        const items = Array.isArray(response.data) ? (response.data as LibraryItem[]) : [];
        set((state) => {
          state.libraryItems = items;
          state.libraryLoading = false;
        });
      } catch (error) {
        set((state) => {
          state.libraryError = coerceAPIError(
            error,
            "LIBRARY_FETCH_FAILED",
            "Failed to fetch library items"
          );
          state.libraryLoading = false;
        });
      }
    },

    saveLibraryItem: async (item) => {
      try {
        const workspace = get().activeWorkspace;
        if (!workspace) {
          throw new Error("No active workspace");
        }

        const client = getAPIClient();
        const response = await client.saveArtifact(
          workspace.id,
          item.content || "",
          String(item.type || "note")
        );
        if (!response.success) {
          throw response.error;
        }
      } catch (error) {
        set((state) => {
          state.libraryError = coerceAPIError(
            error,
            "ARTIFACT_SAVE_FAILED",
            "Failed to save library item"
          );
        });
        throw error;
      }
    },

    deleteLibraryItem: async (id) => {
      try {
        set((state) => {
          state.libraryItems = state.libraryItems.filter((item) => item.id !== id);
        });
      } catch (error) {
        set((state) => {
          state.libraryError = coerceAPIError(
            error,
            "LIBRARY_DELETE_FAILED",
            "Failed to delete library item"
          );
        });
        throw error;
      }
    },

    fetchSettings: async () => {
      set((state) => {
        state.settingsLoading = true;
        state.settingsError = undefined;
      });

      try {
        const client = getAPIClient();
        const response = await client.getSettings();
        if (!response.success) {
          throw response.error;
        }

        set((state) => {
          state.settings = { ...state.settings, ...(response.data || {}) };
          state.settingsLoading = false;
        });
      } catch (error) {
        set((state) => {
          state.settingsError = coerceAPIError(
            error,
            "SETTINGS_FETCH_FAILED",
            "Failed to fetch settings"
          );
          state.settingsLoading = false;
        });
      }
    },

    updateSettings: async (settings) => {
      try {
        const client = getAPIClient();
        const response = await client.updateSettings("user", settings);
        if (!response.success) {
          throw response.error;
        }

        set((state) => {
          state.settings = { ...state.settings, ...settings };
        });
      } catch (error) {
        set((state) => {
          state.settingsError = coerceAPIError(
            error,
            "SETTINGS_UPDATE_FAILED",
            "Failed to update settings"
          );
        });
        throw error;
      }
    },

    toggleSidebar: () => {
      set((state) => {
        state.sidebarOpen = !state.sidebarOpen;
      });
    },

    setActiveTab: (tab) => {
      set((state) => {
        state.activeTab = tab;
      });
    },

    setOnlineStatus: (online) => {
      set((state) => {
        state.isOnline = online;
      });
    },
  }))
);

export const useAppState = () => useAppStore();
