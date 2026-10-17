import { Loader2 } from 'lucide-react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { Layout } from './components/Layout'
import { ClaimDetail } from './pages/ClaimDetail'
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
      <AuthProvider><Gate /></AuthProvider>
    </BrowserRouter>
  )
}
