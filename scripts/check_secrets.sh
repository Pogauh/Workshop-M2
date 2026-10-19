#!/bin/sh
# Garde-fou avant commit/livraison : le .env local (secrets en clair) ne doit jamais être suivi par
# Git, et aucune valeur qui ressemble à un secret ne doit traîner dans un fichier versionné.
set -eu
cd "$(dirname "$0")/.."
FAIL=0
if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "REFUS : .env est suivi par Git (il doit rester local — voir .gitignore)" >&2; FAIL=1
  fi
  FOUND=$(git ls-files | grep -v '\.example$' | xargs -I{} sh -c 'grep -lE "^[A-Z_]+_(PASSWORD|SECRET|TOKEN|KEY)=.{8,}" "{}" 2>/dev/null' || true)
  [ -n "$FOUND" ] && { echo "REFUS : valeur qui ressemble à un secret dans :" >&2; echo "$FOUND" >&2; FAIL=1; }
else
  echo "Pas de dépôt Git ici : vérification de suivi ignorée."
fi
[ "$FAIL" = 0 ] && echo "OK : aucun secret suivi par Git détecté."
exit $FAIL
