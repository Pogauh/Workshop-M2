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
  # scripts/gen_secrets.sh (+ variante .ps1) sont la SOURCE qui écrit les secrets dans .env : ils ne
  # contiennent que du code (openssl rand / RandomNumberGenerator) et WEAK_PASSWORD=sunshine1, un mot de
  # passe volontairement faible et PUBLIC par conception (compte carol, scénario brute-force) — exclus
  # du scan, sinon ce garde-fou bloquerait en permanence scripts/package.sh sur un faux positif.
  FOUND=$(git ls-files | grep -v '\.example$' | grep -v '^scripts/gen_secrets\.sh$' | grep -v '^scripts/windows/gen_secrets\.ps1$' \
          | xargs -I{} sh -c 'grep -lE "^[A-Z_]+_(PASSWORD|SECRET|TOKEN|KEY)=.{8,}" "{}" 2>/dev/null' || true)
  [ -n "$FOUND" ] && { echo "REFUS : valeur qui ressemble à un secret dans :" >&2; echo "$FOUND" >&2; FAIL=1; }
else
  echo "Pas de dépôt Git ici : vérification de suivi ignorée."
fi
[ "$FAIL" = 0 ] && echo "OK : aucun secret suivi par Git détecté."
exit $FAIL
