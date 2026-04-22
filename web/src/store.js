import { create } from 'zustand';
export const useAppStore = create((set) => ({
    messages: [],
    isLoading: false,
    addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
    clearMessages: () => set({ messages: [] }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    status: null,
    setStatus: (status) => set({ status }),
    sidebarOpen: true,
    setSidebarOpen: (open) => set({ sidebarOpen: open }),
    apiKey: localStorage.getItem('apiKey'),
    devMode: localStorage.getItem('devMode') === 'true',
    setApiKey: (key) => {
        localStorage.setItem('apiKey', key || '');
        set({ apiKey: key });
    },
    setDevMode: (dev) => {
        localStorage.setItem('devMode', dev.toString());
        set({ devMode: dev });
    },
}));
