import { eur, fullDate, shortRef } from '../lib/format.js'
import Icon from './Icons.jsx'
import { Avatar } from './ui.jsx'

/** Reçu de paiement : l'objet central de l'écran. `receipt` = { id, amount, label, created_at, from, to, fresh, duplicate }. */
export default function Ticket({ receipt, onClose }) {
  const r = receipt
  const who = r.direction === 'in' ? r.from : r.to
  const head = !r.fresh ? { text: 'Reçu de l’opération', cls: 'bg-brand-soft text-brand-deep', icon: 'receipt' }
    : r.duplicate ? { text: 'Paiement déjà enregistré', cls: 'bg-ok-soft text-ok', icon: 'check' }
    : { text: 'Paiement enregistré', cls: 'bg-ok-soft text-ok', icon: 'check' }
  return (
    <section aria-labelledby="ticket-title" className="ticket-wrap">
      <div className="ticket px-6 pt-5">
        <div className="flex items-start justify-between gap-3">
          <p id="ticket-title" className={`${head.cls} inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold`}>
            <Icon name={head.icon} size={16} /> {head.text}
          </p>
          <button type="button" onClick={onClose} aria-label="Fermer le reçu" className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:text-ink">
            <Icon name="close" size={18} />
          </button>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Avatar name={who} size="lg" />
          <div className="min-w-0">
            <p className="text-sm text-muted">{r.direction === 'in' ? 'Reçu de' : 'Envoyé à'}</p>
            <p className="truncate text-lg font-semibold">{who}</p>
          </div>
        </div>
        <p className="mt-3 text-5xl font-semibold tabular-nums tracking-tight">{eur(r.amount)}</p>
        {r.fresh && r.duplicate && <p className="mt-2 text-sm text-muted">Cette demande avait déjà été traitée : vous n’avez été débité qu’une seule fois.</p>}

        <div className="tear my-6" aria-hidden="true" />

        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2.5 pb-3 text-sm">
          <dt className="text-muted">Libellé</dt><dd className="text-right font-medium">{r.label || 'Aucun'}</dd>
          <dt className="text-muted">De</dt><dd className="text-right font-medium">{r.from}</dd>
          <dt className="text-muted">À</dt><dd className="text-right font-medium">{r.to}</dd>
          <dt className="text-muted">Date</dt><dd className="text-right font-medium">{fullDate(r.created_at)}</dd>
          <dt className="text-muted">Référence</dt><dd className="text-right font-mono text-[13px] font-medium tracking-wide">{shortRef(r.id)}</dd>
        </dl>
      </div>
    </section>
  )
}
