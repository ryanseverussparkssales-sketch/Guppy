import { Routes, Route, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { AppShell } from './components/layout'
import AssistantView from './views/AssistantView'
import InstancesView from './views/InstancesView'
import LibraryView from './views/LibraryView'
import ModelsView from './views/ModelsView'
import ToolsView from './views/ToolsView'
import VoicesView from './views/VoicesView'
import SettingsView from './views/SettingsView'
import StatusView from './views/StatusView'
import AdminPanel from './views/AdminPanel'
import DashboardView from './views/DashboardView'
import { useAppStore } from './store'
import api from './api/client'
import './index.css'

/**
 * App - Main application component
 * 
 * BACKEND INTEGRATION:
 * - Fetches API status on mount and every 30 seconds
 * - Status endpoint: GET /api/ (root)
 * - Navigation is handled via react-router-dom
 * - Custom events from sidebar/command palette trigger navigation
 */
function App() {
  const { setStatus } = useAppStore()
  const navigate = useNavigate()

  // Fetch API status on mount
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await api.get('/')
        setStatus(response.data)
      } catch (error) {
        console.error('Failed to fetch API status:', error)
      }
    }

    checkStatus()
    const interval = setInterval(checkStatus, 30000)
    return () => clearInterval(interval)
  }, [setStatus])

  // Listen for navigation events from sidebar/command palette
  useEffect(() => {
    const handleNavigate = (e: CustomEvent<{ view: string }>) => {
      const viewToRoute: Record<string, string> = {
        dashboard: '/',
        assistant: '/assistant',
        instances: '/instances',
        library: '/library',
        models: '/models',
        tools: '/tools',
        voices: '/voices',
        settings: '/settings',
        status: '/status',
        admin: '/admin',
      }
      const route = viewToRoute[e.detail.view] || '/'
      navigate(route)
    }

    window.addEventListener('guppy:navigate', handleNavigate as EventListener)
    return () => window.removeEventListener('guppy:navigate', handleNavigate as EventListener)
  }, [navigate])

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardView />} />
        <Route path="/assistant" element={<AssistantView />} />
        <Route path="/instances" element={<InstancesView />} />
        <Route path="/library" element={<LibraryView />} />
        <Route path="/models" element={<ModelsView />} />
        <Route path="/tools" element={<ToolsView />} />
        <Route path="/voices" element={<VoicesView />} />
        <Route path="/settings" element={<SettingsView />} />
        <Route path="/status" element={<StatusView />} />
        <Route path="/admin" element={<AdminPanel />} />
      </Routes>
    </AppShell>
  )
}

export default App
