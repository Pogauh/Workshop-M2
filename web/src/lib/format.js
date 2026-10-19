// Formats d'affichage et validation de saisie. Aucune dépendance : testable avec `node --test`.
const money = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
export const MAX_AMOUNT = 10000
export const MAX_LABEL = 64
export const LABEL_RE = /^[\p{L}\p{N}_ .,'()\-]*$/u   // miroir du contrôle serveur (l'API reste l'autorité)

export const eur = (v) => money.format(Number(v))

/** « 12,5 » ou « 12.50 » -> "12.50" ; null si la saisie n'est pas un montant valide (1 centime à 10 000 €). */
export function parseAmount(input) {
  const s = String(input ?? '').trim().replace(/[\s  ]/g, '').replace(',', '.')
  if (!/^\d{1,5}(\.\d{1,2})?$/.test(s)) return null
  const n = Number(s)
  if (!(n >= 0.01) || n > MAX_AMOUNT) return null
  return n.toFixed(2)
}

/** Message d'aide pour le champ montant ('' si rien à signaler ou champ vide). */
export function amountProblem(input, balance) {
  const raw = String(input ?? '').trim()
  if (!raw) return ''
  const a = parseAmount(raw)
  if (a === null) return Number(raw.replace(',', '.')) > MAX_AMOUNT ? 'Le plafond par paiement est de 10 000 €.' : 'Saisissez un montant valide (2 décimales au plus).'
  if (balance !== undefined && balance !== null && Number(a) > Number(balance)) return 'Solde insuffisant pour ce paiement.'
  return ''
}

export const labelProblem = (s) => (s.length > MAX_LABEL ? 'Libellé trop long (64 caractères au plus).'
  : !LABEL_RE.test(s) ? 'Caractères autorisés : lettres, chiffres, espace et . , \' ( ) -' : '')

export function initials(name = '') {
  const parts = String(name).trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

const dayFmt = new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })
const timeFmt = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })
const fullFmt = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long', timeStyle: 'medium' })
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

export function dayLabel(iso, now = new Date()) {
  const d = new Date(iso), diff = Math.round((startOfDay(now) - startOfDay(d)) / 86400000)
  return diff === 0 ? "Aujourd'hui" : diff === 1 ? 'Hier' : dayFmt.format(d)
}
export const timeLabel = (iso) => timeFmt.format(new Date(iso))
export const fullDate = (iso) => fullFmt.format(new Date(iso))
export const shortRef = (id = '') => String(id).replace(/-/g, '').slice(0, 8).toUpperCase()
