/**
 * Central Application State Store (Zustand)
 *
 * Single source of truth for:
 * - Chat conversations and messages
 * - Settings and credentials
 * - Workspaces
 * - Sync status (loading, errors)
 * - UI state (theme, sidebar, etc.)
 *
 * All data flows: UI → syncManager → API → syncManager → store → UI
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

// ============= TYPE DEFINITIONS =============

export type Provider = 'local' | 'anthropic' | 'openai' | 'google' | 'cohere' | 'mistral'

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  model?: string
  created_at: string
}

export interface Conversation {
  id: string
  workspace_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  messages?: ChatMessage[]
}

export interface CredentialStatus {
  anthropic: { configured: boolean }
  openai:    { configured: boolean }
  google:    { configured: boolean }
  cohere:    { configured: boolean }
  mistral:   { configured: boolean }
}

export interface Settings {
  active_provider: Provider
  credentials: CredentialStatus
}

export interface Workspace {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface SyncStatus {
  loading: boolean
  error: string | null
  lastSync: string | null
  pendingChanges: string[] // Track which operations are in flight
}

// ============= STORE STATE INTERFACE =============

export interface AppState {
  // Chat State
  conversations: Conversation[]
  activeConversationId: string | null
  messageCache: Map<string, ChatMessage[]> // Cache messages by conversation ID

  // Settings State
  settings: Settings | null
  settingsLoaded: boolean

  // Workspace State
  workspaces: Workspace[]
  activeWorkspaceId: string | null

  // Sync Status
  syncStatus: {
    chat: SyncStatus
    settings: SyncStatus
    workspaces: SyncStatus
  }

  // UI State
  ui: {
    sidebarOpen: boolean
    theme: 'light' | 'dark' | 'system'
    modals: {
      newConversation: boolean
      deleteConversation: boolean
      settings: boolean
    }
  }

  // ============= CONVERSATION ACTIONS =============

  setConversations: (conversations: Conversation[]) => void
  addConversation: (conversation: Conversation) => void
  updateConversation: (id: string, updates: Partial<Conversation>) => void
  deleteConversation: (id: string) => void
  setActiveConversation: (id: string | null) => void

  // ============= MESSAGE ACTIONS =============

  setMessages: (conversationId: string, messages: ChatMessage[]) => void
  addMessage: (message: ChatMessage) => void
  updateMessage: (conversationId: string, messageId: string, updates: Partial<ChatMessage>) => void
  deleteMessage: (conversationId: string, messageId: string) => void
  clearMessageCache: () => void

  // ============= SETTINGS ACTIONS =============

  setSettings: (settings: Settings) => void
  updateSettings: (updates: Partial<Settings>) => void
  setActiveProvider: (provider: Provider) => void
  setCredentialStatus: (provider: Provider, configured: boolean) => void

  // ============= WORKSPACE ACTIONS =============

  setWorkspaces: (workspaces: Workspace[]) => void
  addWorkspace: (workspace: Workspace) => void
  updateWorkspace: (id: string, updates: Partial<Workspace>) => void
  deleteWorkspace: (id: string) => void
  setActiveWorkspace: (id: string | null) => void

  // ============= SYNC STATUS ACTIONS =============

  setSyncStatus: (domain: 'chat' | 'settings' | 'workspaces', status: Partial<SyncStatus>) => void
  setChatLoading: (loading: boolean) => void
  setSettingsLoading: (loading: boolean) => void
  setWorkspacesLoading: (loading: boolean) => void

  // ============= UI ACTIONS =============

  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark' | 'system') => void
  openModal: (modal: keyof AppState['ui']['modals']) => void
  closeModal: (modal: keyof AppState['ui']['modals']) => void

  // ============= SELECTORS / COMPUTED STATE =============

  getConversations: () => Conversation[]
  getActiveConversation: () => Conversation | null
  getMessages: (conversationId: string) => ChatMessage[]
  getSettings: () => Settings | null
  getActiveProvider: () => Provider | null
  getWorkspaces: () => Workspace[]
  getActiveWorkspace: () => Workspace | null
  isLoading: () => boolean
  getError: () => string | null
}

// ============= STORE CREATION =============

export const useAppStore = create<AppState>()(
  devtools(
    (set, get) => ({
      // Initial State
      conversations: [],
      activeConversationId: null,
      messageCache: new Map(),

      settings: null,
      settingsLoaded: false,

      workspaces: [],
      activeWorkspaceId: null,

      syncStatus: {
        chat: { loading: false, error: null, lastSync: null, pendingChanges: [] },
        settings: { loading: false, error: null, lastSync: null, pendingChanges: [] },
        workspaces: { loading: false, error: null, lastSync: null, pendingChanges: [] },
      },

      ui: {
        sidebarOpen: true,
        theme: 'system',
        modals: {
          newConversation: false,
          deleteConversation: false,
          settings: false,
        },
      },

      // ============= CONVERSATION MUTATIONS =============

      setConversations: (conversations) =>
        set({ conversations }, false, 'setConversations'),

      addConversation: (conversation) =>
        set(
          (state) => ({
            conversations: [conversation, ...state.conversations],
          }),
          false,
          'addConversation'
        ),

      updateConversation: (id, updates) =>
        set(
          (state) => ({
            conversations: state.conversations.map((c) => (c.id === id ? { ...c, ...updates } : c)),
          }),
          false,
          'updateConversation'
        ),

      deleteConversation: (id) =>
        set(
          (state) => ({
            conversations: state.conversations.filter((c) => c.id !== id),
            activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
            messageCache: (() => {
              const newCache = new Map(state.messageCache)
              newCache.delete(id)
              return newCache
            })(),
          }),
          false,
          'deleteConversation'
        ),

      setActiveConversation: (id) =>
        set({ activeConversationId: id }, false, 'setActiveConversation'),

      // ============= MESSAGE MUTATIONS =============

      setMessages: (conversationId, messages) =>
        set(
          (state) => {
            const newCache = new Map(state.messageCache)
            newCache.set(conversationId, messages)
            return { messageCache: newCache }
          },
          false,
          'setMessages'
        ),

      addMessage: (message) =>
        set(
          (state) => {
            const newCache = new Map(state.messageCache)
            const existing = newCache.get(message.conversation_id) || []
            newCache.set(message.conversation_id, [...existing, message])

            // Also update the conversation's messages array if it's loaded
            const updatedConversations = state.conversations.map((c) =>
              c.id === message.conversation_id && c.messages
                ? {
                    ...c,
                    messages: [...(c.messages || []), message],
                    message_count: (c.message_count || 0) + 1,
                    updated_at: new Date().toISOString(),
                  }
                : c
            )

            return { messageCache: newCache, conversations: updatedConversations }
          },
          false,
          'addMessage'
        ),

      updateMessage: (conversationId, messageId, updates) =>
        set(
          (state) => {
            const newCache = new Map(state.messageCache)
            const messages = newCache.get(conversationId) || []
            newCache.set(
              conversationId,
              messages.map((m) => (m.id === messageId ? { ...m, ...updates } : m))
            )
            return { messageCache: newCache }
          },
          false,
          'updateMessage'
        ),

      deleteMessage: (conversationId, messageId) =>
        set(
          (state) => {
            const newCache = new Map(state.messageCache)
            const messages = newCache.get(conversationId) || []
            newCache.set(
              conversationId,
              messages.filter((m) => m.id !== messageId)
            )
            return { messageCache: newCache }
          },
          false,
          'deleteMessage'
        ),

      clearMessageCache: () =>
        set({ messageCache: new Map() }, false, 'clearMessageCache'),

      // ============= SETTINGS MUTATIONS =============

      setSettings: (settings) =>
        set({ settings, settingsLoaded: true }, false, 'setSettings'),

      updateSettings: (updates) =>
        set(
          (state) => ({
            settings: state.settings ? { ...state.settings, ...updates } : null,
          }),
          false,
          'updateSettings'
        ),

      setActiveProvider: (provider) =>
        set(
          (state) => ({
            settings: state.settings ? { ...state.settings, active_provider: provider } : null,
          }),
          false,
          'setActiveProvider'
        ),

      setCredentialStatus: (provider, configured) =>
        set(
          (state) => ({
            settings: state.settings
              ? {
                  ...state.settings,
                  credentials: {
                    ...state.settings.credentials,
                    [provider]: { configured },
                  },
                }
              : null,
          }),
          false,
          'setCredentialStatus'
        ),

      // ============= WORKSPACE MUTATIONS =============

      setWorkspaces: (workspaces) =>
        set({ workspaces }, false, 'setWorkspaces'),

      addWorkspace: (workspace) =>
        set(
          (state) => ({
            workspaces: [workspace, ...state.workspaces],
          }),
          false,
          'addWorkspace'
        ),

      updateWorkspace: (id, updates) =>
        set(
          (state) => ({
            workspaces: state.workspaces.map((w) => (w.id === id ? { ...w, ...updates } : w)),
          }),
          false,
          'updateWorkspace'
        ),

      deleteWorkspace: (id) =>
        set(
          (state) => ({
            workspaces: state.workspaces.filter((w) => w.id !== id),
            activeWorkspaceId: state.activeWorkspaceId === id ? null : state.activeWorkspaceId,
          }),
          false,
          'deleteWorkspace'
        ),

      setActiveWorkspace: (id) =>
        set(
          (_state) => ({
            activeWorkspaceId: id,
            // Clear conversations when switching workspaces
            conversations: [],
            activeConversationId: null,
            messageCache: new Map(),
          }),
          false,
          'setActiveWorkspace'
        ),

      // ============= SYNC STATUS MUTATIONS =============

      setSyncStatus: (domain, status) =>
        set(
          (state) => ({
            syncStatus: {
              ...state.syncStatus,
              [domain]: { ...state.syncStatus[domain], ...status },
            },
          }),
          false,
          'setSyncStatus'
        ),

      setChatLoading: (loading) =>
        set(
          (state) => ({
            syncStatus: {
              ...state.syncStatus,
              chat: { ...state.syncStatus.chat, loading },
            },
          }),
          false,
          'setChatLoading'
        ),

      setSettingsLoading: (loading) =>
        set(
          (state) => ({
            syncStatus: {
              ...state.syncStatus,
              settings: { ...state.syncStatus.settings, loading },
            },
          }),
          false,
          'setSettingsLoading'
        ),

      setWorkspacesLoading: (loading) =>
        set(
          (state) => ({
            syncStatus: {
              ...state.syncStatus,
              workspaces: { ...state.syncStatus.workspaces, loading },
            },
          }),
          false,
          'setWorkspacesLoading'
        ),

      // ============= UI MUTATIONS =============

      toggleSidebar: () =>
        set(
          (state) => ({
            ui: { ...state.ui, sidebarOpen: !state.ui.sidebarOpen },
          }),
          false,
          'toggleSidebar'
        ),

      setTheme: (theme) =>
        set(
          (state) => ({
            ui: { ...state.ui, theme },
          }),
          false,
          'setTheme'
        ),

      openModal: (modal) =>
        set(
          (state) => ({
            ui: {
              ...state.ui,
              modals: { ...state.ui.modals, [modal]: true },
            },
          }),
          false,
          `openModal:${modal}`
        ),

      closeModal: (modal) =>
        set(
          (state) => ({
            ui: {
              ...state.ui,
              modals: { ...state.ui.modals, [modal]: false },
            },
          }),
          false,
          `closeModal:${modal}`
        ),

      // ============= SELECTORS =============

      getConversations: () => get().conversations,

      getActiveConversation: () => {
        const state = get()
        return state.conversations.find((c) => c.id === state.activeConversationId) || null
      },

      getMessages: (conversationId) => {
        return get().messageCache.get(conversationId) || []
      },

      getSettings: () => get().settings,

      getActiveProvider: () => {
        const settings = get().settings
        return settings?.active_provider || null
      },

      getWorkspaces: () => get().workspaces,

      getActiveWorkspace: () => {
        const state = get()
        return state.workspaces.find((w) => w.id === state.activeWorkspaceId) || null
      },

      isLoading: () => {
        const state = get()
        return (
          state.syncStatus.chat.loading ||
          state.syncStatus.settings.loading ||
          state.syncStatus.workspaces.loading
        )
      },

      getError: () => {
        const state = get()
        return (
          state.syncStatus.chat.error ||
          state.syncStatus.settings.error ||
          state.syncStatus.workspaces.error
        )
      },
    }),
    {
      name: 'app-store',
      enabled: import.meta.env.DEV,
    }
  )
)

// ============= CUSTOM HOOKS FOR STORE SUBSETS =============

/**
 * Hook to get only chat-related state and actions
 */
