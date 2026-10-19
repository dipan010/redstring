import type { Claim } from './types'

/** Local preview of unreleased features: shows staged data and talks to a hidden Cloud Run revision. */
export const PREVIEW = import.meta.env.VITE_PREVIEW === '1'

export type Line = 'motor' | 'health' | 'property'
export const LINE_LABEL: Record<Line, string> = { motor: 'Motor', health: 'Health', property: 'Property' }

export const lineOf = (c: Pick<Claim, 'lineOfBusiness'>): Line => (c.lineOfBusiness ?? 'motor') as Line

/** Vehicle for motor; patient and hospital for health; incident and city for property. */
export const subjectOf = (c: Claim & { garageName?: string }) => c.subject ?? c.vehicleRegistration ?? '-'
/** Invoices often print names in capitals ("SPEEDFIX MOTOR WORKS"); show and group them in title case. */
const tidy = (name: string) =>
  name.length > 3 && name === name.toUpperCase()
    ? name.toLowerCase().replace(/\b([a-z])/g, (m) => m.toUpperCase()).replace(/\b(And|Of)\b/g, (m) => m.toLowerCase())
    : name

export const providerOf = (c: Claim & { garageName?: string; providerName?: string }) =>
  tidy(c.garageName ?? c.providerName ?? c.extracted?.invoice?.garage_name ?? c.extracted?.hospital_name ?? c.extracted?.contractor_name ?? '-')

/** Shared entity kinds that many honest customers have in common (garages, hospitals...). */
export const PROVIDER_KINDS = ['garage', 'hospital', 'doctor', 'contractor']

export const visibleTo = (c: Claim, uid?: string) => c.isDemo || c.createdBy === uid || (PREVIEW && !!c.staged)
