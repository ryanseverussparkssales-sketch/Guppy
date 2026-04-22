import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  MessageCircle,
  Package,
  Library,
  Cpu,
  Wrench,
  Volume2,
  Settings,
  Activity,
  Menu,
  X,
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
  { path: '/settings', label: 'Settings', icon: Settings },
  { path: '/status', label: 'Status', icon: Activity },
]

export default function Sidebar() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const { sidebarOpen, setSidebarOpen } = useAppStore()

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
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-version">
            {sidebarOpen && <span>v1.0.0</span>}
          </div>
        </div>
      </aside>
    </>
  )
}
