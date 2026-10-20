"""Moteur de remédiation = système nerveux.  Machine à états + échelles d'actions + VÉRIFICATION après chaque action.

États : HOMEOSTASIS -> SURVEILLANCE -> IMMUNITY -> REGENERATION -> RESTORED -> (CONTAINED | HOMEOSTASIS)
        ESCALATION si la reprise n'a pas pu être vérifiée.

Principes : liste blanche d'actions, idempotence, anti-boucle, régulation (pas de sur-réaction),
preuve de guérison par une VRAIE transaction (et non par l'état d'un conteneur).

Ce module n'a AUCUNE dépendance réseau : toutes les entrées/sorties passent par l'objet `io`
(voir adapters.py en production, FakeIO dans tests/) -> logique testable sans Docker."""
import ipaddress, re, threading, time, uuid
from collections import deque

USER_RE = re.compile(r"^[a-z0-9_]{1,32}$")
STATES = ("HOMEOSTASIS", "SURVEILLANCE", "IMMUNITY", "REGENERATION", "RESTORED", "CONTAINED", "ESCALATION")
ATTACKS = ("dos", "bruteforce", "outage")


class Config:
    def __init__(self, **kw):
        self.pay_default, self.pay_throttled = 60, 10            # req/s par jeton (zone WAF « pay »)
        self.login_default, self.login_throttled = 100, 5        # req/s par IP (zone WAF « login »)
        self.trust_ip = False                                    # False sous Docker Desktop (NAT) : pas d'actions par IP
        self.never_ban = {"127.0.0.1", "10.136.206.89"}
        self.protected_users = {"probe", "merchant"}
        self.max_actions, self.window = 6, 600                   # anti-boucle : 6 actions / 10 min
        self.restart_per_window = 2                              # 2 redémarrages par service / 10 min
        self.hold, self.quiet, self.relax_after = 30, 15, 120    # secondes
        self.lock_seconds, self.compromise_lock_seconds = 180, 900
        self.probe_ok_ms = 1500
        self.verify_need, self.verify_timeout, self.verify_timeout_restart = 3, 25, 40
        self.brute_min_fail_rate, self.brute_ok_rate = 3.0, 1.0  # échecs de connexion / s
        self.outage_threshold = 3                                # sondes en échec consécutives
        self.__dict__.update(kw)

    @classmethod
    def from_env(cls, env):
        g = env.get
        return cls(pay_default=int(g("PAY_RATE_DEFAULT", 60)), pay_throttled=int(g("PAY_RATE_THROTTLED", 10)),
                   login_default=int(g("LOGIN_RATE_DEFAULT", 100)), login_throttled=int(g("LOGIN_RATE_THROTTLED", 5)),
                   trust_ip=g("TRUST_SOURCE_IP", "false").lower() == "true",
                   never_ban={"127.0.0.1", "10.136.206.89"} | {x for x in g("NEVER_BAN", "").split(",") if x},
                   relax_after=int(g("RELAX_AFTER", 120)), lock_seconds=int(g("LOCK_SECONDS", 180)))


def render_waf_rules(rules: dict) -> str:
    """Fichier d'inclusion nginx : bannissements + débits.  Valeurs validées (entiers, IP) : pas d'injection de config."""
    ips = [str(ipaddress.ip_address(ip)) for ip in rules["banned_ips"]]
    return "\n".join(["geo $banned {", "    default 0;"] + [f"    {ip} 1;" for ip in ips] + ["}",
                      f"limit_req_zone $rl_key zone=pay:10m rate={int(rules['pay_rate'])}r/s;",
                      f"limit_req_zone $binary_remote_addr zone=login:10m rate={int(rules['login_rate'])}r/s;"]) + "\n"


