import { useAppStore } from '../store'
import { Activity } from 'lucide-react'
import './StatusBar.css'

export default function StatusBar() {
  const { status } = useAppStore()

  const isHealthy = status && typeof status === 'object' && (status as any).status === 'healthy'

  return (
    <footer className="statusbar">
      <div className="statusbar-content">
        <div className="statusbar-item">
          <Activity size={14} className={`status-icon ${isHealthy ? 'healthy' : 'unhealthy'}`} />
          <span className="status-text">
            {isHealthy ? 'API Connected' : 'Connecting...'}
          </span>
        </div>

        <div className="statusbar-spacer"></div>

        <div className="statusbar-info">
          <span className="info-text">Guppy API v1.0</span>
        </div>
      </div>
    </footer>
  )
}
