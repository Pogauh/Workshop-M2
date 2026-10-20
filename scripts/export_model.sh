#!/bin/sh
# Copie le modèle entraîné (volume detdata) dans detector/model/ pour qu'il soit livré avec le dépôt
# (le détecteur l'utilise si /data/model.joblib n'existe pas encore au démarrage du conteneur).
set -eu
cd "$(dirname "$0")/.."
mkdir -p detector/model
docker cp immune-detector:/data/model.joblib detector/model/model.joblib
docker cp immune-detector:/data/report.json detector/model/report.json
docker cp immune-detector:/data/sweep.json detector/model/sweep.json 2>/dev/null || true   # absent si app.train (pas app.train_sweep) a été utilisé
echo "Modèle exporté dans detector/model/ (à reconstruire : docker compose build detector)"
