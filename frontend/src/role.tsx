import { createContext, useContext, useState, type ReactNode } from 'react'

/** A view switch for the demo (not access control): what each persona looks at first. */
export type Role = 'adjuster' | 'siu' | 'manager'
export const ROLE_LABEL: Record<Role, string> = { adjuster: 'Claims adjuster', siu: 'SIU investigator', manager: 'Claims manager' }
export const ROLE_HOME: Record<Role, { to: string; label: string }> = {
  adjuster: { to: '/', label: 'Queue' },
  siu: { to: '/siu', label: 'Case board' },
  manager: { to: '/manager', label: 'Overview' },
}

const read = (): Role => {
  try {
    const r = localStorage.getItem('rs-role')
    return r === 'siu' || r === 'manager' ? r : 'adjuster'
  } catch {
    return 'adjuster'
  }
}

const Ctx = createContext<{ role: Role; setRole: (r: Role) => void }>({ role: 'adjuster', setRole: () => {} })

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, set] = useState<Role>(read)
  const setRole = (r: Role) => {
    set(r)
    try { localStorage.setItem('rs-role', r) } catch { /* private mode: keep it in memory */ }
  }
  return <Ctx.Provider value={{ role, setRole }}>{children}</Ctx.Provider>
}

export const useRole = () => useContext(Ctx)
