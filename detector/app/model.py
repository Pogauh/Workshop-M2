"""Modèle d'anomalie : IsolationForest non supervisé, entraîné sur le trafic NORMAL uniquement.
Choix documentés (voir docs/ml.md) :
  - log1p sur les observations : les attaques sont de plusieurs ordres de grandeur au-dessus du normal ;
  - seuil = 1er percentile des scores d'entraînement (faux positifs contrôlés) ;
  - détection UNILATÉRALE : on ne signale qu'une dérive vers le HAUT (charge, erreurs, latence, échecs) ;
    un système au repos n'est pas une attaque."""
import os, time
import numpy as np

FEATURES = ["rps", "rps_max_user", "p95_ms", "err5xx_ratio", "waf_block_ratio", "inflight", "login_rps", "login_fail_rate"]
UP_Z = 2.0            # au moins une observation à +2 écarts-types (après log1p) au-dessus de la normale
MODEL_PATHS = ["/data/model.joblib", "/app/model/model.joblib"]


def prep(X):
    return np.log1p(np.clip(np.asarray(X, dtype=float), 0, None))


def transform(bundle, X):
    return bundle["scaler"].transform(prep(X))


def flags(bundle, X):
    """Retourne (scores, anomalies) pour une matrice d'observations (n x p)."""
    Z = transform(bundle, X)
    s = bundle["model"].decision_function(Z)
    return s, (s < bundle["thr"]) & (Z.max(axis=1) >= UP_Z)


def score_one(bundle, features: dict):
    x = [[features[k] for k in bundle["features"]]]
    s, a = flags(bundle, x)
    return float(s[0]), bool(a[0])


def load_bundle():
    import joblib
    for p in MODEL_PATHS:
        if os.path.exists(p):
            try:
                b = joblib.load(p); b["source"] = p; return b
            except Exception as e:
                print(f"modèle illisible ({p}): {e}", flush=True)
    return None


def describe(bundle):
    if not bundle:
        return {"status": "absent"}
    return {"status": "ok", "trained_at": bundle.get("trained_at"), "n_train": bundle.get("n_train"), "source": bundle.get("source")}
