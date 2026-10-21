import { useEffect, useRef, useState } from 'react'
import Icon from './Icons.jsx'

/** Active la caméra USB du PC Hôte (API navigateur `getUserMedia` — aucun accès caméra depuis les
 * conteneurs, qui n'y ont de toute façon pas accès sous Docker Desktop), affiche un aperçu et capture
 * automatiquement une image après un court délai. `onCapture(base64Jpeg)` est appelé une seule fois.
 * Le flux est coupé proprement au démontage (changement d'étape du formulaire, voir Login.jsx). */
export default function FaceCapture({ onCapture, onError, countdownS = 2 }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const firedRef = useRef(false)
  const [status, setStatus] = useState('starting')   // starting | live | error
  const [count, setCount] = useState(countdownS)

  useEffect(() => {
    let cancelled = false
    navigator.mediaDevices?.getUserMedia
      ? navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 }, audio: false }).then((stream) => {
          if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return }
          streamRef.current = stream
          if (videoRef.current) videoRef.current.srcObject = stream
          setStatus('live')
        }).catch((e) => { if (!cancelled) { setStatus('error'); onError?.(e) } })
      : (setStatus('error'), onError?.(new Error('getUserMedia indisponible (navigateur ou contexte non sécurisé)')))
    return () => { cancelled = true; streamRef.current?.getTracks().forEach((t) => t.stop()) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (status !== 'live' || firedRef.current) return
    if (count <= 0) { firedRef.current = true; capture(); return }
    const t = setTimeout(() => setCount((c) => c - 1), 1000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, count])

  function capture() {
    const video = videoRef.current
    if (!video || !video.videoWidth) { onError?.(new Error('flux vidéo pas encore prêt')); return }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth; canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
    onCapture(dataUrl.slice(dataUrl.indexOf(',') + 1))
  }

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-black">
      <div className="relative aspect-[4/3] w-full">
        <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
        {status === 'live' && count > 0 && (
          <div className="absolute inset-x-0 bottom-0 bg-black/60 py-2 text-center text-sm font-medium text-white">
            Analyse dans {count}s — regardez la caméra
          </div>
        )}
        {status === 'starting' && (
          <div className="absolute inset-0 grid place-items-center bg-black/80 text-sm text-white/80">
            <span className="inline-flex items-center gap-2"><Icon name="spinner" spin className="text-white" /> Activation de la caméra…</span>
          </div>
        )}
      </div>
      {status === 'error' && (
        <div className="bg-bad-soft p-3 text-center text-sm text-bad">
          Caméra inaccessible : autorisez l'accès dans le navigateur, ou vérifiez qu'une caméra USB est branchée sur le PC Hôte.
        </div>
      )}
    </div>
  )
}
