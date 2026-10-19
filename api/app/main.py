"""API de paiement fictive : comptes, bénéficiaires, historique, virements idempotents.
Métriques Prometheus + journaux JSON (consommés par Loki, le détecteur et le SIEM)."""
import os, json, time, threading, uuid
from decimal import Decimal
from contextlib import asynccontextmanager

import jwt, psycopg
from psycopg_pool import ConnectionPool, PoolTimeout
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response, Query
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from .schemas import PaymentIn

SECRET = os.environ["JWT_SECRET"]
EXPECTED_TOTAL = Decimal(os.getenv("EXPECTED_TOTAL", "600000"))
DSN = f"host=db dbname=payments user=api_user password={os.environ['API_DB_PASSWORD']} connect_timeout=3"
pool = ConnectionPool(DSN, min_size=2, max_size=int(os.getenv("DB_POOL", "8")), timeout=3, open=False)
suspended: set = set()          # comptes suspendus par le moteur de remédiation
revoked: dict = {}              # utilisateur -> epoch : les jetons émis avant sont refusés

REQS = Counter("http_requests_total", "requêtes", ["endpoint", "status"])
LAT = Histogram("http_request_duration_seconds", "latence", ["endpoint"],
                buckets=(.01, .025, .05, .1, .25, .5, 1, 2, 5, 10))
INFLIGHT = Gauge("http_inflight_requests", "requêtes en cours (file d'attente comprise)")
PAYS = Counter("payments_total", "paiements", ["result"])
REJECTS = Counter("api_session_rejections_total", "jetons refusés", ["reason"])


def watcher():
    """Connexion dédiée : suspensions et révocations restent appliquées même si le pool est saturé."""
    global suspended, revoked
    conn = None
    while True:
        try:
            if conn is None or conn.closed:
                conn = psycopg.connect(DSN, autocommit=True)
            rows = conn.execute("SELECT username, suspended, COALESCE(EXTRACT(EPOCH FROM revoked_after), 0) "
                                "FROM users WHERE suspended OR revoked_after IS NOT NULL").fetchall()
            suspended = {r[0] for r in rows if r[1]}
            revoked = {r[0]: float(r[2]) for r in rows if r[2]}
        except Exception:
            conn = None
        time.sleep(1)


@asynccontextmanager
async def lifespan(app):
    pool.open()
    threading.Thread(target=watcher, daemon=True).start()
    yield
    pool.close()


