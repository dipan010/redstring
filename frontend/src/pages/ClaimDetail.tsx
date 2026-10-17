import { getDownloadURL, ref } from 'firebase/storage'
import { ArrowLeft, ExternalLink, FileText, Link2, Loader2, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { ChatPanel } from '../components/ChatPanel'
import { DraftPanel } from '../components/DraftPanel'
import { FlagCard } from '../components/FlagCard'
import { RiskPill, ScoreRing } from '../components/ScoreRing'
import { StageTracker } from '../components/StageTracker'
import { bandColor, inr } from '../format'
import { storage } from '../firebase'
import { useClaim } from '../hooks'
import type { Claim } from '../types'

const SEV_ORDER = { high: 0, medium: 1, low: 2 }
const KIND_LABEL: Record<string, string> = { phone: 'phone', email: 'email', bank: 'bank a/c', vehicle: 'vehicle', garage: 'garage', invoice: 'invoice', photo: 'same photo' }

function Docs({ docs }: { docs: Claim['documents'] }) {
  const [urls, setUrls] = useState<Record<string, string>>({})
  useEffect(() => {
    docs.forEach((d) => getDownloadURL(ref(storage, d.path)).then((u) => setUrls((p) => ({ ...p, [d.path]: u }))).catch(() => {}))
  }, [docs])
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
      {docs.map((d, i) => (
        <a key={d.path} href={urls[d.path]} target="_blank" rel="noreferrer"
          className="group relative aspect-[4/3] overflow-hidden rounded-md border border-line bg-panel-2" title={d.name}>
          {d.mime_type.startsWith('image/') && urls[d.path] ? (
            <img src={urls[d.path]} alt={d.name} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-1 p-2 text-center">
              <FileText size={18} className="text-muted" />
              <span className="line-clamp-2 text-[10px] text-muted">{d.name}</span>
            </div>
          )}
          <span className="absolute left-1 top-1 rounded bg-ink/80 px-1 font-mono text-[10px]">doc:{i}</span>
        </a>
      ))}
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value?: string | number | null; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`mt-0.5 text-sm ${mono ? 'font-mono text-xs' : ''}`}>{value ?? '—'}</dd>
    </div>
  )
}

