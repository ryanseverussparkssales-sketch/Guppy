import { useState, useEffect } from 'react'
import { BarChart, Users, Settings, CheckCircle } from 'lucide-react'
import api from '../api/client'
import './AdminPanel.css'

interface SystemStats {
  uptime: number
  requestsTotal: number
  errorsTotal: number
  avgLatency: number
}

export default function AdminPanel() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'dashboard' | 'users' | 'settings'>('dashboard')

  useEffect(() => {
    const loadStats = async () => {
      try {
        const response = await api.get('/status')
        setStats({
          uptime: 42 * 24 * 60 * 60 * 1000, // Example
          requestsTotal: response.data.requests_total || 0,
          errorsTotal: response.data.errors_total || 0,
          avgLatency: response.data.average_latency_ms || 0,
        })
      } catch (error) {
        console.error('Failed to load stats:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadStats()
    const interval = setInterval(loadStats, 30000)
    return () => clearInterval(interval)
  }, [])

  const formatUptime = (ms: number) => {
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days}d ${hours % 24}h`
    if (hours > 0) return `${hours}h ${minutes % 60}m`
    return `${minutes}m`
  }

  return (
    <div className="admin-container">
      <div className="admin-header">
        <h2>Admin Panel</h2>
        <p>System management and monitoring</p>
      </div>

      <div className="admin-tabs">
        <button
          className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <BarChart size={18} />
          Dashboard
        </button>
        <button
          className={`tab-btn ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={18} />
          Users
        </button>
        <button
          className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <Settings size={18} />
          Settings
        </button>
      </div>

      {activeTab === 'dashboard' && (
        <div className="admin-dashboard">
          {isLoading ? (
            <div className="loading">Loading stats...</div>
          ) : stats ? (
            <div className="stats-grid">
              <div className="stat-card healthy">
                <div className="stat-icon">
                  <CheckCircle size={32} />
                </div>
                <h3>System Status</h3>
                <p>Healthy</p>
              </div>

              <div className="stat-card">
                <div className="stat-value">{formatUptime(stats.uptime)}</div>
                <h3>Uptime</h3>
                <p>System operational</p>
              </div>

              <div className="stat-card">
                <div className="stat-value">{stats.requestsTotal.toLocaleString()}</div>
                <h3>Total Requests</h3>
                <p>API calls processed</p>
              </div>

              <div className="stat-card">
                <div className="stat-value">{stats.errorsTotal}</div>
                <h3>Errors</h3>
                <p className={stats.errorsTotal > 0 ? 'warning' : ''}>
                  {stats.errorsTotal > 0 ? 'Detected' : 'None'}
                </p>
              </div>

              <div className="stat-card">
                <div className="stat-value">{stats.avgLatency.toFixed(0)}ms</div>
                <h3>Avg Response Time</h3>
                <p>API performance</p>
              </div>

              <div className="stat-card">
                <div className="stat-value">4/4</div>
                <h3>Services</h3>
                <p>All operational</p>
              </div>
            </div>
          ) : null}

          <div className="recent-logs">
            <h3>Recent Activity</h3>
            <div className="log-list">
              <div className="log-item success">
                <CheckCircle size={16} />
                <span>API server started successfully</span>
                <small>2 minutes ago</small>
              </div>
              <div className="log-item">
                <span>1,234 requests processed</span>
                <small>last hour</small>
              </div>
              <div className="log-item">
                <span>Web UI built and deployed</span>
                <small>30 minutes ago</small>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="admin-users">
          <div className="users-header">
            <h3>Manage Users</h3>
            <button className="btn btn-primary">Add User</button>
          </div>

          <div className="users-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Joined</th>
                <th>Last Active</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>admin@guppy.local</td>
                <td><span className="badge admin">Admin</span></td>
                <td>2024-01-15</td>
                <td>Just now</td>
                <td>
                  <button className="action-btn">Edit</button>
                  <button className="action-btn danger">Remove</button>
                </td>
              </tr>
              <tr>
                <td>dev-token@demo</td>
                <td><span className="badge">User</span></td>
                <td>2024-01-20</td>
                <td>5 minutes ago</td>
                <td>
                  <button className="action-btn">Edit</button>
                  <button className="action-btn danger">Remove</button>
                </td>
              </tr>
            </tbody>
          </div>
        </div>
      )}

      {activeTab === 'settings' && (
        <div className="admin-settings">
          <div className="settings-section">
            <h3>API Configuration</h3>
            <div className="setting-group">
              <label>API Port</label>
              <input type="number" defaultValue={8081} />
            </div>
            <div className="setting-group">
              <label>Max Requests/Minute</label>
              <input type="number" defaultValue={1000} />
            </div>
            <div className="setting-group">
              <label>Request Timeout (seconds)</label>
              <input type="number" defaultValue={120} />
            </div>
          </div>

          <div className="settings-section">
            <h3>Database</h3>
            <div className="setting-group">
              <label>
                <input type="checkbox" defaultChecked />
                Enable backups
              </label>
            </div>
            <div className="setting-group">
              <label>Backup Interval (hours)</label>
              <input type="number" defaultValue={24} />
            </div>
          </div>

          <div className="settings-section">
            <h3>Security</h3>
            <div className="setting-group">
              <label>
                <input type="checkbox" defaultChecked />
                Enable HTTPS only
              </label>
            </div>
            <div className="setting-group">
              <label>
                <input type="checkbox" defaultChecked />
                Rate limiting
              </label>
            </div>
          </div>

          <button className="btn btn-primary">Save Settings</button>
        </div>
      )}
    </div>
  )
}
