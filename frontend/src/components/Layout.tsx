import { Archive, BarChart3, Inbox, LogOut, Network, Plus, ShieldAlert } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { logOut } from '../auth'
import { ROLE_HOME, ROLE_LABEL, useRole, type Role } from '../role'
import { Logo } from './Logo'

const HOME_ICON = { adjuster: Inbox, siu: ShieldAlert, manager: BarChart3 }
const common: { to: string; label: string; icon: typeof Archive; end?: boolean }[] = [
  { to: '/closed', label: 'Closed claims', icon: Archive },
  { to: '/network', label: 'Red String', icon: Network },
  { to: '/new', label: 'New claim', icon: Plus },
]

export function Layout() {
  const { role, setRole } = useRole()
  const go = useNavigate()
  const nav = [{ ...ROLE_HOME[role], icon: HOME_ICON[role], end: true }, ...common]
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
            <label className="flex items-center gap-2">
              <span className="hidden lg:inline">View as</span>
              <select value={role} aria-label="View as"
                onChange={(e) => { const r = e.target.value as Role; setRole(r); go(ROLE_HOME[r].to) }}
                className="rounded-md bg-panel px-2 py-1 text-xs text-text ring-1 ring-line outline-none">
                {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </select>
            </label>
            <button onClick={logOut} className="hover:text-text" title="Sign out"><LogOut size={16} /></button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6"><Outlet /></main>
    </div>
  )
}
