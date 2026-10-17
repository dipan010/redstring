import { collection, doc, limit, onSnapshot, orderBy, query, where } from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { auth, db } from './firebase'
import type { Claim } from './types'

/** Demo claims plus the signed-in user's own submissions (evaluators don't see each other's). */
export function useQueue() {
  const [claims, setClaims] = useState<Claim[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const q = query(collection(db, 'claims'), where('inQueue', '==', true), orderBy('createdAt', 'desc'), limit(300))
    return onSnapshot(
      q,
      (s) => {
        const uid = auth.currentUser?.uid
        setClaims(s.docs.map((d) => ({ id: d.id, ...d.data() }) as Claim).filter((c) => c.isDemo || c.createdBy === uid))
      },
      (e) => setError(e.message),
    )
  }, [])
  return { claims, error }
}

export function useClaim(id: string | undefined) {
  const [claim, setClaim] = useState<Claim | null | undefined>(undefined)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!id) return
    return onSnapshot(
      doc(db, 'claims', id),
      (s) => setClaim(s.exists() ? ({ id: s.id, ...s.data() } as Claim) : null),
      (e) => setError(e.message),
    )
  }, [id])
  return { claim, error }
}
