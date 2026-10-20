"""Collecte d'observations : python -m app.collect --label normal --minutes 8
Étiquettes : normal | flood | brute  (un trafic correspondant tourne pendant ce temps : voir scripts/bootstrap_model.sh)."""
import argparse, csv, os, time
from .features import sample
from .model import EVERY, FEATURES

ap = argparse.ArgumentParser()
ap.add_argument("--label", required=True, choices=["normal", "flood", "brute"])
ap.add_argument("--minutes", type=float, default=8)
ap.add_argument("--every", type=float, default=EVERY)   # même cadence que la détection live (model.EVERY) par défaut
a = ap.parse_args()
path = f"/data/{a.label}.csv"
new = not os.path.exists(path)
end = time.time() + a.minutes * 60
with open(path, "a", newline="") as fh:
    w = csv.writer(fh)
    if new:
        w.writerow(["ts"] + FEATURES)
    while time.time() < end:
        try:
            f = sample()
            w.writerow([int(time.time())] + [round(f[k], 4) for k in FEATURES]); fh.flush()
            print(a.label, {k: round(v, 2) for k, v in f.items()}, flush=True)
        except Exception as e:
            print("échec échantillon:", e, flush=True)
        time.sleep(a.every)
