#!/bin/sh
# Prépare Code.zip (livrable) : code source uniquement, sans secrets, sans journaux, sans node_modules.
#   ./scripts/package.sh [nom-du-groupe]           ex: ./scripts/package.sh G3
set -eu
cd "$(dirname "$0")/.."
./scripts/check_secrets.sh
GROUP=${1:-G0}
OUT="Workshop2026-M2-${GROUP}-Code.zip"
rm -f "$OUT"
git ls-files -z 2>/dev/null | xargs -0 zip -q "$OUT" 2>/dev/null \
  || find . -type f \
       -not -path './.git/*' -not -name '*.zip' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' \
       -not -path '*/dist/*' -not -name '*.pyc' -not -name '.env' -not -name '*.csv' -not -name '*.joblib' \
       -print | sed 's#^\./##' | zip -q "$OUT" -@
echo "Créé : $OUT"
unzip -l "$OUT" | grep -Ei '(^|/)\.env$' && { echo "ALERTE : un secret est présent dans l'archive" >&2; exit 1; } || true
echo "Aucun secret détecté dans l'archive."
