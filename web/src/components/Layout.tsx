import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import StatusBar from './StatusBar'
import './Layout.css'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="layout">
      <Sidebar />
      <div className="layout-main">
        <TopBar />
        <main className="layout-content">
          {children}
        </main>
        <StatusBar />
      </div>
    </div>
  )
}