export function ClaimDetail() {
  const { id } = useParams()
  const { claim, error } = useClaim(id)
  const [actionBusy, setActionBusy] = useState(false)

  if (error) return <p className="text-string">Couldn't load this claim: {error}</p>
  if (claim === undefined) return <Loader2 className="animate-spin text-muted" />
  if (claim === null) return <p className="text-muted">Claim not found. <Link to="/" className="text-string">Back to queue</Link></p>

  const x = claim.extracted ?? {}
  const pa = claim.policy?.assessment
  const flags = [...(claim.flags ?? [])].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity])
  const working = claim.status === 'queued' || claim.status === 'processing'

  const decide = async (action: string) => {
    setActionBusy(true)
    try { await api(`/claims/${claim.id}/decision`, { action }) } finally { setActionBusy(false) }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/" className="text-muted hover:text-text"><ArrowLeft size={18} /></Link>
        <h1 className="font-mono text-lg font-semibold">{claim.claimNumber}</h1>
        {claim.isDemo && <span className="rounded border border-line px-1.5 text-[10px] uppercase text-muted">demo</span>}
        <span className="text-sm text-muted">{x.claimant_name}{x.vehicle_make_model ? ` · ${x.vehicle_make_model}` : ''}</span>
        {!claim.isDemo && (claim.status === 'ready' || claim.status === 'error') && (
          <button onClick={() => api(`/claims/${claim.id}/rerun`, {})} className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted hover:text-text">
            <RefreshCw size={13} /> Re-run agents
          </button>
        )}
      </div>

      <StageTracker stages={claim.stages} />
      {claim.status === 'error' && <p className="rounded-lg border border-string/40 bg-string/10 p-3 text-sm">Processing failed: {claim.error}</p>}

      {/* Verdict */}
      <section className="flex flex-col gap-5 rounded-xl border border-line bg-panel p-5 md:flex-row">
        <ScoreRing score={claim.risk?.score} band={claim.risk?.band} />
        <div className="flex-1">
          {claim.verdict ? (
            <>
              <p className={`text-lg font-semibold ${bandColor(claim.risk?.band)}`}>{claim.risk?.actionLabel}</p>
              <p className="mt-2 text-sm leading-relaxed">{claim.verdict.summary}</p>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
                {claim.verdict.key_reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </>
          ) : (
            <p className="flex items-center gap-2 text-muted">{working && <Loader2 size={15} className="animate-spin" />} Verdict pending…</p>
          )}
        </div>
        <div className="flex shrink-0 flex-row gap-2 md:flex-col">
          {[['approve', 'Approve'], ['request_info', 'Request info'], ['investigate', 'Refer to SIU']].map(([a, l]) => (
            <button key={a} disabled={actionBusy || working} onClick={() => decide(a)}
              className={`rounded-md border px-3 py-1.5 text-xs disabled:opacity-40 ${claim.decision?.action === a ? 'border-string bg-string/15' : 'border-line hover:border-muted'}`}>
              {l}
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          {/* Flags */}
          <section>
            <h2 className="mb-2 text-sm font-semibold">Evidence & flags <span className="text-muted">({flags.filter((f) => f.status !== 'dismissed').length})</span></h2>
            {flags.length ? (
              <ul className="space-y-2">{flags.map((f) => <FlagCard key={f.id} claimId={claim.id} flag={f} />)}</ul>
            ) : (
              <p className="rounded-lg border border-line bg-panel p-3 text-sm text-muted">{claim.status === 'ready' ? 'No inconsistencies found.' : 'Waiting for agents…'}</p>
            )}
          </section>

          {/* Linked claims */}
          {!!claim.links?.length && (
            <section>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Link2 size={15} className="text-string" /> Red strings: linked claims ({claim.links.length})</h2>
              <ul className="divide-y divide-line rounded-lg border border-line bg-panel text-sm">
                {claim.links.map((l) => (
                  <li key={l.claimId} className="flex flex-wrap items-center gap-3 px-3 py-2">
                    <Link to={`/claims/${l.claimId}`} className="font-mono text-xs hover:text-string">{l.claimNumber}</Link>
                    <span>{l.claimantName}</span>
                    {l.fraudConfirmed && <span className="rounded bg-string/15 px-1.5 text-[10px] font-semibold uppercase text-string">confirmed fraud</span>}
                    <span className="ml-auto flex flex-wrap gap-1">
                      {l.shared.map((s) => <span key={s.key} className="rounded border border-string/30 px-1.5 text-[11px] text-string">{KIND_LABEL[s.kind] ?? s.kind}</span>)}
                    </span>
                    <RiskPill score={l.riskScore} band={l.riskScore == null ? undefined : l.riskScore >= 60 ? 'high' : l.riskScore >= 25 ? 'medium' : 'low'} />
                  </li>
                ))}
              </ul>
              <Link to={`/network?focus=${claim.id}`} className="mt-2 inline-flex items-center gap-1 text-xs text-string">Open in Red String view <ExternalLink size={12} /></Link>
            </section>
          )}

          {/* Policy */}
          {pa && (
            <section className="rounded-lg border border-line bg-panel p-4">
              <h2 className="text-sm font-semibold">Policy check · <span className={pa.covered ? 'text-ok' : 'text-string'}>{pa.covered ? 'Covered' : 'Not covered'}</span></h2>
              <p className="mt-2 text-sm text-muted">{pa.coverage_summary}</p>
              <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field label="Deductible" value={inr(pa.deductible)} />
                <Field label="Estimated payable" value={inr(pa.payable_estimate)} />
                <Field label="Missing docs" value={pa.missing_documents.join(', ') || 'None'} />
              </dl>
              {[...pa.exclusions_triggered, ...pa.supporting_clauses].length > 0 && (
                <ul className="mt-4 space-y-2">
                  {[...pa.exclusions_triggered.map((c) => ({ ...c, ex: true })), ...pa.supporting_clauses.map((c) => ({ ...c, ex: false }))].map((c, i) => (
                    <li key={i} className={`border-l-2 pl-3 text-sm ${c.ex ? 'border-string' : 'border-line'}`}>
                      <span className="font-mono text-xs text-muted">§{c.clause_id}</span> <span className="font-medium">{c.title}</span>
                      <p className="mt-0.5 text-xs italic text-muted">“{c.quote}”</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Extracted */}
          <section className="rounded-lg border border-line bg-panel p-4">
            <h2 className="mb-3 text-sm font-semibold">Extracted by Reader agent</h2>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Field label="Policy no." value={x.policy_number} mono />
              <Field label="Vehicle" value={x.vehicle_registration} mono />
              <Field label="Incident date" value={x.incident_date} />
              <Field label="Location" value={x.incident_location} />
              <Field label="Amount claimed" value={inr(x.claim_amount)} />
              <Field label="Phone" value={x.claimant_phone} mono />
              <Field label="Garage" value={x.invoice?.garage_name} />
              <Field label="Invoice" value={x.invoice ? `#${x.invoice.number ?? '—'} · ${x.invoice.date ?? ''}` : null} />
              <Field label="Invoice total" value={inr(x.invoice?.total)} />
            </dl>
            {x.incident_description && <p className="mt-3 text-sm text-muted">“{x.incident_description}”</p>}
          </section>
        </div>

        <div className="space-y-6">
          <section>
            <h2 className="mb-2 text-sm font-semibold">Documents</h2>
            <Docs docs={claim.documents} />
          </section>
          <ChatPanel claimId={claim.id} />
          <DraftPanel claimId={claim.id} />
          {claim.processingMs && <p className="text-xs text-muted">Triage completed in {(claim.processingMs / 1000).toFixed(1)}s by 5 agents.</p>}
        </div>
      </div>
    </div>
  )
}
