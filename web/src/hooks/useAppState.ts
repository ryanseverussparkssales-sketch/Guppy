/**
 * useAppState - Global state management hook using Zustand
 * Manages all app state and actions for the web UI
 */

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { AppState, AppActions, Workspace, Model, Message, LibraryItem, UserSettings, APIError } from "@/types/api";

interface StoreState extends AppState, AppActions {}

export const useAppStore = create<StoreState>()(
  immer((set, get) => ({
    // Initial state
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

    // Workspace actions
    fetchWorkspaces: async () => {
      set((state) => {
        state.workspacesLoading = true;
      });
      try {
        // TODO: Call API
        const workspaces: Workspace[] = [];
        set((state) => {
          state.workspaces = workspaces;
          state.workspacesLoading = false;
        });
      } catch (error: any) {
        set((state) => {
          state.workspacesError = error;
          state.workspacesLoading = false;
        });
      }
    },

    createWorkspace: async (config) => {
      try {
        // TODO: Call API
        const workspace: Workspace = {
          id: "new-id",
          name: config.name,
          description: config.description,
          type: config.type,
          status: "active",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        set((state) => {
          state.workspaces.push(workspace);
        });
      } catch (error: any) {
        set((state) => {
          state.workspacesError = error;
        });
        throw error;
      }
    },

    updateWorkspace: async (id, config) => {
      try {
        // TODO: Call API
        set((state) => {
          const workspace = state.workspaces.find((w) => w.id === id);
          if (workspace) {
            Object.assign(workspace, config, {
              updatedAt: new Date().toISOString(),
            });
          }
        });
      } catch (error: any) {
        set((state) => {
          state.workspacesError = error;
        });
        throw error;
      }
    },

    deleteWorkspace: async (id) => {
      try {
        // TODO: Call API
        set((state) => {
          state.workspaces = state.workspaces.filter((w) => w.id !== id);
          if (state.activeWorkspace?.id === id) {
            state.activeWorkspace = undefined;
          }
        });
      } catch (error: any) {
        set((state) => {
          state.workspacesError = error;
        });
        throw error;
      }
    },

    setActiveWorkspace: (workspace) => {
      set((state) => {
        state.activeWorkspace = workspace;
      });
    },

    // Model actions
    fetchModels: async () => {
      set((state) => {
        state.modelsLoading = true;
      });
      try {
        // TODO: Call API
        const models: Model[] = [];
        set((state) => {
          state.models = models;
          state.modelsLoading = false;
        });
      } catch (error: any) {
        set((state) => {
          state.modelsError = error;
          state.modelsLoading = false;
        });
      }
    },

    getRuntimeStatus: async () => {
      try {
        // TODO: Call API
        set((state) => {
          state.runtimeStatus = {
            status: "healthy",
            uptime: 0,
          };
        });
      } catch (error: any) {
        // Silently fail, don't block UI
      }
    },

    setActiveModel: async (model) => {
      try {
        // TODO: Call API
        set((state) => {
          state.activeModel = model;
        });
      } catch (error: any) {
        set((state) => {
          state.modelsError = error;
        });
        throw error;
      }
    },

    // Chat actions
    sendMessage: async (content) => {
      const workspace = get().activeWorkspace;
      if (!workspace) throw new Error("No active workspace");

      const userMessage: Message = {
        id: `msg-${Date.now()}`,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };

      set((state) => {
        state.messages.push(userMessage);
        state.messagesLoading = true;
      });

      try {
        // TODO: Call API and stream response
        const assistantMessage: Message = {
          id: `msg-${Date.now() + 1}`,
          role: "assistant",
          content: "Response pending...",
          timestamp: new Date().toISOString(),
        };
        set((state) => {
          state.messages.push(assistantMessage);
          state.messagesLoading = false;
        });
      } catch (error: any) {
        set((state) => {
          state.messagesError = error;
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
        // TODO: Call API
        const messages: Message[] = [];
        set((state) => {
          state.messages = messages;
          state.messagesLoading = false;
        });
      } catch (error: any) {
        set((state) => {
          state.messagesError = error;
          state.messagesLoading = false;
        });
      }
    },

    clearConversation: () => {
      set((state) => {
        state.messages = [];
      });
    },

    // Library actions
    fetchLibraryItems: async (workspaceId) => {
      set((state) => {
        state.libraryLoading = true;
      });
      try {
        // TODO: Call API
        const items: LibraryItem[] = [];
        set((state) => {
          state.libraryItems = items;
          state.libraryLoading = false;
        });
      } catch (error: any) {
        set((state) => {
          state.libraryError = error;
          state.libraryLoading = false;
        });
      }
    },

    saveLibraryItem: async (item) => {
      try {
        // TODO: Call API
        const workspace = get().activeWorkspace;
        if (!workspace) throw new Error("No active workspace");

        const newItem: LibraryItem = {
          id: `item-${Date.now()}`,
          type: (item.type as any) || "note",
          title: item.title || "Untitled",
          content: item.content || "",
          workspaceId: workspace.id,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };

        set((state) => {
          state.libraryItems.push(newItem);
        });
      } catch (error: any) {
        set((state) => {
          state.libraryError = error;
        });
        throw error;
      }
    },

    deleteLibraryItem: async (id) => {
      try {
        // TODO: Call API
        set((state) => {
          state.libraryItems = state.libraryItems.filter((i) => i.id !== id);
        });
      } catch (error: any) {
        set((state) => {
          state.libraryError = error;
        });
        throw error;
      }
    },

    // Settings actions
    fetchSettings: async () => {
      set((state) => {
        state.settingsLoading = true;
      });
      try {
        // TODO: Call API
        set((state) => {
          state.settingsLoading = false;
        });
      } catch (error: any) {
        set((state) => {
          state.settingsError = error;
          state.settingsLoading = false;
        });
      }
    },

    updateSettings: async (settings) => {
      try {
        // TODO: Call API
        set((state) => {
          state.settings = { ...state.settings, ...settings };
        });
      } catch (error: any) {
        set((state) => {
          state.settingsError = error;
        });
        throw error;
      }
    },

    // UI actions
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

// Export hook for use in components
export const useAppState = () => useAppStore();
