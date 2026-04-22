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
  const [isMobileOpen, setIsMobileOpen] = useState(false)

  const handleLogout = () => {
    localStorage.removeItem('accessToken')
  }

  const isActive = (path: string) => {
    return location.pathname === path
  }

  return (
    <>
      <button className="sidebar-mobile-toggle" onClick={() => setIsMobileOpen(!isMobileOpen)}>
        {isMobileOpen ? <X size={24} /> : <Menu size={24} />}
      </button>
      <aside className={`sidebar ${isMobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <h1 className="sidebar-title">Guppy</h1>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            <div className="nav-section-title">Main</div>
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                onClick={() => setIsMobileOpen(false)}
              >
                <item.icon size={20} />
                <span>{item.label}</span>
              </Link>
            ))}
          </div>

          <div className="nav-section">
            <div className="nav-section-title">Admin</div>
            {adminItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                onClick={() => setIsMobileOpen(false)}
              >
                <item.icon size={20} />
                <span>{item.label}</span>
              </Link>
            ))}
          </div>
        </nav>

        <button className="sidebar-logout" onClick={handleLogout}>
          <LogOut size={20} />
          <span>Logout</span>
        </button>
      </aside>
    </>
  )
}
