import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import Layout from './components/Layout'
import AssistantView from './views/AssistantView'
import InstancesView from './views/InstancesView'
import LibraryView from './views/LibraryView'
import ModelsView from './views/ModelsView'
import ToolsView from './views/ToolsView'
import VoicesView from './views/VoicesView'
import SettingsView from './views/SettingsView'
import StatusView from './views/StatusView'
import { useAppStore } from './store'
import api from './api/client'
import './App.css'

function App() {
  const { setStatus } = useAppStore()

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
    const interval = setInterval(checkStatus, 30000) // Check every 30s
    return () => clearInterval(interval)
  }, [setStatus])

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<AssistantView />} />
        <Route path="/instances" element={<InstancesView />} />
        <Route path="/library" element={<LibraryView />} />
        <Route path="/models" element={<ModelsView />} />
        <Route path="/tools" element={<ToolsView />} />
        <Route path="/voices" element={<VoicesView />} />
        <Route path="/settings" element={<SettingsView />} />
        <Route path="/status" element={<StatusView />} />
      </Routes>
    </Layout>
  )
}

export default App
