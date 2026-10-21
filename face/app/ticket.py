"""Billet d'authentification faciale : preuve signée et de courte durée de vie que `face` émet après une
reconnaissance réussie, et que `auth` seul vérifie avant d'accepter un mot de passe sur un compte
`face_required` (consigne additionnelle 1). Même principe que la signature des évènements
détecteur -> remédiateur (HMAC-SHA256, voir detector/app/main.py), ici partagé entre `face` et `auth`
UNIQUEMENT via le secret `FACE_TICKET_KEY` — aucun appel réseau entre ces deux services n'est nécessaire.

Pur (aucune E/S) : testable sans réseau, voir tests/test_ticket.py."""
import hashlib, hmac, os, time

TTL_S = 120   # assez pour saisir un mot de passe, pas assez pour rejouer un billet intercepté plus tard


def _key() -> bytes:
    return os.environ["FACE_TICKET_KEY"].encode()


def issue(username: str, ttl_s: int = TTL_S, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time())) + ttl_s
    payload = f"{username}:{exp}"
    sig = hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


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
