import { useTheme } from '../hooks/useTheme'
import { Moon, Sun } from 'lucide-react'
import './TopBar.css'

export default function TopBar() {
  const { theme, setThemeMode } = useTheme()

  const toggleTheme = () => {
    setThemeMode(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <header className="topbar">
      <div className="topbar-content">
        <h2 className="topbar-title">Welcome</h2>
        <button className="topbar-theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </div>
    </header>
  )
}
