import { ATTACKS, DEFAULT_PAY_RATE, RULES, SERVICES, SEVERITY, actionLabel, currentIncident, detectorView, fmtClock, fmtDur, fmtNum, serviceView } from '../lib/derive.js'
import { Badge, Chip, Empty, Icon, Panel, TONE } from './ui.jsx'

const FEATURES = [['rps', 'Débit', 'req/s'], ['rps_max_user', 'Plus gros compte', 'req/s'], ['p95_ms', 'Latence p95', 'ms'], ['err5xx_ratio', 'Erreurs 5xx', '%'],
  ['waf_block_ratio', 'Blocages WAF', '%'], ['inflight', 'Requêtes en cours', ''], ['login_rps', 'Connexions', '/s'], ['login_fail_rate', 'Échecs de connexion', '/s']]
const PCT = new Set(['err5xx_ratio', 'waf_block_ratio'])

export function Services({ state }) {
  const p = state.probe ?? {}, tx = (state.verifs ?? [])[0]
  const mttr = state.last_mttr
  return (
    <Panel id="services" title="Services et preuve de reprise">
      <ul className="divide-y divide-line">
        {Object.entries(SERVICES).map(([k, name]) => {
          const v = serviceView(state.services?.[k])
          return <li key={k} className="flex items-center justify-between py-2"><span>{name}</span><Badge tone={v.tone}>{v.text}</Badge></li>
        })}
      </ul>
      <div className="mt-3 rounded-lg border border-line bg-raise p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Transaction témoin</h3>
          <Badge tone={p.ok === undefined ? 'off' : p.ok ? 'ok' : 'crit'}>{p.ok === undefined ? 'En attente' : p.ok ? 'Réussie' : 'En échec'}</Badge>
        </div>
        {tx ? (
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">Paiement</dt><dd className="text-right tabular-nums">{tx.amount} € vers {tx.to}</dd>
            <dt className="text-muted">Écriture</dt><dd className="text-right">{tx.created === 201 ? 'créée' : `code ${tx.created}`}</dd>
            <dt className="text-muted">Relecture</dt><dd className="text-right">{tx.reread === 200 ? 'identique' : `code ${tx.reread}`}</dd>
            <dt className="text-muted">Total des soldes</dt><dd className="text-right">{tx.consistent ? 'cohérent' : 'incohérent'}</dd>
            <dt className="text-muted">Durée</dt><dd className="text-right tabular-nums">{tx.ms} ms</dd>
          </dl>
        ) : <p className="mt-2 text-sm text-muted">{p.detail || 'Aucune transaction témoin pour l’instant.'}</p>}
        {!p.ok && p.detail && tx && <p className="mt-2 text-sm text-crit">{p.detail}</p>}
      </div>
      <p className="mt-3 flex items-baseline justify-between text-sm"><span className="text-muted">Dernier rétablissement</span>
        <span className="text-2xl font-semibold tabular-nums">{mttr ? fmtDur(mttr) : 'n/a'}</span></p>
    </Panel>
  )
}

export function Detector({ state }) {
  const d = state.detector ?? {}, v = detectorView(d), f = d.features ?? {}, m = d.model
  return (
    <Panel id="detector" title="Détection" right={<Badge tone={v.tone}>{v.text}</Badge>}>
      <dl className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
        {FEATURES.map(([k, label, unit]) => (
          <div key={k} className="flex items-baseline justify-between gap-2 border-b border-line/60 py-0.5">
            <dt className="truncate text-muted">{label}</dt>
            <dd className="tabular-nums">{f[k] == null ? 'n/a' : PCT.has(k) ? `${fmtNum(f[k] * 100)} %` : `${fmtNum(f[k])}${unit ? ` ${unit}` : ''}`}</dd>
          </div>))}
      </dl>
      <p className="mt-3 text-sm">
        {m?.status === 'ok'
          ? <span className="text-muted">Modèle IsolationForest chargé, entraîné sur {m.n_train} observations de trafic normal ({m.trained_at}).</span>
          : <span className="text-crit">Aucun modèle chargé : la détection ML est inactive (les règles SIEM restent actives).</span>}
      </p>
      {d.error && <p className="mt-1 text-sm text-crit">Erreur de collecte : {d.error}</p>}
    </Panel>
  )
}

