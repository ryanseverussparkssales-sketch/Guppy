import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useTheme } from './hooks/useTheme'
import Layout from './components/Layout'
import AdvancedAssistantView from './views/AdvancedAssistantView'
import InstancesView from './views/InstancesView'
import LibraryView from './views/LibraryView'
import ModelsView from './views/ModelsView'
import ToolsView from './views/ToolsView'
import VoicesView from './views/VoicesView'
import AdminPanel from './views/AdminPanel'
import ThemeSettings from './views/ThemeSettings'
import LoginView from './views/LoginView'
import StatusView from './views/StatusView'
import api from './api/client'
import './App.css'

// Protected route component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('accessToken')
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('accessToken'))
  const { setThemeMode, setThemePreset } = useTheme()

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('accessToken')
    setIsLoggedIn(!!token)

    // Load saved theme preferences
    const savedTheme = localStorage.getItem('theme')
    const savedPreset = localStorage.getItem('themePreset')
    if (savedTheme) setThemeMode(savedTheme as any)
    if (savedPreset) setThemePreset(savedPreset)
  }, [setThemeMode, setThemePreset])

  // Check token validity
  useEffect(() => {
    const verifyToken = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) return

      try {
        await api.get('/auth/self-check')
      } catch {
        // Token is invalid or expired
        localStorage.removeItem('accessToken')
        setIsLoggedIn(false)
      }
    }

    if (isLoggedIn) {
      verifyToken()
      const interval = setInterval(verifyToken, 5 * 60 * 1000) // Check every 5 minutes
      return () => clearInterval(interval)
    }
  }, [isLoggedIn])

  if (!isLoggedIn) {
    return <LoginView />
  }

  return (
    <Layout>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AdvancedAssistantView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/instances"
          element={
            <ProtectedRoute>
              <InstancesView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/library"
          element={
            <ProtectedRoute>
              <LibraryView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/models"
          element={
            <ProtectedRoute>
              <ModelsView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tools"
          element={
            <ProtectedRoute>
              <ToolsView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/voices"
          element={
            <ProtectedRoute>
              <VoicesView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/themes"
          element={
            <ProtectedRoute>
              <ThemeSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminPanel />
            </ProtectedRoute>
          }
        />
        <Route
          path="/status"
          element={
            <ProtectedRoute>
              <StatusView />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<LoginView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
