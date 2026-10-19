import { STATES, ATTACKS, fmtDur } from './lib/derive.js'
import { useRemediator } from './lib/useRemediator.js'
import { Icon, TONE } from './components/ui.jsx'
import Vitals from './components/Vitals.jsx'
import { Defenses, Detector, Incident, Journal, Services, Siem } from './components/Panels.jsx'

const LINKS = [['Grafana', 'http://localhost:3001'], ['Assistant IA', 'http://localhost:3002'], ['Application de paiement', 'http://localhost:8080']]

/** Électrocardiogramme décoratif : défile tant que le système vit, devient une ligne plate en cas d'escalade. */
function Ecg({ flat, color }) {
  const beat = 'M0 24h40l6-10 6 22 8-34 8 30 6-8h30'
  return (
    <svg className="absolute inset-y-0 left-[38%] hidden h-full w-[26%] opacity-40 xl:block [mask-image:linear-gradient(90deg,transparent,#000_25%,#000_75%,transparent)]" viewBox="0 0 400 48" preserveAspectRatio="none" aria-hidden="true">
      <g className={flat ? '' : 'ecg'} style={{ transformBox: 'fill-box' }}>
        <path d={flat ? 'M0 24h800' : [0, 1, 2, 3].map((i) => `M${i * 100} 24h40l6-10 6 22 8-34 8 30 6-8h26`).join('') + 'M400 24h400'} fill="none" stroke={color} strokeWidth="2.2" vectorEffect="non-scaling-stroke" />
      </g>
    </svg>
  )
}

export default function App() {
  const { state, now, lost, lostFor } = useRemediator()
  if (!state) {
    return (
      <main className="grid min-h-screen place-items-center px-4">
        <p role="status" className="flex items-center gap-3 text-muted">
          <Icon name="clock" /> {lost ? 'Moteur de remédiation injoignable. Nouvel essai chaque seconde.' : 'Connexion au moteur de remédiation…'}
        </p>
      </main>
    )
  }
  const meta = STATES[state.state] ?? { label: state.state, text: '', tone: 'off' }
  const tone = TONE[meta.tone]
  const color = { ok: 'var(--ok)', warn: 'var(--warn)', serious: 'var(--serious)', crit: 'var(--crit)', info: 'var(--info)' }[meta.tone] ?? 'var(--muted)'
  return (
    <div className="mx-auto max-w-[1500px] px-4 pb-10 pt-4 sm:px-6">
      {lost && (
        <p role="alert" className="mb-3 flex items-center gap-2 rounded-lg border border-crit bg-panel px-4 py-2.5 text-sm font-semibold text-crit">
          <Icon name="cross" /> Connexion au moteur perdue depuis {fmtDur(lostFor)}. Les valeurs affichées datent d’avant la coupure.
        </p>)}
      <header className="relative mb-4 overflow-hidden rounded-xl border border-line bg-panel">
        <Ecg flat={state.state === 'ESCALATION'} color={color} />
        <div className="relative flex flex-wrap items-center justify-between gap-x-8 gap-y-3 px-5 py-4">
          <div className="min-w-0">
            <p className="text-sm text-muted">Système immunitaire numérique</p>
            <h1 className={`${tone.text} flex items-center gap-3 text-3xl font-semibold tracking-tight`}>
              {state.state === 'HOMEOSTASIS' ? <span className="live" aria-hidden="true" /> : <Icon name={tone.icon} size={28} />}
              {meta.label}
            </h1>
            <p className="mt-1 max-w-[60ch] text-ink">{meta.text}</p>
          </div>
          <div className="flex flex-col items-start gap-2 text-sm md:items-end">
            <p className="tabular-nums text-muted">Dans cet état depuis {fmtDur(now - state.since)}</p>
            {state.attack && <p>Type de menace : <span className="font-semibold">{ATTACKS[state.attack] ?? state.attack}</span></p>}
            <nav aria-label="Autres outils" className="flex flex-wrap gap-x-4 gap-y-1">
              {LINKS.map(([l, h]) => <a key={l} href={h} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-info underline-offset-4 hover:underline"><Icon name="link" size={15} />{l}</a>)}
            </nav>
          </div>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <Vitals state={state} now={now} />
          <div className="grid gap-4 xl:grid-cols-2">
            <Incident state={state} now={now} />
            <Siem state={state} now={now} />
          </div>
        </div>
        <div className="min-w-0 space-y-4">
          <Services state={state} />
          <Detector state={state} />
          <Defenses state={state} now={now} />
        </div>
        <Journal state={state} />
      </div>
    </div>
  )
}
