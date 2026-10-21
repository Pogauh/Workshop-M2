import { useEffect, useRef, useState } from 'react'
import { explain } from '../lib/api.js'
import FaceCapture from './FaceCapture.jsx'
import Icon from './Icons.jsx'
import { Notice } from './ui.jsx'

/** Compte à rebours en secondes jusqu'à `untilMs` (epoch ms) ; 0 une fois écoulé. Ré-exécuté à chaque
 * changement de `untilMs` (ex. nouvel ordre de verrouillage reçu du serveur). */
function useCountdown(untilMs) {
  const [left, setLeft] = useState(() => Math.max(0, Math.ceil((untilMs - Date.now()) / 1000)))
  useEffect(() => {
    setLeft(Math.max(0, Math.ceil((untilMs - Date.now()) / 1000)))
    if (!untilMs) return
    const t = setInterval(() => setLeft(Math.max(0, Math.ceil((untilMs - Date.now()) / 1000))), 250)
    return () => clearInterval(t)
  }, [untilMs])
  return left
}

/** Connexion renforcée du back-office (consigne additionnelle 1) : identifiant -> reconnaissance faciale
 * (caméra USB du PC Hôte + IA locale, voir docs/face-auth.md) -> mot de passe. La LED du badge ESP8266
 * reflète chaque étape côté serveur (face/app/esp_led.py, auth/app/main.py) ; cette page ne fait que
 * refléter les réponses de l'API, elle ne pilote jamais la LED elle-même.
 *
 * Les comptes qui n'exigent pas la reconnaissance faciale (alice, bob, carol, merchant, attacker, probe —
 * voir auth/app/main.py:SEED) passent l'étape caméra quasi instantanément : le serveur répond
 * `bootstrap:true` dès qu'aucun visage n'est inscrit pour ce compte, sans comparaison. */
