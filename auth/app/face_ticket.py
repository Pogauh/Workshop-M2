"""Vérification du billet de reconnaissance faciale émis par le service `face` (voir face/app/ticket.py
pour l'émission : même secret FACE_TICKET_KEY, même format). Dupliqué à dessein plutôt que partagé en
paquet commun : chaque service de ce dépôt reste un conteneur autonome, sans dépendance croisée au build.

Pur (aucune E/S) : testable sans réseau, voir tests/test_face_ticket.py."""
import hashlib, hmac, os, time


def _key() -> bytes:
    return os.environ["FACE_TICKET_KEY"].encode()


def verify(ticket: str | None, username: str, now: float | None = None) -> bool:
    if not ticket:
        return False
    parts = ticket.split(":")
    if len(parts) != 3:
        return False
    u, exp_s, sig = parts
    if u != username or not exp_s.isdigit():
        return False
    expected = hmac.new(_key(), f"{u}:{exp_s}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False
    return int(exp_s) >= int(now if now is not None else time.time())