app = FastAPI(title="Payment API", lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    t0 = time.perf_counter(); INFLIGHT.inc(); status = 500
    try:
        resp = await call_next(request); status = resp.status_code
        return resp
    finally:
        INFLIGHT.dec(); dur = time.perf_counter() - t0
        route = request.scope.get("route"); ep = route.path if route else "unmatched"
        REQS.labels(ep, str(status)).inc(); LAT.labels(ep).observe(dur)
        if ep != "/metrics":
            print(json.dumps({"user": getattr(request.state, "user", "-"), "method": request.method,
                              "path": ep, "status": status, "dur": round(dur, 4)}), flush=True)


def current_user(request: Request, authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    try:
        claims = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid token")
    user = claims["sub"]; request.state.user = user
    if user in suspended:
        REJECTS.labels("suspended").inc()
        raise HTTPException(403, "account suspended")
    if claims.get("iat", 0) < revoked.get(user, 0):
        REJECTS.labels("revoked").inc()
        raise HTTPException(401, "session revoked")
    return user


def _pay_json(r, status: str) -> dict:
    """r = (id, payee, amount, label, created_at)"""
    return {"id": str(r[0]), "status": status, "to": r[1], "amount": str(r[2]), "label": r[3],
            "created_at": r[4].isoformat()}


def _busy():
    PAYS.labels("unavailable").inc()
    raise HTTPException(503, "service busy")


@app.post("/api/payments", status_code=201)
def create_payment(p: PaymentIn, user: str = Depends(current_user),
                   idempotency_key: str | None = Header(None, pattern=r"^[A-Za-z0-9_-]{8,64}$")):
    if p.to == user:
        raise HTTPException(400, "self payment")
    try:
        with pool.connection() as conn:   # commit à la sortie, rollback sur exception
            if idempotency_key:
                ex = conn.execute("SELECT id, payee, amount, label, created_at FROM payments "
                                  "WHERE payer=%s AND idem_key=%s", (user, idempotency_key)).fetchone()
                if ex:
                    return JSONResponse(_pay_json(ex, "duplicate"), status_code=200)
            rows = conn.execute("SELECT owner, balance FROM accounts WHERE owner IN (%s,%s) "
                                "ORDER BY owner FOR UPDATE", (user, p.to)).fetchall()
            bal = {r[0]: r[1] for r in rows}
            if user not in bal or p.to not in bal:
                raise HTTPException(404, "unknown account")
            if bal[user] < p.amount:
                PAYS.labels("insufficient").inc()
                raise HTTPException(402, "insufficient funds")
            time.sleep(0.01)  # temps de traitement simulé (verrou tenu) -> contention réaliste sous charge
            conn.execute("UPDATE accounts SET balance = balance - %s WHERE owner = %s", (p.amount, user))
            conn.execute("UPDATE accounts SET balance = balance + %s WHERE owner = %s", (p.amount, p.to))
            row = conn.execute("INSERT INTO payments(payer,payee,amount,label,idem_key) VALUES (%s,%s,%s,%s,%s) "
                               "RETURNING id, payee, amount, label, created_at",
                               (user, p.to, p.amount, p.label, idempotency_key)).fetchone()
    except psycopg.errors.UniqueViolation:     # deux requêtes simultanées avec la même clé : la seconde relit la première
        with pool.connection() as conn:
            ex = conn.execute("SELECT id, payee, amount, label, created_at FROM payments WHERE payer=%s AND idem_key=%s",
                              (user, idempotency_key)).fetchone()
        return JSONResponse(_pay_json(ex, "duplicate"), status_code=200)
    except (PoolTimeout, psycopg.OperationalError):
        _busy()
    PAYS.labels("ok").inc()
    return _pay_json(row, "accepted")


@app.get("/api/payments")
def list_payments(user: str = Depends(current_user), limit: int = Query(20, ge=1, le=50)):
    try:
        with pool.connection() as conn:
            rows = conn.execute(
                "SELECT id, payer, payee, amount, label, created_at FROM payments "
                "WHERE (payer=%s OR payee=%s) AND payer <> 'probe' AND payee <> 'probe' "
                "ORDER BY created_at DESC LIMIT %s", (user, user, limit)).fetchall()
    except (PoolTimeout, psycopg.OperationalError):
        raise HTTPException(503, "service busy")
    return [{"id": str(r[0]), "direction": "out" if r[1] == user else "in", "counterparty": r[2] if r[1] == user else r[1],
             "amount": str(r[3]), "label": r[4], "created_at": r[5].isoformat()} for r in rows]


@app.get("/api/payments/{pid}")
def get_payment(pid: str, user: str = Depends(current_user)):
    try:
        uid = uuid.UUID(pid)
    except ValueError:
        raise HTTPException(404, "not found")
    try:
        with pool.connection() as conn:
            r = conn.execute("SELECT id, payer, payee, amount, label, created_at FROM payments "
                             "WHERE id=%s AND (payer=%s OR payee=%s)", (uid, user, user)).fetchone()
    except (PoolTimeout, psycopg.OperationalError):
        raise HTTPException(503, "service busy")
    if not r:
        raise HTTPException(404, "not found")
    return {"id": str(r[0]), "payer": r[1], "payee": r[2], "amount": str(r[3]), "label": r[4],
            "created_at": r[5].isoformat()}


@app.get("/api/accounts/me")
def my_account(user: str = Depends(current_user)):
    try:
        with pool.connection() as conn:
            r = conn.execute("SELECT a.balance, u.display_name FROM accounts a JOIN users u ON u.username = a.owner "
                             "WHERE a.owner=%s", (user,)).fetchone()
    except (PoolTimeout, psycopg.OperationalError):
        raise HTTPException(503, "service busy")
    if not r:
        raise HTTPException(404, "unknown account")
    return {"owner": user, "display_name": r[1], "balance": str(r[0]), "currency": "EUR"}


@app.get("/api/beneficiaries")
def beneficiaries(user: str = Depends(current_user)):
    try:
        with pool.connection() as conn:
            rows = conn.execute("SELECT a.owner, u.display_name FROM accounts a JOIN users u ON u.username = a.owner "
                                "WHERE a.owner <> %s AND a.owner NOT IN ('probe','attacker') ORDER BY u.display_name",
                                (user,)).fetchall()
    except (PoolTimeout, psycopg.OperationalError):
        raise HTTPException(503, "service busy")
    return [{"id": r[0], "name": r[1]} for r in rows]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/health/deep")
def health_deep():
    """Santé métier : base joignable ET invariant comptable respecté (somme des soldes constante).
    Non routé par le WAF : lu uniquement par le moteur de remédiation, sur le réseau interne."""
    try:
        with pool.connection() as c:
            total = c.execute("SELECT COALESCE(SUM(balance),0) FROM accounts").fetchone()[0]
    except Exception:
        raise HTTPException(503, "db unavailable")
    return {"db": "ok", "total": str(total), "expected": str(EXPECTED_TOTAL), "consistent": total == EXPECTED_TOTAL}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
