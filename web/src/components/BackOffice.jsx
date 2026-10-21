import { useEffect, useState } from 'react'
import { explain } from '../lib/api.js'
import FaceCapture from './FaceCapture.jsx'
import Icon from './Icons.jsx'
import { Notice } from './ui.jsx'

const SHOTS_NEEDED = 5

/** Console du compte « manager » (rôle backoffice, voir auth/app/main.py:SEED) : gestion complète des
 * habilitations de reconnaissance faciale (consigne additionnelle 1) — inscrire ou révoquer le visage
 * associé à un compte protégé. Remplace le tableau de bord de paiement (voir App.jsx:Home) : ce compte
 * ne traite pas de transactions, il administre la sécurité du back-office. */
export default function BackOffice({ api }) {
  const [enrollments, setEnrollments] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [target, setTarget] = useState('')
  const [capturing, setCapturing] = useState(false)
  const [shots, setShots] = useState([])
  const [captureKey, setCaptureKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const refresh = () => api.faceEnrollments().then((e) => { setEnrollments(e); setLoadError(null) }).catch((e) => setLoadError(explain(e.status, e.detail)))
  useEffect(() => { refresh() }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  function startCapture() {
    if (!target.trim() || busy) return
    setShots([]); setMsg(null); setCapturing(true); setCaptureKey((k) => k + 1)
  }

  function onShot(b64) {
    const next = [...shots, b64]
    setShots(next)
    if (next.length >= SHOTS_NEEDED) { setCapturing(false); submitEnroll(next) }
    else setCaptureKey((k) => k + 1)
  }

  async function submitEnroll(images) {
    setBusy(true); setMsg(null)
    try {
      const r = await api.faceEnroll(target.trim().toLowerCase(), images)
      setMsg({ tone: 'ok', text: `Visage enregistré pour « ${r.username} » (${r.n_images} photo(s) exploitées sur ${images.length}).` })
      setTarget(''); refresh()
    } catch (e) { setMsg({ tone: 'bad', text: explain(e.status, e.detail) }) }
    finally { setBusy(false) }
  }

  async function revoke(username) {
    if (!confirmInline(username)) return
    setBusy(true); setMsg(null)
    try { await api.faceUnenroll(username); setMsg({ tone: 'ok', text: `Habilitation révoquée pour « ${username} ».` }); refresh() }
    catch (e) { setMsg({ tone: 'bad', text: explain(e.status, e.detail) }) }
    finally { setBusy(false) }
  }

  // Pas de window.confirm (indisponible dans certains contextes) : confirmation en deux clics, état local simple.
  const [pendingRevoke, setPendingRevoke] = useState(null)
  function confirmInline(username) {
    if (pendingRevoke !== username) { setPendingRevoke(username); return false }
    setPendingRevoke(null); return true
  }

  return (
    <main className="mx-auto max-w-[760px] space-y-8 px-4 py-8 sm:px-6">
      <section>
        <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight"><Icon name="shield" size={22} /> Back-office — Gestion des habilitations</h1>
        <p className="mt-1 text-muted">Reconnaissance faciale (consigne additionnelle 1) : inscrivez ou révoquez le visage associé à un compte protégé.</p>
      </section>

      {msg && (
        <Notice tone={msg.tone} role="status" icon={<Icon name={msg.tone === 'ok' ? 'check' : 'alert'} size={18} className="mt-0.5 shrink-0" />}>
          {msg.text}
        </Notice>
      )}

      <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
        <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Inscrire un visage</p>
        {!capturing ? (
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[180px] flex-1">
              <label htmlFor="target" className="mb-1.5 block text-sm font-medium">Identifiant du compte</label>
              <input id="target" className="field" autoCapitalize="none" spellCheck="false" value={target} onChange={(e) => setTarget(e.target.value)} />
            </div>
            <button type="button" onClick={startCapture} disabled={!target.trim() || busy} className="btn btn-primary">
              <Icon name="camera" size={18} /> Démarrer ({SHOTS_NEEDED} photos)
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              Photo {shots.length + 1} / {SHOTS_NEEDED} pour « {target.trim().toLowerCase()} » — variez légèrement l'angle entre chaque prise.
            </p>
            <FaceCapture key={captureKey} countdownS={2} onCapture={onShot} onError={() => {}} />
            <button type="button" onClick={() => setCapturing(false)} className="text-sm font-medium text-muted hover:text-ink">Annuler</button>
          </div>
        )}
        {busy && !capturing && (
          <p className="mt-3 inline-flex items-center gap-2 text-sm text-muted"><Icon name="spinner" spin /> Entraînement du modèle…</p>
        )}
      </section>

      <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
        <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Comptes avec un visage enregistré</p>
        {loadError && <Notice tone="warn" role="status" icon={<Icon name="alert" size={18} className="mt-0.5 shrink-0" />}>{loadError}</Notice>}
        {enrollments && Object.keys(enrollments).length === 0 && <p className="text-sm text-muted">Aucun visage enregistré pour l'instant.</p>}
        {enrollments && Object.keys(enrollments).length > 0 && (
          <ul className="divide-y divide-line">
            {Object.entries(enrollments).map(([u, meta]) => (
              <li key={u} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate font-medium">{u}</p>
                  <p className="text-xs text-muted">{meta.n_images} photo(s) · inscrit le {new Date(meta.enrolled_at * 1000).toLocaleString('fr-FR')}</p>
                </div>
                <button type="button" onClick={() => revoke(u)} disabled={busy}
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-bad hover:bg-bad-soft">
                  <Icon name="trash" size={16} /> {pendingRevoke === u ? 'Confirmer ?' : 'Révoquer'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
