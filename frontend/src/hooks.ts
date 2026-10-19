import { collection, doc, limit, onSnapshot, orderBy, query, where } from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { auth, db } from './firebase'
import { visibleTo } from './lines'
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
        setClaims(s.docs.map((d) => ({ id: d.id, ...d.data() }) as Claim).filter((c) => visibleTo(c, uid)))
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

/** Closed (historical) claims visible to this user. */
export function useClosed() {
  const [claims, setClaims] = useState<Claim[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const q = query(collection(db, 'claims'), where('status', '==', 'closed'))
    return onSnapshot(
      q,
      (s) => setClaims(s.docs.map((d) => ({ id: d.id, ...d.data() }) as Claim).filter((c) => visibleTo(c, auth.currentUser?.uid))),
      (e) => setError(e.message),
    )
  }, [])
  return { claims, error }
}

export type Review = { flagStatus?: Record<string, 'open' | 'confirmed' | 'dismissed'>; risk?: Claim['risk']; decision?: Claim['decision'] }

/** This user's private review of a shared demo claim (flag feedback, rescored risk, decision). */
export function useReview(id: string | undefined) {
  const [review, setReview] = useState<Review | null>(null)
  useEffect(() => {
    const uid = auth.currentUser?.uid
    if (!id || !uid) return
    return onSnapshot(doc(db, 'claims', id, 'reviews', uid), (s) => setReview(s.exists() ? (s.data() as Review) : null), () => setReview(null))
  }, [id])
  return review
}

export function withReview(claim: Claim, review: Review | null): Claim {
  if (!review || !claim.isDemo) return claim
  return {
    ...claim,
    flags: claim.flags.map((f) => ({ ...f, status: review.flagStatus?.[f.id] ?? f.status })),
    risk: review.risk ?? claim.risk,
    decision: review.decision ?? claim.decision,
  }
}
