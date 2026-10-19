import { BarChart3, Loader2 } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { inr } from '../format'
import { useClosed, useQueue } from '../hooks'
import { LINE_LABEL, lineOf, providerOf, type Line } from '../lines'
import type { Claim } from '../types'

// Outcome colours: validated together on the dark surface (adjacent CVD ΔE 6.3, so every mark also
// carries an icon and a text label, never colour alone).
const OUTCOME = [
  { key: 'fast_track', label: 'Fast-track', icon: '✓', color: '#30a46c' },
  { key: 'request_info', label: 'Request info', icon: '?', color: '#c98500' },
  { key: 'investigate', label: 'Refer to SIU', icon: '!', color: '#e5484d' },
] as const

// USD per 1M tokens (input, output incl. thinking); measured usage is stored on each claim.
const PRICE: Record<string, [number, number]> = {
  'gemini-3.5-flash': [1.5, 9], 'gemini-2.5-flash': [0.3, 2.5], 'gemini-2.5-flash-lite': [0.1, 0.4],
}
const USD_INR = 84

function aiCost(c: Claim & { usage?: { byModel?: Record<string, { in: number; out: number; think: number }> } }): number | null {
  const by = c.usage?.byModel
  if (!by) return null
  let usd = 0
  for (const [m, u] of Object.entries(by)) {
    const [pi, po] = PRICE[m] ?? PRICE['gemini-3.5-flash']
    usd += (u.in * pi + (u.out + u.think) * po) / 1e6
  }
  return usd * USD_INR
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  )
}

/** Small hover tooltip shared by the charts. */
function useTip() {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const on = (text: string) => ({
    onMouseMove: (e: React.MouseEvent) => setTip({ x: e.clientX, y: e.clientY, text }),
    onMouseLeave: () => setTip(null),
    onFocus: (e: React.FocusEvent) => { const r = (e.target as HTMLElement).getBoundingClientRect(); setTip({ x: r.left + r.width / 2, y: r.top, text }) },
    onBlur: () => setTip(null),
    tabIndex: 0,
    'aria-label': text,
  })
  const node: ReactNode = tip && (
    <div role="tooltip" className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full rounded-md border border-line bg-ink px-2.5 py-1.5 text-xs shadow-lg"
      style={{ left: tip.x, top: tip.y - 10 }}>{tip.text}</div>
  )
  return { on, node }
}

