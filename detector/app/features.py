"""Extraction des observations : fenêtre glissante sur les journaux (Loki : WAF, API, auth) et les métriques
(Prometheus : requêtes en cours, tentatives de connexion).  Les requêtes n'extraient QUE les champs utiles
(`| json status, banned`) : un `| json` complet créerait une série par requête pendant un flood."""
import os, httpx

from .model import FEATURES

PROM = os.getenv("PROM_URL", "http://prometheus:9090")
LOKI = os.getenv("LOKI_URL", "http://loki:3100")
WIN = os.getenv("WINDOW", "15s"); WSEC = int(WIN[:-1])
_c = httpx.Client(timeout=5)

# Le trafic déjà banni est exclu : après remédiation, le signal doit refléter l'état réel du service.
WAF = '{service="waf"} | json status, banned | __error__="" | banned="0"'
WAF_STATUS = '{service="waf"} | json status | __error__=""'


def _q(url, q):
    r = _c.get(url, params={"query": q}); r.raise_for_status()
    return r.json()["data"]["result"]


def _loki(q): return _q(f"{LOKI}/loki/api/v1/query", q)
def _prom(q): return _q(f"{PROM}/api/v1/query", q)


def _scalar(res):
    return float(res[0]["value"][1]) if res else 0.0


def _by(res, label):
    return {s["metric"].get(label, "-"): float(s["value"][1]) for s in res}


def sample():
    """Retourne le vecteur d'observations de la dernière fenêtre."""
    total = _scalar(_loki(f"sum(count_over_time({WAF} [{WIN}]))"))
    n5 = _scalar(_loki(f"sum(count_over_time({WAF_STATUS} | status>=500 [{WIN}]))"))
    nblock = _scalar(_loki(f'sum(count_over_time({WAF_STATUS} | status=~"403|429" [{WIN}]))'))
    p95 = _scalar(_loki(f'max(quantile_over_time(0.95, {{service="waf"}} | json rt | __error__="" | unwrap rt [{WIN}]))'))
    top_user = _scalar(_loki('max(sum by (user) (count_over_time({service="api"} | json user, path | __error__="" '
                             f'| path="/api/payments" [{WIN}])))'))
    return {"rps": total / WSEC, "rps_max_user": top_user / WSEC, "p95_ms": p95 * 1000,
            "err5xx_ratio": (n5 / total) if total else 0.0, "waf_block_ratio": (nblock / total) if total else 0.0,
            "inflight": _scalar(_prom("sum(http_inflight_requests)")),
            "login_rps": _scalar(_prom(f"sum(rate(auth_logins_total[{WIN}]))")),
            "login_fail_rate": _scalar(_prom(f'sum(rate(auth_logins_total{{result="fail"}}[{WIN}]))'))}


def collect_stats():
    """Attribution et corrélation (SIEM) : QUI fait quoi.  Ne sert pas à détecter, mais à qualifier."""
    j = '| json event, user, result | __error__="" | event="login"'
    return {
        "user_rate": {u: n / WSEC for u, n in _by(_loki(
            'sum by (user) (count_over_time({service="api"} | json user, path | __error__="" '
            f'| path="/api/payments" [{WIN}]))'), "user").items()},
        "login_fail_15": _by(_loki(f'sum by (user) (count_over_time({{service="auth"}} {j} | result="fail" [{WIN}]))'), "user"),
        "login_fail_60": _by(_loki(f'sum by (user) (count_over_time({{service="auth"}} {j} | result="fail" [60s]))'), "user"),
        "login_ok_60": _by(_loki(f'sum by (user) (count_over_time({{service="auth"}} {j} | result="ok" [60s]))'), "user"),
        "waf_rules": _by(_loki(f'sum by (rule) (count_over_time({{service="waf"}} | json rule | __error__="" | rule!="" [{WIN}]))'), "rule"),
        "suspended_hits": _by(_loki('sum by (user) (count_over_time({service="api"} | json user, status | __error__="" '
                                    f'| status="403" [{WIN}]))'), "user"),
    }
