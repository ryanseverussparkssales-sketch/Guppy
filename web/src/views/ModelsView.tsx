import { useEffect, useState } from 'react'
import { Settings } from 'lucide-react'
import api from '../api/client'
import './ModelsView.css'

interface Model {
  id: string
  name: string
  type: string
  provider?: string
  status?: string
  enabled?: boolean
}

export default function ModelsView() {
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchModels = async () => {
      try {
        setLoading(true)
        // Try to fetch from /models endpoint
        const response = await api.get('/models')
        const modelData = response.data.data || response.data.models || []
        setModels(Array.isArray(modelData) ? modelData : [])
        setError(null)
      } catch (err: any) {
        console.error('Failed to fetch models:', err)
        // Gracefully handle error - show info message instead of blocking
        if (err.response?.status === 404) {
          setError('Models endpoint not configured')
        } else {
          setError('Unable to load models. Please check the backend configuration.')
        }
        setModels([])
      } finally {
        setLoading(false)
      }
    }

    fetchModels()
  }, [])

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Models & LLMs</h2>
        <button className="btn btn-primary">
          <Settings size={18} />
          Configure
        </button>
      </div>

      {loading ? (
        <div className="empty-state">
          <p>Loading models...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <h3>Models Configuration</h3>
          <p>{error}</p>
          <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '12px' }}>
            Make sure all backend services are properly configured and running.
          </p>
        </div>
      ) : models.length === 0 ? (
        <div className="empty-state">
          <h3>No models configured</h3>
          <p>Set up your preferred AI models (local or cloud)</p>
          <button className="btn btn-primary">Add Model</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
          {models.map((model) => (
            <div key={model.id} style={{
              backgroundColor: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--border-radius)',
              padding: '16px',
            }}>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '16px', fontWeight: '600' }}>
                {model.name}
              </h3>
              <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: 'var(--color-text-secondary)' }}>
                Type: {model.type}
              </p>
              {model.provider && (
                <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: 'var(--color-text-secondary)' }}>
                  Provider: {model.provider}
                </p>
              )}
              {model.status && (
                <p style={{ margin: '0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                  Status: {model.status}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