function Card({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-panel p-5">
      <h2 className="text-sm font-semibold">{title}</h2>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

export function Manager() {
  const { claims: open, error } = useQueue()
  const { claims: closed } = useClosed()
  const tip = useTip()

  const data = useMemo(() => {
    const ready = (open ?? []).filter((c) => c.status === 'ready' && c.risk)
    const lines = [...new Set(ready.map(lineOf))] as Line[]
    const byLine = lines.map((l) => {
      const rs = ready.filter((c) => lineOf(c) === l)
      return { line: l, total: rs.length, counts: OUTCOME.map((o) => rs.filter((c) => c.risk?.action === o.key).length) }
    })
    const bins = Array.from({ length: 10 }, (_, i) => ({ lo: i * 10, n: ready.filter((c) => Math.min(9, Math.floor((c.risk?.score ?? 0) / 10)) === i).length }))
    const providers = new Map<string, { referred: number; fraud: number }>()
    const bump = (p: string, k: 'referred' | 'fraud') => {
      if (p === '-') return
      const v = providers.get(p) ?? { referred: 0, fraud: 0 }
      v[k] += 1
      providers.set(p, v)
    }
    ready.filter((c) => c.risk?.action === 'investigate').forEach((c) => bump(providerOf(c), 'referred'))
    ;(closed ?? []).filter((c) => c.fraudConfirmed).forEach((c) => bump(providerOf(c), 'fraud'))
    const topProviders = [...providers.entries()].map(([name, v]) => ({ name, ...v, total: v.referred + v.fraud }))
      .sort((a, b) => b.total - a.total).slice(0, 6)
    const costs = ready.map(aiCost).filter((x): x is number => x != null)
    const ms = ready.map((c) => c.processingMs ?? 0).filter(Boolean)
    const sum = (k: string) => ready.filter((c) => c.risk?.action === k).reduce((n, c) => n + (c.claimAmount ?? 0), 0)
    return {
      ready, byLine, bins, topProviders,
      siu: ready.filter((c) => c.risk?.action === 'investigate').length, siuAmt: sum('investigate'),
      ft: ready.filter((c) => c.risk?.action === 'fast_track').length, ftAmt: sum('fast_track'),
      avgS: ms.length ? ms.reduce((a, b) => a + b, 0) / ms.length / 1000 : 0,
      avgCost: costs.length ? costs.reduce((a, b) => a + b, 0) / costs.length : null,
    }
  }, [open, closed])

  if (error) return <p className="text-string">Couldn't load the overview: {error}</p>
  if (!open) return <Loader2 className="animate-spin text-muted" />
  const maxBin = Math.max(1, ...data.bins.map((b) => b.n))
  const maxProv = Math.max(1, ...data.topProviders.map((p) => p.total))

  return (
    <div className="space-y-6">
      {tip.node}
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold"><BarChart3 size={18} /> Claims overview</h1>
        <p className="text-sm text-muted">Open claims triaged by Redstring across all lines of business. Updates live.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Tile label="Claims triaged" value={String(data.ready.length)} />
        <Tile label="Referred to SIU" value={String(data.siu)} sub={`${inr(data.siuAmt)} held for review`} />
        <Tile label="Fast-tracked" value={String(data.ft)} sub={`${inr(data.ftAmt)} ready to settle`} />
        <Tile label="Avg. triage time" value={data.avgS ? `${data.avgS.toFixed(0)}s` : '-'} sub="5 agents per claim" />
        <Tile label="AI cost per claim" value={data.avgCost != null ? `₹${data.avgCost.toFixed(2)}` : '-'} sub="from measured token usage" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Recommendation by line of business" sub="Share of triaged claims in each outcome">
          <ul className="mb-4 flex flex-wrap gap-4 text-xs text-muted" aria-label="Legend">
            {OUTCOME.map((o) => (
              <li key={o.key} className="flex items-center gap-1.5">
                <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-sm text-[9px] font-bold text-ink" style={{ background: o.color }}>{o.icon}</span>
                {o.label}
              </li>
            ))}
          </ul>
          <div className="space-y-4">
            {data.byLine.map((row) => (
              <div key={row.line}>
                <div className="mb-1 flex text-xs"><span>{LINE_LABEL[row.line]}</span><span className="ml-auto text-muted">{row.total} claims</span></div>
                <div className="flex h-7 gap-[2px] overflow-hidden rounded">
                  {row.counts.map((n, i) => n > 0 && (
                    <div key={i} {...tip.on(`${LINE_LABEL[row.line]} · ${OUTCOME[i].label}: ${n} of ${row.total}`)}
                      className="flex items-center justify-center text-[11px] font-semibold text-ink outline-none focus-visible:ring-2 focus-visible:ring-text"
                      style={{ width: `${(n / row.total) * 100}%`, background: OUTCOME[i].color, borderRadius: 4 }}>
                      {n / row.total >= 0.12 ? `${OUTCOME[i].icon} ${n}` : ''}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Risk score distribution" sub="Open claims by risk score (0 to 100)">
          <div className="flex h-44 items-end gap-[2px] border-b border-line">
            {data.bins.map((b) => {
              const color = b.lo >= 60 ? OUTCOME[2].color : b.lo >= 20 ? OUTCOME[1].color : OUTCOME[0].color
              return (
                <div key={b.lo} className="flex h-full flex-1 flex-col justify-end outline-none focus-visible:ring-2 focus-visible:ring-text"
                  {...tip.on(`Risk ${b.lo} to ${b.lo + 9}${b.lo === 90 ? '+' : ''}: ${b.n} claim${b.n === 1 ? '' : 's'}`)}>
                  {b.n > 0 && <span className="mb-1 text-center text-[11px] text-muted">{b.n}</span>}
                  <div style={{ height: `${(b.n / maxBin) * 85}%`, background: color, borderRadius: '4px 4px 0 0', minHeight: b.n ? 4 : 0 }} />
                </div>
              )
            })}
          </div>
          <div className="mt-1 flex text-[11px] text-muted">
            {data.bins.map((b) => <span key={b.lo} className="flex-1 text-center">{b.lo}</span>)}
          </div>
          <p className="mt-2 text-xs text-muted">Below 20 fast-track · 20 to 59 request info · 60 and above refer to SIU</p>
        </Card>
      </div>

      <Card title="Providers with the most risk" sub="Garages, hospitals and contractors: open claims referred to SIU plus confirmed fraud in history">
        <div className="space-y-2.5">
          {data.topProviders.map((p) => (
            <div key={p.name} className="grid grid-cols-[minmax(0,14rem)_1fr_3rem] items-center gap-3 text-sm">
              <span className="truncate">{p.name}</span>
              <div className="h-5 rounded-sm bg-panel-2">
                <div {...tip.on(`${p.name}: ${p.referred} open referral${p.referred === 1 ? '' : 's'}, ${p.fraud} confirmed fraud`)}
                  className="h-full outline-none focus-visible:ring-2 focus-visible:ring-text"
                  style={{ width: `${(p.total / maxProv) * 100}%`, background: OUTCOME[2].color, borderRadius: '0 4px 4px 0' }} />
              </div>
              <span className="text-right tabular-nums text-muted">{p.total}</span>
            </div>
          ))}
          {data.topProviders.length === 0 && <p className="text-sm text-muted">No high-risk providers.</p>}
        </div>
      </Card>
    </div>
  )
}
