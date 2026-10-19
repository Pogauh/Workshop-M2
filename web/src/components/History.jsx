import { dayLabel, eur, timeLabel } from '../lib/format.js'
import Icon from './Icons.jsx'
import { Avatar } from './ui.jsx'

export default function History({ items, names, onOpen, loading }) {
  const groups = []
  for (const p of items) {
    const d = dayLabel(p.created_at)
    if (groups.at(-1)?.day !== d) groups.push({ day: d, rows: [] })
    groups.at(-1).rows.push(p)
  }
  return (
    <section aria-labelledby="hist-title" className="rounded-2xl border border-line bg-surface">
      <h2 id="hist-title" className="px-5 pb-2 pt-5 text-xl font-semibold tracking-tight sm:px-6">Dernières opérations</h2>
      {items.length === 0 ? (
        <p className="px-5 pb-6 pt-2 text-muted sm:px-6">{loading ? 'Chargement…' : 'Aucune opération pour l’instant. Votre premier paiement apparaîtra ici.'}</p>
      ) : (
        <div className="pb-2">
          {groups.map((g) => (
            <div key={g.day}>
              <h3 className="px-5 pb-1 pt-3 text-xs font-semibold text-muted sm:px-6">{g.day}</h3>
              <ul>
                {g.rows.map((p) => {
                  const out = p.direction === 'out', who = names[p.counterparty] ?? p.counterparty
                  return (
                    <li key={p.id}>
                      <button type="button" onClick={() => onOpen(p)} className="flex w-full items-center gap-3 px-5 py-2.5 text-left hover:bg-bg sm:px-6"
                              aria-label={`${out ? 'Envoyé à' : 'Reçu de'} ${who}, ${eur(p.amount)}, ${timeLabel(p.created_at)}. Ouvrir le reçu`}>
                        <Avatar name={who} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{who}</span>
                          <span className="block truncate text-sm text-muted">{p.label || (out ? 'Paiement envoyé' : 'Paiement reçu')}, {timeLabel(p.created_at)}</span>
                        </span>
                        <span className={`flex items-center gap-1 text-right font-semibold tabular-nums ${out ? 'text-ink' : 'text-ok'}`}>
                          <Icon name={out ? 'out' : 'in'} size={16} />
                          {out ? '−' : '+'}{eur(p.amount)}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
