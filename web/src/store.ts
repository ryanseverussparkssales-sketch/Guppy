import { create } from 'zustand'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  metadata?: Record<string, unknown>
}

interface AppState {
  // Chat
  messages: Message[]
  isLoading: boolean
  addMessage: (message: Message) => void
  clearMessages: () => void
  setIsLoading: (loading: boolean) => void

  // Status
  status: unknown
  setStatus: (status: unknown) => void

  // UI State
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void

  // Settings
  apiKey: string | null
  devMode: boolean
  setApiKey: (key: string | null) => void
  setDevMode: (dev: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  messages: [],
  isLoading: false,
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  clearMessages: () => set({ messages: [] }),
  setIsLoading: (loading) => set({ isLoading: loading }),

  status: null,
  setStatus: (status) => set({ status }),

  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  apiKey: localStorage.getItem('apiKey'),
  devMode: localStorage.getItem('devMode') === 'true',
  setApiKey: (key) => {
    localStorage.setItem('apiKey', key || '')
    set({ apiKey: key })
  },
  setDevMode: (dev) => {
    localStorage.setItem('devMode', dev.toString())
    set({ devMode: dev })
  },
}))
