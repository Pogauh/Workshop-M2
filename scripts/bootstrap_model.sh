#!/bin/sh
# Entraîne le modèle d'anomalie sur un trafic NORMAL réel, puis l'évalue sur de vraies attaques (flood, brute-force),
# en testant PLUSIEURS volumes de lignes normales (app.train_sweep) pour retenir le plus performant sur cette machine.
# À lancer une fois la plateforme démarrée (docker compose up -d). La cadence d'échantillonnage (EVERY, 1 ligne par
# seconde par défaut) DOIT correspondre à detector/app/model.py:EVERY (utilisée par la détection live) : ne changez
# pas l'un sans l'autre, sinon les délais de détection du rapport ne correspondent plus à ce qui tourne réellement.
#
#   ./scripts/bootstrap_model.sh                    défaut : 8 / 3 / 3 min -> ~480 / 180 / 180 lignes (rapide, itératif)
#   ./scripts/bootstrap_model.sh 50 6 6              gros volume : ~3000 / 360 / 360 lignes (~65 min, voir README)
#   ./scripts/bootstrap_model.sh 50 6 6 1 400 1000 2000 3000   + tailles personnalisées pour app.train_sweep
#
# Brute-force : automatique par défaut (attacker/bruteforce.py, inclus dans le dépôt, aucun outil externe requis).
#   MANUAL_BRUTE=1 ./scripts/bootstrap_model.sh ...   bascule sur la procédure manuelle (second PC + Hydra, ou tout
#                                                      autre outil) si vous voulez rejouer l'entraînement avec une
#                                                      vraie attaque externe plutôt que le simulateur interne.
set -eu
cd "$(dirname "$0")/.."
N=${1:-8}; F=${2:-3}; B=${3:-3}; EVERY=${4:-1}
shift $(( $# > 4 ? 4 : $# )) 2>/dev/null || true
SIZES="$*"
DC="docker compose"

echo "1/4 Collecte du trafic NORMAL (${N} min, 1 ligne / ${EVERY}s) : démarrage du générateur..."
$DC --profile lab run -d --name immune-boot-traffic traffic python normal_traffic.py --seconds $((N * 60 + 30)) >/dev/null
$DC exec -T detector python -m app.collect --label normal --minutes "$N" --every "$EVERY"
$DC stop immune-boot-traffic >/dev/null 2>&1 || true; $DC rm -f immune-boot-traffic >/dev/null 2>&1 || true

echo "2/4 Collecte du trafic FLOOD (${F} min) : lancement de l'attaquant..."
ATTACKER_PW=$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)
$DC --profile lab run -d --name immune-boot-flood attacker python flood.py --password "$ATTACKER_PW" --target http://waf:8080 --seconds $((F * 60 + 20)) >/dev/null
$DC exec -T detector python -m app.collect --label flood --minutes "$F" --every "$EVERY"
$DC stop immune-boot-flood >/dev/null 2>&1 || true; $DC rm -f immune-boot-flood >/dev/null 2>&1 || true

echo "3/4 Collecte du trafic BRUTE-FORCE (${B} min)."
if [ "${MANUAL_BRUTE:-0}" = "1" ]; then
  echo "    MANUAL_BRUTE=1 : lancez MAINTENANT, depuis le PC Attaquant (ou un autre terminal), votre propre outil"
  echo "    de brute-force contre POST http://10.136.206.89:8080/auth/login, compte 'carol', pendant au moins"
  echo "    ${B} minute(s). Exemple avec Hydra (JSON, body brut + en-tête Content-Type) :"
  echo "      hydra -l carol -P wordlist.txt -s 8080 10.136.206.89 http-post-form \\"
  echo "        '/auth/login:{\"username\":\"^USER^\",\"password\":\"^PASS^\"}:F=bad credentials:H=Content-Type: application/json'"
  echo "    Ce script attend pendant ce temps et enregistre les observations du détecteur."
  $DC exec -T detector python -m app.collect --label brute --minutes "$B" --every "$EVERY"
else
  echo "    Automatique (attacker/bruteforce.py, intégré au dépôt) : compte 'carol', échecs répétés."
  $DC --profile lab run -d --name immune-boot-brute attacker python bruteforce.py --target http://waf:8080 \
      --threads 8 --delay-ms 150 --seconds $((B * 60 + 20)) >/dev/null
  $DC exec -T detector python -m app.collect --label brute --minutes "$B" --every "$EVERY"
  $DC stop immune-boot-brute >/dev/null 2>&1 || true; $DC rm -f immune-boot-brute >/dev/null 2>&1 || true
fi

echo "4/4 Entraînement et évaluation (balayage de volumes : app.train_sweep)..."
$DC exec -T detector python -m app.train_sweep $SIZES
./scripts/reset.sh
echo "Terminé. Rapport retenu : docker compose exec detector cat /data/report.json"
echo "Comparatif des volumes testés : docker compose exec detector cat /data/sweep.json"
echo "Pour l'embarquer dans l'image (livrable Code.zip) : ./scripts/export_model.sh"
