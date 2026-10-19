"""API du moteur de remédiation : réception des évènements signés du détecteur, état pour le dashboard et l'assistant,
reset de laboratoire, métriques.  La logique est dans engine.py."""
import hashlib, hmac, json, os, threading, time

from fastapi import FastAPI, Header, HTTPException, Request, Response

from .adapters import LiveIO
from .engine import Config, Engine

HMAC_KEY = os.environ["EVENT_HMAC_KEY"].encode()
ADMIN = os.environ["INTERNAL_TOKEN"]
io = LiveIO()
engine = Engine(io, Config.from_env(os.environ))
app = FastAPI(title="Remediator")


def _spawn(ev, attack):
    threading.Thread(target=engine.guarded, args=(ev, attack), daemon=True).start()


@app.post("/event")
async def event(request: Request, x_signature: str = Header(...)):
    raw = await request.body()
    if not hmac.compare_digest(hmac.new(HMAC_KEY, raw, hashlib.sha256).hexdigest(), x_signature):
        raise HTTPException(401, "bad signature")
    ev = json.loads(raw)
    if abs(time.time() - ev.get("ts", 0)) > 30:
        raise HTTPException(401, "stale event")
    attack = engine.handle_event(ev)
    if attack:
        _spawn(ev, attack)
    return {"accepted": True}


@app.get("/state")
def state():
    return engine.snapshot()


@app.get("/incidents")
def incidents(n: int = 50):
    return io.load_journal(min(max(n, 1), 200))


@app.post("/reset")
def reset(x_admin_token: str | None = Header(None)):
    if not hmac.compare_digest(x_admin_token or "", ADMIN):
        raise HTTPException(401, "admin only")
    engine.reset()
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(engine.metrics_text(), media_type="text/plain; version=0.0.4")


def monitor():
    while True:
        try:
            out = engine.monitor_tick()
            if out:
                _spawn(*out)
        except Exception as e:
            engine.log("error", f"monitor: {e}")
        time.sleep(engine.cfg.__dict__.get("monitor_every", 2.0))


@app.on_event("startup")
def startup():
    try:
        io.write_rules(engine.S["rules"])
    except Exception as e:
        engine.log("error", f"écriture initiale des règles WAF impossible: {e}")
    threading.Thread(target=monitor, daemon=True).start()
