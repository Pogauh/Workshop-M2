import test from 'node:test'
import assert from 'node:assert/strict'
import { windowSeries, phaseBands, fmtDur, serviceView, detectorView, actionLabel, STATES, currentIncident } from '../src/lib/derive.js'

const state = {
  now: 1000,
  dhist: [{ ts: 600, rps: 3, score: 0.1, kind: 'normal' }, { ts: 900, rps: 90, score: -0.2, kind: 'anomaly' }, { ts: 990, rps: null, score: null, kind: 'no_model' }],
  hist: [{ ts: 800, ms: 40, ok: true }, { ts: 995, ms: 500, ok: false }],
}

test('windowSeries filtre par fenêtre et ignore les valeurs absentes', () => {
  const w = windowSeries(state, 300)
  assert.deepEqual(w.rps.map((p) => p.v), [90]); assert.deepEqual(w.score.map((p) => p.v), [-0.2]); assert.equal(w.latency.length, 2)
  assert.equal(windowSeries(state, 1000).rps.length, 2)
})

test('phaseBands : régime normal sans incident', () => {
  assert.deepEqual(phaseBands([], 700, 1000).map((b) => b.id), ['before'])
})
test('phaseBands : avant / pendant / après', () => {
  const m = [{ ts: 800, kind: 'detect' }, { ts: 820, kind: 'action' }, { ts: 900, kind: 'restored' }]
  const b = phaseBands(m, 700, 1000)
  assert.deepEqual(b.map((x) => [x.id, x.from, x.to]), [['before', 700, 800], ['during', 800, 900], ['after', 900, 1000]])
})
test('phaseBands : incident en cours et escalade', () => {
  assert.deepEqual(phaseBands([{ ts: 800, kind: 'detect' }], 700, 1000).map((b) => b.id), ['before', 'during'])
  assert.equal(phaseBands([{ ts: 800, kind: 'detect' }, { ts: 950, kind: 'escalation' }], 700, 1000).at(-1).id, 'escalation')
  assert.deepEqual(phaseBands([{ ts: 100, kind: 'detect' }], 700, 1000).map((b) => b.id), ['during'])   // détecté avant la fenêtre
})
test('formats et libellés', () => {
  assert.equal(fmtDur(18.4), '18 s'); assert.equal(fmtDur(125), '2 min 05 s'); assert.equal(fmtDur(null), 'n/a')
  assert.equal(serviceView({ state: 'running', health: 'healthy' }).tone, 'ok'); assert.equal(serviceView({ state: 'running', health: 'unhealthy' }).tone, 'serious')
  assert.equal(serviceView(undefined).text, 'Absent'); assert.equal(serviceView({ state: 'exited' }).text, 'Arrêté')
  assert.equal(detectorView({ kind: 'no_model' }).tone, 'crit'); assert.equal(detectorView(null).tone, 'off')
  assert.match(actionLabel('throttle'), /débit/); assert.equal(actionLabel('restart_x'), 'restart x')
  assert.deepEqual(Object.keys(STATES), ['HOMEOSTASIS', 'SURVEILLANCE', 'IMMUNITY', 'REGENERATION', 'RESTORED', 'CONTAINED', 'ESCALATION'])
  assert.equal(currentIncident({ incident: null }), null); assert.equal(currentIncident({ busy: true, incident: { id: 'a' } }).live, true)
  assert.equal(currentIncident({ busy: false, incident: { id: 'a', restored_at: 5 } }).live, false)
})
