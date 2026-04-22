import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  MessageCircle,
  Package,
  Library,
  Cpu,
  Wrench,
  Volume2,
  Palette,
  Shield,
  Activity,
  Menu,
  X,
  LogOut,
} from 'lucide-react'
import { useAppStore } from '../store'
import './Sidebar.css'

const navItems = [
  { path: '/', label: 'Assistant', icon: MessageCircle },
  { path: '/instances', label: 'Instances', icon: Package },
  { path: '/library', label: 'Library', icon: Library },
  { path: '/models', label: 'Models', icon: Cpu },
  { path: '/tools', label: 'Tools', icon: Wrench },
  { path: '/voices', label: 'Voices', icon: Volume2 },
  { path: '/themes', label: 'Themes', icon: Palette },
]

const adminItems = [
  { path: '/admin', label: 'Admin Panel', icon: Shield },
  { path: '/status', label: 'Status', icon: Activity },
]

export default function Sidebar() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const { sidebarOpen, setSidebarOpen } = useAppStore()

  const handleLogout = () => {
    localStorage.removeItem('accessToken')
    window.location.href = '/login'
  }

  return (
    <>
      <button className="sidebar-toggle" onClick={() => setMobileOpen(!mobileOpen)}>
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''} ${sidebarOpen ? 'expanded' : 'collapsed'}`}>
        <div className="sidebar-header">
          <h1 className="sidebar-title">Guppy</h1>
          <button
            className="sidebar-collapse-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title={sidebarOpen ? 'Collapse' : 'Expand'}
          >
            {sidebarOpen ? '▶' : '◀'}
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                  onClick={() => setMobileOpen(false)}
                >
                  <Icon size={20} className="nav-icon" />
                  {sidebarOpen && <span className="nav-label">{item.label}</span>}
                </Link>
              )
            })}
          </div>

          <div className="nav-divider" />

          <div className="nav-section">
            {adminItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                  onClick={() => setMobileOpen(false)}
                >
                  <Icon size={20} className="nav-icon" />
                  {sidebarOpen && <span className="nav-label">{item.label}</span>}
                </Link>
              )
            })}
          </div>
        </nav>

        <div className="sidebar-footer">
          <button className="logout-btn" onClick={handleLogout} title="Logout">
            <LogOut size={18} />
            {sidebarOpen && <span>Logout</span>}
          </button>
          <div className="sidebar-version">
            {sidebarOpen && <span>v1.0.0</span>}
          </div>
        </div>
      </aside>
    </>
  )
}
