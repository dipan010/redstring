import { Loader2 } from 'lucide-react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { Layout } from './components/Layout'
import { ClaimDetail } from './pages/ClaimDetail'
import { ClosedClaims } from './pages/ClosedClaims'
import { Manager } from './pages/Manager'
import { SiuBoard } from './pages/SiuBoard'
import { RoleProvider } from './role'
import { Login } from './pages/Login'
import { Network } from './pages/Network'
import { NewClaim } from './pages/NewClaim'
import { Queue } from './pages/Queue'

function Gate() {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin text-muted" /></div>
  if (!user) return <Login />
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Queue />} />
        <Route path="new" element={<NewClaim />} />
        <Route path="closed" element={<ClosedClaims />} />
        <Route path="siu" element={<SiuBoard />} />
        <Route path="manager" element={<Manager />} />
        <Route path="claims/:id" element={<ClaimDetail />} />
        <Route path="network" element={<Network />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider><RoleProvider><Gate /></RoleProvider></AuthProvider>
    </BrowserRouter>
  )
}
