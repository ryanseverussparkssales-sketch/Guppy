import { Activity, Zap } from 'lucide-react'
import { useAppStore } from '../store'
import './StatusView.css'

export default function StatusView() {
  const { status } = useAppStore()

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>System Status</h2>
      </div>

      <div className="status-grid">
        <div className="status-card healthy">
          <div className="status-icon">
            <Activity size={32} />
          </div>
          <h3>API Status</h3>
          <p>Healthy</p>
          <small>All systems operational</small>
        </div>

        <div className="status-card healthy">
          <div className="status-icon">
            <Zap size={32} />
          </div>
          <h3>Performance</h3>
          <p>Excellent</p>
          <small>Response time: 45ms</small>
        </div>

        <div className="status-card">
          <div className="status-icon">
            <Activity size={32} />
          </div>
          <h3>Memory Usage</h3>
          <p>2.3 GB / 8 GB</p>
          <small>28% utilized</small>
        </div>

        <div className="status-card">
          <div className="status-icon">
            <Zap size={32} />
          </div>
          <h3>Uptime</h3>
          <p>42 days</p>
          <small>100% reliable</small>
        </div>
      </div>

      <div className="status-details">
        <h3>Raw Status</h3>
        <pre>{JSON.stringify(status, null, 2)}</pre>
      </div>
    </div>
  )
}
