import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import api from '../api/client'
import './InstancesView.css'

interface Instance {
  name: string
  description?: string
  type?: string
  mode?: string
  persona?: string
  status?: string
  enabled?: boolean
}

export default function InstancesView() {
  const [instances, setInstances] = useState<Instance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchInstances = async () => {
      try {
        setLoading(true)
        const response = await api.get('/instances')
        const instanceData = response.data.instances || []
        setInstances(Array.isArray(instanceData) ? instanceData : [])
        setError(null)
      } catch (err: any) {
        console.error('Failed to fetch instances:', err)
        setError('Unable to load instances')
        setInstances([])
      } finally {
        setLoading(false)
      }
    }

    fetchInstances()
  }, [])

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Instances</h2>
        <button className="btn btn-primary">
          <Plus size={18} />
          New Instance
        </button>
      </div>

      {loading ? (
        <div className="empty-state">
          <p>Loading instances...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <h3>Error Loading Instances</h3>
          <p>{error}</p>
        </div>
      ) : instances.length === 0 ? (
        <div className="empty-state">
          <h3>No instances yet</h3>
          <p>Create your first instance to get started with Guppy</p>
          <button className="btn btn-primary">Create Instance</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {instances.map((instance) => (
            <div key={instance.name} style={{
              backgroundColor: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--border-radius)',
              padding: '20px',
              cursor: 'pointer',
              transition: 'var(--transition)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}
            >
              <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '600' }}>
                {instance.name}
              </h3>
              {instance.description && (
                <p style={{ margin: '0 0 12px 0', color: 'var(--color-text-secondary)' }}>
                  {instance.description}
                </p>
              )}
              <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                {instance.status && <span>Status: {instance.status}</span>}
                {instance.type && <span>Type: {instance.type}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
