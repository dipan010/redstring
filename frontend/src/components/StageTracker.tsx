import { Check, FileSearch, Gavel, Loader2, Microscope, Network, ScrollText, X } from 'lucide-react'
import type { Claim, StageName } from '../types'

const STAGES: { key: StageName; label: string; desc: string; icon: typeof Check }[] = [
  { key: 'reader', label: 'Reader', desc: 'Reads every document & photo', icon: FileSearch },
  { key: 'policy', label: 'Policy', desc: 'Checks cover & clauses', icon: ScrollText },
  { key: 'forensics', label: 'Forensics', desc: 'Spots inconsistencies', icon: Microscope },
  { key: 'linker', label: 'Linker', desc: 'Connects related claims', icon: Network },
  { key: 'verdict', label: 'Verdict', desc: 'Scores & explains', icon: Gavel },
]

export function StageTracker({ stages }: { stages: Claim['stages'] }) {
  return (
    <ol className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {STAGES.map(({ key, label, desc, icon: Icon }) => {
        const s = stages?.[key]?.status ?? 'pending'
        const ms = stages?.[key]?.ms
        const ring = s === 'done' ? 'border-ok/40' : s === 'running' ? 'border-string animate-pulse' : s === 'error' ? 'border-string' : 'border-line'
        return (
          <li key={key} className={`rounded-lg border ${ring} bg-panel p-3`}>
            <div className="flex items-center gap-2 text-sm font-medium">
              <Icon size={15} className="text-muted" /> {label}
              <span className="ml-auto">
                {s === 'done' && <Check size={15} className="text-ok" />}
                {s === 'running' && <Loader2 size={15} className="animate-spin text-string" />}
                {s === 'error' && <X size={15} className="text-string" />}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted">{s === 'done' && ms ? `${(ms / 1000).toFixed(1)}s · ` : ''}{desc}</p>
          </li>
        )
      })}
    </ol>
  )
}
