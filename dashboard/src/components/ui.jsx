const P = {
  check: <><circle cx="12" cy="12" r="9" /><path d="M8 12.5l2.7 2.7L16 9.5" /></>,
  alert: <><path d="M12 4l9 16H3z" /><path d="M12 10v4.5M12 17.6v.1" /></>,
  cross: <><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.1" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  shield: <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />,
  lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  link: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.700l1-1" /></>,
  off: <><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>,
}
export function Icon({ name, size = 18, className = '' }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={className}>{P[name]}</svg>
}

export const TONE = {
  ok: { text: 'text-ok', icon: 'check' }, warn: { text: 'text-warn', icon: 'alert' }, serious: { text: 'text-serious', icon: 'alert' },
  crit: { text: 'text-crit', icon: 'cross' }, info: { text: 'text-info', icon: 'info' }, off: { text: 'text-muted', icon: 'off' },
}

/** État = icône + libellé + couleur : jamais la couleur seule. */
export function Badge({ tone = 'off', children, className = '' }) {
  const t = TONE[tone]
  return <span className={`${t.text} inline-flex items-center gap-1.5 text-sm font-semibold ${className}`}><Icon name={t.icon} size={16} />{children}</span>
}

export function Panel({ title, right, children, className = '', id }) {
  return (
    <section aria-labelledby={id} className={`rounded-xl border border-line bg-panel ${className}`}>
      <header className="flex flex-wrap items-center justify-between gap-2 px-4 pb-1 pt-3.5">
        <h2 id={id} className="text-[0.95rem] font-semibold">{title}</h2>
        {right}
      </header>
      <div className="px-4 pb-4 pt-2">{children}</div>
    </section>
  )
}

export function Chip({ children, tone = 'off', title }) {
  return <span title={title} className={`${TONE[tone].text} inline-flex items-center rounded-md border border-line bg-raise px-2 py-0.5 text-[0.8rem] font-medium`}>{children}</span>
}

export const Empty = ({ children }) => <p className="text-sm text-muted">{children}</p>
