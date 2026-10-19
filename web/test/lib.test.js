import test from 'node:test'
import assert from 'node:assert/strict'
import { parseAmount, amountProblem, labelProblem, initials, dayLabel, shortRef, eur } from '../src/lib/format.js'
import { createClient, explain, newKey, ApiError, BACKOFF } from '../src/lib/api.js'

test('parseAmount accepte virgule et point, refuse le reste', () => {
  assert.equal(parseAmount('12,5'), '12.50')
  assert.equal(parseAmount(' 1 234,56 '), '1234.56')
  assert.equal(parseAmount('0.01'), '0.01')
  assert.equal(parseAmount('10000'), '10000.00')
  for (const bad of ['', '0', '0,00', '10000,01', '12.345', '-5', 'abc', '1e3', '12.', '.5', '100000']) assert.equal(parseAmount(bad), null, bad)
})

test('amountProblem : solde insuffisant et plafond', () => {
  assert.equal(amountProblem('', 100), '')
  assert.equal(amountProblem('50', 100), '')
  assert.match(amountProblem('150', 100), /insuffisant/)
  assert.match(amountProblem('20000', 50000), /plafond/)
  assert.match(amountProblem('abc', 100), /valide/)
})

test('labelProblem reflète le contrôle serveur', () => {
  assert.equal(labelProblem("Loyer d'octobre (2-3) - café"), '')
  assert.match(labelProblem('<script>'), /Caractères/)
  assert.match(labelProblem("a'; drop table users;--"), /Caractères/)
  assert.match(labelProblem('x'.repeat(65)), /long/)
})

test('initials, shortRef, dayLabel, eur', () => {
  assert.equal(initials('Alice Martin'), 'AM'); assert.equal(initials('Boutique'), 'B'); assert.equal(initials(''), '?')
  assert.equal(shortRef('8f3a1c2e-77aa-4b0c-9a55-0c9e0d3f1b22'), '8F3A1C2E')
  const now = new Date(2026, 9, 19, 15, 0)
  assert.equal(dayLabel(new Date(2026, 9, 19, 9, 0).toISOString(), now), "Aujourd'hui")
  assert.equal(dayLabel(new Date(2026, 9, 18, 23, 0).toISOString(), now), 'Hier')
  assert.match(eur('1234.5').replace(/\s/g, ' '), /1 234,50 €/)
})

test('explain traduit les erreurs du serveur et du WAF', () => {
  assert.match(explain(401, 'bad credentials'), /incorrect/)
  assert.match(explain(423, 'account temporarily locked'), /verrouillé/)
  assert.match(explain(403, 'account suspended'), /suspendu/)
  assert.match(explain(403, 'password reset required'), /réinitialisé/)
  assert.match(explain(402, 'insufficient funds'), /insuffisant/)
  assert.equal(explain(403, 'Requête bloquée par le pare-feu applicatif'), 'Requête bloquée par le pare-feu applicatif')
  assert.match(explain(503, null), /indisponible/); assert.match(explain(0, null), /indisponible/); assert.match(explain(429, null), /Trop de requêtes/)
})

test('newKey : 32 hex, conforme au motif serveur, sans crypto.randomUUID', () => {
  const k = newKey({ getRandomValues: (b) => { b.fill(171); return b } })
  assert.match(k, /^[a-f0-9]{32}$/); assert.match(newKey(), /^[A-Za-z0-9_-]{8,64}$/); assert.notEqual(newKey(), newKey())
})

function fakeFetch(script) {
  const calls = []
  const f = async (url, init) => {
    calls.push({ url, init })
    const step = script.shift()
    if (step === 'network') throw new TypeError('failed to fetch')
    return { status: step.status, ok: step.status < 400, json: async () => step.body }
  }
  return { f, calls }
}
const created = { status: 201, body: { id: 'a-1', status: 'accepted', to: 'bob', amount: '10.00', label: '', created_at: '2026-10-19T10:00:00Z' } }

