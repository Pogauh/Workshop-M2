import { useRef, useState } from 'react'
import { newKey, explain } from '../lib/api.js'
import { amountProblem, eur, labelProblem, parseAmount, MAX_LABEL } from '../lib/format.js'
import Icon from './Icons.jsx'
import { Avatar, Notice } from './ui.jsx'

const QUICK = [10, 25, 50, 100]

export default function Composer({ api, balance, beneficiaries, onPaid, onSessionLost }) {
  const [to, setTo] = useState('')
  const [amountText, setAmountText] = useState('')
  const [label, setLabel] = useState('')
  const [phase, setPhase] = useState({ kind: 'idle' })       // idle | sending | retrying
  const [error, setError] = useState(null)
  const keyRef = useRef(null)                                  // { intent, key } : une même intention garde la même clé anti-doublon

  const amount = parseAmount(amountText)
  const aProblem = amountProblem(amountText, balance)
  const lProblem = labelProblem(label)
  const target = beneficiaries.find((b) => b.id === to)
  const ready = Boolean(target && amount && !aProblem && !lProblem) && phase.kind === 'idle'

  async function submit(e) {
    e.preventDefault()
    if (!ready) return
    const intent = `${to}|${amount}|${label}`
    if (keyRef.current?.intent !== intent) keyRef.current = { intent, key: newKey() }
    setError(null); setPhase({ kind: 'sending' })
    try {
      const res = await api.pay({ to, amount, label: label.trim() }, keyRef.current.key, (r) => setPhase({ kind: 'retrying', ...r }))
      keyRef.current = null
      setTo(''); setAmountText(''); setLabel('')
      onPaid({ ...res, toName: target.name })
    } catch (err) {
      if (err.status === 401 || (err.status === 403 && /suspended/.test(err.detail || ''))) { onSessionLost(err); return }
      setError(explain(err.status, err.detail))
    } finally { setPhase({ kind: 'idle' }) }
  }

  const busy = phase.kind !== 'idle'
  return (
    <form onSubmit={submit} noValidate className="rounded-2xl border border-line bg-surface p-5 sm:p-6" aria-labelledby="pay-title">
      <h2 id="pay-title" className="text-xl font-semibold tracking-tight">Nouveau paiement</h2>

      <fieldset className="mt-5" disabled={busy}>
        <legend className="mb-2 text-sm font-medium">Bénéficiaire</legend>
        {beneficiaries.length === 0 ? (
          <p className="text-sm text-muted">Chargement des bénéficiaires…</p>
        ) : (
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Bénéficiaire">
            {beneficiaries.map((b) => {
              const on = b.id === to
              return (
                <label key={b.id} className={`flex cursor-pointer items-center gap-2.5 rounded-full border py-1.5 pl-1.5 pr-4 text-sm font-medium transition-colors
                  ${on ? 'border-brand bg-brand-soft text-brand-deep' : 'border-line bg-surface hover:border-[#b4c0d8]'} has-[:focus-visible]:outline has-[:focus-visible]:outline-[3px] has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand`}>
                  <input type="radio" name="to" value={b.id} checked={on} onChange={() => setTo(b.id)} className="sr-only" />
                  <Avatar name={b.name} />
                  <span>{b.name}</span>
                  {on && <Icon name="check" size={16} />}
                </label>
              )
            })}
          </div>
        )}
      </fieldset>

      <div className="mt-6">
        <label htmlFor="amount" className="mb-1 block text-sm font-medium">Montant</label>
        <div className={`flex items-baseline gap-2 border-b-2 pb-1 transition-colors ${aProblem ? 'border-bad' : 'border-line focus-within:border-brand focus-within:shadow-[0_2px_0_0_var(--brand)]'}`}>
          <input id="amount" inputMode="decimal" autoComplete="off" placeholder="0,00" disabled={busy}
                 aria-invalid={Boolean(aProblem)} aria-describedby={aProblem ? 'amount-help' : undefined}
                 className="w-full min-w-0 flex-1 bg-transparent text-4xl font-semibold tabular-nums tracking-tight placeholder:text-[#b9c3d9] focus:outline-none sm:text-6xl"
                 value={amountText} onChange={(e) => setAmountText(e.target.value)} />
          <span className="text-3xl font-semibold text-muted sm:text-5xl" aria-hidden="true">€</span>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {QUICK.map((q) => (
            <button key={q} type="button" disabled={busy} onClick={() => setAmountText(String(q))}
                    className="rounded-full border border-line px-3 py-1 text-sm font-medium tabular-nums text-muted hover:border-[#b4c0d8] hover:text-ink">{q} €</button>
          ))}
          {aProblem && <p id="amount-help" role="alert" className="ml-auto text-sm font-medium text-bad">{aProblem}</p>}
        </div>
      </div>

      <div className="mt-5">
        <div className="mb-1.5 flex items-baseline justify-between">
          <label htmlFor="label" className="text-sm font-medium">Libellé <span className="font-normal text-muted">(facultatif)</span></label>
          <span className={`text-xs tabular-nums ${label.length > MAX_LABEL ? 'text-bad' : 'text-muted'}`}>{label.length}/{MAX_LABEL}</span>
        </div>
        <input id="label" className="field" autoComplete="off" disabled={busy} value={label} onChange={(e) => setLabel(e.target.value)}
               aria-invalid={Boolean(lProblem)} aria-describedby={lProblem ? 'label-help' : undefined} />
        {lProblem && <p id="label-help" role="alert" className="mt-1.5 text-sm font-medium text-bad">{lProblem}</p>}
      </div>

      <div className="mt-6 space-y-3" aria-live="polite">
        {phase.kind === 'retrying' && (
          <Notice tone="warn" icon={<Icon name="spinner" size={18} spin className="mt-0.5 shrink-0" />}>
            Le service reprend, nouvelle tentative {phase.attempt} sur {phase.max}. Votre paiement ne sera débité qu’une seule fois.
          </Notice>
        )}
        {error && <Notice tone="bad" role="alert" icon={<Icon name="alert" size={18} className="mt-0.5 shrink-0" />}>{error}</Notice>}
      </div>

      <button type="submit" disabled={!ready} className="btn btn-primary mt-4 w-full py-3.5 text-base">
        {busy ? <><Icon name="spinner" spin /> Envoi en cours…</>
          : ready ? <>Envoyer {eur(amount)} à {target.name}</> : 'Envoyer le paiement'}
      </button>
    </form>
  )
}
