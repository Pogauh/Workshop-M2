"""Logique de l'actionneur, séparée du transport HTTP pour être testable sans Docker.
Surface volontairement minimale : 3 services redémarrables (liste blanche), rechargement du WAF, statut.
Aucune création de conteneur, aucun exec, aucun accès aux volumes : même compromis, le moteur ne peut rien d'autre."""
import hmac, time

RESTART_ALLOW = {"api": "immune-api", "auth": "immune-auth", "db": "immune-db"}
STATUS = {"waf": "immune-waf", "api": "immune-api", "auth": "immune-auth", "db": "immune-db"}
MIN_INTERVAL = 20          # secondes entre deux redémarrages du même service


class Denied(Exception):
    def __init__(self, code, msg):
        super().__init__(msg); self.code, self.msg = code, msg


class Actuator:
    def __init__(self, cli, token, clock=time.time):
        self.cli, self.token, self.clock, self.last = cli, token, clock, {}

    def check(self, tok):
        if not self.token or not hmac.compare_digest((tok or "").encode(), self.token.encode()):
            raise Denied(401, "unauthorized")

    def restart(self, tok, svc):
        self.check(tok)
        if svc not in RESTART_ALLOW:
            raise Denied(403, "service not allowed")
        now = self.clock()
        if now - self.last.get(svc, -1e9) < MIN_INTERVAL:
            raise Denied(429, "restart too soon")
        self.last[svc] = now
        self.cli.containers.get(RESTART_ALLOW[svc]).restart(timeout=10)
        return {"ok": True, "restarted": svc}

    def reload_waf(self, tok):
        self.check(tok)
        self.cli.containers.get(STATUS["waf"]).kill(signal="HUP")      # nginx recharge ses règles sans coupure
        return {"ok": True}

    def status(self, tok):
        self.check(tok)
        out = {}
        for k, name in STATUS.items():
            try:
                c = self.cli.containers.get(name)
                out[k] = {"state": c.status, "health": c.attrs["State"].get("Health", {}).get("Status", "n/a")}
            except Exception:
                out[k] = {"state": "missing", "health": "n/a"}
        return out
