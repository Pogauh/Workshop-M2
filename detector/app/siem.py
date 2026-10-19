"""Fonction SOC/SIEM intégrée : règles de corrélation sur les journaux (WAF, API, auth) -> alertes + attribution.
Pur (aucune E/S) : testable sans Loki.  Les règles :
  R1  rafale de blocages WAF (signatures d'injection / scanners)
  R2  brute-force : trop d'échecs de connexion sur un même compte
  R3  compromission probable : échecs en rafale PUIS succès sur le même compte  (sévérité critique)
  R4  abus d'API : un compte concentre le débit de paiement
  R5  usage d'un compte suspendu"""
import re, time

DEFAULTS = {"min_rps": 30.0, "dominant_min_rps": 10.0, "dominant_share": 0.6, "brute_fails": 10,
            "compromise_fails": 10, "waf_block": 5, "suspended_hits": 3}
USER_RE = re.compile(r"^[a-z0-9_]{1,32}$")
IGNORED_USERS = {"-", "probe"}


def evaluate(stats, thr=None, now=None):
    thr, now = {**DEFAULTS, **(thr or {})}, now or time.time()
    alerts, sus = [], {"users": [], "ips": [], "targets": [], "compromised": [], "waf_rules": []}

    def alert(rule, severity, subject, title, detail):
        alerts.append({"rule": rule, "severity": severity, "subject": subject, "title": title, "detail": detail, "ts": now})

    rates = {u: r for u, r in stats.get("user_rate", {}).items() if u not in IGNORED_USERS and USER_RE.match(u)}
    total = sum(rates.values())
    for u, r in sorted(rates.items(), key=lambda kv: -kv[1]):
        if r >= thr["min_rps"] or (r >= thr["dominant_min_rps"] and total and r / total >= thr["dominant_share"]):
            sus["users"].append(u)
            alert("R4", "high", u, "Abus d'API de paiement", f"{u} : {r:.0f} req/s sur /api/payments ({100 * r / total:.0f} % du débit)")
    for u, n in sorted(stats.get("login_fail_15", {}).items(), key=lambda kv: -kv[1]):
        if n >= thr["brute_fails"] and USER_RE.match(u):
            sus["targets"].append(u)
            alert("R2", "high", u, "Brute-force sur la connexion", f"{int(n)} échecs de connexion sur le compte {u}")
    for u, n in stats.get("login_fail_60", {}).items():
        if n >= thr["compromise_fails"] and stats.get("login_ok_60", {}).get(u, 0) >= 1 and USER_RE.match(u):
            sus["compromised"].append(u)
            alert("R3", "critical", u, "Compromission probable d'un compte",
                  f"{int(n)} échecs puis une connexion réussie sur {u} en moins de 60 s")
    for rule, n in sorted(stats.get("waf_rules", {}).items(), key=lambda kv: -kv[1]):
        if n >= thr["waf_block"]:
            sus["waf_rules"].append(rule)
            alert("R1", "medium", rule, "Attaque applicative bloquée par le WAF", f"{int(n)} requêtes bloquées (règle {rule})")
    for u, n in stats.get("suspended_hits", {}).items():
        if n >= thr["suspended_hits"] and USER_RE.match(u):
            alert("R5", "info", u, "Compte suspendu toujours actif", f"{int(n)} requêtes refusées (403) pour {u}")
    return alerts, sus


class AlertBook:
    """Mémoire courte des alertes : dédoublonnage par (règle, sujet), expiration, tri du plus récent au plus ancien."""
    def __init__(self, ttl=120, size=12):
        self.ttl, self.size, self.items = ttl, size, {}

    def update(self, alerts, now=None):
        now = now or time.time()
        for a in alerts:
            key = (a["rule"], a["subject"])
            prev = self.items.get(key)
            self.items[key] = {**a, "first_ts": prev["first_ts"] if prev else a["ts"], "count": (prev["count"] + 1) if prev else 1}
        self.items = {k: v for k, v in self.items.items() if now - v["ts"] <= self.ttl}
        return self.latest()

    def latest(self):
        return sorted(self.items.values(), key=lambda a: -a["ts"])[: self.size]
