import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'

export interface Workspace {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export function useWorkspaces() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch all workspaces
  const fetchWorkspaces = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/workspaces')
      setWorkspaces(res.data.workspaces || [])
      setActiveWorkspaceId(res.data.active_id || null)
    } catch (err) {
      setError('Failed to fetch workspaces')
      console.error('Workspace fetch error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Create new workspace
  const createWorkspace = useCallback(async (name: string, description: string = '') => {
    try {
      const res = await api.post('/api/workspaces', { name, description })
      setWorkspaces((prev) => [res.data, ...prev])
      return res.data
    } catch (err) {
      setError('Failed to create workspace')
      console.error('Create workspace error:', err)
      throw err
    }
  }, [])

  // Update workspace
  const updateWorkspace = useCallback(async (id: string, updates: { name?: string; description?: string }) => {
    try {
      const res = await api.put(`/api/workspaces/${id}`, updates)
      setWorkspaces((prev) => prev.map((ws) => (ws.id === id ? res.data : ws)))
      return res.data
    } catch (err) {
      setError('Failed to update workspace')
      console.error('Update workspace error:', err)
      throw err
    }
  }, [])

  // Delete workspace
  const deleteWorkspace = useCallback(async (id: string) => {
    try {
      await api.delete(`/api/workspaces/${id}`)
      setWorkspaces((prev) => prev.filter((ws) => ws.id !== id))
      if (activeWorkspaceId === id) {
        setActiveWorkspaceId(null)
      }
    } catch (err) {
      setError('Failed to delete workspace')
      console.error('Delete workspace error:', err)
      throw err
    }
  }, [activeWorkspaceId])

  // Switch active workspace
  const switchWorkspace = useCallback(async (id: string) => {
    try {
      await api.post(`/api/workspaces/${id}/activate`)
      setActiveWorkspaceId(id)
      setWorkspaces((prev) => prev.map((ws) => ({ ...ws, is_active: ws.id === id })))
    } catch (err) {
      setError('Failed to switch workspace')
      console.error('Switch workspace error:', err)
      throw err
    }
  }, [])

  // Load workspaces on mount
  useEffect(() => {
    fetchWorkspaces()
  }, [fetchWorkspaces])

  const activeWorkspace = workspaces.find((ws) => ws.id === activeWorkspaceId)

  return {
    workspaces,
    activeWorkspace,
    activeWorkspaceId,
    loading,
    error,
    fetchWorkspaces,
    createWorkspace,
    updateWorkspace,
    deleteWorkspace,
    switchWorkspace,
  }
}
