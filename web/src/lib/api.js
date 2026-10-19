// Client HTTP de PayAlpha. Pas de dépendance : `fetch` et `sleep` sont injectables, donc testable sans navigateur.
//
// Reprise après incident : un paiement est envoyé avec une clé d'idempotence unique. Si le service est momentanément
// indisponible (redémarrage, limitation de débit, panne), la MÊME clé est renvoyée : le serveur ne débite jamais deux fois.

export class ApiError extends Error {
  constructor(status, detail, kind) { super(detail || kind || String(status)); this.status = status; this.detail = detail; this.kind = kind }
}

const FR = {
  'bad credentials': 'Identifiant ou mot de passe incorrect.',
  'account temporarily locked': 'Ce compte est verrouillé temporairement par mesure de sécurité. Réessayez dans quelques minutes.',
  'account suspended': 'Ce compte est suspendu par mesure de sécurité. Contactez votre conseiller.',
  'password reset required': 'Votre mot de passe doit être réinitialisé. Contactez votre conseiller.',
  'session revoked': 'Votre session a été fermée par mesure de sécurité. Reconnectez-vous.',
  'invalid token': 'Votre session a expiré. Reconnectez-vous.',
  'missing token': 'Votre session a expiré. Reconnectez-vous.',
  'insufficient funds': 'Solde insuffisant pour ce paiement.',
  'self payment': 'Vous ne pouvez pas vous envoyer de l’argent à vous-même.',
  'unknown account': 'Bénéficiaire inconnu.',
  'service busy': 'Le service est très sollicité. Votre demande est reprise automatiquement.',
}
export const RETRYABLE = new Set([429, 502, 503, 504])
// Pauses (secondes) entre deux tentatives : ~40 s au total, assez pour laisser le moteur de remédiation redémarrer un service.
export const BACKOFF = [1, 1.5, 2, 3, 4, 5, 6, 8, 10]

export function explain(status, detail) {
  if (typeof detail === 'string' && FR[detail]) return FR[detail]
  if (status === 429) return 'Trop de requêtes : patientez un instant.'
  if (status === 422) return 'Montant ou libellé invalide.'
  if (status === 0 || status >= 500) return 'Service momentanément indisponible. Reprise en cours.'
  if (status === 403 && typeof detail === 'string') return detail   // message du pare-feu applicatif (déjà en français)
  return 'La demande a échoué. Réessayez.'
}

/** Clé aléatoire de 32 hex : `crypto.randomUUID` n'existe pas hors contexte sécurisé (http://192.168.x.x). */
export function newKey(c = globalThis.crypto) {
  const b = new Uint8Array(16); c.getRandomValues(b)
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
}

export function createClient({ base = '', fetchImpl = (...a) => globalThis.fetch(...a), sleep = (s) => new Promise((r) => setTimeout(r, s * 1000)),
                               getToken = () => null, onSession = () => {} } = {}) {
  async function call(method, path, { body, headers = {}, auth = true } = {}) {
    const h = { Accept: 'application/json', ...headers }
    if (body !== undefined) h['Content-Type'] = 'application/json'
    const tok = auth ? getToken() : null
    if (tok) h.Authorization = `Bearer ${tok}`
    let res
    try {
      res = await fetchImpl(base + path, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) })
    } catch {
      throw new ApiError(0, null, 'network')
    }
    let data = null
    try { data = await res.json() } catch { /* corps vide ou non JSON */ }
    if (res.status === 401 && auth && tok) onSession('expired', data?.detail)
    if (!res.ok) throw new ApiError(res.status, typeof data?.detail === 'string' ? data.detail : null)
    return { status: res.status, data }
  }

  return {
    login: async (username, password) => (await call('POST', '/auth/login', { body: { username, password }, auth: false })).data,
    me: async () => (await call('GET', '/api/accounts/me')).data,
    beneficiaries: async () => (await call('GET', '/api/beneficiaries')).data,
    payments: async (limit = 20) => (await call('GET', `/api/payments?limit=${limit}`)).data,
    /** health : résultat + latence mesurée côté client (alimente la bande d'état du service). */
    health: async () => {
      const t0 = performance.now()
      try { await call('GET', '/api/health', { auth: false }); return { up: true, ms: Math.round(performance.now() - t0) } }
      catch (e) { return { up: false, ms: Math.round(performance.now() - t0), status: e.status } }
    },
    /** Envoie un paiement ; reprend automatiquement sur erreur transitoire avec la même clé. onRetry({attempt, max, wait}). */
    async pay({ to, amount, label }, key = newKey(), onRetry = () => {}) {
      for (let attempt = 0; ; attempt++) {
        try {
          const r = await call('POST', '/api/payments', { body: { to, amount, label }, headers: { 'Idempotency-Key': key } })
          return { ...r.data, key, duplicate: r.status === 200 || r.data.status === 'duplicate', attempts: attempt + 1 }
        } catch (e) {
          const transient = e.status === 0 || RETRYABLE.has(e.status)
          if (!transient || attempt >= BACKOFF.length) throw e
          onRetry({ attempt: attempt + 1, max: BACKOFF.length, wait: BACKOFF[attempt] })
          await sleep(BACKOFF[attempt])
        }
      }
    },
  }
}