export function Defenses({ state, now }) {
  const r = state.rules ?? {}
  const locked = Object.entries(r.locked_users ?? {}), items = []
  const throttled = r.pay_rate != null && r.pay_rate < DEFAULT_PAY_RATE
  return (
    <Panel id="defenses" title="Défenses actives">
      <ul className="space-y-2.5 text-sm">
        <li className="flex items-center justify-between gap-3"><span>Débit de paiement par session</span>
          <span className="flex items-center gap-2"><span className="tabular-nums">{r.pay_rate ?? 'n/a'} req/s</span>
            <Badge tone={throttled ? 'warn' : 'ok'}>{throttled ? 'Restreint' : 'Normal'}</Badge></span></li>
        <li className="flex flex-wrap items-center justify-between gap-2"><span>Comptes suspendus</span>
          <span className="flex flex-wrap gap-1.5">{(r.suspended_users ?? []).length ? r.suspended_users.map((u) => <Chip key={u} tone="serious">{u}</Chip>) : <span className="text-muted">aucun</span>}</span></li>
        <li className="flex flex-wrap items-center justify-between gap-2"><span>Comptes verrouillés</span>
          <span className="flex flex-wrap gap-1.5">{locked.length ? locked.map(([u, until]) => <Chip key={u} tone="warn">{u}, encore {fmtDur(until - (now ?? state.now))}</Chip>) : <span className="text-muted">aucun</span>}</span></li>
        <li className="flex flex-wrap items-center justify-between gap-2"><span>Mot de passe à réinitialiser</span>
          <span className="flex flex-wrap gap-1.5">{(r.compromised_users ?? []).length ? r.compromised_users.map((u) => <Chip key={u} tone="crit">{u}</Chip>) : <span className="text-muted">aucun</span>}</span></li>
        <li className="flex flex-wrap items-center justify-between gap-2"><span>Adresses bannies au WAF</span>
          <span className="flex flex-wrap gap-1.5">{(r.banned_ips ?? []).length ? r.banned_ips.map((u) => <Chip key={u} tone="serious">{u}</Chip>) : <span className="text-muted">aucune</span>}</span></li>
      </ul>
    </Panel>
  )
}

const SUSPECT_LABELS = { users: 'comptes', targets: 'cibles', compromised: 'compromis', ips: 'adresses', services: 'services' }