export function useChatStore() {
  return useAppStore((state) => ({
    conversations: state.conversations,
    activeConversationId: state.activeConversationId,
    messages: state.getMessages(state.activeConversationId || ''),
    activeConversation: state.getActiveConversation(),
    loading: state.syncStatus.chat.loading,
    error: state.syncStatus.chat.error,
    // Actions
    setConversations: state.setConversations,
    addConversation: state.addConversation,
    updateConversation: state.updateConversation,
    deleteConversation: state.deleteConversation,
    setActiveConversation: state.setActiveConversation,
    setMessages: state.setMessages,
    addMessage: state.addMessage,
  }))
}

/**
 * Hook to get only settings-related state and actions
 */
export function useSettingsStore() {
  return useAppStore((state) => ({
    settings: state.settings,
    activeProvider: state.getActiveProvider(),
    loading: state.syncStatus.settings.loading,
    error: state.syncStatus.settings.error,
    // Actions
    setSettings: state.setSettings,
    updateSettings: state.updateSettings,
    setActiveProvider: state.setActiveProvider,
    setCredentialStatus: state.setCredentialStatus,
  }))
}

/**
 * Hook to get only workspace-related state and actions
 */
export function useWorkspaceStore() {
  return useAppStore((state) => ({
    workspaces: state.workspaces,
    activeWorkspaceId: state.activeWorkspaceId,
    activeWorkspace: state.getActiveWorkspace(),
    loading: state.syncStatus.workspaces.loading,
    error: state.syncStatus.workspaces.error,
    // Actions
    setWorkspaces: state.setWorkspaces,
    addWorkspace: state.addWorkspace,
    updateWorkspace: state.updateWorkspace,
    deleteWorkspace: state.deleteWorkspace,
    setActiveWorkspace: state.setActiveWorkspace,
  }))
}

/**
 * Hook to get only UI-related state and actions
 */
export function useUIStore() {
  return useAppStore((state) => ({
    sidebarOpen: state.ui.sidebarOpen,
    theme: state.ui.theme,
    modals: state.ui.modals,
    // Actions
    toggleSidebar: state.toggleSidebar,
    setTheme: state.setTheme,
    openModal: state.openModal,
    closeModal: state.closeModal,
  }))
}
