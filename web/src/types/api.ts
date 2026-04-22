/**
 * Shared API Types
 * Used by both React web UI and can be imported by desktop app
 */

export enum ErrorSeverity {
  INFO = "info",
  WARNING = "warning",
  ERROR = "error",
  CRITICAL = "critical",
}

export interface APIError {
  code: string;
  message: string;
  severity: ErrorSeverity;
  details?: Record<string, any>;
  timestamp?: string;
}

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: APIError;
  metadata?: Record<string, any>;
}

// Workspace Types
export interface Workspace {
  id: string;
  name: string;
  description: string;
  type: "user_instance" | "shared_instance" | "read_only_instance";
  status: "active" | "inactive" | "error";
  createdAt: string;
  updatedAt: string;
  settings?: Record<string, any>;
}

export interface WorkspaceCreate {
  name: string;
  description: string;
  type: "user_instance" | "shared_instance";
  persona?: string;
  mode?: string;
  voice?: string;
}

// Model Types
export interface Model {
  id: string;
  name: string;
  provider: string;
  size: string;
  status: "available" | "downloading" | "installed" | "error";
  metadata?: Record<string, any>;
}

export interface RuntimeStatus {
  status: "healthy" | "degraded" | "offline";
  uptime: number;
  activeModel?: string;
  memory?: {
    used: number;
    total: number;
  };
  health?: {
    api: boolean;
    models: boolean;
    runtime: boolean;
  };
}

// Assistant Types
export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  context?: {
    library?: string[];
    instances?: string[];
  };
}

export interface ConversationContext {
  activeWorkspace: string;
  activeModel: string;
  attachedLibrary: string[];
  mode: string;
}

// Library Types
export interface LibraryItem {
  id: string;
  type: "file" | "note" | "artifact";
  title: string;
  content: string;
  workspaceId: string;
  createdAt: string;
  updatedAt: string;
  metadata?: Record<string, any>;
}

// Settings Types
export interface UserSettings {
  theme: "light" | "dark" | "system";
  layout: "default" | "compact";
  notifications: boolean;
  autoSave: boolean;
  language: string;
  [key: string]: any;
}

// State Management
export interface AppState {
  // Authentication
  isAuthenticated: boolean;
  user?: { id: string; name: string; email: string };

  // Workspaces
  workspaces: Workspace[];
  activeWorkspace?: Workspace;
  workspacesLoading: boolean;
  workspacesError?: APIError;

  // Models
  models: Model[];
  activeModel?: Model;
  runtimeStatus?: RuntimeStatus;
  modelsLoading: boolean;
  modelsError?: APIError;

  // Chat/Assistant
  messages: Message[];
  conversationContext?: ConversationContext;
  messagesLoading: boolean;
  messagesError?: APIError;

  // Library
  libraryItems: LibraryItem[];
  libraryLoading: boolean;
  libraryError?: APIError;

  // Settings
  settings: UserSettings;
  settingsLoading: boolean;
  settingsError?: APIError;

  // UI State
  sidebarOpen: boolean;
  activeTab: string;
  isOnline: boolean;
}

export interface AppActions {
  // Workspace actions
  fetchWorkspaces: () => Promise<void>;
  createWorkspace: (config: WorkspaceCreate) => Promise<void>;
  updateWorkspace: (id: string, config: Partial<Workspace>) => Promise<void>;
  deleteWorkspace: (id: string) => Promise<void>;
  setActiveWorkspace: (workspace: Workspace) => void;

  // Model actions
  fetchModels: () => Promise<void>;
  getRuntimeStatus: () => Promise<void>;
  setActiveModel: (model: Model) => Promise<void>;

  // Chat actions
  sendMessage: (content: string) => Promise<void>;
  getConversationHistory: (workspaceId: string) => Promise<void>;
  clearConversation: () => void;

  // Library actions
  fetchLibraryItems: (workspaceId: string) => Promise<void>;
  saveLibraryItem: (item: Partial<LibraryItem>) => Promise<void>;
  deleteLibraryItem: (id: string) => Promise<void>;

  // Settings actions
  fetchSettings: () => Promise<void>;
  updateSettings: (settings: Partial<UserSettings>) => Promise<void>;

  // UI actions
  toggleSidebar: () => void;
  setActiveTab: (tab: string) => void;
  setOnlineStatus: (online: boolean) => void;
}