export function Incident({ state, now }) {
  const inc = currentIncident(state), t0 = inc?.detected_at
  const done = inc?.restored_at, esc = state.state === 'ESCALATION' && !done
  const sus = Object.entries(inc?.suspects ?? {}).filter(([k, v]) => SUSPECT_LABELS[k] && v?.length)
  return (
    <Panel id="incident" title="Incident"
      right={inc && <Badge tone={done ? 'ok' : esc ? 'crit' : 'serious'}>{done ? 'Rétabli' : esc ? 'Escalade' : 'En cours'}</Badge>}>
      {!inc ? <Empty>Aucun incident en cours. Les défenses n’ont rien à corriger.</Empty> : (
        <>
          <h3 className="font-semibold">{ATTACKS[inc.attack] ?? inc.attack}</h3>
          <p className="mt-0.5 text-sm text-muted">Détecté à {fmtClock(t0)}, identifiant {inc.id}</p>
          {sus.length > 0 && (
            <p className="mt-2 flex flex-wrap items-center gap-1.5 text-sm">
              {sus.map(([k, v]) => <span key={k} className="flex items-center gap-1.5"><span className="text-muted">{SUSPECT_LABELS[k]}</span>{v.map((x) => <Chip key={x} tone="warn">{x}</Chip>)}</span>)}
            </p>)}
          <ol className="mt-3 space-y-2.5 border-l border-line pl-4">
            {inc.actions.map((a, i) => (
              <li key={a.t + a.name} className="relative text-sm">
                <span className="absolute -left-[1.45rem] top-0.5 grid h-[18px] w-[18px] place-items-center rounded-full bg-info text-[11px] font-bold text-[#06121a]">{i + 1}</span>
                <p className="font-medium">{actionLabel(a.name)} <span className="font-normal text-muted tabular-nums">+{fmtDur(a.t - t0)}</span></p>
                <p className="text-muted">{a.detail}</p>
              </li>))}
            {inc.actions.length === 0 && <li className="text-sm text-muted">Analyse en cours, aucune action appliquée pour l’instant.</li>}
          </ol>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
            <span className="text-muted">Vérifications</span>
            <span className="flex items-center gap-1" aria-label={`${(inc.checks ?? []).filter((c) => c.ok).length} contrôles réussis sur ${(inc.checks ?? []).length}`}>
              {(inc.checks ?? []).slice(-12).map((c, i) => (
                <svg key={i} width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">{c.ok ? <circle cx="7" cy="7" r="5" fill="var(--ok)" /> : <path d="M3 3l8 8M11 3l-8 8" stroke="var(--crit)" strokeWidth="2" strokeLinecap="round" />}</svg>))}
              {(inc.checks ?? []).length === 0 && <span className="text-muted">aucune</span>}
            </span>
            <span className="text-muted">3 réussies d’affilée = service rétabli</span>
          </div>
          {done && <p className="mt-3 text-sm font-semibold text-ok">Service vérifié {fmtDur(inc.mttr_s ?? done - t0)} après la détection.</p>}
          {esc && <p className="mt-3 text-sm font-semibold text-crit">La reprise n’a pas pu être vérifiée : un opérateur doit intervenir.</p>}
        </>)}
    </Panel>
  )
}

export function Siem({ state, now }) {
  const alerts = [...(state.siem ?? [])].sort((a, b) => b.ts - a.ts)
  return (
    <Panel id="siem" title="Alertes de sécurité (SIEM)" right={<span className="text-sm text-muted">{alerts.length} active{alerts.length > 1 ? 's' : ''}</span>}>
      {alerts.length === 0 ? <Empty>Aucune alerte. Les règles R1 à R5 surveillent les journaux du WAF, de l’API et de l’authentification.</Empty> : (
        <ul className="divide-y divide-line">
          {alerts.map((a) => {
            const sev = SEVERITY[a.severity] ?? { tone: 'off', text: a.severity }
            return (
              <li key={a.rule + a.subject} className="py-2.5 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge tone={sev.tone}>{sev.text}</Badge>
                  <span className="text-muted"><span className="tabular-nums">{a.rule}</span>, {RULES[a.rule] ?? a.title}</span>
                </div>
                <p className="mt-1">{a.detail}</p>
                <p className="mt-0.5 text-muted tabular-nums">il y a {fmtDur((now ?? state.now) - a.ts)}{a.count > 1 ? `, vue ${a.count} fois` : ''}</p>
              </li>)
          })}
        </ul>)}
    </Panel>
  )
}

export function Journal({ state }) {
  const hist = state.history ?? [], log = [...(state.log ?? [])].slice(-12).reverse()
  const lvl = { info: 'info', warn: 'warn', error: 'crit' }
  return (
    <Panel id="journal" title="Mémoire immunitaire et journal du moteur" className="lg:col-span-2">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-x-auto">
          <h3 className="mb-1 text-sm font-semibold text-muted">Derniers incidents</h3>
          {hist.length === 0 ? <Empty>Aucun incident enregistré depuis le dernier reset.</Empty> : (
            <table className="w-full min-w-[420px] text-sm">
              <thead><tr className="text-left text-muted"><th className="py-1 pr-3 font-medium">Type</th><th className="pr-3 font-medium">Détecté</th><th className="pr-3 font-medium">Actions</th><th className="pr-3 font-medium">Durée</th><th className="font-medium">Issue</th></tr></thead>
              <tbody>{hist.map((h) => (
                <tr key={h.id} className="border-t border-line align-top">
                  <td className="py-1.5 pr-3">{{ dos: 'Surcharge', bruteforce: 'Brute-force', outage: 'Panne' }[h.attack] ?? h.attack}</td>
                  <td className="pr-3 tabular-nums">{fmtClock(h.detected_at)}</td><td className="pr-3 tabular-nums">{h.actions?.length ?? 0}</td>
                  <td className="pr-3 tabular-nums">{h.mttr_s != null ? fmtDur(h.mttr_s) : 'n/a'}</td>
                  <td><Badge tone={h.restored ? 'ok' : 'crit'}>{h.restored ? 'Rétabli' : 'Escalade'}</Badge></td>
                </tr>))}</tbody>
            </table>)}
        </div>
        <div>
          <h3 className="mb-1 text-sm font-semibold text-muted">Journal du moteur</h3>
          {log.length === 0 ? <Empty>Aucune entrée.</Empty> : (
            <ul className="space-y-1 text-sm">
              {log.map((l, i) => (
                <li key={l.ts + i} className="flex items-start gap-2">
                  <span className={`${TONE[lvl[l.level] ?? 'off'].text} mt-0.5`}><Icon name={TONE[lvl[l.level] ?? 'off'].icon} size={15} /></span>
                  <span className="tabular-nums text-muted">{fmtClock(l.ts)}</span><span className="min-w-0 flex-1">{l.msg}</span>
                </li>))}
            </ul>)}
        </div>
      </div>
    </Panel>
  )
}
