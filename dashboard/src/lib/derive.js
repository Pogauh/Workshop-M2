// Dérivations pures de l'état du moteur de remédiation (testables sans navigateur).

export const STATES = {
  HOMEOSTASIS: { label: 'Homéostasie', text: 'Tout est normal : le service répond et les comptes sont cohérents.', tone: 'ok' },
  SURVEILLANCE: { label: 'Surveillance', text: 'Anomalie suspectée : observation renforcée, aucune action encore.', tone: 'warn' },
  IMMUNITY: { label: 'Immunité', text: 'Défense active : le moteur applique des contre-mesures.', tone: 'serious' },
  REGENERATION: { label: 'Régénération', text: 'Reprise en cours : vérification par une vraie transaction.', tone: 'info' },
  RESTORED: { label: 'Rétabli', text: 'Service vérifié : transaction écrite, relue et solde total cohérent.', tone: 'ok' },
  CONTAINED: { label: 'Menace contenue', text: 'L’attaque persiste mais ne touche plus le service.', tone: 'warn' },
  ESCALATION: { label: 'Escalade', text: 'Reprise non vérifiée : intervention humaine requise.', tone: 'crit' },
}
export const ATTACKS = {
  dos: 'Surcharge d’un compte (déni de service applicatif)',
  bruteforce: 'Brute-force sur la connexion',
  outage: 'Panne d’un service',
}
export const ACTIONS = {
  throttle: 'Limiter le débit de paiement par session',
  suspend_user: 'Suspendre le compte abusif',
  ban_ip: 'Bannir l’adresse source au WAF',
  restart_api: 'Redémarrer l’API depuis l’image saine',
  contain_compromise: 'Contenir la compromission : révoquer les sessions, forcer la réinitialisation, verrouiller',
  lock_account: 'Verrouiller le compte attaqué',
  throttle_login: 'Limiter le débit de connexion par IP',
  restart_auth: 'Redémarrer le service d’authentification',
  restart_db: 'Redémarrer la base de données',
}
export const SERVICES = { waf: 'Pare-feu applicatif', api: 'API de paiement', auth: 'Authentification', db: 'Base de données' }
export const DEFAULT_PAY_RATE = 60

export const actionLabel = (n) => ACTIONS[n] ?? String(n).replaceAll('_', ' ')

/** Fenêtre temporelle : points des 3 pistes + bornes. now/windowSec en secondes. */
export function windowSeries(s, windowSec, now = s?.now ?? 0) {
  const from = now - windowSec
  const inWin = (p) => p.ts >= from && p.ts <= now + 1
  const det = (s?.dhist ?? []).filter(inWin), probe = (s?.hist ?? []).filter(inWin)
  return {
    from, to: now,
    rps: det.filter((p) => p.rps != null).map((p) => ({ ts: p.ts, v: p.rps, kind: p.kind })),
    score: det.filter((p) => p.score != null).map((p) => ({ ts: p.ts, v: p.score, kind: p.kind })),
    latency: probe.map((p) => ({ ts: p.ts, v: p.ms, ok: p.ok })),
  }
}

/** Bandes avant / pendant / après autour du dernier incident, à partir des repères (markers) du moteur. */
export function phaseBands(markers = [], from, to) {
  const detect = [...markers].reverse().find((m) => m.kind === 'detect')
  if (!detect) return [{ id: 'before', from, to, label: 'Régime normal' }]
  const end = markers.find((m) => (m.kind === 'restored' || m.kind === 'escalation') && m.ts >= detect.ts)
  const bands = []
  if (detect.ts > from) bands.push({ id: 'before', from, to: Math.min(detect.ts, to), label: 'Avant' })
  bands.push({ id: 'during', from: Math.max(detect.ts, from), to: Math.min(end ? end.ts : to, to), label: 'Attaque et défense' })
  if (end && end.ts < to) bands.push({ id: end.kind === 'restored' ? 'after' : 'escalation', from: Math.max(end.ts, from), to,
    label: end.kind === 'restored' ? 'Service rétabli' : 'Escalade' })
  return bands.filter((b) => b.to > b.from)
}

export function fmtDur(sec) {
  if (sec == null || !Number.isFinite(sec)) return 'n/a'
  const s = Math.max(0, Math.round(sec))
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`
}
export const fmtClock = (ts) => new Date(ts * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
export const fmtNum = (v, d = 1) => (v == null || !Number.isFinite(v) ? 'n/a' : v.toLocaleString('fr-FR', { maximumFractionDigits: d, minimumFractionDigits: 0 }))

export function serviceView(v) {
  if (!v || v.state === 'missing') return { tone: 'crit', text: 'Absent' }
  if (v.state !== 'running') return { tone: 'crit', text: 'Arrêté' }
  if (v.health === 'unhealthy') return { tone: 'serious', text: 'Défaillant' }
  if (v.health === 'starting') return { tone: 'warn', text: 'Démarrage' }
  return { tone: 'ok', text: 'En service' }
}

export function detectorView(d) {
  if (!d || !d.kind) return { tone: 'off', text: 'En attente du détecteur' }
  return ({ normal: { tone: 'ok', text: 'Trafic normal' }, suspect: { tone: 'warn', text: 'Fenêtre suspecte' },
    anomaly: { tone: 'serious', text: 'Anomalie qualifiée' }, no_model: { tone: 'crit', text: 'Aucun modèle chargé' },
    detector_error: { tone: 'crit', text: 'Détecteur en erreur' } })[d.kind] ?? { tone: 'off', text: d.kind }
}

/** Incident à afficher : en cours, sinon le dernier de l'historique. */
export function currentIncident(s) {
  if (s?.incident) return { ...s.incident, live: s.busy || !s.incident.restored_at }
  return null
}

export const SEVERITY = { critical: { tone: 'crit', text: 'Critique' }, high: { tone: 'serious', text: 'Élevée' }, medium: { tone: 'warn', text: 'Moyenne' }, info: { tone: 'info', text: 'Info' } }
export const RULES = { R1: 'Attaque applicative bloquée', R2: 'Brute-force', R3: 'Compromission probable', R4: 'Abus d’API', R5: 'Compte suspendu actif' }