export default function Login({ api, onSubmit, notice }) {
  const [phase, setPhase] = useState('username')   // username | face | password | blocked
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [faceNotice, setFaceNotice] = useState(null)   // { tone, text }
  const [faceTicket, setFaceTicket] = useState(null)
  const [blockedUntil, setBlockedUntil] = useState(0)
  const [captureKey, setCaptureKey] = useState(0)
  const resetTimer = useRef(null)
  const blockedLeft = useCountdown(blockedUntil)

  useEffect(() => () => clearTimeout(resetTimer.current), [])

  useEffect(() => {
    if (phase === 'blocked' && blockedLeft === 0) resetToUsername()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, blockedLeft])

  function resetToUsername() {
    clearTimeout(resetTimer.current)
    setUsername(''); setPassword(''); setFaceTicket(null); setFaceNotice(null); setBlockedUntil(0); setPhase('username')
  }

  async function submitUsername(e) {
    e.preventDefault()
    if (!username.trim() || busy) return
    setError(null); setFaceNotice(null); setCaptureKey((k) => k + 1); setPhase('face')
  }

  async function onFaceCaptured(imageB64) {
    const u = username.trim().toLowerCase()
    try {
      const r = await api.faceVerify(u, imageB64)
      if (r.recognized) {
        setFaceTicket(r.ticket)
        setFaceNotice(r.bootstrap
          ? { tone: 'info', text: "Aucun visage enregistré pour ce compte : connexion au mot de passe seul. Vous pourrez enregistrer votre visage ensuite dans Gestion des habilitations." }
          : { tone: 'ok', text: 'Visage reconnu.' })
        setPhase('password')
        return
      }
      // Déjà bloqué (aucune nouvelle tentative comptée) : pas d'attente de 30 s, le compte à rebours réel suffit.
      if (r.locked) {
        setFaceNotice({ tone: 'warn', text: `Trop d'échecs de reconnaissance. Nouvel essai dans ${r.retry_after_s ?? 300} s.` })
        setBlockedUntil(Date.now() + (r.retry_after_s ?? 300) * 1000); setPhase('blocked')
        return
      }
      // Non reconnu (nouvelle tentative) : la LED reste rouge fixe 30 s côté badge (face/app/esp_led.py) —
      // on reflète le même délai ici (caméra visible, message rouge) avant de rendre la main.
      setFaceNotice({ tone: 'bad', text: r.locked_until
        ? `Visage non reconnu. Trop d'échecs : blocage de ${r.retry_after_s ?? 300} s après ce délai.`
        : "Visage non reconnu. Nouvelle tentative possible dans 30 s." })
      resetTimer.current = setTimeout(() => {
        if (r.locked_until) { setBlockedUntil(Date.now() + Math.max(0, r.retry_after_s ?? 300) * 1000); setPhase('blocked') }
        else resetToUsername()
      }, 30000)
    } catch (err) {
      setFaceNotice({ tone: 'bad', text: explain(err.status, err.detail) })
      resetTimer.current = setTimeout(resetToUsername, 5000)
    }
  }

  async function submitPassword(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try { await onSubmit(username.trim().toLowerCase(), password, faceTicket) }
    catch (err) {
      // Mot de passe refusé (401) : la LED clignote rouge 10 fois côté serveur (auth/app/main.py) et on
      // recommence TOUTE la phase d'identification (consigne additionnelle 1) — identifiant y compris,
      // pas seulement le mot de passe. Les autres refus (423 verrouillé, 403 suspendu...) restent affichés
      // sur place : ce ne sont pas des échecs de mot de passe au sens de la consigne.
      if (err.status === 401) { setBusy(false); resetToUsername(); setError({ status: err.status, text: explain(err.status, err.detail) }); return }
      setError({ status: err.status, text: explain(err.status, err.detail) }); setPassword('')
    }
    finally { setBusy(false) }
  }

  const locked = error && (error.status === 423 || error.status === 403)

  return (
    <main className="mx-auto grid min-h-[calc(100vh-4.5rem)] max-w-md place-items-center px-4 pb-16">
      <div className="w-full">
        <h1 className="text-3xl font-semibold tracking-tight">Connexion</h1>
        <p className="mt-2 text-muted">
          {phase === 'username' && 'Connectez-vous pour envoyer et suivre vos paiements.'}
          {phase === 'face' && 'Confirmation de votre identité par reconnaissance faciale.'}
          {phase === 'password' && `Identité confirmée pour ${username} — saisissez votre mot de passe.`}
          {phase === 'blocked' && 'Trop de tentatives de reconnaissance faciale.'}
        </p>

        <div className="mt-6 space-y-4 rounded-2xl border border-line bg-surface p-5 sm:p-6">
          {notice && !error && phase === 'username' && (
            <Notice tone="info" role="status" icon={<Icon name="lock" size={18} className="mt-0.5 shrink-0" />}>{notice}</Notice>
          )}
          {error && phase !== 'password' && (
            <Notice tone={locked ? 'warn' : 'bad'} role="alert" icon={<Icon name={locked ? 'lock' : 'alert'} size={18} className="mt-0.5 shrink-0" />}>
              {error.text}
            </Notice>
          )}

          {phase === 'username' && (
            <form onSubmit={submitUsername} className="space-y-4" noValidate>
              <div>
                <label htmlFor="username" className="mb-1.5 block text-sm font-medium">Identifiant</label>
                <input id="username" className="field" autoComplete="username" autoCapitalize="none" spellCheck="false" required
                       autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
              <button type="submit" className="btn btn-primary w-full" disabled={!username.trim()}>
                Continuer <Icon name="camera" size={18} className="ml-1" />
              </button>
            </form>
          )}

          {phase === 'face' && (
            <div className="space-y-3">
              <FaceCapture key={captureKey} onCapture={onFaceCaptured} onError={() => {}} />
              {faceNotice && (
                <Notice tone={faceNotice.tone} role="status"
                        icon={<Icon name={faceNotice.tone === 'ok' ? 'check' : faceNotice.tone === 'bad' ? 'alert' : 'lock'} size={18} className="mt-0.5 shrink-0" />}>
                  {faceNotice.text}
                </Notice>
              )}
            </div>
          )}

          {phase === 'blocked' && (
            <Notice tone="warn" role="alert" icon={<Icon name="lock" size={18} className="mt-0.5 shrink-0" />}>
              Compte temporairement bloqué. Nouvel essai possible dans {blockedLeft} s.
            </Notice>
          )}

          {phase === 'password' && (
            <form onSubmit={submitPassword} className="space-y-4" noValidate>
              {faceNotice && (
                <Notice tone={faceNotice.tone} role="status" icon={<Icon name={faceNotice.tone === 'ok' ? 'check' : 'lock'} size={18} className="mt-0.5 shrink-0" />}>
                  {faceNotice.text}
                </Notice>
              )}
              <div>
                <label className="mb-1.5 block text-sm font-medium">Identifiant</label>
                <div className="flex items-center justify-between gap-2 rounded-xl border border-line bg-bg px-3.5 py-2.5 text-sm">
                  <span className="font-medium">{username}</span>
                  <button type="button" onClick={resetToUsername} className="text-xs font-medium text-muted hover:text-ink">Changer</button>
                </div>
              </div>
              <div>
                <label htmlFor="password" className="mb-1.5 block text-sm font-medium">Mot de passe</label>
                <div className="relative">
                  <input id="password" className="field pr-12" type={show ? 'text' : 'password'} autoComplete="current-password" required
                         maxLength={72} autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
                  <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                          aria-pressed={show} className="absolute right-1.5 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-lg text-muted hover:text-ink">
                    <Icon name={show ? 'eyeOff' : 'eye'} />
                  </button>
                </div>
              </div>
              {error && (
                <Notice tone={locked ? 'warn' : 'bad'} role="alert" icon={<Icon name={locked ? 'lock' : 'alert'} size={18} className="mt-0.5 shrink-0" />}>
                  {error.text}
                </Notice>
              )}
              <button type="submit" className="btn btn-primary w-full" disabled={busy || !password}>
                {busy ? <><Icon name="spinner" spin /> Connexion…</> : 'Se connecter'}
              </button>
            </form>
          )}
        </div>
      </div>
    </main>
  )
}
