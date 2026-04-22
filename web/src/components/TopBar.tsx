import { useLocation } from 'react-router-dom'
import { Bell, User } from 'lucide-react'
import './TopBar.css'

const routeTitles: Record<string, string> = {
  '/': 'Assistant',
  '/instances': 'Instances',
  '/library': 'Library',
  '/models': 'Models',
  '/tools': 'Tools',
  '/voices': 'Voices',
  '/settings': 'Settings',
  '/status': 'Status',
}

export default function TopBar() {
  const location = useLocation()
  const title = routeTitles[location.pathname] || 'Guppy'

  return (
    <header className="topbar">
      <div className="topbar-left">
        <h2 className="topbar-title">{title}</h2>
      </div>

      <div className="topbar-right">
        <button className="topbar-btn" title="Notifications">
          <Bell size={18} />
        </button>

        <div className="topbar-divider"></div>

        <button className="topbar-btn" title="User Menu">
          <User size={18} />
        </button>
      </div>
    </header>
  )
}
