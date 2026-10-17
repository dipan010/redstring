export type Severity = 'low' | 'medium' | 'high'
export type StageName = 'reader' | 'policy' | 'forensics' | 'linker' | 'verdict'
export type StageStatus = 'pending' | 'running' | 'done' | 'error'

export interface Flag {
  id: string
  agent: StageName
  code: string
  severity: Severity
  title: string
  evidence: string
  source?: string | null
  status: 'open' | 'confirmed' | 'dismissed'
}

export interface ClauseRef { clause_id: string; title: string; quote: string; reason: string }

export interface Link {
  claimId: string
  claimNumber?: string
  claimantName?: string
  riskScore?: number
  fraudConfirmed: boolean
  shared: { key: string; kind: string }[]
}

export interface Claim {
  id: string
  claimNumber: string
  status: 'queued' | 'processing' | 'ready' | 'error'
  error?: string | null
  isDemo?: boolean
  inQueue?: boolean
  createdAt?: { toDate(): Date }
  claimantName?: string
  vehicleRegistration?: string
  claimAmount?: number
  incidentDate?: string
  documents: { path: string; name: string; mime_type: string }[]
  stages: Record<StageName, { status: StageStatus; ms?: number; error?: string }>
  extracted?: Record<string, any>
  policy?: {
    assessment: {
      covered: boolean
      coverage_summary: string
      deductible?: number | null
      payable_estimate?: number | null
      exclusions_triggered: ClauseRef[]
      supporting_clauses: ClauseRef[]
      missing_documents: string[]
    } | null
    schedule: Record<string, any> | null
  }
  flags: Flag[]
  links?: Link[]
  risk?: { score: number; band: 'low' | 'medium' | 'high'; action: string; actionLabel: string }
  verdict?: { summary: string; key_reasons: string[]; next_steps: string[] }
  decision?: { action: string; note?: string }
  processingMs?: number
}
