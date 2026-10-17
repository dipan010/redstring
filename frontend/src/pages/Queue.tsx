import { AlertTriangle, CheckCircle2, Clock, Inbox, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { RiskPill } from '../components/ScoreRing'
import { inr } from '../format'
import { useQueue } from '../hooks'
import type { Claim } from '../types'

const ACTION_STYLE: Record<string, string> = {
  investigate: 'text-string',
  request_info: 'text-warn',
  fast_track: 'text-ok',
}

function Tile({ icon: Icon, label, value, tone = '' }: { icon: typeof Inbox; label: string; value: string | number; tone?: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="flex items-center gap-2 text-xs text-muted"><Icon size={14} /> {label}</div>
      <div className={`mt-2 text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
    </div>
  )
}

export function Queue() {
  const claims = useQueue()
  if (!claims) return <Loader2 className="animate-spin text-muted" />

  const ready = claims.filter((c) => c.status === 'ready')
  const sorted = [...claims].sort((a, b) => (b.risk?.score ?? 101) - (a.risk?.score ?? 101))
  const avgS = ready.length ? ready.reduce((s, c) => s + (c.processingMs ?? 0), 0) / ready.length / 1000 : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Claims queue</h1>
        <p className="text-sm text-muted">Sorted by risk. Updates live as agents finish.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile icon={Inbox} label="In queue" value={claims.length} />
        <Tile icon={AlertTriangle} label="Refer to SIU" value={ready.filter((c) => c.risk?.action === 'investigate').length} tone="text-string" />
        <Tile icon={CheckCircle2} label="Fast-track" value={ready.filter((c) => c.risk?.action === 'fast_track').length} tone="text-ok" />
        <Tile icon={Clock} label="Avg. triage time" value={avgS ? `${avgS.toFixed(0)}s` : '—'} />
      </div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-panel text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">Risk</th>
              <th className="px-4 py-2.5 font-medium">Claim</th>
              <th className="px-4 py-2.5 font-medium">Claimant</th>
              <th className="px-4 py-2.5 font-medium">Vehicle</th>
              <th className="px-4 py-2.5 font-medium text-right">Amount</th>
              <th className="px-4 py-2.5 font-medium">Flags</th>
              <th className="px-4 py-2.5 font-medium">Recommendation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {sorted.map((c: Claim) => (
              <tr key={c.id} className="hover:bg-panel/60">
                <td className="px-4 py-3"><RiskPill score={c.risk?.score} band={c.risk?.band} /></td>
                <td className="px-4 py-3 font-mono text-xs">
                  <Link to={`/claims/${c.id}`} className="hover:text-string">{c.claimNumber}</Link>
                </td>
                <td className="px-4 py-3">{c.claimantName ?? '—'}</td>
                <td className="px-4 py-3 font-mono text-xs text-muted">{c.vehicleRegistration ?? '—'}</td>
                <td className="px-4 py-3 text-right tabular-nums">{inr(c.claimAmount)}</td>
                <td className="px-4 py-3 text-muted">{c.status === 'ready' ? c.flags.filter((f) => f.status !== 'dismissed').length : ''}</td>
                <td className="px-4 py-3">
                  {c.status === 'ready' ? (
                    <span className={ACTION_STYLE[c.risk?.action ?? ''] ?? ''}>{c.risk?.actionLabel}</span>
                  ) : c.status === 'error' ? (
                    <span className="text-string">Processing failed</span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-muted"><Loader2 size={13} className="animate-spin" /> Agents working…</span>
                  )}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-muted">No claims yet. <Link to="/new" className="text-string">Submit one</Link>.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
