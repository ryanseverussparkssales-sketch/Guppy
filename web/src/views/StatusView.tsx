import { useEffect, useState } from 'react'
import { Activity, Zap, AlertCircle } from 'lucide-react'
import api from '../api/client'
import './StatusView.css'

interface StatusData {
  status?: string
  message?: string
  [key: string]: any
}

export default function StatusView() {
  const [statusData, setStatusData] = useState<StatusData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true)
        const response = await api.get('/status')
        setStatusData(response.data)
      } catch (error) {
        console.error('Failed to fetch status:', error)
        setStatusData({ error: 'Failed to fetch system status' })
      } finally {
        setLoading(false)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const isHealthy = statusData?.status === 'healthy'

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>System Status</h2>
      </div>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <p>Loading system status...</p>
        </div>
      ) : (
        <>
          <div className="status-grid">
            <div className={`status-card ${isHealthy ? 'healthy' : 'warning'}`}>
              <div className="status-icon">
                {isHealthy ? <Activity size={32} /> : <AlertCircle size={32} />}
              </div>
              <h3>API Status</h3>
              <p>{isHealthy ? 'Healthy' : 'Unhealthy'}</p>
              <small>{statusData?.message || 'Checking systems...'}</small>
            </div>

            <div className="status-card">
              <div className="status-icon">
                <Zap size={32} />
              </div>
              <h3>Guppy Core</h3>
              <p>{statusData?.guppy_core_available ? 'Available' : 'Not Available'}</p>
              <small>{statusData?.guppy_core_available ? 'Core services ready' : 'Limited functionality'}</small>
            </div>

            <div className="status-card">
              <div className="status-icon">
                <Activity size={32} />
              </div>
              <h3>Memory</h3>
              <p>Running</p>
              <small>Backend is operational</small>
            </div>

            <div className="status-card">
              <div className="status-icon">
                <Zap size={32} />
              </div>
              <h3>Voice System</h3>
              <p>{statusData?.voice_available ? 'Available' : 'Not Available'}</p>
              <small>{statusData?.voice_available ? 'Voice features enabled' : 'Voice features disabled'}</small>
            </div>
          </div>

          <div className="status-details">
            <h3>Detailed Status</h3>
            <pre>{JSON.stringify(statusData, null, 2)}</pre>
          </div>
        </>
      )}
    </div>
  )
}
