import { collection, onSnapshot, query, where } from 'firebase/firestore'
import { Archive, Loader2, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { RiskPill } from '../components/ScoreRing'
import { db } from '../firebase'
import { inr } from '../format'
import type { Claim } from '../types'
import { LINE_LABEL, lineOf, providerOf, subjectOf, visibleTo, type Line } from '../lines'
import { auth } from '../firebase'

type Row = Claim & { garageName?: string; providerName?: string }
type Filter = 'all' | 'fraud' | 'settled'

/** Past claims decided before Redstring: the history the Linker connects new claims to. */
export function ClosedClaims() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [garage, setGarage] = useState('')
  const [line, setLine] = useState<Line | 'all'>('all')

  useEffect(() => {
    const q = query(collection(db, 'claims'), where('status', '==', 'closed'))
    return onSnapshot(
      q,
      (s) => setRows(s.docs.map((d) => ({ id: d.id, ...d.data() }) as Row).filter((c) => visibleTo(c, auth.currentUser?.uid))),
      (e) => setError(e.message),
    )
  }, [])

  const garages = useMemo(() => [...new Set((rows ?? []).filter((r) => line === 'all' || lineOf(r) === line)
    .map(providerOf).filter((p) => p !== '-'))].sort(), [rows, line])
  const lines = useMemo(() => [...new Set((rows ?? []).map(lineOf))], [rows])

  const shown = useMemo(() => {
    const t = text.trim().toLowerCase()
    return (rows ?? [])
      .filter((r) => filter === 'all' || (filter === 'fraud' ? r.fraudConfirmed : !r.fraudConfirmed))
      .filter((r) => line === 'all' || lineOf(r) === line)
      .filter((r) => !garage || providerOf(r) === garage)
      .filter((r) => !t || [r.claimNumber, r.claimantName, subjectOf(r), providerOf(r)]
        .some((v) => v?.toLowerCase().includes(t)))
      .sort((a, b) => Number(!!b.fraudConfirmed) - Number(!!a.fraudConfirmed) || (b.closedAt ?? '').localeCompare(a.closedAt ?? ''))
  }, [rows, text, filter, garage, line])

  if (error) return <p className="text-string">Couldn't load closed claims: {error}</p>
  if (!rows) return <Loader2 className="animate-spin text-muted" />

  const fraud = rows.filter((r) => r.fraudConfirmed).length
  const chip = (f: Filter, label: string) => (
    <button key={f} onClick={() => setFilter(f)}
      className={`rounded-full border px-3 py-1 text-xs ${filter === f ? 'border-string bg-string/15 text-text' : 'border-line text-muted hover:text-text'}`}>
      {label}
    </button>
  )

  return (
    <div className="space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold"><Archive size={18} /> Closed claims</h1>
        <p className="text-sm text-muted">
          {rows.length} past claims decided by adjusters and the SIU before Redstring ({fraud} confirmed fraud). The Linker checks every new claim against them.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-w-64 flex-1 items-center gap-2 rounded-md bg-panel px-3 py-2 ring-1 ring-line focus-within:ring-string">
          <Search size={14} className="text-muted" />
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={lines.length > 1 ? "Search claim, claimant, subject or provider" : "Search claim, claimant, vehicle or garage"}
            className="w-full bg-transparent text-sm outline-none" />
        </label>
        <div className="flex gap-2">{chip('all', 'All')}{chip('fraud', 'Fraud confirmed')}{chip('settled', 'Settled')}</div>
        {lines.length > 1 && (
          <select value={line} onChange={(e) => { setLine(e.target.value as Line | 'all'); setGarage('') }}
            className="rounded-md bg-panel px-3 py-2 text-sm text-text ring-1 ring-line outline-none">
            <option value="all">All lines</option>
            {lines.map((l) => <option key={l} value={l}>{LINE_LABEL[l]}</option>)}
          </select>
        )}
        <select value={garage} onChange={(e) => setGarage(e.target.value)}
          className="rounded-md bg-panel px-3 py-2 text-sm text-text ring-1 ring-line outline-none">
          <option value="">{lines.length > 1 ? 'All providers' : 'All garages'}</option>
          {garages.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-panel text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">Risk</th>
              <th className="px-4 py-2.5 font-medium">Claim</th>
              <th className="px-4 py-2.5 font-medium">Claimant</th>
              <th className="px-4 py-2.5 font-medium">{lines.length > 1 ? 'Subject' : 'Vehicle'}</th>
              <th className="px-4 py-2.5 font-medium">{lines.length > 1 ? 'Provider' : 'Garage'}</th>
              <th className="px-4 py-2.5 font-medium text-right">Amount</th>
              <th className="px-4 py-2.5 font-medium">Outcome</th>
              <th className="px-4 py-2.5 font-medium">Closed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {shown.map((r) => (
              <tr key={r.id} className="hover:bg-panel/60">
                <td className="px-4 py-3"><RiskPill score={r.risk?.score} band={r.risk?.band} /></td>
                <td className="px-4 py-3 font-mono text-xs"><Link to={`/claims/${r.id}`} className="hover:text-string">{r.claimNumber}</Link></td>
                <td className="px-4 py-3">{r.claimantName}</td>
                <td className={`px-4 py-3 text-xs text-muted ${lineOf(r) === 'motor' ? 'font-mono' : ''}`}>{subjectOf(r)}</td>
                <td className="px-4 py-3 text-muted">{providerOf(r)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{inr(r.claimAmount)}</td>
                <td className={`px-4 py-3 ${r.fraudConfirmed ? 'text-string' : 'text-ok'}`}>{r.fraudConfirmed ? 'Fraud confirmed' : 'Settled'}</td>
                <td className="px-4 py-3 text-muted">{r.closedAt}</td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-muted">No closed claims match these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">Showing {shown.length} of {rows.length}</p>
    </div>
  )
}
