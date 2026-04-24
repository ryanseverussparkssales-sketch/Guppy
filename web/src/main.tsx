import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

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
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
