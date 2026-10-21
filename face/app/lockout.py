"""Verrouillage propre à la phase de RECONNAISSANCE FACIALE (avant tout mot de passe) : 1 nouvel essai
après un échec, puis blocage 5 minutes — repart à zéro ensuite (consigne additionnelle 1 : « L'utilisateur
peut recommencer 1 fois puis est bloqué 5 minutes, etc. »). Indépendant du verrouillage mot de passe déjà
en place côté `auth` (locked_until en base, 180 s par défaut, voir auth/app/main.py) : deux défenses
distinctes pour deux étapes distinctes de la connexion renforcée.

En mémoire (par processus) : un redémarrage du service lève les verrous en cours — acceptable pour un
badge de démonstration, à noter comme limite si industrialisé (voir docs/face-auth.md)."""
import time

FAILS_BEFORE_LOCK = 2
LOCK_SECONDS = 300

_fails: dict[str, int] = {}
_locked_until: dict[str, float] = {}


def is_locked(username: str, now: float | None = None):
    """Retourne l'horodatage de fin de blocage si verrouillé, sinon None."""
    now = now if now is not None else time.time()
    until = _locked_until.get(username, 0)
    return until if until > now else None


def record_failure(username: str, now: float | None = None):
    """Retourne l'horodatage de fin de blocage si CET échec vient de déclencher le verrou, sinon None."""
    now = now if now is not None else time.time()
    _fails[username] = _fails.get(username, 0) + 1
    if _fails[username] >= FAILS_BEFORE_LOCK:
        until = now + LOCK_SECONDS
        _locked_until[username] = until
        _fails[username] = 0
        return until
    return None


def record_success(username: str):
    _fails.pop(username, None)


def reset(username: str):
    """Remise à zéro de laboratoire (voir scripts/reset.sh)."""
    _fails.pop(username, None); _locked_until.pop(username, None)
