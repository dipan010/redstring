import { ExternalLink, Loader2, ShieldAlert } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { RiskPill } from '../components/ScoreRing'
import { inr } from '../format'
import { useQueue } from '../hooks'
import { LINE_LABEL, lineOf, PROVIDER_KINDS, providerOf } from '../lines'
import type { Claim } from '../types'

const KIND: Record<string, string> = {
  bank: 'shared bank a/c', phone: 'shared phone', email: 'shared email', photo: 'reused photo', invoice: 'reused invoice',
  bill: 'reused hospital bill', garage: 'same garage', hospital: 'same hospital', doctor: 'same doctor',
  contractor: 'same contractor', address: 'same address', vehicle: 'same vehicle',
}

type Past = { id: string; number: string; name: string }
type Case = { open: Claim[]; past: Past[]; signals: Set<string>; provider: string; amount: number; top: number }

/** Groups referred claims into possible rings: claims joined by shared people, accounts or documents,
 *  or by a provider with confirmed fraud. Single referrals are listed separately. */
function buildCases(claims: Claim[]): { rings: Case[]; singles: Claim[] } {
  const referred = claims.filter((c) => c.status === 'ready' && c.risk?.action === 'investigate')
  const ids = new Set(referred.map((c) => c.id))
  const parent = new Map<string, string>()
  const find = (x: string): string => {
    if (!parent.has(x)) parent.set(x, x)
    const p = parent.get(x)!
    if (p === x) return x
    const root = find(p)
    parent.set(x, root)
    return root
  }
  const union = (a: string, b: string) => parent.set(find(a), find(b))
  const past = new Map<string, Past>()
  const signals = new Map<string, Set<string>>()

  for (const c of referred) {
    find(c.id)
    for (const l of c.links ?? []) {
      const kinds = l.shared.map((s) => s.kind)
      const personal = kinds.some((k) => !PROVIDER_KINDS.includes(k))
      const joinsOpen = ids.has(l.claimId) && personal
      const joinsFraud = l.fraudConfirmed && (personal || kinds.some((k) => PROVIDER_KINDS.includes(k)))
      if (!joinsOpen && !joinsFraud) continue
      union(c.id, l.claimId)
      if (l.fraudConfirmed) past.set(l.claimId, { id: l.claimId, number: l.claimNumber ?? l.claimId, name: l.claimantName ?? '' })
      const set = signals.get(c.id) ?? new Set<string>()
      kinds.forEach((k) => set.add(k))
      signals.set(c.id, set)
    }
  }

  const groups = new Map<string, Case>()
  const touch = (root: string) => {
    if (!groups.has(root)) groups.set(root, { open: [], past: [], signals: new Set(), provider: '-', amount: 0, top: 0 })
    return groups.get(root)!
  }
  for (const c of referred) {
    const g = touch(find(c.id))
    g.open.push(c)
    g.amount += c.claimAmount ?? 0
    g.top = Math.max(g.top, c.risk?.score ?? 0)
    signals.get(c.id)?.forEach((k) => g.signals.add(k))
  }
  for (const p of past.values()) touch(find(p.id)).past.push(p)
  for (const g of groups.values()) {
    const counts = new Map<string, number>()
    g.open.forEach((c) => { const p = providerOf(c); if (p !== '-') counts.set(p, (counts.get(p) ?? 0) + 1) })
    g.provider = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? '-'
  }
  const all = [...groups.values()].filter((g) => g.open.length > 0)
  const rings = all.filter((g) => g.open.length > 1 || g.past.length > 0).sort((a, b) => b.open.length - a.open.length || b.amount - a.amount)
  const singles = all.filter((g) => !rings.includes(g)).flatMap((g) => g.open).sort((a, b) => (b.risk?.score ?? 0) - (a.risk?.score ?? 0))
  return { rings, singles }
}

