import { ref, uploadBytes } from 'firebase/storage'
import { FileText, Image, Loader2, Package, Upload, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { storage } from '../firebase'

type SamplePack = { id: string; title: string; description: string; files: string[] }
const ACCEPT = 'application/pdf,image/jpeg,image/png,image/webp'

export function NewClaim() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [files, setFiles] = useState<File[]>([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [packs, setPacks] = useState<SamplePack[]>([])

  useEffect(() => {
    fetch('/samples/manifest.json').then((r) => (r.ok ? r.json() : [])).then(setPacks).catch(() => setPacks([]))
  }, [])

  const add = (list: FileList | null) => {
    if (!list) return
    const ok = Array.from(list).filter((f) => ACCEPT.includes(f.type) && f.size < 15 * 1024 * 1024)
    setFiles((prev) => [...prev, ...ok].slice(0, 10))
  }

  const submit = async (toSend: File[], claimNote?: string, samplePack?: string) => {
    if (!user || toSend.length === 0) return
    setError('')
    try {
      const batch = crypto.randomUUID()
      setBusy('Uploading documents…')
      const documents = await Promise.all(
        toSend.map(async (f) => {
          const path = `uploads/${user.uid}/${batch}/${f.name.replace(/[^\w.-]+/g, '_')}`
          await uploadBytes(ref(storage, path), f, { contentType: f.type })
          return { path, name: f.name, mime_type: f.type }
        }),
      )
      setBusy('Starting agents…')
      const { id } = await api<{ id: string }>('/claims', { documents, note: claimNote || undefined, sample_pack: samplePack })
      nav(`/claims/${id}`)
    } catch (e) {
      setError((e as Error).message)
      setBusy('')
    }
  }

  const useSample = async (p: SamplePack) => {
    setBusy(`Loading “${p.title}”…`)
    try {
      const loaded = await Promise.all(
        p.files.map(async (name) => {
          const blob = await (await fetch(`/samples/${p.id}/${name}`)).blob()
          return new File([blob], name, { type: blob.type })
        }),
      )
      await submit(loaded, undefined, p.id)
    } catch (e) {
      setError((e as Error).message)
      setBusy('')
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <div>
          <h1 className="text-xl font-semibold">New claim</h1>
          <p className="text-sm text-muted">Drop the claim pack: claim form, invoice, photos, police report. The agents extract everything else.</p>
        </div>
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files) }}
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-line bg-panel px-6 py-14 text-center hover:border-string">
          <Upload className="text-string" />
          <span className="font-medium">Drag files here or click to browse</span>
          <span className="text-xs text-muted">PDF, JPG, PNG · up to 10 files · 15 MB each</span>
          <input type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => add(e.target.files)} />
        </label>
        {files.length > 0 && (
          <ul className="divide-y divide-line rounded-lg border border-line bg-panel text-sm">
            {files.map((f, i) => (
              <li key={i} className="flex items-center gap-3 px-3 py-2">
                {f.type.startsWith('image/') ? <Image size={15} className="text-muted" /> : <FileText size={15} className="text-muted" />}
                <span className="flex-1 truncate">{f.name}</span>
                <span className="text-xs text-muted">{(f.size / 1024).toFixed(0)} KB</span>
                <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="text-muted hover:text-text"><X size={14} /></button>
              </li>
            ))}
          </ul>
        )}
        <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note for the agents (e.g. 'Customer called twice asking for quick settlement')"
          rows={2} className="w-full rounded-lg bg-panel p-3 text-sm outline-none ring-1 ring-line focus:ring-string" />
        <button onClick={() => submit(files, note)} disabled={!files.length || !!busy}
          className="inline-flex items-center gap-2 rounded-lg bg-string px-5 py-2.5 font-medium text-white disabled:opacity-40">
          {busy && <Loader2 size={15} className="animate-spin" />} {busy || 'Analyse claim'}
        </button>
        {error && <p className="text-sm text-string">{error}</p>}
      </div>

      <aside className="space-y-3">
        <p className="flex items-center gap-2 text-sm font-medium"><Package size={15} /> No documents handy? Try a sample pack</p>
        {packs.map((p) => (
          <button key={p.id} onClick={() => useSample(p)} disabled={!!busy}
            className="w-full rounded-lg border border-line bg-panel p-3 text-left hover:border-string disabled:opacity-50">
            <p className="text-sm font-medium">{p.title}</p>
            <p className="mt-1 text-xs text-muted">{p.description}</p>
            <p className="mt-2 text-[11px] font-mono text-muted/80">{p.files.length} files</p>
          </button>
        ))}
        {packs.length === 0 && <p className="text-xs text-muted">Sample packs unavailable.</p>}
      </aside>
    </div>
  )
}
