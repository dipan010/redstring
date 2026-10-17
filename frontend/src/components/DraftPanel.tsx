import { Copy, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'

const KINDS = [
  { kind: 'request_info', label: 'Request info email' },
  { kind: 'investigation_referral', label: 'SIU referral memo' },
  { kind: 'approval', label: 'Approval email' },
] as const

export function DraftPanel({ claimId }: { claimId: string }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const draft = async (kind: string) => {
    setBusy(kind); setError('')
    try { setText((await api<{ text: string }>(`/claims/${claimId}/draft`, { kind })).text) }
    catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <p className="text-sm font-medium">Draft correspondence</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {KINDS.map(({ kind, label }) => (
          <button key={kind} onClick={() => draft(kind)} disabled={!!busy}
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-xs hover:border-string disabled:opacity-50">
            {busy === kind && <Loader2 size={12} className="animate-spin" />} {label}
          </button>
        ))}
      </div>
      {error && <p className="mt-2 text-xs text-string">{error}</p>}
      {text && (
        <div className="relative mt-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10}
            className="w-full rounded-md bg-ink p-3 font-mono text-xs leading-relaxed outline-none ring-1 ring-line" />
          <button onClick={() => navigator.clipboard.writeText(text)} title="Copy"
            className="absolute right-2 top-2 rounded p-1 text-muted hover:text-text"><Copy size={14} /></button>
        </div>
      )}
    </div>
  )
}
