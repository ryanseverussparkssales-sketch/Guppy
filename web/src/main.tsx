import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import { initTheme } from '@/themes'

// Apply stored theme before first paint to avoid flash of unstyled content
initTheme()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

console.log('[v0] main.tsx loading')

const rootElement = document.getElementById('root')
console.log('[v0] root element:', rootElement)

if (!rootElement) {
  console.error('[v0] Root element not found!')
} else {
  console.log('[v0] Rendering app...')
}

ReactDOM.createRoot(rootElement!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
