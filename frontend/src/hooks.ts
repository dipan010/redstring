import { collection, doc, limit, onSnapshot, orderBy, query, where } from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { db } from './firebase'
import type { Claim } from './types'

export function useQueue() {
  const [claims, setClaims] = useState<Claim[] | null>(null)
  useEffect(() => {
    const q = query(collection(db, 'claims'), where('inQueue', '==', true), orderBy('createdAt', 'desc'), limit(200))
    return onSnapshot(q, (s) => setClaims(s.docs.map((d) => ({ id: d.id, ...d.data() }) as Claim)))
  }, [])
  return claims
}

export function useClaim(id: string | undefined) {
  const [claim, setClaim] = useState<Claim | null | undefined>(undefined)
  useEffect(() => {
    if (!id) return
    return onSnapshot(doc(db, 'claims', id), (s) => setClaim(s.exists() ? ({ id: s.id, ...s.data() } as Claim) : null))
  }, [id])
  return claim
}
