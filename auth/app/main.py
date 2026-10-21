"""Service d'authentification : JWT, journal d'audit JSON (lu par le SIEM), et endpoints internes
(suspension, verrouillage, révocation de sessions, réinitialisation forcée) réservés au moteur de remédiation."""
import os, time, hmac, json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import bcrypt, jwt
from psycopg_pool import ConnectionPool
from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

from . import esp_led, face_ticket

SECRET = os.environ["JWT_SECRET"]
INTERNAL = os.environ["INTERNAL_TOKEN"]
TOKEN_TTL = 900
DSN = f"host=db dbname=payments user=auth_user password={os.environ['AUTH_DB_PASSWORD']} connect_timeout=3"
pool = ConnectionPool(DSN, min_size=1, max_size=8, timeout=3, open=False, kwargs={"autocommit": True})

LOGINS = Counter("auth_logins_total", "tentatives de connexion", ["result"])
# (identifiant, rôle, nom affiché, variable d'environnement du mot de passe, reconnaissance faciale requise)
SEED = [
    ("alice", "customer", "Alice Martin", "DEMO_PASSWORD", False),
    ("bob", "customer", "Bob Durand", "DEMO_PASSWORD", False),
    ("carol", "customer", "Carol Lefèvre", "WEAK_PASSWORD", False),      # compte volontairement faible (scénario brute-force) ;
                                                                          # SANS reconnaissance faciale à dessein (voir docs/face-auth.md)
    ("merchant", "customer", "Boutique Alpha", "DEMO_PASSWORD", False),
    ("attacker", "customer", "Compte client A. Tack", "ATTACKER_PASSWORD", False),
    ("probe", "monitor", "Sonde de santé", "PROBE_PASSWORD", False),
    ("manager", "backoffice", "Opérateur Back-Office", "MANAGER_PASSWORD", True),   # consigne additionnelle 1
]
DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=10)).decode()   # égalise les temps de réponse


def audit(event: str, **kw):
    """Une ligne JSON par évènement : promtail -> Loki -> SIEM (détecteur) et registre d'incidents."""
    print(json.dumps({"event": event, **kw}), flush=True)


@asynccontextmanager
async def lifespan(app):
    pool.open()
    with pool.connection() as c:
        for user, role, display, env, face_required in SEED:
            pw = os.environ.get(env) or os.environ["DEMO_PASSWORD"]
            h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()
            # .env reste la source de vérité des mots de passe ; les drapeaux (suspension, verrouillage...) sont conservés
            c.execute("INSERT INTO users(username,pw_hash,role,display_name,face_required) VALUES (%s,%s,%s,%s,%s) "
                      "ON CONFLICT (username) DO UPDATE SET pw_hash=EXCLUDED.pw_hash, display_name=EXCLUDED.display_name, "
                      "face_required=EXCLUDED.face_required",
                      (user, h, role, display, face_required))
    yield
    pool.close()


app = FastAPI(title="Auth", lifespan=lifespan)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)   # limite de bcrypt
    face_ticket: str | None = Field(default=None, max_length=256)   # requis si le compte a face_required (voir docs/face-auth.md)


