import { collection, limit, onSnapshot, orderBy, query } from 'firebase/firestore'
import { Loader2, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { db } from '../firebase'

type Msg = { id: string; role: 'user' | 'assistant'; text: string }
const SUGGESTIONS = ['Why is this claim flagged?', 'What is the estimated payout?', 'Which documents are missing?', 'How is this linked to other claims?']

export function ChatPanel({ claimId }: { claimId: string }) {
  const { user } = useAuth()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!user) return
    const q = query(collection(db, 'claims', claimId, 'chats', user.uid, 'messages'), orderBy('at'), limit(100))
    return onSnapshot(q, (s) => setMsgs(s.docs.map((d) => ({ id: d.id, ...d.data() }) as Msg)))
  }, [claimId, user])
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), [msgs, busy])

  const send = async (message: string) => {
    if (!message.trim() || busy) return
    setBusy(true); setError(''); setText('')
    try { await api(`/claims/${claimId}/chat`, { message }) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="flex h-[440px] flex-col rounded-lg border border-line bg-panel">
      <div className="border-b border-line px-4 py-2.5 text-sm font-medium">Ask about this claim</div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)} className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-string hover:text-text">{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'ml-8 rounded-lg bg-panel-2 px-3 py-2' : 'mr-4 whitespace-pre-wrap leading-relaxed'}>
            {m.text}
          </div>
        ))}
        {busy && <Loader2 size={16} className="animate-spin text-muted" />}
        {error && <p className="text-xs text-string">{error}</p>}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(text) }} className="flex gap-2 border-t border-line p-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Is the invoice consistent with the photos?"
          className="flex-1 rounded-md bg-ink px-3 py-2 text-sm outline-none ring-1 ring-line focus:ring-string" />
        <button disabled={busy} className="rounded-md bg-string px-3 text-white disabled:opacity-50" aria-label="Send"><Send size={15} /></button>
      </form>
    </div>
  )
}
