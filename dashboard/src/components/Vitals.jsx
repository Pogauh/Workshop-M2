import { useEffect, useMemo, useRef, useState } from 'react'
import { actionLabel, fmtClock, fmtNum, phaseBands, windowSeries } from '../lib/derive.js'
import { Panel } from './ui.jsx'

const BAND = { before: 'transparent', during: 'rgba(239,91,83,0.10)', after: 'rgba(63,178,127,0.10)', escalation: 'rgba(239,91,83,0.20)' }
const TRACKS = [
  { id: 'rps', title: 'Débit de requêtes', unit: 'req/s', pick: (w) => w.rps, min: 0, floor: 10 },
  { id: 'latency', title: 'Transaction témoin : latence', unit: 'ms', pick: (w) => w.latency, min: 0, floor: 300 },
  { id: 'score', title: 'Score d’anomalie (plus bas : plus anormal)', unit: '', pick: (w) => w.score, min: null, floor: null },
]
const G = { left: 52, right: 14, top: 46, track: 80, gap: 14, bottom: 24 }
const WINDOWS = [[120, '2 min'], [300, '5 min'], [600, '10 min']]

function domain(t, pts) {
  const vals = pts.map((p) => p.v)
  if (t.id === 'score') {
    const lo = Math.min(-0.05, ...vals), hi = Math.max(0.05, ...vals), pad = (hi - lo) * 0.12
    return [lo - pad, hi + pad]
  }
  return [0, Math.max(t.floor, ...vals) * 1.12]
}
const line = (pts, x, y) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.ts).toFixed(1)},${y(p.v).toFixed(1)}`).join('')

export default function Vitals({ state, now }) {
  const [win, setWin] = useState(300)
  const [table, setTable] = useState(false)
  const [hover, setHover] = useState(null)
  const wrap = useRef(null)
  const [W, setW] = useState(960)

  useEffect(() => {
    if (!wrap.current || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.floor(e.contentRect.width))))
    ro.observe(wrap.current)
    return () => ro.disconnect()
  }, [table])

  const w = useMemo(() => windowSeries(state, win, now), [state, win, now])
  const bands = useMemo(() => phaseBands(state.markers, w.from, w.to), [state.markers, w.from, w.to])
  const marks = (state.markers ?? []).filter((m) => m.ts >= w.from && m.ts <= w.to)
  const actions = marks.filter((m) => m.kind === 'action')
  const H = G.top + TRACKS.length * G.track + (TRACKS.length - 1) * G.gap + G.bottom
  const plotW = W - G.left - G.right
  const x = (ts) => G.left + ((ts - w.from) / (w.to - w.from)) * plotW
  const trackTop = (i) => G.top + i * (G.track + G.gap)

  function onMove(e) {
    const r = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - r.left
    if (px < G.left || px > W - G.right) return setHover(null)
    const ts = w.from + ((px - G.left) / plotW) * (w.to - w.from)
    const near = (arr) => arr.reduce((b, p) => (!b || Math.abs(p.ts - ts) < Math.abs(b.ts - ts) ? p : b), null)
    setHover({ px, ts, rps: near(w.rps), latency: near(w.latency), score: near(w.score) })
  }

  const rows = useMemo(() => [...w.rps].reverse().slice(0, 14).map((p) => {
    const l = w.latency.reduce((b, q) => (!b || Math.abs(q.ts - p.ts) < Math.abs(b.ts - p.ts) ? q : b), null)
    const sc = w.score.find((q) => q.ts === p.ts)
    return { ts: p.ts, rps: p.v, kind: p.kind, ms: l?.v, ok: l?.ok, score: sc?.v }
  }), [w])

  return (
    <Panel id="vitals" title="Signes vitaux"
      right={<div className="flex flex-wrap items-center gap-3">
        <div className="seg" role="group" aria-label="Fenêtre d’observation">
          {WINDOWS.map(([s, l]) => <button key={s} type="button" aria-pressed={win === s} onClick={() => setWin(s)}>{l}</button>)}
        </div>
        <button type="button" onClick={() => setTable(!table)} aria-pressed={table} className="rounded-lg border border-line px-3 py-1 text-sm text-muted hover:text-ink">
          {table ? 'Voir le graphique' : 'Voir en tableau'}
        </button>
      </div>}>
      {table ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <caption className="sr-only">Dernières mesures du détecteur et de la transaction témoin</caption>
            <thead><tr className="text-left text-muted">
              <th className="py-1.5 pr-3 font-medium">Heure</th><th className="pr-3 font-medium">Débit (req/s)</th><th className="pr-3 font-medium">Latence témoin (ms)</th>
              <th className="pr-3 font-medium">Score</th><th className="font-medium">Détecteur</th></tr></thead>
            <tbody className="tabular-nums">
              {rows.map((r) => (
                <tr key={r.ts} className="border-t border-line">
                  <td className="py-1.5 pr-3">{fmtClock(r.ts)}</td><td className="pr-3">{fmtNum(r.rps)}</td>
                  <td className="pr-3">{r.ms == null ? 'n/a' : `${fmtNum(r.ms, 0)}${r.ok === false ? ' (échec)' : ''}`}</td><td className="pr-3">{fmtNum(r.score, 3)}</td>
                  <td>{{ normal: 'Normal', suspect: 'Suspect', anomaly: 'Anomalie' }[r.kind] ?? r.kind}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan="5" className="py-3 text-muted">Aucune mesure dans cette fenêtre.</td></tr>}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={wrap} className="relative">
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" onMouseMove={onMove} onMouseLeave={() => setHover(null)}
               aria-label="Débit, latence de la transaction témoin et score d’anomalie sur la fenêtre choisie, avec les phases avant, attaque et après"
               className="block max-w-full select-none">
            {/* phases : avant / pendant / après */}
            {bands.map((b) => (
              <g key={b.id + b.from}>
                <rect x={x(b.from)} y={G.top - 6} width={Math.max(0, x(b.to) - x(b.from))} height={H - G.top - G.bottom + 12} fill={BAND[b.id]} />
                {x(b.to) - x(b.from) > b.label.length * 6.4 + 12 && <text x={x(b.from) + 6} y={13} fontSize="11.5" fill="var(--muted)">{b.label}</text>}
              </g>
            ))}
            {TRACKS.map((t, i) => {
              const pts = t.pick(w), top = trackTop(i), [lo, hi] = domain(t, pts)
              const y = (v) => top + G.track - ((v - lo) / (hi - lo)) * G.track
              return (
                <g key={t.id}>
                  <text x={G.left} y={top + 11} fontSize="12" fill="var(--ink)" fontWeight="600" style={{ paintOrder: 'stroke' }}>{t.title}{t.unit ? ` (${t.unit})` : ''}</text>
                  <line x1={G.left} x2={W - G.right} y1={top + G.track} y2={top + G.track} stroke="var(--line)" />
                  {[0, 1].map((k) => { const v = lo + (hi - lo) * (k ? 1 : 0); return (
                    <text key={k} x={G.left - 8} y={y(v) + (k ? 9 : 0)} textAnchor="end" fontSize="11" fill="var(--muted)" className="tabular-nums">{fmtNum(v, t.id === 'score' ? 2 : 0)}</text>) })}
                  {pts.length > 1 && <path d={line(pts, x, y)} fill="none" stroke="var(--series)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />}
                  {pts.length === 1 && <circle cx={x(pts[0].ts)} cy={y(pts[0].v)} r="3.5" fill="var(--series)" />}
                  {pts.length === 0 && <text x={G.left + 8} y={top + G.track / 2 + 4} fontSize="12" fill="var(--muted)">En attente de mesures</text>}
                  {t.id === 'rps' && pts.map((p) => p.kind === 'anomaly' ? <circle key={p.ts} cx={x(p.ts)} cy={top + G.track - 4} r="3.5" fill="var(--crit)" stroke="var(--panel)" strokeWidth="1.5" />
                    : p.kind === 'suspect' ? <rect key={p.ts} x={x(p.ts) - 3} y={top + G.track - 7} width="6" height="6" transform={`rotate(45 ${x(p.ts)} ${top + G.track - 4})`} fill="none" stroke="var(--warn)" strokeWidth="1.8" /> : null)}
                  {t.id === 'latency' && pts.filter((p) => !p.ok).map((p) => (
                    <path key={p.ts} d={`M${x(p.ts) - 4},${y(p.v) - 4}l8,8M${x(p.ts) + 4},${y(p.v) - 4}l-8,8`} stroke="var(--crit)" strokeWidth="2" strokeLinecap="round" />))}
                </g>
              )
            })}
            {/* repères du moteur : détection, actions numérotées, rétablissement */}
            {marks.map((m, i) => {
              const n = actions.indexOf(m) + 1
              const c = m.kind === 'detect' ? 'var(--crit)' : m.kind === 'restored' ? 'var(--ok)' : m.kind === 'escalation' ? 'var(--crit)' : 'var(--info)'
              return (
                <g key={m.ts + m.label + i}>
                  <line x1={x(m.ts)} x2={x(m.ts)} y1={G.top - 12} y2={H - G.bottom} stroke={c} strokeWidth="1.5" strokeDasharray={m.kind === 'action' ? '2 3' : '5 3'} />
                  {m.kind === 'action'
                    ? <g><circle cx={x(m.ts)} cy={G.top - 20} r="8" fill={c} /><text x={x(m.ts)} y={G.top - 16} textAnchor="middle" fontSize="11" fontWeight="700" fill="#06121a">{n}</text></g>
                    : <text x={x(m.ts) + (x(m.ts) > W - 90 ? -4 : 4)} y={H - G.bottom - 4} textAnchor={x(m.ts) > W - 90 ? 'end' : 'start'} fontSize="11.5" fontWeight="600" fill={c}>{m.kind === 'detect' ? 'Détection' : m.kind === 'restored' ? 'Rétabli' : 'Escalade'}</text>}
                </g>
              )
            })}
            {/* axe du temps */}
            {(plotW < 520 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]).map((f) => (
              <text key={f} x={G.left + f * plotW} y={H - 6} fontSize="11" fill="var(--muted)" textAnchor={f === 0 ? 'start' : f === 1 ? 'end' : 'middle'} className="tabular-nums">{fmtClock(w.from + f * (w.to - w.from))}</text>))}
            {hover && <line x1={hover.px} x2={hover.px} y1={G.top - 4} y2={H - G.bottom} stroke="var(--ink)" strokeOpacity=".55" />}
          </svg>
          {hover && (
            <div className="pointer-events-none absolute top-10 z-10 min-w-[190px] rounded-lg border border-line bg-raise px-3 py-2 text-xs shadow-lg"
                 style={{ left: Math.min(Math.max(hover.px + 12, 4), W - 210) }}>
              <p className="mb-1 font-semibold tabular-nums">{fmtClock(hover.ts)}</p>
              <p className="tabular-nums">Débit : {hover.rps ? `${fmtNum(hover.rps.v)} req/s` : 'n/a'}</p>
              <p className="tabular-nums">Latence témoin : {hover.latency ? `${fmtNum(hover.latency.v, 0)} ms${hover.latency.ok ? '' : ' (échec)'}` : 'n/a'}</p>
              <p className="tabular-nums">Score : {hover.score ? fmtNum(hover.score.v, 3) : 'n/a'}</p>
            </div>
          )}
        </div>
      )}

      {/* légende : toujours visible, jamais la couleur seule */}
      <ul className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[0.8rem] text-muted">
        <li className="flex items-center gap-1.5"><svg width="22" height="8" aria-hidden="true"><path d="M1 4h20" stroke="var(--series)" strokeWidth="2" strokeLinecap="round" /></svg>Mesure</li>
        <li className="flex items-center gap-1.5"><svg width="12" height="12" aria-hidden="true"><rect x="3" y="3" width="6" height="6" transform="rotate(45 6 6)" fill="none" stroke="var(--warn)" strokeWidth="1.8" /></svg>Fenêtre suspecte</li>
        <li className="flex items-center gap-1.5"><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="3.5" fill="var(--crit)" /></svg>Anomalie qualifiée</li>
        <li className="flex items-center gap-1.5"><svg width="12" height="12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="var(--crit)" strokeWidth="2" strokeLinecap="round" /></svg>Transaction témoin en échec</li>
      </ul>
      {actions.length > 0 && (
        <ol className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[0.82rem]">
          {actions.map((a, i) => (
            <li key={a.ts + a.label} className="flex items-center gap-1.5 text-ink">
              <span className="grid h-[18px] w-[18px] place-items-center rounded-full bg-info text-[11px] font-bold text-[#06121a]">{i + 1}</span>{actionLabel(a.label)}
            </li>))}
        </ol>
      )}
    </Panel>
  )
}