@app.post("/auth/login")
def login(b: Login):
    with pool.connection() as c:
        r = c.execute("SELECT pw_hash, role, suspended, locked_until, must_reset, face_required FROM users WHERE username=%s",
                      (b.username,)).fetchone()
    now = datetime.now(timezone.utc)
    if r and r[3] and r[3] > now:
        # Refus peu coûteux AVANT bcrypt : un compte verrouillé ne consomme plus de CPU
        LOGINS.labels("locked").inc(); audit("login", user=b.username, result="locked")
        raise HTTPException(423, "account temporarily locked")
    # Compte non trouvé ou ne nécessitant pas la reconnaissance faciale : étape ignorée (comportement
    # inchangé pour alice/bob/carol/merchant/attacker/probe — voir docs/face-auth.md pour la justification
    # de ce périmètre). Sinon, un billet valide signé par `face` est obligatoire.
    face_ok = (not r or not r[5]) or face_ticket.verify(b.face_ticket, b.username)
    good = bcrypt.checkpw(b.password.encode(), (r[0] if r else DUMMY_HASH).encode())
    if not r or not good or not face_ok:
        LOGINS.labels("fail").inc(); audit("login", user=b.username, result="fail")
        if r and r[5]:          # consigne additionnelle 1 : mot de passe refusé -> LED rouge x10, puis ré-identification
            esp_led.set_led("red_blink10")
        raise HTTPException(401, "bad credentials")
    if r[2]:
        LOGINS.labels("suspended").inc(); audit("login", user=b.username, result="suspended")
        raise HTTPException(403, "account suspended")
    if r[4]:
        LOGINS.labels("reset_required").inc(); audit("login", user=b.username, result="reset_required")
        raise HTTPException(403, "password reset required")
    LOGINS.labels("ok").inc(); audit("login", user=b.username, result="ok")
    if r[5]:                    # consigne additionnelle 1 : mot de passe validé -> LED verte fixe 30 s
        esp_led.set_led("green_solid_30")
    iat = int(time.time())
    return {"token": jwt.encode({"sub": b.username, "role": r[1], "iat": iat, "exp": iat + TOKEN_TTL},
                                SECRET, algorithm="HS256"), "expires_in": TOKEN_TTL}


# ---------- endpoints internes : non routés par le WAF, jeton interne obligatoire ----------
class Target(BaseModel):
    username: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")


class LockReq(Target):
    seconds: int = Field(default=180, ge=10, le=3600)


def _internal(tok):
    if not hmac.compare_digest(tok or "", INTERNAL):
        raise HTTPException(401, "internal only")


def _update(sql: str, params: tuple):
    with pool.connection() as c:
        c.execute(sql, params)


@app.post("/internal/suspend")
def suspend(t: Target, x_internal_token: str | None = Header(None)):
    _internal(x_internal_token)
    _update("UPDATE users SET suspended=true WHERE username=%s", (t.username,))
    audit("admin", action="suspend", user=t.username)
    return {"suspended": t.username}


@app.post("/internal/reinstate")
def reinstate(t: Target, x_internal_token: str | None = Header(None)):
    _internal(x_internal_token)
    _update("UPDATE users SET suspended=false WHERE username=%s", (t.username,))
    audit("admin", action="reinstate", user=t.username)
    return {"reinstated": t.username}


@app.post("/internal/lock")
def lock(t: LockReq, x_internal_token: str | None = Header(None)):
    _internal(x_internal_token)
    _update("UPDATE users SET locked_until = now() + make_interval(secs => %s::double precision) WHERE username=%s", (t.seconds, t.username))
    audit("admin", action="lock", user=t.username, seconds=t.seconds)
    return {"locked": t.username, "seconds": t.seconds}


@app.post("/internal/revoke")
def revoke(t: Target, x_internal_token: str | None = Header(None)):
    """Révoque toutes les sessions en cours : l'API refuse les jetons émis avant cette date."""
    _internal(x_internal_token)
    _update("UPDATE users SET revoked_after = now() + interval '1 second' WHERE username=%s", (t.username,))
    audit("admin", action="revoke_sessions", user=t.username)
    return {"revoked": t.username}


@app.post("/internal/force_reset")
def force_reset(t: Target, x_internal_token: str | None = Header(None)):
    _internal(x_internal_token)
    _update("UPDATE users SET must_reset=true WHERE username=%s", (t.username,))
    audit("admin", action="force_reset", user=t.username)
    return {"must_reset": t.username}


@app.post("/internal/clear")
def clear(t: Target, x_internal_token: str | None = Header(None)):
    """Remise à zéro de laboratoire : lève suspension, verrou, révocation et réinitialisation forcée."""
    _internal(x_internal_token)
    _update("UPDATE users SET suspended=false, locked_until=NULL, revoked_after=NULL, must_reset=false WHERE username=%s",
            (t.username,))
    audit("admin", action="clear", user=t.username)
    return {"cleared": t.username}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
