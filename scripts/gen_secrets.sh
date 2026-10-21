#!/bin/sh
# Génère un .env local (en clair, jamais commité) avec toutes les valeurs attendues par
# docker-compose.yml. Docker Compose le charge automatiquement depuis la racine du projet :
# aucun wrapper n'est nécessaire, "docker compose up -d --build" suffit ensuite.
#   ./scripts/gen_secrets.sh            première fois (ne remplace rien d'existant)
#   ./scripts/gen_secrets.sh --force    régénère tout (la base existante devra être recréée :
#                                       docker compose down -v)
set -eu
cd "$(dirname "$0")/.."

command -v openssl >/dev/null 2>&1 || { echo "Outil manquant : openssl" >&2; exit 1; }

OUT=.env
if [ -f "$OUT" ] && [ "${1:-}" != "--force" ]; then
  echo "$OUT existe déjà. Utilisez --force pour tout régénérer."; exit 0
fi

r() { openssl rand -hex 24; }

(umask 077; cat > "$OUT") <<EOT
# Généré par scripts/gen_secrets.sh — NE JAMAIS COMMITER (déjà exclu par .gitignore).
# Noms de variables documentés sans valeur dans .env.example.
POSTGRES_PASSWORD=$(r)
API_DB_PASSWORD=$(r)
AUTH_DB_PASSWORD=$(r)
JWT_SECRET=$(r)
INTERNAL_TOKEN=$(r)
ACTUATOR_TOKEN=$(r)
EVENT_HMAC_KEY=$(r)
GRAFANA_PASSWORD=$(r)
DEMO_PASSWORD=$(r)
ATTACKER_PASSWORD=$(r)
PROBE_PASSWORD=$(r)
MANAGER_PASSWORD=$(r)
FACE_TICKET_KEY=$(r)
WEAK_PASSWORD=sunshine1
TRUST_SOURCE_IP=false
NEVER_BAN=
TRAFFIC_RPS=4
ASSISTANT_CHAT_MODEL=qwen2.5:3b-instruct
ASSISTANT_EMBED_MODEL=nomic-embed-text
ESP_LED_URL=http://192.168.137.50
EOT

echo "OK : $OUT créé (secrets en clair, locaux à cette machine, jamais commités)."
echo "WEAK_PASSWORD (compte volontairement faible 'carol', scénario brute-force) est fixe : sunshine1."
echo "ESP_LED_URL suppose le badge ESP8266 sur 192.168.137.50 (défaut esp8266/platformio.ini) : ajustez si besoin."
echo "Suite : docker compose up -d --build"
