#!/bin/sh
# Enchaîne : reset -> scénario -> attend le rétablissement -> reset. Pratique pour répéter la vidéo chronométrée (<= 60 s).
#   ./scripts/repeat_demo.sh dos          ./scripts/repeat_demo.sh brute
set -eu
cd "$(dirname "$0")/.."
SCENARIO=${1:-dos}
./scripts/reset.sh
case "$SCENARIO" in
  dos)
    PW=$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)
    docker compose --profile lab run --rm attacker python flood.py --password "$PW" --target http://waf:8080 --seconds 30 ;;
  brute)
    echo "Déclenchez le brute-force sur carol depuis le PC Attaquant (voir attacker/README.md)." ;;
  *) echo "scénario inconnu : $SCENARIO (dos|brute)" >&2; exit 2 ;;
esac
echo "Observez la console de supervision : http://localhost:3000"
