"""Balayage du volume d'entraînement : quelle taille de jeu NORMAL donne le modèle le plus performant
SUR CETTE MACHINE, évalué sur les mêmes attaques réelles (flood.csv, brute.csv) ?
  python -m app.train_sweep                 tailles par défaut (DEFAULT_SIZES, bornées à ce qui est disponible)
  python -m app.train_sweep 400 1000 2200    tailles personnalisées (nombre de lignes de /data/normal.csv)

Réutilise train() (train.py) sans le modifier : mêmes prétraitements, même cadence (model.EVERY), même
découpage temporel 75/25. Pour chaque taille, on entraîne sur le PRÉFIXE des n premières lignes de
normal.csv (ordre chronologique conservé) et on évalue sur la totalité de flood.csv / brute.csv.

Écrit :
  /data/model.joblib, /data/report.json : le meilleur modèle retenu (mêmes noms que train.py -> aucun
                                           changement nécessaire côté detector/app/main.py ou Dockerfile)
  /data/sweep.json                      : le tableau comparatif complet, à joindre au Dossier (section IA/Data)
"""
import json, os, sys, time

import joblib
import numpy as np

from .model import FEATURES
from .train import load_csv, train

DEFAULT_SIZES = [400, 800, 1200, 1800, 2400, 3000]


def score(rep):
    """Score composite pour classer les tailles : rappel minimal (tous types d'attaque) pénalisé par le
    taux de faux positifs (x2, car plus coûteux en démo : une alerte intempestive dérange le jury) et par
    un léger malus si une attaque n'est jamais détectée. Le rappel individuel par attaque reste dans le
    rapport : ce score ne sert qu'à CLASSER les tailles testées, pas à juger un seul type d'attaque."""
    attacks = rep.get("attacks") or {}
    recalls = [v["recall"] for v in attacks.values()]
    min_recall = min(recalls) if recalls else 0.0
    fp = rep.get("false_positive_rate") or 0.0
    undetected = sum(1 for v in attacks.values() if v["detected_after_s"] is None)
    return round(min_recall - 2.0 * fp - 0.25 * undetected, 4)


def sweep(sizes=None, data_dir="/data"):
    normal_all = load_csv(os.path.join(data_dir, "normal.csv"))
    attacks = {n: load_csv(os.path.join(data_dir, f"{n}.csv")) for n in ("flood", "brute")
               if os.path.exists(os.path.join(data_dir, f"{n}.csv"))}
    if not len(normal_all):
        raise SystemExit(f"{data_dir}/normal.csv est vide : lancez d'abord la collecte (scripts/bootstrap_model.sh)")
    sizes = sorted({s for s in (sizes or DEFAULT_SIZES) if 0 < s <= len(normal_all)} | {len(normal_all)})

    print(f"normal.csv : {len(normal_all)} lignes disponibles | attaques : "
          + ", ".join(f"{k}={len(v)}" for k, v in attacks.items()) + f"\ntailles testées : {sizes}\n", flush=True)

    rows = []
    for n in sizes:
        t0 = time.perf_counter()
        bundle, rep = train(normal_all[:n], attacks)
        fit_s = round(time.perf_counter() - t0, 4)
        rep.update(n_rows_normal=n, fit_seconds=fit_s, score=score(rep))
        rows.append((rep["score"], n, bundle, rep))
        recalls = {k: round(v["recall"], 3) for k, v in rep["attacks"].items()}
        delays = {k: v["detected_after_s"] for k, v in rep["attacks"].items()}
        print(f"n={n:5d}  fit={fit_s:7.4f}s  fp_rate={rep['false_positive_rate']:.4f}  "
              f"faux_pos_k3={rep['false_alerts_after_debounce_k3']:2d}  recall={recalls}  "
              f"detecte_apres_s={delays}  score={rep['score']:+.4f}", flush=True)

    rows.sort(key=lambda r: (-r[0], r[1]))   # meilleur score d'abord ; à score égal, la taille la plus PETITE gagne (plus rapide à collecter/entraîner)
    best_score, best_n, best_bundle, best_rep = rows[0]

    joblib.dump(best_bundle, os.path.join(data_dir, "model.joblib"))
    with open(os.path.join(data_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(best_rep, f, indent=2, ensure_ascii=False)
    sweep_out = [{"n_rows_normal": r[3]["n_rows_normal"], "fit_seconds": r[3]["fit_seconds"],
                  "false_positive_rate": r[3]["false_positive_rate"],
                  "false_alerts_after_debounce_k3": r[3]["false_alerts_after_debounce_k3"],
                  "attacks": r[3]["attacks"], "score": r[3]["score"]}
                 for r in sorted(rows, key=lambda r: r[1])]
    with open(os.path.join(data_dir, "sweep.json"), "w", encoding="utf-8") as f:
        json.dump({"chosen_n_rows_normal": best_n, "sizes_tested": sizes, "results": sweep_out}, f, indent=2, ensure_ascii=False)

    print(f"\nMEILLEUR : n={best_n} lignes normales (score={best_score:+.4f})"
          f" -> {data_dir}/model.joblib, {data_dir}/report.json")
    print(f"Comparatif complet ({len(rows)} tailles) -> {data_dir}/sweep.json")
    return best_n, best_rep


if __name__ == "__main__":
    custom = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else None
    sweep(custom)
