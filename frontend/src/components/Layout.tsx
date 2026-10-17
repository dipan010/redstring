import { Inbox, LogOut, Network, Plus } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { logOut, useAuth } from '../auth'
import { Logo } from './Logo'

const nav = [
  { to: '/', label: 'Queue', icon: Inbox, end: true },
  { to: '/network', label: 'Red String', icon: Network },
  { to: '/new', label: 'New claim', icon: Plus },
]

export function Layout() {
  const { user } = useAuth()
  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-ink/90 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 h-14 flex items-center gap-6">
          <NavLink to="/"><Logo /></NavLink>
          <nav className="flex gap-1 text-sm">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => `flex items-center gap-1.5 rounded-md px-3 py-1.5 transition ${isActive ? 'bg-panel-2 text-text' : 'text-muted hover:text-text'}`}>
                <Icon size={15} /> <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-muted">
            <span className="hidden md:inline">{user?.isAnonymous ? 'Demo adjuster' : user?.displayName || user?.email}</span>
            <button onClick={logOut} className="hover:text-text" title="Sign out"><LogOut size={16} /></button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6"><Outlet /></main>
    </div>
  )
}
