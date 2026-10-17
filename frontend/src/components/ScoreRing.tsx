export function ScoreRing({ score, band, size = 120 }: { score?: number; band?: string; size?: number }) {
  const r = size / 2 - 10
  const c = 2 * Math.PI * r
  const pct = score == null ? 0 : score / 100
  const color = band === 'high' ? 'var(--color-string)' : band === 'medium' ? 'var(--color-warn)' : 'var(--color-ok)'
  return (
    <svg width={size} height={size} className="shrink-0" role="img" aria-label={`Risk score ${score ?? 'pending'}`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--color-line)" strokeWidth="8" fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="8" fill="none" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - pct)} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 700ms ease' }} />
      <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle" fill="var(--color-text)"
        fontSize={size / 3.6} fontWeight={700}>{score ?? '–'}</text>
      <text x="50%" y="68%" textAnchor="middle" fill="var(--color-muted)" fontSize={size / 11}>risk / 100</text>
    </svg>
  )
}

export function RiskPill({ score, band }: { score?: number; band?: string }) {
  if (score == null) return <span className="text-muted text-xs">-</span>
  const cls = band === 'high' ? 'bg-string/15 text-string' : band === 'medium' ? 'bg-warn/15 text-warn' : 'bg-ok/15 text-ok'
  return <span className={`inline-flex min-w-10 justify-center rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums ${cls}`}>{score}</span>
}
