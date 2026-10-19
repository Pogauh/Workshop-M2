# Secrets (.env local)

## Principe
Toutes les valeurs secrètes (mots de passe DB, `JWT_SECRET`, jetons internes, clé HMAC des
événements...) vivent dans un seul fichier `.env` à la racine du dépôt, en clair, généré
localement et **jamais commité** (`.gitignore` l'exclut ; `scripts/check_secrets.sh` le vérifie
avant livraison). Docker Compose le charge automatiquement depuis le dossier où il est lancé :
aucun wrapper n'est nécessaire pour démarrer la plateforme.

`.env.example` documente uniquement les NOMS de variables attendues (jamais de valeurs), pour la
revue de code et comme référence.

## Première utilisation
```
./scripts/gen_secrets.sh              # Linux / macOS / WSL
scripts\windows\gen_secrets.ps1       # Windows (PowerShell)
```
Génère `.env` avec des valeurs aléatoires pour chaque secret, sauf `WEAK_PASSWORD`
(volontairement fixe et faible : `sunshine1`, pour le scénario de brute-force sur le compte
`carol`).

## Démarrer la plateforme
```
docker compose up -d --build
```
Aucun wrapper : Docker Compose lit `.env` nativement depuis la racine du projet.

## Régénérer les secrets
```
./scripts/gen_secrets.sh --force
```
La base existante devra alors être recréée (`docker compose down -v`), puisque les mots de passe
qu'elle contient ne correspondront plus.

## Afficher un secret précis (par exemple pour le PC Attaquant)
```
sed -n 's/^ATTACKER_PASSWORD=//p' .env
```
Ou, sous PowerShell :
```powershell
(Get-Content .env | Select-String '^ATTACKER_PASSWORD=').Line.Split('=',2)[1]
```
Plus simple encore : ouvrir `.env` dans un éditeur de texte.

## Limite assumée
Ce choix privilégie la fiabilité du démarrage pendant le temps du workshop (voir
`docs/qa-jury.md`) au détriment d'un vrai chiffrement au repos. Le fichier ne quitte jamais la
machine de démonstration (ni commit, ni transmission réseau) ; une évolution naturelle serait
SOPS/age ou un vrai gestionnaire de secrets (Vault...) — voir le risque résiduel documenté dans
`docs/ebios-rm.md`.
