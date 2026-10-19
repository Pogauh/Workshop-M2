// Icônes en trait (24x24), dessinées pour ce projet. Toujours accompagnées d'un libellé : jamais la couleur seule.
const P = {
  check: <path d="M5 12.5l4.2 4.2L19 7" />,
  alert: <><path d="M12 4l9 16H3z" /><path d="M12 10v4.5M12 17.6v.1" /></>,
  lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  out: <path d="M7 17L17 7M9 7h8v8" />,
  in: <path d="M17 7L7 17M15 17H7V9" />,
  logout: <><path d="M14 5h4a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-4" /><path d="M10 8l-4 4 4 4M6 12h10" /></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.8" /></>,
  eyeOff: <><path d="M4 4l16 16" /><path d="M9.9 6A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 0 1-3.2 3.9M6.3 8.1A15.5 15.5 0 0 0 2.5 12S6 18.5 12 18.5c1.6 0 3-.4 4.2-1" /></>,
  spinner: <path d="M12 3a9 9 0 1 0 9 9" />,
  receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>,
  close: <path d="M6 6l12 12M18 6L6 18" />,
}
export default function Icon({ name, size = 20, className = '', spin = false }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true" focusable="false" className={`${className}${spin ? ' spin' : ''}`}>
      {P[name]}
    </svg>
  )
}