export function SiuBoard() {
  const { claims, error } = useQueue()
  const { rings, singles } = useMemo(() => buildCases(claims ?? []), [claims])
  if (error) return <p className="text-string">Couldn't load cases: {error}</p>
  if (!claims) return <Loader2 className="animate-spin text-muted" />
  const referred = rings.reduce((n, r) => n + r.open.length, 0) + singles.length
  const atStake = rings.reduce((n, r) => n + r.amount, 0) + singles.reduce((n, c) => n + (c.claimAmount ?? 0), 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold"><ShieldAlert size={18} /> SIU case board</h1>
        <p className="text-sm text-muted">
          {referred} claims referred to the Special Investigation Unit ({inr(atStake)} at stake), grouped into possible rings
          where they share people, accounts or documents, or a provider with confirmed fraud.
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Possible rings <span className="text-muted">({rings.length})</span></h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {rings.map((r) => (
            <article key={r.open[0].id} className="rounded-xl border border-string/30 bg-panel p-4">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{r.provider !== '-' ? r.provider : 'Linked claimants'}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {r.open.length} open claim{r.open.length > 1 ? 's' : ''} · {inr(r.amount)} at stake
                    {r.past.length > 0 && ` · ${r.past.length} confirmed fraud in history`}
                    {' · '}{[...new Set(r.open.map((c) => LINE_LABEL[lineOf(c)]))].join(', ')}
                  </p>
                </div>
                <RiskPill score={r.top} band="high" />
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {[...r.signals].map((k) => (
                  <span key={k} className="rounded border border-string/30 px-1.5 text-[11px] text-string">{KIND[k] ?? k}</span>
                ))}
              </div>
              <ul className="mt-3 divide-y divide-line rounded-lg border border-line text-sm">
                {r.open.map((c) => (
                  <li key={c.id} className="flex items-center gap-3 px-3 py-2">
                    <Link to={`/claims/${c.id}`} className="font-mono text-xs hover:text-string">{c.claimNumber}</Link>
                    <span className="truncate">{c.claimantName}</span>
                    <span className="ml-auto tabular-nums text-muted">{inr(c.claimAmount)}</span>
                    <RiskPill score={c.risk?.score} band={c.risk?.band} />
                  </li>
                ))}
                {r.past.map((p) => (
                  <li key={p.id} className="flex items-center gap-3 px-3 py-2 text-muted">
                    <Link to={`/claims/${p.id}`} className="font-mono text-xs hover:text-string">{p.number}</Link>
                    <span className="truncate">{p.name}</span>
                    <span className="ml-auto rounded bg-string/15 px-1.5 text-[10px] font-semibold uppercase text-string">confirmed fraud</span>
                  </li>
                ))}
              </ul>
              <Link to={`/network?focus=${r.open[0].id}`} className="mt-3 inline-flex items-center gap-1 text-xs text-string">
                Open in Red String view <ExternalLink size={12} />
              </Link>
            </article>
          ))}
          {rings.length === 0 && <p className="text-sm text-muted">No linked cases right now.</p>}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Individual referrals <span className="text-muted">({singles.length})</span></h2>
        <ul className="divide-y divide-line rounded-lg border border-line bg-panel text-sm">
          {singles.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <RiskPill score={c.risk?.score} band={c.risk?.band} />
              <Link to={`/claims/${c.id}`} className="font-mono text-xs hover:text-string">{c.claimNumber}</Link>
              <span>{c.claimantName}</span>
              <span className="rounded border border-line px-1 text-[10px] uppercase text-muted">{LINE_LABEL[lineOf(c)]}</span>
              <span className="text-muted">{c.flags.filter((f) => f.severity === 'high')[0]?.title}</span>
              <span className="ml-auto tabular-nums text-muted">{inr(c.claimAmount)}</span>
            </li>
          ))}
          {singles.length === 0 && <li className="px-4 py-6 text-center text-muted">None.</li>}
        </ul>
      </section>
    </div>
  )
}
