export const inr = (n?: number | null) =>
  n == null ? '-' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)

export const bandColor = (band?: string) =>
  band === 'high' ? 'text-string' : band === 'medium' ? 'text-warn' : band === 'low' ? 'text-ok' : 'text-muted'

export const severityStyles: Record<string, string> = {
  high: 'bg-string/15 text-string border-string/30',
  medium: 'bg-warn/15 text-warn border-warn/30',
  low: 'bg-muted/15 text-muted border-muted/30',
}
