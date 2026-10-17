export function Logo({ size = 22 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
        <circle cx="9" cy="10" r="3.2" fill="var(--color-string)" />
        <circle cx="23" cy="9" r="3.2" fill="var(--color-string)" />
        <circle cx="16" cy="23" r="3.2" fill="var(--color-string)" />
        <path d="M9 10 L23 9 L16 23 Z" fill="none" stroke="var(--color-string)" strokeWidth="1.6" />
      </svg>
      Redstring
    </span>
  )
}
