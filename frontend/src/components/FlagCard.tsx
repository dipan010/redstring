import { Check, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { severityStyles } from '../format'
import type { Flag } from '../types'

export function FlagCard({ claimId, flag, readOnly = false }: { claimId: string; flag: Flag; readOnly?: boolean }) {
  const [busy, setBusy] = useState(false)
  const set = async (status: Flag['status']) => {
    setBusy(true)
    try { await api(`/claims/${claimId}/flags/${flag.id}`, { status }) } finally { setBusy(false) }
  }
  const dim = flag.status === 'dismissed' ? 'opacity-45' : ''
  return (
    <li className={`rounded-lg border border-line bg-panel p-3 ${dim}`}>
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 rounded border px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide ${severityStyles[flag.severity]}`}>
          {flag.severity}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{flag.title}</p>
          <p className="mt-1 text-sm text-muted">{flag.evidence}</p>
          <p className="mt-1.5 text-[11px] font-mono text-muted/80">
            {flag.agent}{flag.source ? ` · ${flag.source}` : ''}{flag.status !== 'open' ? ` · ${flag.status}${readOnly ? ' by SIU' : ' by adjuster'}` : ''}
          </p>
        </div>
        {!readOnly && <div className="flex gap-1">
          {flag.status === 'open' ? (
            <>
              <button disabled={busy} onClick={() => set('confirmed')} title="Confirm flag"
                className="rounded p-1 text-muted hover:bg-panel-2 hover:text-string"><Check size={15} /></button>
              <button disabled={busy} onClick={() => set('dismissed')} title="Dismiss flag"
                className="rounded p-1 text-muted hover:bg-panel-2 hover:text-text"><X size={15} /></button>
            </>
          ) : (
            <button disabled={busy} onClick={() => set('open')} title="Undo"
              className="rounded p-1 text-muted hover:bg-panel-2 hover:text-text"><RotateCcw size={14} /></button>
          )}
        </div>}
      </div>
    </li>
  )
}
