import { Loader2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'

type Node = { id: string; type: string; label: string; claimant?: string; score?: number; fraudConfirmed?: boolean; inQueue?: boolean; x?: number; y?: number }
type Edge = { source: string | Node; target: string | Node; kind: string }
type Graph = { nodes: Node[]; edges: Edge[] }

const ENTITY_COLOR: Record<string, string> = {
  bank: '#e5484d', phone: '#f76b15', email: '#f5a524', garage: '#8e4ec6', vehicle: '#3e63dd', invoice: '#e93d82', photo: '#12a594',
}
const ENTITY_LABEL: Record<string, string> = { bank: 'Bank account', phone: 'Phone', email: 'Email', garage: 'Garage', vehicle: 'Vehicle', invoice: 'Invoice', photo: 'Photo' }
const idOf = (n: string | Node) => (typeof n === 'string' ? n : n.id)

export function Network() {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [error, setError] = useState('')
  const [hover, setHover] = useState<Node | null>(null)
  const [params] = useSearchParams()
  const focus = params.get('focus')
  const nav = useNavigate()
  const fg = useRef<ForceGraphMethods<any, any>>(undefined)
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(800)

  useEffect(() => { api<Graph>('/network').then(setGraph).catch((e) => setError(e.message)) }, [])
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    if (box.current) ro.observe(box.current)
    return () => ro.disconnect()
  }, [])

  // Highlight the focused claim's neighbourhood (2 hops: claim -> entity -> claims)
  const highlighted = useMemo(() => {
    const target = hover?.id ?? focus
    if (!graph || !target) return null
    const set = new Set([target])
    for (let hop = 0; hop < 2; hop++) {
      for (const e of graph.edges) {
        const s = idOf(e.source), t = idOf(e.target)
        if (set.has(s)) set.add(t)
        else if (set.has(t)) set.add(s)
      }
    }
    return set
  }, [graph, hover, focus])

  const data = useMemo(() => (graph ? { nodes: graph.nodes, links: graph.edges } : { nodes: [], links: [] }), [graph])

  if (error) return <p className="text-string">{error}</p>
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h1 className="text-xl font-semibold">Red String</h1>
          <p className="text-sm text-muted">Claims connected by shared phones, bank accounts, garages, vehicles and invoices. Click a claim to open it.</p>
        </div>
        <ul className="ml-auto flex flex-wrap gap-3 text-xs text-muted">
          <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-text" /> Claim</li>
          <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2 border-string" /> Confirmed fraud</li>
          {Object.entries(ENTITY_COLOR).map(([k, c]) => (
            <li key={k} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rotate-45" style={{ background: c }} /> {ENTITY_LABEL[k]}</li>
          ))}
        </ul>
      </div>
      <div ref={box} className="relative h-[70vh] overflow-hidden rounded-xl border border-line bg-panel">
        {!graph && <Loader2 className="absolute left-1/2 top-1/2 animate-spin text-muted" />}
        {graph && (
          <ForceGraph2D
            ref={fg}
            graphData={data}
            width={width}
            height={box.current?.clientHeight ?? 600}
            backgroundColor="#161920"
            cooldownTicks={120}
            onEngineStop={() => fg.current?.zoomToFit(400, 40)}
            linkColor={(l: any) => {
              const on = !highlighted || (highlighted.has(idOf(l.source)) && highlighted.has(idOf(l.target)))
              return on ? ENTITY_COLOR[l.kind] + 'cc' : '#2a2f3a55'
            }}
            linkWidth={(l: any) => (highlighted && highlighted.has(idOf(l.source)) && highlighted.has(idOf(l.target)) ? 2 : 1)}
            onNodeHover={(n: any) => setHover(n)}
            onNodeClick={(n: any) => n.type === 'claim' && nav(`/claims/${n.id}`)}
            nodeCanvasObject={(n: any, ctx, scale) => {
              const dim = highlighted && !highlighted.has(n.id)
              ctx.globalAlpha = dim ? 0.15 : 1
              if (n.type === 'claim') {
                const r = 5 + (n.score ?? 0) / 20
                ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI)
                ctx.fillStyle = n.inQueue ? '#e6e8ec' : '#8b93a3'; ctx.fill()
                if (n.fraudConfirmed || (n.score ?? 0) >= 60) { ctx.lineWidth = 2 / scale + 1; ctx.strokeStyle = '#e5484d'; ctx.stroke() }
                if (scale > 1.2 || n.id === focus) {
                  ctx.font = `${11 / scale}px JetBrains Mono`; ctx.fillStyle = '#e6e8ec'; ctx.textAlign = 'center'
                  ctx.fillText(n.label, n.x, n.y + r + 10 / scale)
                }
              } else {
                const s = 5
                ctx.save(); ctx.translate(n.x, n.y); ctx.rotate(Math.PI / 4)
                ctx.fillStyle = ENTITY_COLOR[n.type] ?? '#8b93a3'; ctx.fillRect(-s / 2, -s / 2, s, s); ctx.restore()
                if (scale > 2) {
                  ctx.font = `${9 / scale}px Inter`; ctx.fillStyle = '#8b93a3'; ctx.textAlign = 'center'
                  ctx.fillText(n.label, n.x, n.y + 9 / scale + 4)
                }
              }
              ctx.globalAlpha = 1
            }}
            nodePointerAreaPaint={(n: any, color, ctx) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x, n.y, 8, 0, 2 * Math.PI); ctx.fill() }}
          />
        )}
        {hover && (
          <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-line bg-ink/90 px-3 py-2 text-xs">
            {hover.type === 'claim' ? (
              <>
                <p className="font-mono font-semibold">{hover.label}</p>
                <p className="text-muted">{hover.claimant} · risk {hover.score ?? '-'}{hover.fraudConfirmed ? ' · confirmed fraud' : ''}</p>
              </>
            ) : (
              <p><span className="text-muted">{ENTITY_LABEL[hover.type]}:</span> {hover.label}</p>
            )}
          </div>
        )}
      </div>
      {graph && <p className="text-xs text-muted">{graph.nodes.filter((n) => n.type === 'claim').length} linked claims · {graph.nodes.filter((n) => n.type !== 'claim').length} shared entities</p>}
    </div>
  )
}
