"""Entrées/sorties réelles du moteur : actionneur Docker, service d'authentification, sonde de transaction,
règles WAF, journal d'incidents.  Isolées ici pour que engine.py reste testable sans réseau."""
import base64, json, os, re, time, uuid
from pathlib import Path

import httpx

from .engine import render_waf_rules

AUTH_PATHS = {"suspend": "/internal/suspend", "reinstate": "/internal/reinstate", "lock": "/internal/lock",
              "revoke": "/internal/revoke", "force_reset": "/internal/force_reset", "clear": "/internal/clear"}


class LiveIO:
    def __init__(self, env=os.environ):
        g = env.get
        self.gate, self.api = g("GATE_URL", "http://waf:8080"), g("API_URL", "http://api:8000")
        self.auth_url, self.act_url = g("AUTH_URL", "http://auth:8001"), g("ACTUATOR_URL", "http://actuator:9200")
        self.internal, self.act_token = env["INTERNAL_TOKEN"], env["ACTUATOR_TOKEN"]
        self.probe_password = env["PROBE_PASSWORD"]
        self.rules_path = Path(g("RULES_PATH", "/rules/active.conf"))
        self.journal_path = Path(g("JOURNAL_PATH", "/data/incidents.jsonl"))
        self._tok, self._tok_exp, self._auth_prev = None, 0.0, None

    # ---- journal / sorties ----
    def emit(self, event):
        print(json.dumps(event, default=str), flush=True)      # -> promtail -> Loki (registre d'incidents, SIEM)

    def journal(self, inc):
        with self.journal_path.open("a") as f:
            f.write(json.dumps(inc, default=str) + "\n")
        self.emit({"event": "incident", **{k: inc.get(k) for k in ("id", "attack", "mttr_s", "suspects")},
                   "actions": [a["name"] for a in inc["actions"]], "restored": "restored_at" in inc})

    def load_journal(self, n):
        try:
            lines = self.journal_path.read_text().splitlines()[-n:]
            return [json.loads(x) for x in lines]
        except Exception:
            return []

    # ---- actions sur le monde (toutes en liste blanche côté actionneur) ----
    def write_rules(self, rules):
        tmp = self.rules_path.with_suffix(".tmp")
        tmp.write_text(render_waf_rules(rules)); tmp.replace(self.rules_path)

    def _act(self, path, method="POST"):
        r = httpx.request(method, self.act_url + path, headers={"X-Actuator-Token": self.act_token}, timeout=30)
        r.raise_for_status(); return r.json()

    def reload_waf(self):
        self._act("/waf/reload")

    def restart(self, svc):
        self._act(f"/restart/{svc}")

    def services_status(self):
        return self._act("/status", "GET")

    def auth(self, action, payload):
        r = httpx.post(self.auth_url + AUTH_PATHS[action], json=payload, headers={"X-Internal-Token": self.internal}, timeout=5)
        r.raise_for_status()

    # ---- sonde de transaction : la PREUVE de reprise ----
    def _token(self, c):
        if self._tok and time.time() < self._tok_exp - 60:
            return self._tok
        r = c.post(self.gate + "/auth/login", json={"username": "probe", "password": self.probe_password})
        if r.status_code != 200:
            raise RuntimeError(f"connexion sonde {r.status_code}")
        self._tok = r.json()["token"]
        try:
            pad = self._tok.split(".")[1]; pad += "=" * (-len(pad) % 4)
            self._tok_exp = float(json.loads(base64.urlsafe_b64decode(pad))["exp"])
        except Exception:
            self._tok_exp = time.time() + 600
        return self._tok

    def probe(self):
        t0, ok, detail, tx = time.perf_counter(), False, "", None
        try:
            with httpx.Client(timeout=3) as c:
                h = {"Authorization": "Bearer " + self._token(c)}
                r = c.post(self.gate + "/api/payments", json={"to": "merchant", "amount": "0.01", "label": "sonde"},
                           headers={**h, "Idempotency-Key": uuid.uuid4().hex})
                if r.status_code == 401:
                    self._tok = None
                if r.status_code != 201:
                    raise RuntimeError(f"paiement {r.status_code}")
                pid = r.json()["id"]
                g = c.get(f"{self.gate}/api/payments/{pid}", headers=h)      # la transaction est bien relisible
                me = c.get(self.gate + "/api/accounts/me", headers=h)        # le compte répond
                d = c.get(self.api + "/api/health/deep")                     # base OK + invariant comptable (réseau interne)
                consistent = d.status_code == 200 and d.json().get("consistent") is True
                ok = g.status_code == 200 and me.status_code == 200 and consistent
                tx = {"id": pid, "amount": "0.01", "to": "merchant", "created": r.status_code,
                      "reread": g.status_code, "consistent": consistent}
                if not ok:
                    detail = f"relecture {g.status_code}, compte {me.status_code}, invariant {consistent}"
        except Exception as e:
            detail = str(e)[:80]
        return {"ok": ok, "ms": round((time.perf_counter() - t0) * 1000), "detail": detail, "ts": time.time(), "tx": tx}

    def login_defense_ok(self):
        """Brute-force neutralisé ? Taux d'échecs de connexion ÉVALUÉS (bcrypt) revenu sous le seuil."""
        try:
            txt = httpx.get(self.auth_url + "/metrics", timeout=3).text
            m = re.search(r'^auth_logins_total\{result="fail"\} ([0-9.eE+-]+)', txt, re.M)
            count, now = float(m.group(1)) if m else 0.0, time.time()
        except Exception as e:
            return False, f"métriques auth indisponibles: {str(e)[:40]}"
        prev, self._auth_prev = self._auth_prev, (now, count)
        if not prev or now - prev[0] < 0.5:
            return False, "mesure initiale"
        rate = max(0.0, count - prev[1]) / (now - prev[0])
        return rate < 1.0, f"{rate:.1f} échecs/s"