class Engine:
    def __init__(self, io, cfg=None, clock=time.time, sleep=time.sleep):
        self.io, self.cfg, self.clock, self.sleep = io, cfg or Config(), clock, sleep
        self.lock = threading.RLock()
        self.S = {"state": "HOMEOSTASIS", "since": clock(), "busy": False, "incident": None, "attack": None,
                  "services": {}, "probe": {}, "detector": {}, "siem": [], "last_anomaly": 0.0, "hold_until": 0.0,
                  "probe_fail_streak": 0, "rules": self._default_rules(), "history": [], "markers": []}
        self.hist, self.dhist, self.logs, self.verifs = deque(maxlen=300), deque(maxlen=300), deque(maxlen=80), deque(maxlen=12)
        self.actions_ts, self.restarts = deque(), {}
        self.counters = {"incidents": {}, "actions": {}}
        self.last_mttr = 0.0
        for inc in self.io.load_journal(10):                      # mémoire immunitaire : historique des derniers incidents
            self.S["history"].insert(0, self._summary(inc))

    # ---------- utilitaires ----------
    def _default_rules(self):
        return {"pay_rate": self.cfg.pay_default, "login_rate": self.cfg.login_default, "banned_ips": [],
                "suspended_users": [], "locked_users": {}, "compromised_users": []}

    def log(self, level, msg, **kw):
        e = {"ts": self.clock(), "level": level, "msg": msg, **kw}
        self.logs.append(e); self.io.emit({"event": "remediator", **e})

    def set_state(self, new):
        with self.lock:
            if self.S["state"] != new:
                self.log("info", f"état {self.S['state']} -> {new}")
                self.S["state"], self.S["since"] = new, self.clock()

    def mark(self, label, kind):
        with self.lock:
            self.S["markers"] = (self.S["markers"] + [{"ts": self.clock(), "label": label, "kind": kind}])[-30:]

    @staticmethod
    def _summary(inc):
        return {"id": inc.get("id"), "attack": inc.get("attack"), "detected_at": inc.get("detected_at"),
                "mttr_s": inc.get("mttr_s"), "restored": "restored_at" in inc,
                "actions": [a["name"] for a in inc.get("actions", [])]}

    def _apply_rules(self):
        with self.lock:
            rules = {**self.S["rules"], "banned_ips": list(self.S["rules"]["banned_ips"])}
        self.io.write_rules(rules); self.io.reload_waf()

    def _guard_ok(self):
        now = self.clock()
        while self.actions_ts and now - self.actions_ts[0] > self.cfg.window:
            self.actions_ts.popleft()
        return len(self.actions_ts) < self.cfg.max_actions

    # ---------- actions (toutes en liste blanche, idempotentes : None = rien de nouveau à faire) ----------
    def a_throttle(self, ev):
        with self.lock:
            if self.S["rules"]["pay_rate"] <= self.cfg.pay_throttled:
                return None
            self.S["rules"]["pay_rate"] = self.cfg.pay_throttled
        self._apply_rules()
        return f"limitation du débit de paiement par session : {self.cfg.pay_default} -> {self.cfg.pay_throttled} req/s"

    def a_suspend(self, ev):
        done = []
        for u in (ev.get("suspects") or {}).get("users", []):
            if not USER_RE.match(str(u)) or u in self.cfg.protected_users or u in self.S["rules"]["suspended_users"]:
                continue
            self.io.auth("suspend", {"username": u})
            with self.lock:
                self.S["rules"]["suspended_users"].append(u)
            done.append(u)
        return f"suspension du compte {', '.join(done)} (jetons refusés par l'API)" if done else None

    def a_ban(self, ev):
        if not self.cfg.trust_ip:
            return None   # Docker Desktop peut masquer l'IP source : on ne bannit pas à l'aveugle (voir README)
        done = []
        for ip in (ev.get("suspects") or {}).get("ips", []):
            try:
                ip = str(ipaddress.ip_address(ip))
            except ValueError:
                continue
            if ip in self.cfg.never_ban or ip in self.S["rules"]["banned_ips"]:
                continue
            with self.lock:
                self.S["rules"]["banned_ips"].append(ip)
            done.append(ip)
        if not done:
            return None
        self._apply_rules()
        return f"bannissement WAF de {', '.join(done)}"

    def a_throttle_login(self, ev):
        if not self.cfg.trust_ip:
            return None   # limiter /auth/login par IP sous NAT pénaliserait aussi les utilisateurs légitimes
        with self.lock:
            if self.S["rules"]["login_rate"] <= self.cfg.login_throttled:
                return None
            self.S["rules"]["login_rate"] = self.cfg.login_throttled
        self._apply_rules()
        return f"limitation du débit de connexion {self.cfg.login_default} -> {self.cfg.login_throttled} req/s par IP"

    def a_lock_targets(self, ev):
        done = []
        now = self.clock()
        for u in (ev.get("suspects") or {}).get("targets", []):
            if not USER_RE.match(str(u)) or u in self.cfg.protected_users:
                continue
            if self.S["rules"]["locked_users"].get(u, 0) > now:
                continue
            self.io.auth("lock", {"username": u, "seconds": self.cfg.lock_seconds})
            with self.lock:
                self.S["rules"]["locked_users"][u] = now + self.cfg.lock_seconds
            done.append(u)
        return (f"verrouillage temporaire ({self.cfg.lock_seconds} s) du compte attaqué {', '.join(done)} "
                f"(refus avant bcrypt)") if done else None

    def a_contain_compromise(self, ev):
        """Compromission probable (succès après nombreux échecs) : on ne se contente pas de rétablir la disponibilité."""
        done = []
        for u in (ev.get("suspects") or {}).get("compromised", []):
            if not USER_RE.match(str(u)) or u in self.cfg.protected_users or u in self.S["rules"]["compromised_users"]:
                continue
            self.io.auth("revoke", {"username": u})
            self.io.auth("force_reset", {"username": u})
            self.io.auth("lock", {"username": u, "seconds": self.cfg.compromise_lock_seconds})
            with self.lock:
                self.S["rules"]["compromised_users"].append(u)
                self.S["rules"]["locked_users"][u] = self.clock() + self.cfg.compromise_lock_seconds
            done.append(u)
        return (f"compromission probable de {', '.join(done)} : sessions révoquées, mot de passe à réinitialiser, "
                f"compte verrouillé") if done else None

    def a_restart(self, svc):
        now = self.clock()
        q = self.restarts.setdefault(svc, deque())
        while q and now - q[0] > self.cfg.window:
            q.popleft()
        if len(q) >= self.cfg.restart_per_window:
            self.log("warn", f"anti-boucle: redémarrages de {svc} plafonnés")
            return None
        q.append(now)
        self.io.restart(svc)
        return f"redémarrage du service {svc} depuis l'image saine"

    # ---------- échelles d'actions : du moins au plus invasif ----------
    def ladder(self, attack, ev):
        if attack == "bruteforce":
            return [("contain_compromise", self.a_contain_compromise, "contain"),
                    ("lock_account", self.a_lock_targets, "contain"),
                    ("throttle_login", self.a_throttle_login, "mitigate"),
                    ("restart_auth", lambda e: self.a_restart("auth"), "restart")]
        if attack == "outage":
            svcs = (ev.get("suspects") or {}).get("services", [])
            return [(f"restart_{s}", (lambda e, s=s: self.a_restart(s)), "restart") for s in svcs]
        return [("throttle", self.a_throttle, "mitigate"), ("suspend_user", self.a_suspend, "contain"),
                ("ban_ip", self.a_ban, "contain"), ("restart_api", lambda e: self.a_restart("api"), "restart")]

    # ---------- vérification = preuve de guérison ----------
    def _probe_record(self):
        r = self.io.probe()
        with self.lock:
            self.hist.append({"ts": r["ts"], "ms": r["ms"], "ok": r["ok"]})
            self.S["probe"] = {k: r.get(k) for k in ("ok", "ms", "detail", "ts")}
            if r.get("tx"):
                self.verifs.appendleft({**r["tx"], "ts": r["ts"], "ms": r["ms"], "ok": r["ok"]})
            self.S["probe_fail_streak"] = 0 if r["ok"] else self.S["probe_fail_streak"] + 1
        return r

    def verify(self, inc, timeout, extra=None):
        """Réussi si `verify_need` sondes consécutives passent (transaction + relecture + invariant comptable),
        et, pour un brute-force, si l'attaque ne produit plus d'échecs de connexion évalués."""
        end, streak = self.clock() + timeout, 0
        while self.clock() < end:
            r = self._probe_record()
            good = bool(r["ok"]) and r["ms"] < self.cfg.probe_ok_ms
            if good and extra is not None:
                good, detail = extra()
                if not good:
                    self.log("info", f"défense encore insuffisante: {detail}")
            inc["checks"] = (inc["checks"] + [{"t": r["ts"], "ok": good, "ms": r["ms"]}])[-20:]
            streak = streak + 1 if good else 0
            if streak >= self.cfg.verify_need:
                return True
            self.sleep(1)
        return False

    # ---------- déroulé d'un incident ----------
    def run_incident(self, ev, attack):
        now = self.clock()
        inc = {"id": uuid.uuid4().hex[:8], "attack": attack, "detected_at": now, "score": ev.get("score"),
               "features": ev.get("features"), "suspects": ev.get("suspects"), "actions": [], "checks": []}
        with self.lock:
            prev = self.S["incident"]
            self.S["incident"], self.S["attack"] = inc, attack
        self.set_state("IMMUNITY"); self.mark("Anomalie qualifiée", "detect")
        self.log("info", "incident ouvert", id=inc["id"], attack=attack, score=ev.get("score"), suspects=ev.get("suspects"))
        ok = False
        extra = self.io.login_defense_ok if attack == "bruteforce" else None
        for name, fn, kind in self.ladder(attack, ev):
            if not self._guard_ok():
                self.log("warn", "anti-boucle: plafond d'actions atteint"); break
            # Le redémarrage n'est tenté que si le service est RÉELLEMENT en échec à cet instant
            if kind == "restart" and (ok or self._probe_record()["ok"]):
                continue
            self.set_state("IMMUNITY")
            try:
                res = fn(ev)
            except Exception as e:
                self.log("error", f"action {name} en échec: {e}"); continue
            if res is None:
                continue
            self.actions_ts.append(self.clock())
            self.counters["actions"][name] = self.counters["actions"].get(name, 0) + 1
            inc["actions"].append({"t": self.clock(), "name": name, "detail": res})
            self.log("info", f"action {name}: {res}"); self.mark(name, "action")
            self.set_state("REGENERATION")
            ok = self.verify(inc, self.cfg.verify_timeout_restart if kind == "restart" else self.cfg.verify_timeout, extra)
            self.log("info", f"vérification après {name}: {'OK' if ok else 'ÉCHEC'}")
        with self.lock:
            self.S["hold_until"] = self.clock() + self.cfg.hold
        if not inc["actions"]:                                    # déjà contenu : rien de nouveau à faire
            with self.lock:
                self.S["incident"] = prev
                self.S["attack"] = prev["attack"] if prev else None
            self.set_state("CONTAINED" if self.clock() - self.S["last_anomaly"] < self.cfg.quiet else "HOMEOSTASIS")
            self.log("info", "aucune action nouvelle : menace déjà contenue")
            return
        if ok:
            inc["restored_at"] = self.clock(); inc["mttr_s"] = round(inc["restored_at"] - inc["detected_at"], 1)
            self.counters["incidents"]["restored"] = self.counters["incidents"].get("restored", 0) + 1
            self.last_mttr = inc["mttr_s"]
            self.set_state("RESTORED"); self.mark("Service vérifié", "restored")
            self.log("info", "service restauré et vérifié", mttr_s=inc["mttr_s"], attack=attack)
        else:
            self.counters["incidents"]["escalation"] = self.counters["incidents"].get("escalation", 0) + 1
            self.set_state("ESCALATION"); self.mark("Escalade", "escalation")
            self.log("error", "reprise non vérifiée: escalade opérateur")
        self.io.journal(inc)
        with self.lock:
            self.S["history"] = ([self._summary(inc)] + self.S["history"])[:10]

    def guarded(self, ev, attack):
        try:
            self.run_incident(ev, attack)
        except Exception as e:
            self.log("error", f"incident interrompu: {e}")
        finally:
            with self.lock:
                self.S["busy"] = False

    # ---------- évènements du détecteur ----------
    def classify(self, ev):
        f, sus = ev.get("features") or {}, ev.get("suspects") or {}
        if sus.get("compromised") or sus.get("targets") or f.get("login_fail_rate", 0) >= self.cfg.brute_min_fail_rate:
            return "bruteforce"
        return "dos"

    def new_threat(self, ev, attack):
        """Une anomalie qui persiste alors que la menace est déjà contenue n'ouvre PAS un nouvel incident."""
        sus, r, now = ev.get("suspects") or {}, self.S["rules"], self.clock()
        if not self.S["probe"].get("ok", True):
            return True
        if attack == "bruteforce":
            fresh = [u for u in sus.get("targets", []) if r["locked_users"].get(u, 0) <= now and u not in self.cfg.protected_users]
            comp = [u for u in sus.get("compromised", []) if u not in r["compromised_users"]]
            return bool(fresh or comp)
        users = [u for u in sus.get("users", []) if u not in self.cfg.protected_users and u not in r["suspended_users"]]
        return bool(users) or r["pay_rate"] > self.cfg.pay_throttled

    def handle_event(self, ev):
        """Retourne le type d'attaque si un incident doit démarrer (l'appelant lance `guarded` dans un thread)."""
        now, kind, f = self.clock(), ev.get("kind"), ev.get("features") or {}
        with self.lock:
            self.dhist.append({"ts": now, "score": ev.get("score"), "rps": f.get("rps"), "kind": kind})
            self.S["detector"] = {"kind": kind, "score": ev.get("score"), "features": f, "ts": now,
                                  "model": ev.get("model"), "error": ev.get("error")}
            if ev.get("alerts") is not None:
                self.S["siem"] = ev["alerts"][-20:]
            if kind in ("suspect", "anomaly"):
                self.S["last_anomaly"] = now
            if kind == "suspect" and self.S["state"] == "HOMEOSTASIS":
                self.set_state("SURVEILLANCE")
            elif kind == "normal" and self.S["state"] == "SURVEILLANCE":
                self.set_state("HOMEOSTASIS")
            if kind != "anomaly" or self.S["busy"] or now < self.S["hold_until"]:
                return None
            if self.S["state"] not in ("HOMEOSTASIS", "SURVEILLANCE", "ESCALATION", "CONTAINED"):
                return None
            attack = self.classify(ev)
            if self.S["state"] == "CONTAINED" and not self.new_threat(ev, attack):
                return None
            self.S["busy"] = True
            return attack

    # ---------- surveillance continue (appelée toutes les ~2 s) ----------
    def monitor_tick(self):
        """Sonde, états des services, transitions d'état, régulation, et chien de garde de panne.
        Retourne (event, 'outage') si une panne franche doit ouvrir un incident."""
        if not self.S["busy"]:
            self._probe_record()
        try:
            self.S["services"] = self.io.services_status()
        except Exception:
            pass
        now, relax, outage = self.clock(), False, None
        with self.lock:
            st, r = self.S["state"], self.S["rules"]
            r["locked_users"] = {u: t for u, t in r["locked_users"].items() if t > now}
            if not self.S["busy"] and now >= self.S["hold_until"]:
                if st == "RESTORED":
                    self.set_state("CONTAINED" if now - self.S["last_anomaly"] < self.cfg.quiet else "HOMEOSTASIS")
                elif st == "CONTAINED" and now - self.S["last_anomaly"] >= self.cfg.quiet:
                    self.set_state("HOMEOSTASIS")
            if (self.S["state"] == "HOMEOSTASIS" and not self.S["busy"] and now - self.S["last_anomaly"] > self.cfg.relax_after
                    and (r["pay_rate"] != self.cfg.pay_default or r["login_rate"] != self.cfg.login_default or r["banned_ips"])):
                r["pay_rate"], r["login_rate"], r["banned_ips"] = self.cfg.pay_default, self.cfg.login_default, []
                relax = True
            if (not self.S["busy"] and now >= self.S["hold_until"] and self.S["state"] in
                    ("HOMEOSTASIS", "SURVEILLANCE", "CONTAINED", "ESCALATION")
                    and self.S["probe_fail_streak"] >= self.cfg.outage_threshold):
                svcs = self._failed_services()
                if not svcs and self.S["probe_fail_streak"] >= 3 * self.cfg.outage_threshold \
                        and now - self.S["last_anomaly"] > self.cfg.quiet:
                    svcs = ["api"]                      # service figé sans conteneur en défaut ni charge anormale
                if svcs:
                    self.S["busy"] = True
                    outage = ({"kind": "outage", "score": None, "features": {}, "suspects": {"services": svcs}}, "outage")
        if relax:
            self._apply_rules(); self.log("info", "régulation: assouplissement des défenses après retour au calme")
        return outage

    def _failed_services(self):
        svc = self.S["services"] or {}
        bad = [s for s in ("db", "auth", "api") if s in svc and (svc[s].get("state") != "running" or svc[s].get("health") == "unhealthy")]
        return bad

    # ---------- remise à zéro de laboratoire ----------
    def reset(self):
        with self.lock:
            r = self.S["rules"]
            users = set(r["suspended_users"]) | set(r["locked_users"]) | set(r["compromised_users"])
        for u in sorted(users):
            try:
                self.io.auth("clear", {"username": u})
            except Exception as e:
                self.log("warn", f"reset: {u}: {e}")
        with self.lock:
            self.S["rules"] = self._default_rules()
            self.S.update(incident=None, attack=None, hold_until=0.0, last_anomaly=0.0, markers=[], probe_fail_streak=0)
        self._apply_rules(); self.set_state("HOMEOSTASIS"); self.log("info", "reset laboratoire")

    def metrics_text(self):
        """Exposition Prometheus écrite à la main (aucune dépendance) : état, incidents, actions, MTTR, services."""
        s, out = self.snapshot(), []
        out += ["# TYPE remediator_state gauge"] + [f'remediator_state{{state="{x}"}} {int(s["state"] == x)}' for x in STATES]
        out += ["# TYPE remediator_incidents_total counter"] + [
            f'remediator_incidents_total{{outcome="{k}"}} {v}' for k, v in sorted(self.counters["incidents"].items())]
        out += ["# TYPE remediator_actions_total counter"] + [
            f'remediator_actions_total{{action="{k}"}} {v}' for k, v in sorted(self.counters["actions"].items())]
        out += ["# TYPE remediator_last_mttr_seconds gauge", f"remediator_last_mttr_seconds {s['last_mttr']}",
                "# TYPE remediator_probe_ok gauge", f"remediator_probe_ok {int(bool(s['probe'].get('ok')))}",
                "# TYPE remediator_probe_ms gauge", f"remediator_probe_ms {s['probe'].get('ms') or 0}",
                "# TYPE remediator_pay_rate_limit gauge", f"remediator_pay_rate_limit {s['rules']['pay_rate']}",
                "# TYPE remediator_locked_accounts gauge", f"remediator_locked_accounts {len(s['rules']['locked_users'])}",
                "# TYPE remediator_suspended_accounts gauge", f"remediator_suspended_accounts {len(s['rules']['suspended_users'])}",
                "# TYPE remediator_service_up gauge"]
        for name, v in sorted((s["services"] or {}).items()):
            up = int(v.get("state") == "running" and v.get("health") != "unhealthy")
            out.append(f'remediator_service_up{{service="{name}"}} {up}')
        return "\n".join(out) + "\n"

    def snapshot(self):
        with self.lock:
            rules = {**self.S["rules"], "banned_ips": list(self.S["rules"]["banned_ips"]),
                     "suspended_users": list(self.S["rules"]["suspended_users"]),
                     "locked_users": dict(self.S["rules"]["locked_users"]),
                     "compromised_users": list(self.S["rules"]["compromised_users"])}
            return {**self.S, "rules": rules, "hist": list(self.hist), "dhist": list(self.dhist),
                    "verifs": list(self.verifs), "log": list(self.logs)[-40:], "now": self.clock(),
                    "last_mttr": self.last_mttr}
