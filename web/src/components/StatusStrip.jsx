import { useEffect, useState } from 'react'
import Icon from './Icons.jsx'

/** Bande d'état du service, mesurée depuis le navigateur du client (même chemin que ses paiements, WAF compris). */
export function useServiceHealth(api, every = 4000) {
  const [h, setH] = useState({ level: 'checking', ms: null })
  useEffect(() => {
    let stop = false, fails = 0, timer
    const tick = async () => {
      const r = await api.health()
      if (stop) return
      fails = r.up ? 0 : fails + 1
      setH(r.up ? { level: r.ms >= 800 ? 'slow' : 'ok', ms: r.ms } : { level: fails >= 2 ? 'down' : 'slow', ms: null })
      timer = setTimeout(tick, document.hidden ? every * 4 : every)
    }
    tick()
    return () => { stop = true; clearTimeout(timer) }
  }, [api, every])
  return h
}

const VIEW = {
  checking: { text: 'Vérification du service', cls: 'text-muted', icon: 'spinner' },
  ok: { text: 'Service opérationnel', cls: 'text-ok', icon: null },
  slow: { text: 'Service ralenti', cls: 'text-warn', icon: 'alert' },
  down: { text: 'Reprise du service en cours', cls: 'text-bad', icon: 'alert' },
}

export default function StatusStrip({ health }) {
  const v = VIEW[health.level]
  return (
    <p role="status" aria-live="polite" className={`${v.cls} flex items-center gap-2 text-sm font-medium`}>
      {v.icon ? <Icon name={v.icon} size={16} spin={health.level === 'checking'} /> : <span className="pulse" aria-hidden="true" />}
      <span>{v.text}</span>
      {health.ms != null && <span className="tabular-nums text-muted font-normal">{health.ms} ms</span>}
    </p>
  )
}
