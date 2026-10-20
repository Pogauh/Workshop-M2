#!/bin/sh
# Vérifie si le WAF voit la VRAIE adresse IP du PC Attaquant, ou l'adresse du NAT interne de Docker
# Desktop (voir la section « Limite connue » du README). À lancer DEPUIS LE PC HÔTE, PENDANT qu'une
# requête part du PC Attaquant (ex. ouvrir http://<IP_PC_HOTE>:8080 dans un navigateur sur ce poste,
# ou lancer attacker/flood.py --seconds 5).
#   ./scripts/check_source_ip.sh                attend 15 s et affiche les IP sources vues par le WAF
#   ./scripts/check_source_ip.sh 30              fenêtre d'écoute personnalisée (secondes)
set -eu
cd "$(dirname "$0")/.."
SECS=${1:-15}

echo "Écoute des journaux du WAF pendant ${SECS}s : lancez MAINTENANT une requête depuis le PC Attaquant"
echo "(navigateur sur http://<IP_PC_HOTE>:8080, ou attacker/flood.py --seconds 5)."
IPS=$(timeout "${SECS}" docker compose logs -f --no-log-prefix --since 1s waf 2>/dev/null \
      | grep -o '"ip":"[^"]*"' | cut -d'"' -f4 | sort -u || true)

echo
if [ -z "$IPS" ]; then
  echo "Aucune requête observée pendant la fenêtre : relancez en déclenchant une requête plus tôt/plus longtemps."
  exit 2
fi
echo "Adresses IP sources vues par le WAF :"
echo "$IPS" | sed 's/^/  /'
echo
N=$(echo "$IPS" | wc -l)
if [ "$N" -eq 1 ] && echo "$IPS" | grep -qE '^(172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1]\.|192\.168\.65\.)'; then
  echo "-> Ressemble au NAT interne de Docker Desktop (une seule IP, plage privée Docker/WSL typique)."
  echo "   Laissez TRUST_SOURCE_IP=false dans .env (valeur par défaut) : le bannissement par IP resterait"
  echo "   inefficace ou dangereux (une seule IP NAT pour tout le monde). Le système s'appuie alors sur la"
  echo "   suspension de compte, le verrouillage et la limitation de débit par jeton, qui restent fiables."
else
  echo "-> Comparez cette adresse à celle réellement configurée sur le PC Attaquant (ipconfig / ifconfig)."
  echo "   Si elle correspond : vous pouvez passer TRUST_SOURCE_IP=true dans .env pour activer le"
  echo "   bannissement par IP (action a_ban dans remediator/app/engine.py)."
fi
