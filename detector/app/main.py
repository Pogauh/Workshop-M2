"""Globules blancs : score ML en continu + règles SIEM -> évènement signé vers le moteur de remédiation.
Visible, jamais silencieux : modèle absent ou source de données en panne sont signalés au dashboard."""
import hashlib, hmac, json, os, time

import httpx
from prometheus_client import Counter, Gauge, start_http_server

from . import features, model, siem

KEY = os.environ["EVENT_HMAC_KEY"].encode()
URL = os.getenv("REMEDIATOR_URL", "http://remediator:9000") + "/event"
EVERY, K = model.EVERY, 3                     # une observation / EVERY s ; 3 fenêtres anormales consécutives = anomalie qualifiée
THR = {"min_rps": float(os.getenv("SUSPECT_MIN_RPS", "30"))}
SCORE = Gauge("anomaly_score", "score IsolationForest (plus bas = plus anormal)")
FLAG = Gauge("anomaly_flag", "1 si la fenêtre est anormale")
MODEL_OK = Gauge("detector_model_loaded", "1 si un modèle est chargé")
ERRORS = Counter("detector_errors_total", "échecs de collecte (Loki/Prometheus)")
ALERTS = Counter("siem_alerts_total", "alertes SIEM", ["rule"])


def send(ev):
    raw = json.dumps(ev).encode()
    sig = hmac.new(KEY, raw, hashlib.sha256).hexdigest()
    httpx.post(URL, content=raw, headers={"X-Signature": sig, "Content-Type": "application/json"}, timeout=5)


def main():
    start_http_server(9100)
    bundle, last_try, streak, book, seen = None, 0.0, 0, siem.AlertBook(), set()
    while True:
        try:
            if bundle is None and time.time() - last_try > 10:
                last_try = time.time(); bundle = model.load_bundle()
                print("modèle chargé" if bundle else "PAS DE MODÈLE : lancer scripts/bootstrap_model.sh (README)", flush=True)
            MODEL_OK.set(int(bundle is not None))
            f, stats = features.sample(), features.collect_stats()
            alerts, sus = siem.evaluate(stats, THR)
            for a in alerts:
                if (a["rule"], a["subject"]) not in seen:
                    ALERTS.labels(a["rule"]).inc(); seen.add((a["rule"], a["subject"]))
                    print(json.dumps({"event": "siem_alert", **a}), flush=True)    # trace dans Loki : registre d'incidents
            board = book.update(alerts)
            seen &= {(a["rule"], a["subject"]) for a in board}
            if bundle is None:
                kind, score = "no_model", None
            else:
                score, anomalous = model.score_one(bundle, f)
                SCORE.set(score); FLAG.set(int(anomalous))
                streak = streak + 1 if anomalous else 0
                kind = "anomaly" if streak >= K else "suspect" if anomalous else "normal"
            send({"ts": time.time(), "kind": kind, "score": None if score is None else round(score, 4),
                  "features": {k: round(v, 3) for k, v in f.items()}, "suspects": sus, "alerts": board,
                  "model": model.describe(bundle)})
        except Exception as e:
            ERRORS.inc(); print("detector:", e, flush=True)
            try:
                send({"ts": time.time(), "kind": "detector_error", "error": str(e)[:120]})
            except Exception:
                pass
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
