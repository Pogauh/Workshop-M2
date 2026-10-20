"""Entraînement non supervisé sur le trafic NORMAL uniquement ; évaluation sur de vraies données d'attaque.
  python -m app.train     (lit /data/normal.csv, /data/flood.csv, /data/brute.csv ; écrit /data/model.joblib et report.json)
Le découpage train/test est TEMPOREL (les fenêtres glissantes se chevauchent : un tirage aléatoire fuirait)."""
import csv, json, os, time
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .model import EVERY, FEATURES, flags, prep


def load_csv(path, features=FEATURES):
    with open(path) as fh:
        return np.array([[float(r[k]) for k in features] for r in csv.DictReader(fh)])


def runs_of(flag, k=3):
    """Nombre de fenêtres qui terminent une série de >= k anomalies consécutives (= alertes après anti-rebond)."""
    n = c = 0
    for f in flag:
        c = c + 1 if f else 0
        n += c >= k
    return n


def first_detection_s(flag, k=3, every=EVERY):
    """`every` DOIT correspondre à la cadence réelle de collecte des lignes de `flag` (voir model.EVERY) :
    sinon le délai annoncé ne correspond pas à ce qu'observerait le détecteur en production."""
    c = 0
    for i, f in enumerate(flag):
        c = c + 1 if f else 0
        if c >= k:
            return (i + 1) * every
    return None


def train(normal, attacks=None, features=FEATURES, seed=42, every=EVERY):
    attacks = attacks or {}
    cut = int(len(normal) * 0.75)
    tr, te = normal[:cut], normal[cut:]
    sc = StandardScaler().fit(prep(tr))
    Z = sc.transform(prep(tr))
    model = IsolationForest(n_estimators=300, random_state=seed).fit(Z)
    thr = float(np.quantile(model.decision_function(Z), 0.01))
    bundle = {"scaler": sc, "model": model, "thr": thr, "features": list(features), "n_train": int(len(tr)),
              "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"), "version": 2}
    _, fte = flags(bundle, te)
    rep = {"features": list(features), "n_train": int(len(tr)), "n_normal_test": int(len(te)), "threshold": thr,
           "sample_every_s": every,
           "false_positive_rate": float(fte.mean()) if len(te) else None,
           "false_alerts_after_debounce_k3": int(runs_of(fte)), "attacks": {}}
    for name, A in attacks.items():
        _, fa = flags(bundle, A)
        rep["attacks"][name] = {"n": int(len(A)), "recall": float(fa.mean()), "detected_after_s": first_detection_s(fa, every=every)}
    return bundle, rep


def main():
    import joblib
    normal = load_csv("/data/normal.csv")
    attacks = {n: load_csv(f"/data/{n}.csv") for n in ("flood", "brute") if os.path.exists(f"/data/{n}.csv")}
    bundle, rep = train(normal, attacks)
    joblib.dump(bundle, "/data/model.joblib")
    json.dump(rep, open("/data/report.json", "w"), indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
