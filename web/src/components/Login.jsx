import { useState } from 'react'
import { explain } from '../lib/api.js'
import Icon from './Icons.jsx'
import { Notice } from './ui.jsx'

export default function Login({ onSubmit, notice }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try { await onSubmit(username.trim().toLowerCase(), password) }
    catch (err) { setError({ status: err.status, text: explain(err.status, err.detail) }); setPassword('') }
    finally { setBusy(false) }
  }

  const locked = error && (error.status === 423 || error.status === 403)
  return (
    <main className="mx-auto grid min-h-[calc(100vh-4.5rem)] max-w-md place-items-center px-4 pb-16">
      <div className="w-full">
        <h1 className="text-3xl font-semibold tracking-tight">Connexion</h1>
        <p className="mt-2 text-muted">Connectez-vous pour envoyer et suivre vos paiements.</p>

        <form onSubmit={submit} className="mt-6 space-y-4 rounded-2xl border border-line bg-surface p-5 sm:p-6" noValidate>
          {notice && !error && <Notice tone="info" role="status" icon={<Icon name="lock" size={18} className="mt-0.5 shrink-0" />}>{notice}</Notice>}
          <div>
            <label htmlFor="username" className="mb-1.5 block text-sm font-medium">Identifiant</label>
            <input id="username" className="field" autoComplete="username" autoCapitalize="none" spellCheck="false" required
                   value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium">Mot de passe</label>
            <div className="relative">
              <input id="password" className="field pr-12" type={show ? 'text' : 'password'} autoComplete="current-password" required maxLength={72}
                     value={password} onChange={(e) => setPassword(e.target.value)} />
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
          <button type="submit" className="btn btn-primary w-full" disabled={busy || !username || !password}>
            {busy ? <><Icon name="spinner" spin /> Connexion…</> : 'Se connecter'}
          </button>
        </form>
      </div>
    </main>
  )
}
