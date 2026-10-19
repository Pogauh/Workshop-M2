import { initials } from '../lib/format.js'

const TONES = ['bg-[#dfe7ff] text-[#1f3aa8]', 'bg-[#dff3ea] text-[#0a6a47]', 'bg-[#fdebd0] text-[#7a4a00]', 'bg-[#f1e3fb] text-[#6a2a93]', 'bg-[#e1eef6] text-[#1d5a7d]']
const tone = (s = '') => TONES[[...s].reduce((a, c) => a + c.charCodeAt(0), 0) % TONES.length]

export function Avatar({ name, size = 'md' }) {
  const dim = size === 'lg' ? 'h-12 w-12 text-base' : 'h-10 w-10 text-sm'
  return <span aria-hidden="true" className={`${dim} ${tone(name)} inline-flex shrink-0 items-center justify-center rounded-full font-semibold`}>{initials(name)}</span>
}

export function Logo({ className = '' }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" fill="#2f5bff" />
        <path d="M9 22V10h7a4 4 0 0 1 0 8h-3" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M19.5 22.5c2.2-.5 3.7-2 4.3-4.1" fill="none" stroke="#cfdaff" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <span className="text-lg font-semibold tracking-tight text-ink">PayAlpha</span>
    </span>
  )
}

/** Message d'état annoncé aux lecteurs d'écran. tone: bad | warn | ok | info */
export function Notice({ tone: t = 'info', icon, children, ...rest }) {
  const cls = { bad: 'bg-bad-soft text-bad', warn: 'bg-warn-soft text-warn', ok: 'bg-ok-soft text-ok', info: 'bg-brand-soft text-brand-deep' }[t]
  return <div className={`${cls} flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm font-medium`} {...rest}>{icon}<div className="min-w-0">{children}</div></div>
}
