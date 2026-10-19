import { useEffect, useRef, useState } from 'react'

/** Interroge /state chaque seconde. Jamais silencieux : en cas d'échec on garde la dernière donnée ET on le signale. */
export function useRemediator(url = '/state', every = 1000) {
  const [snap, setSnap] = useState(null)       // { s: état du moteur, at: horloge locale (ms) à la réception }
  const [lost, setLost] = useState(null)       // { since: ms } tant que le moteur est injoignable
  const [tick, setTick] = useState(() => Date.now())
  const failRef = useRef(0)

  useEffect(() => {
    let stop = false, timer
    const poll = async () => {
      const ctl = new AbortController(), kill = setTimeout(() => ctl.abort(), 2500)
      try {
        const r = await fetch(url, { signal: ctl.signal, cache: 'no-store' })
        if (!r.ok) throw new Error(String(r.status))
        const s = await r.json()
        if (!stop) { setSnap({ s, at: Date.now() }); failRef.current = 0; setLost(null) }
      } catch {
        if (!stop) { failRef.current += 1; setLost((l) => l ?? { since: Date.now() }) }
      } finally { clearTimeout(kill); if (!stop) timer = setTimeout(poll, every) }
    }
    poll()
    return () => { stop = true; clearTimeout(timer) }
  }, [url, every])

  useEffect(() => { const t = setInterval(() => setTick(Date.now()), 1000); return () => clearInterval(t) }, [])
  // heure serveur « maintenant » : dernière heure reçue + temps écoulé localement
  const now = snap ? snap.s.now + (tick - snap.at) / 1000 : null
  return { state: snap?.s ?? null, now, lost, lostFor: lost ? (tick - lost.since) / 1000 : 0 }
}