test('pay : succès immédiat avec clé d’idempotence', async () => {
  const { f, calls } = fakeFetch([created])
  const api = createClient({ fetchImpl: f, sleep: async () => {}, getToken: () => 'tok' })
  const r = await api.pay({ to: 'bob', amount: '10.00', label: '' }, 'k'.repeat(16))
  assert.equal(r.duplicate, false); assert.equal(r.attempts, 1)
  assert.equal(calls[0].init.headers['Idempotency-Key'], 'k'.repeat(16)); assert.equal(calls[0].init.headers.Authorization, 'Bearer tok')
})

test('pay : reprise sur 503, réseau et 429 avec la MÊME clé, puis succès', async () => {
  const { f, calls } = fakeFetch([{ status: 503, body: { detail: 'Service momentanément indisponible' } }, 'network', { status: 429, body: null }, created])
  const waits = [], retries = []
  const api = createClient({ fetchImpl: f, sleep: async (s) => { waits.push(s) }, getToken: () => 'tok' })
  const r = await api.pay({ to: 'bob', amount: '10.00', label: 'x' }, 'key-12345678', (x) => retries.push(x.attempt))
  assert.equal(r.attempts, 4); assert.deepEqual(waits, BACKOFF.slice(0, 3)); assert.deepEqual(retries, [1, 2, 3])
  assert.equal(new Set(calls.map((c) => c.init.headers['Idempotency-Key'])).size, 1)
})

test('pay : une réponse 200 signifie « déjà enregistré » (aucun second débit)', async () => {
  const { f } = fakeFetch([{ status: 503, body: null }, { status: 200, body: { ...created.body, status: 'duplicate' } }])
  const r = await createClient({ fetchImpl: f, sleep: async () => {}, getToken: () => 't' }).pay({ to: 'bob', amount: '10.00', label: '' })
  assert.equal(r.duplicate, true)
})

test('pay : les erreurs définitives ne sont pas rejouées', async () => {
  for (const [status, detail] of [[402, 'insufficient funds'], [400, 'self payment'], [404, 'unknown account'], [422, null], [403, 'account suspended']]) {
    const { f, calls } = fakeFetch([{ status, body: { detail } }])
    await assert.rejects(createClient({ fetchImpl: f, sleep: async () => {}, getToken: () => 't' }).pay({ to: 'bob', amount: '1.00', label: '' }),
      (e) => e instanceof ApiError && e.status === status)
    assert.equal(calls.length, 1)
  }
})

test('pay : abandon après le budget de tentatives', async () => {
  const script = Array.from({ length: BACKOFF.length + 1 }, () => ({ status: 503, body: null }))
  const { f, calls } = fakeFetch(script)
  await assert.rejects(createClient({ fetchImpl: f, sleep: async () => {}, getToken: () => 't' }).pay({ to: 'bob', amount: '1.00', label: '' }),
    (e) => e.status === 503)
  assert.equal(calls.length, BACKOFF.length + 1)
})

test('401 avec jeton prévient la session ; pas pour la connexion', async () => {
  const seen = []
  const { f } = fakeFetch([{ status: 401, body: { detail: 'session revoked' } }, { status: 401, body: { detail: 'bad credentials' } }])
  const api = createClient({ fetchImpl: f, getToken: () => 'tok', onSession: (k, d) => seen.push([k, d]) })
  await assert.rejects(api.me(), (e) => e.status === 401)
  await assert.rejects(api.login('alice', 'x'), (e) => e.detail === 'bad credentials')
  assert.deepEqual(seen, [['expired', 'session revoked']])
})

test('health mesure la disponibilité sans jeton', async () => {
  const { f, calls } = fakeFetch([{ status: 200, body: { status: 'ok' } }, { status: 503, body: null }, 'network'])
  const api = createClient({ fetchImpl: f, getToken: () => 'tok' })
  assert.equal((await api.health()).up, true); assert.equal(calls[0].init.headers.Authorization, undefined)
  assert.equal((await api.health()).up, false); assert.equal((await api.health()).up, false)
})
