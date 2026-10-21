import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createClient, explain } from './lib/api.js'
import { eur } from './lib/format.js'
import BackOffice from './components/BackOffice.jsx'
import Composer from './components/Composer.jsx'
import History from './components/History.jsx'
import Icon from './components/Icons.jsx'
import Login from './components/Login.jsx'
import StatusStrip, { useServiceHealth } from './components/StatusStrip.jsx'
import Ticket from './components/Ticket.jsx'
import { Logo, Notice } from './components/ui.jsx'

const KEY = 'payalpha.session'
const read = () => { try { return JSON.parse(sessionStorage.getItem(KEY)) } catch { return null } }
const write = (v) => { try { v ? sessionStorage.setItem(KEY, JSON.stringify(v)) : sessionStorage.removeItem(KEY) } catch { /* stockage indisponible : session en mémoire */ } }

export default function App() {
  const [session, setSession] = useState(read)
  const [notice, setNotice] = useState(null)
  const tokenRef = useRef(session?.token ?? null)
  tokenRef.current = session?.token ?? null

  const logout = useCallback((reason) => {
    write(null); setSession(null)
    setNotice(reason === 'expired' ? 'Votre session a expiré. Reconnectez-vous.' : typeof reason === 'string' && reason ? reason : null)
  }, [])
  const api = useMemo(() => createClient({
    getToken: () => tokenRef.current,
    onSession: (kind, detail) => logout(explain(401, detail)),
  }), [logout])
  const health = useServiceHealth(api)

  async function login(username, password, faceTicket) {
    const { token } = await api.login(username, password, faceTicket)
    const s = { token, user: username }
    tokenRef.current = token; write(s); setNotice(null); setSession(s)
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1080px] flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Logo />
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <StatusStrip health={health} />
            {session && (
              <button type="button" onClick={() => logout(null)} className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-muted hover:text-ink">
                <Icon name="logout" size={18} /> Se déconnecter
              </button>
            )}
          </div>
        </div>
      </header>
      {session ? <Home api={api} session={session} onLogout={logout} /> : <Login api={api} onSubmit={login} notice={notice} />}
    </div>
  )
}

/** Aiguille vers la console back-office (consigne additionnelle 1, compte « manager ») ou le tableau de
 * bord client PayAlpha, selon le rôle renvoyé par /api/accounts/me. */
function Home({ api, session, onLogout }) {
  const [role, setRole] = useState(null)   // null = résolution en cours
  useEffect(() => {
    api.me().then((m) => setRole(m.role)).catch((e) => {
      if (e.status === 401 || (e.status === 403 && /suspended/.test(e.detail || ''))) onLogout(explain(e.status, e.detail))
      else setRole('customer')   // dégradé : CustomerHome réessaiera via son propre refresh()
    })
  }, [api, onLogout])

  if (role === null) return <main className="grid min-h-[50vh] place-items-center text-muted"><Icon name="spinner" spin size={28} /></main>
  return role === 'backoffice' ? <BackOffice api={api} /> : <CustomerHome api={api} session={session} onLogout={onLogout} />
}

function CustomerHome({ api, session, onLogout }) {
  const [me, setMe] = useState(null)
  const [benef, setBenef] = useState([])
  const [pays, setPays] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const topRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const [m, p] = await Promise.all([api.me(), api.payments(30)])
      setMe(m); setPays(p); setLoadError(null)
    } catch (e) {
      if (e.status === 401 || (e.status === 403 && /suspended/.test(e.detail || ''))) return onLogout(explain(e.status, e.detail))
      setLoadError(explain(e.status, e.detail))
    } finally { setLoading(false) }
  }, [api, onLogout])

  useEffect(() => { api.beneficiaries().then(setBenef).catch(() => {}) }, [api])
  useEffect(() => {
    refresh()
    const t = setInterval(() => { if (!document.hidden) refresh() }, 12000)
    return () => clearInterval(t)
  }, [refresh])

  const names = useMemo(() => Object.fromEntries(benef.map((b) => [b.id, b.name])), [benef])
  const myName = me?.display_name ?? session.user

  function onPaid(res) {
    setReceipt({ id: res.id, amount: res.amount, label: res.label, created_at: res.created_at, direction: 'out',
                 from: myName, to: res.toName, fresh: true, duplicate: res.duplicate })
    refresh()
    topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  function openReceipt(p) {
    const who = names[p.counterparty] ?? p.counterparty
    setReceipt({ id: p.id, amount: p.amount, label: p.label, created_at: p.created_at, direction: p.direction,
                 from: p.direction === 'out' ? myName : who, to: p.direction === 'out' ? who : myName, fresh: false })
    topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <main className="mx-auto grid max-w-[1080px] grid-cols-[minmax(0,1fr)] gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <div className="space-y-6">
        <section aria-labelledby="solde" ref={topRef} className="scroll-mt-4">
          <h1 id="solde" className="text-sm font-medium text-muted">Solde disponible</h1>
          <p className="mt-1 text-[2.5rem] font-semibold leading-tight tracking-tight tabular-nums sm:text-6xl">{me ? eur(me.balance) : <span className="text-[#b9c3d9]">––––,–– €</span>}</p>
          <p className="mt-1 text-sm text-muted">Compte courant de {myName}</p>
        </section>
        {loadError && (
          <Notice tone="warn" role="status" icon={<Icon name="alert" size={18} className="mt-0.5 shrink-0" />}>
            {loadError} Les données se réactualisent automatiquement.
          </Notice>
        )}
        {receipt && <Ticket receipt={receipt} onClose={() => setReceipt(null)} />}
        <Composer api={api} balance={me?.balance} beneficiaries={benef} onPaid={onPaid}
                  onSessionLost={(e) => onLogout(explain(e.status, e.detail))} />
      </div>
      <History items={pays} names={names} onOpen={openReceipt} loading={loading} />
    </main>
  )
}
