import { ArrowRight, FileSearch, Network, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { signInDemo, signInGoogle } from '../auth'
import { Logo } from '../components/Logo'

export function Login() {
  const [error, setError] = useState('')
  const go = (fn: () => Promise<unknown>) => fn().catch((e) => setError(e.message))
  return (
    <div className="min-h-full flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-xl">
        <Logo size={30} />
        <h1 className="mt-8 text-4xl font-bold leading-tight tracking-tight">
          Connect the dots on <span className="text-string">every claim</span>.
        </h1>
        <p className="mt-4 text-muted leading-relaxed">
          Rules check claims one at a time. Fraud works in networks. Redstring reads every document,
          checks it against the policy, spots inconsistencies and links each claim to the others, with
          evidence an auditor would accept.
        </p>
        <ul className="mt-8 grid gap-3 sm:grid-cols-3 text-sm">
          {[
            [FileSearch, 'Reads PDFs & photos with Gemini'],
            [ShieldCheck, 'Cites the exact policy clause'],
            [Network, 'Exposes linked claims & rings'],
          ].map(([Icon, t]: any) => (
            <li key={t} className="flex items-start gap-2 rounded-lg border border-line bg-panel p-3">
              <Icon size={16} className="mt-0.5 shrink-0 text-string" /> {t}
            </li>
          ))}
        </ul>
        <div className="mt-10 flex flex-wrap gap-3">
          <button onClick={() => go(signInDemo)}
            className="inline-flex items-center gap-2 rounded-lg bg-string px-5 py-3 font-medium text-white hover:brightness-110">
            Enter demo as adjuster <ArrowRight size={16} />
          </button>
          <button onClick={() => go(signInGoogle)}
            className="rounded-lg border border-line px-5 py-3 font-medium hover:border-muted">Sign in with Google</button>
        </div>
        {error && <p className="mt-4 text-sm text-string">{error}</p>}
        <p className="mt-10 text-xs text-muted">Demo data only. All claimants, policies and garages are fictional.</p>
      </div>
    </div>
  )
}
